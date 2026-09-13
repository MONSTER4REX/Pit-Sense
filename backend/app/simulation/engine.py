"""Simulation Lab engine: historical replay, counterfactual fork, rolling
re-optimisation, and the final historical-vs-projected comparison.

Two phases, and the difference between them is absolute:

	HISTORICAL  Both cars report their real recorded state. Nothing is projected.
	PROJECTED   Both cars are propagated forward by the stated model in
	            ``app.simulation.projection``. Our car follows the user's decision
	            and the engine's rolling re-optimisation; the opponent follows its
	            own named baseline model. Neither replays recorded history.

Every re-optimisation is a fresh backend computation tagged with the triggers that
caused it, so the decision history can show that a changed recommendation is
genuinely new rather than a relabelled old value (PRD 5.H / FR-27).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from app.engine.baseline import BaselineContext, baseline_decision
from app.engine.reoptimizer import optimize_strategy
from app.replay.shock_events import ShockEventType
from app.schemas.race_state import RaceState
from app.schemas.simulation import (
	CarSimulationState,
	CounterfactualSummary,
	DecisionRecord,
	ReoptimizationRecord,
	ReoptimizationTrigger,
	SimulationTick,
	StrategyDecision,
)
from app.simulation.projection import (
	FRESH_TYRE_AGE,
	ProjectedCarState,
	build_pace_model,
	elapsed_time_at,
	project_lap_time,
	bound_relative_pace,
	rank_by_race_time,
	shared_clean_laps,
)

# Gap swing (seconds) that counts as a material GAP_CHANGE trigger.
GAP_CHANGE_THRESHOLD_SECONDS = 1.0
# Laps between scheduled strategy reviews after the fork (PRD 5.H).
SCHEDULED_REVIEW_INTERVAL_LAPS = 5

_ACTION_FROM_RECOMMENDATION = {"pit_now": "PIT", "stay_out": "STAY_OUT", "extend_stint": "EXTEND"}


@dataclass
class SimulationEngine:
	p1: RaceState
	p2: RaceState
	# Field median lap per lap number, used to separate tyre wear from fuel burn
	# and track evolution (app.tyre_model.field_pace).
	field_median_lap_times: dict[int, float] = field(default_factory=dict)

	def __post_init__(self) -> None:
		self.session_id = uuid4().hex
		self.scenario_id = "historical"
		self.shock_event: ShockEventType | None = None
		self.shock_lap: int | None = None
		self.fork_lap: int | None = None
		self.user_action: str | None = None
		self.next_review_lap: int | None = None
		self.decision_history: list[DecisionRecord] = []
		self.reoptimization_log: list[ReoptimizationRecord] = []
		self._last_trigger_state: dict[str, dict[str, object]] | None = None
		# Projected branch state, rebuilt deterministically from the fork lap.
		self._projection_cache: dict[int, tuple[ProjectedCarState, ProjectedCarState]] = {}
		self._p1_model = None
		self._p2_model = None
		self._baseline_context: BaselineContext | None = None
		self._pace_cap_note: str | None = None

	@property
	def end_lap(self) -> int:
		return max(
			self.p1.total_laps or 0,
			self.p2.total_laps or 0,
			len(self.p1.laps),
			len(self.p2.laps),
		)

	# ---------------------------------------------------------------- historical

	def _historical_car(self, race: RaceState, car: str, lap: int) -> CarSimulationState:
		row = next((item for item in race.laps if item.lap_number == lap), None)
		previous = [item for item in race.laps if item.lap_number <= lap and item.compound]
		compound = row.compound if row and row.compound else (previous[-1].compound if previous else None)
		tyre_age = row.tyre_life if row and row.tyre_life is not None else 0
		pit_laps = {stop.lap_number for stop in race.pit_stops}
		pit_status = "PIT_IN" if lap in pit_laps else "PIT_OUT" if lap - 1 in pit_laps else "NONE"
		return CarSimulationState(
			car=car,
			driver=race.driver,
			lap=lap,
			mode="HISTORICAL",
			compound=compound,
			tyre_age=tyre_age,
			position=row.position if row and row.position else (1 if car == "P1" else 2),
			gap_to_leader_seconds=(row.gap_to_leader_seconds or 0.0) if row else 0.0,
			lap_time_seconds=row.lap_time_seconds if row else None,
			pit_status=pit_status,
		)

	# ----------------------------------------------------------------- decisions

	def _stint_history(self, race: RaceState, lap: int) -> dict[str, tuple]:
		history = [row for row in race.laps if row.lap_number <= lap]
		return {
			"stint_lap_numbers": tuple(row.lap_number for row in history),
			"stint_compounds": tuple(row.compound for row in history),
			"stint_tyre_ages": tuple(row.tyre_life for row in history),
			"stint_lap_times": tuple(row.lap_time_seconds for row in history),
		}

	def _gaps_ahead(self, ours: CarSimulationState, rival: CarSimulationState) -> list[float] | None:
		if rival.position < ours.position:
			gap = ours.gap_to_leader_seconds - rival.gap_to_leader_seconds
			if gap > 0:
				return [gap]
		return None

	def _pitsense_decision(
		self,
		ours: CarSimulationState,
		rival: CarSimulationState,
		lap: int,
	) -> StrategyDecision:
		lap_times = [row.lap_time_seconds for row in self.p2.laps if row.lap_time_seconds is not None]
		rival_pit_laps = tuple(stop.lap_number for stop in self.p1.pit_stops if stop.lap_number <= lap)
		recommendation = optimize_strategy(
			start_lap=max(1, lap),
			end_lap=max(lap + 1, self.end_lap),
			current_compound=ours.compound or "UNKNOWN",
			current_tyre_age=ours.tyre_age,
			lap_time_seconds=lap_times or [90.0, 90.0],
			uncertainty_events=(self.shock_event.value,) if self.shock_event else (),
			rival_pit_laps=rival_pit_laps,
			rival_tyre_age=rival.tyre_age,
			cars_ahead_gaps_seconds=self._gaps_ahead(ours, rival),
			pit_lane_loss_seconds=self._pace_models()[1].pit_lane_loss_seconds,
			field_baseline=self.field_median_lap_times,
			**self._stint_history(self.p2, lap),
		)
		return StrategyDecision(
			car="P2",
			lap=lap,
			action=_ACTION_FROM_RECOMMENDATION[recommendation.action],
			target_lap=recommendation.pit_lap,
			confidence=recommendation.confidence.upper,
			projected_time_cost=recommendation.projected_total_time_seconds,
			projected_position=ours.position,
			explanation=recommendation.reasoning,
			model_type="PITSENSE",
			recommendation=recommendation,
		)

	def _opponent_decision(self, opponent: CarSimulationState) -> StrategyDecision:
		return baseline_decision(
			car=opponent,
			end_lap=self.end_lap,
			shock_event=self.shock_event.value if self.shock_event else None,
			context=self._baseline_ctx(),
		)

	# ------------------------------------------------------------------- models

	def _pace_models(self):
		"""Measure both cars once, at the fork lap, and reuse thereafter.

		Both are measured over the same set of laps. Sampling each car's pace from
		whichever laps happened to be clean for it alone would let a wet phase or a
		safety-car stint land in one car's sample and not the other's, and that
		difference would then compound over every projected lap into a finishing
		gap that is an artefact of sampling rather than of pace.
		"""
		if self._p1_model is None or self._p2_model is None:
			reference_lap = self.fork_lap or self.end_lap
			shared = shared_clean_laps(self.p1, self.p2, reference_lap)
			self._p1_model = build_pace_model(
				self.p1, "P1", reference_lap, self.field_median_lap_times, shared_laps=shared
			)
			self._p2_model = build_pace_model(
				self.p2, "P2", reference_lap, self.field_median_lap_times, shared_laps=shared
			)
			self._p1_model, self._p2_model, self._pace_cap_note = bound_relative_pace(
				self._p1_model, self._p2_model
			)
		return self._p1_model, self._p2_model

	def _baseline_ctx(self) -> BaselineContext:
		if self._baseline_context is None:
			p1_model, _ = self._pace_models()
			self._baseline_context = BaselineContext(
				typical_stint_laps=p1_model.typical_stint_laps,
				pit_lane_loss_seconds=p1_model.pit_lane_loss_seconds,
				pit_loss_measured=p1_model.pit_loss_measured,
			)
		return self._baseline_context

	# --------------------------------------------------------------- projection

	def _fork_state(self) -> tuple[ProjectedCarState, ProjectedCarState]:
		"""Both cars' real state on the fork lap - the last honest data point."""
		fork_lap = self.fork_lap
		assert fork_lap is not None
		p1_hist = self._historical_car(self.p1, "P1", fork_lap)
		p2_hist = self._historical_car(self.p2, "P2", fork_lap)
		states = (
			ProjectedCarState(
				car="P1",
				driver=self.p1.driver,
				lap=fork_lap,
				compound=p1_hist.compound or "UNKNOWN",
				tyre_age=p1_hist.tyre_age,
				lap_time_seconds=p1_hist.lap_time_seconds,
				cumulative_time_seconds=elapsed_time_at(self.p1, fork_lap),
				position=p1_hist.position,
				gap_to_leader_seconds=p1_hist.gap_to_leader_seconds,
			),
			ProjectedCarState(
				car="P2",
				driver=self.p2.driver,
				lap=fork_lap,
				compound=p2_hist.compound or "UNKNOWN",
				tyre_age=p2_hist.tyre_age,
				lap_time_seconds=p2_hist.lap_time_seconds,
				cumulative_time_seconds=elapsed_time_at(self.p2, fork_lap),
				position=p2_hist.position,
				gap_to_leader_seconds=p2_hist.gap_to_leader_seconds,
			),
		)
		rank_by_race_time(states)
		return states

	def _advance(
		self,
		state: ProjectedCarState,
		model,
		*,
		pitting: bool,
		new_compound: str | None,
	) -> ProjectedCarState:
		"""One projected lap for one car.

		A stop taken on this lap is marked on *this* lap's state, so the projected
		pit phases read the same way as the historical ones: PIT_IN on the lap the
		car enters, PIT_OUT on the lap it rejoins. A car never jumps straight from
		track to track with no visible pit phase.
		"""
		shock = self.shock_event.value if self.shock_event else None
		lap_time = project_lap_time(model, tyre_age=state.tyre_age, pitting=pitting, shock_event=shock)
		if pitting:
			state.pit_status = "PIT_IN"
			state.pit_laps = [*state.pit_laps, state.lap]
		return ProjectedCarState(
			car=state.car,
			driver=state.driver,
			lap=state.lap + 1,
			compound=new_compound if pitting and new_compound else state.compound,
			tyre_age=FRESH_TYRE_AGE if pitting else state.tyre_age + 1,
			lap_time_seconds=lap_time,
			cumulative_time_seconds=round(state.cumulative_time_seconds + (lap_time or 0.0), 3),
			position=state.position,
			gap_to_leader_seconds=state.gap_to_leader_seconds,
			pit_status="PIT_OUT" if pitting else "NONE",
			pit_laps=list(state.pit_laps),
		)

	@staticmethod
	def _replacement_compound(current: str, shock_event: str | None) -> str:
		"""Which compound a car fits at a stop, given the conditions."""
		if shock_event == "rain":
			return "INTERMEDIATE"
		# A dry stop moves to the harder race compound; this is stated, not tuned.
		return "HARD" if (current or "").upper() in {"SOFT", "MEDIUM"} else "MEDIUM"

	def _project_to(self, lap: int) -> tuple[ProjectedCarState, ProjectedCarState]:
		"""Deterministically propagate both cars from the fork to the given lap."""
		fork_lap = self.fork_lap
		assert fork_lap is not None
		if lap in self._projection_cache:
			return self._projection_cache[lap]

		p1_model, p2_model = self._pace_models()
		shock = self.shock_event.value if self.shock_event else None
		p1_state, p2_state = self._fork_state()
		self._projection_cache[fork_lap] = (p1_state, p2_state)
		# Always resolve at least one lap past the fork, so a stop committed on the
		# fork lap is marked on that lap regardless of which lap is asked for first.
		target = max(lap, min(fork_lap + 1, self.end_lap))

		# Our car's committed action at the fork; re-optimisation may change it
		# later, and each change is logged as its own computation.
		our_plan = self.user_action
		our_pit_due = fork_lap if our_plan == "PIT" else None
		if our_plan == "EXTEND":
			our_pit_due = None

		for current_lap in range(fork_lap, target):
			p1_sim = self._as_sim_state(p1_state)
			opponent_call = baseline_decision(
				car=p1_sim,
				end_lap=self.end_lap,
				shock_event=shock,
				context=self._baseline_ctx(),
			)
			p1_pits = opponent_call.action == "PIT"

			our_pits = our_pit_due == current_lap
			if not our_pits and our_plan in {"STAY_OUT", "EXTEND", None}:
				# Our car re-evaluates at each scheduled review; a stop it decides
				# on there is taken on that lap.
				p2_sim = self._as_sim_state(p2_state)
				if self._is_review_lap(current_lap):
					call = self._pitsense_decision(p2_sim, p1_sim, current_lap)
					our_pits = call.action == "PIT"

			p1_state = self._advance(
				p1_state,
				p1_model,
				pitting=p1_pits,
				new_compound=self._replacement_compound(p1_state.compound, shock),
			)
			p2_state = self._advance(
				p2_state,
				p2_model,
				pitting=our_pits,
				new_compound=self._replacement_compound(p2_state.compound, shock),
			)
			if our_pits:
				our_pit_due = None
				our_plan = "STAY_OUT"
			rank_by_race_time((p1_state, p2_state))
			self._projection_cache[current_lap + 1] = (p1_state, p2_state)

		return self._projection_cache[lap]

	def _is_review_lap(self, lap: int) -> bool:
		fork_lap = self.fork_lap or lap
		return lap > fork_lap and (lap - fork_lap) % SCHEDULED_REVIEW_INTERVAL_LAPS == 0

	@staticmethod
	def _as_sim_state(state: ProjectedCarState) -> CarSimulationState:
		return CarSimulationState(
			car=state.car,
			driver=state.driver,
			lap=state.lap,
			mode="PROJECTED",
			compound=state.compound,
			tyre_age=state.tyre_age,
			position=state.position,
			gap_to_leader_seconds=state.gap_to_leader_seconds,
			lap_time_seconds=state.lap_time_seconds,
			pit_status=state.pit_status,
		)

	# ---------------------------------------------------------------- triggers

	def _detect_material_triggers(
		self, p1: CarSimulationState, p2: CarSimulationState
	) -> list[ReoptimizationTrigger]:
		"""Triggers whose condition changed since the previous tick.

		An empty list means nothing material happened, and no recomputation is
		allowed to fire - there is no timer-based recompute.
		"""
		triggers: list[ReoptimizationTrigger] = []
		prev = self._last_trigger_state
		if prev is not None:
			prev_p1, prev_p2 = prev["P1"], prev["P2"]
			if p1.pit_status == "PIT_IN" and prev_p1["pit_status"] != "PIT_IN":
				triggers.append("P1_PIT")
			if p2.pit_status == "PIT_IN" and prev_p2["pit_status"] != "PIT_IN":
				triggers.append("P2_PIT")
			if (
				p1.compound != prev_p1["compound"]
				or p2.compound != prev_p2["compound"]
				or p1.tyre_age < prev_p1["tyre_age"]
				or p2.tyre_age < prev_p2["tyre_age"]
			):
				triggers.append("TYRE_STATE_CHANGE")
			if (p1.position < p2.position) != (prev_p1["position"] < prev_p2["position"]):
				triggers.append("TRAFFIC_CHANGE")
			if (
				abs(p1.gap_to_leader_seconds - prev_p1["gap"]) >= GAP_CHANGE_THRESHOLD_SECONDS
				or abs(p2.gap_to_leader_seconds - prev_p2["gap"]) >= GAP_CHANGE_THRESHOLD_SECONDS
			):
				triggers.append("GAP_CHANGE")
		self._last_trigger_state = {
			car.car: {
				"pit_status": car.pit_status,
				"compound": car.compound,
				"tyre_age": car.tyre_age,
				"position": car.position,
				"gap": car.gap_to_leader_seconds,
			}
			for car in (p1, p2)
		}
		return triggers

	@staticmethod
	def _state_summary(p1: CarSimulationState, p2: CarSimulationState) -> dict:
		return {
			"p1_position": p1.position,
			"p1_gap_to_leader_seconds": p1.gap_to_leader_seconds,
			"p1_compound": p1.compound,
			"p1_tyre_age": p1.tyre_age,
			"p1_pit_status": p1.pit_status,
			"p2_position": p2.position,
			"p2_gap_to_leader_seconds": p2.gap_to_leader_seconds,
			"p2_compound": p2.compound,
			"p2_tyre_age": p2.tyre_age,
			"p2_pit_status": p2.pit_status,
		}

	def _merge_triggers(self, *groups) -> list[ReoptimizationTrigger]:
		merged: list[ReoptimizationTrigger] = []
		for group in groups:
			for trigger in group or []:
				if trigger not in merged:
					merged.append(trigger)
		return merged

	def _record_reoptimization(
		self,
		lap: int,
		p1: CarSimulationState,
		p2: CarSimulationState,
		triggers: list[ReoptimizationTrigger],
	) -> list[StrategyDecision]:
		opponent = self._opponent_decision(p1)
		ours = self._pitsense_decision(p2, p1, lap)
		self.reoptimization_log.append(
			ReoptimizationRecord(
				lap=lap,
				triggers=triggers,
				p1_decision=opponent,
				p2_decision=ours,
				state_summary=self._state_summary(p1, p2),
				computation_id=uuid4().hex[:12],
				reason=self._trigger_reason(triggers),
			)
		)
		return [opponent, ours]

	@staticmethod
	def _trigger_reason(triggers: list[ReoptimizationTrigger]) -> str:
		readable = {
			"SHOCK_EVENT": "a shock event was injected",
			"USER_DECISION": "the strategist committed a decision",
			"TARGET_LAP_REACHED": "the scheduled strategy review came due",
			"P1_PIT": "the opponent pitted",
			"P2_PIT": "our car pitted",
			"TYRE_STATE_CHANGE": "tyre state changed materially",
			"TRAFFIC_CHANGE": "track position between the cars changed",
			"GAP_CHANGE": "the gap moved materially",
			"OTHER_MATERIAL_EVENT": "a material event was flagged",
		}
		causes = [readable.get(trigger, trigger) for trigger in triggers]
		return f"Recomputed because {', and '.join(causes)}." if causes else ""

	# ------------------------------------------------------------------- ticks

	def tick(self, lap: int, explicit_triggers: list[ReoptimizationTrigger] | None = None) -> SimulationTick:
		if self.fork_lap is not None and lap >= self.fork_lap:
			return self.projected_tick(lap, explicit_triggers=explicit_triggers)

		p1 = self._historical_car(self.p1, "P1", lap)
		p2 = self._historical_car(self.p2, "P2", lap)
		explicit = list(explicit_triggers or [])
		if self.shock_lap == lap:
			explicit.append("SHOCK_EVENT")
		triggers = self._merge_triggers(explicit, self._detect_material_triggers(p1, p2))
		decisions = self._record_reoptimization(lap, p1, p2, triggers) if triggers else []

		return SimulationTick(
			lap=lap,
			session_id=self.session_id,
			mode="HISTORICAL",
			scenario_id=self.scenario_id,
			shock_event=self.shock_event.value if self.shock_event else None,
			cars=[p1, p2],
			decisions=decisions,
			decision_lap=self.shock_lap,
			next_review_lap=None,
			triggers=triggers,
		)

	def projected_tick(
		self, lap: int, explicit_triggers: list[ReoptimizationTrigger] | None = None
	) -> SimulationTick:
		if self.fork_lap is None:
			raise ValueError("A decision must be accepted before a projected tick can be produced")

		p1_state, p2_state = self._project_to(lap)
		p1 = self._as_sim_state(p1_state)
		p2 = self._as_sim_state(p2_state)

		explicit = list(explicit_triggers or [])
		if self._is_review_lap(lap) and "TARGET_LAP_REACHED" not in explicit:
			explicit.append("TARGET_LAP_REACHED")
		triggers = self._merge_triggers(explicit, self._detect_material_triggers(p1, p2))

		decisions = self._record_reoptimization(lap, p1, p2, triggers) if triggers else []
		if not decisions:
			# A tick with no trigger still has to show the standing call, but it is
			# explicitly the previous computation, not a new one.
			last = self.reoptimization_log[-1] if self.reoptimization_log else None
			decisions = [last.p1_decision, last.p2_decision] if last else []

		self.next_review_lap = self._next_review_lap(lap)

		return SimulationTick(
			lap=lap,
			session_id=self.session_id,
			mode="PROJECTED",
			scenario_id=self.scenario_id,
			shock_event=self.shock_event.value if self.shock_event else None,
			cars=[p1, p2],
			decisions=decisions,
			decision_lap=self.fork_lap,
			next_review_lap=self.next_review_lap,
			triggers=triggers,
		)

	def _next_review_lap(self, lap: int) -> int | None:
		fork_lap = self.fork_lap
		if fork_lap is None or lap >= self.end_lap:
			return None
		elapsed = lap - fork_lap
		ahead = SCHEDULED_REVIEW_INTERVAL_LAPS - (elapsed % SCHEDULED_REVIEW_INTERVAL_LAPS)
		return min(self.end_lap, lap + ahead)

	# ------------------------------------------------------------------ actions

	def inject_shock(self, lap: int, event_type: ShockEventType) -> SimulationTick:
		if lap < 1 or lap > self.end_lap:
			raise ValueError("Shock lap must be within the loaded race")
		self.shock_event = event_type
		self.shock_lap = lap
		self.scenario_id = f"shock-{uuid4().hex[:8]}"
		self._projection_cache.clear()
		return self.tick(lap)

	def accept_decision(self, lap: int, action: str) -> SimulationTick:
		if action not in {"PIT", "STAY_OUT", "EXTEND"}:
			raise ValueError("Action must be PIT, STAY_OUT, or EXTEND")
		self.fork_lap = lap
		self.user_action = action
		self._projection_cache.clear()
		self._p1_model = self._p2_model = self._baseline_context = None
		self._pace_cap_note = None
		self.decision_history.append(DecisionRecord(lap=lap, action=action))
		if self.scenario_id == "historical":
			self.scenario_id = f"decision-{uuid4().hex[:8]}"
		return self.projected_tick(lap, explicit_triggers=["USER_DECISION"])

	def flag_material_event(self, lap: int) -> SimulationTick:
		"""Force a recomputation for events outside the deterministic detectors,
		such as a red flag or a retirement, that a caller has classified itself."""
		return self.tick(lap, explicit_triggers=["OTHER_MATERIAL_EVENT"])

	# ------------------------------------------------------------------ summary

	def model_assumptions(self) -> list[str]:
		p1_model, p2_model = self._pace_models()
		return [
			"Both cars are projected forward from the fork by the same model; neither replays recorded history.",
			*p2_model.assumptions(),
			*p1_model.assumptions(),
			*self._baseline_ctx().assumptions(),
			*([self._pace_cap_note] if self._pace_cap_note else []),
			"Positions are derived from accumulated projected race time, not asserted.",
			"All post-fork values are a projection, not a claim about the recorded race.",
		]

	def summary(self) -> CounterfactualSummary:
		if self.fork_lap is None:
			raise ValueError("A decision must be accepted before requesting a counterfactual summary")

		historical = {
			"P1": self._historical_car(self.p1, "P1", self.end_lap).position,
			"P2": self._historical_car(self.p2, "P2", self.end_lap).position,
		}
		p1_final, p2_final = self._project_to(self.end_lap)

		# Both margins are signed the same way: positive means our car is behind the
		# opponent. Taking absolute values here would make "60s ahead" and "60s
		# behind" look identical, and the advantage below would then contradict the
		# projected finishing position.
		historical_deficit = round(
			elapsed_time_at(self.p2, self.end_lap) - elapsed_time_at(self.p1, self.end_lap), 3
		)
		projected_deficit = round(
			p2_final.cumulative_time_seconds - p1_final.cumulative_time_seconds, 3
		)
		# Positive means our car finishes further up the road than it really did.
		projected_advantage = round(historical_deficit - projected_deficit, 3)
		historical_margin = abs(historical_deficit)
		projected_margin = abs(projected_deficit)

		return CounterfactualSummary(
			session_id=self.session_id,
			historical_finish=historical,
			pitsense_projected_finish=p2_final.position,
			baseline_projected_finish=p1_final.position,
			projected_finishing_gap_seconds=projected_margin,
			historical_finishing_gap_seconds=historical_margin,
			projected_advantage_seconds=projected_advantage,
			projected_gain_loss_vs_historical=historical["P2"] - p2_final.position,
			decision_history=self.decision_history,
			assumptions=self.model_assumptions(),
		)
