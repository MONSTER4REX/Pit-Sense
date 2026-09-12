from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from app.engine.baseline import baseline_decision
from app.engine.reoptimizer import optimize_strategy
from app.replay.shock_events import ShockEventType
from app.schemas.race_state import RaceState
from app.schemas.simulation import CarSimulationState, CounterfactualSummary, SimulationTick, StrategyDecision


@dataclass
class SimulationEngine:
	p1: RaceState
	p2: RaceState
	pit_lane_loss_seconds: float = 20.0

	def __post_init__(self) -> None:
		self.scenario_id = "historical"
		self.shock_event: ShockEventType | None = None
		self.shock_lap: int | None = None
		self.fork_lap: int | None = None
		self.user_action: str | None = None

	@property
	def end_lap(self) -> int:
		return max(self.p1.total_laps or 0, self.p2.total_laps or 0, len(self.p1.laps), len(self.p2.laps))

	def _historical_car(self, race: RaceState, car: str, lap: int) -> CarSimulationState:
		row = next((item for item in race.laps if item.lap_number == lap), None)
		previous = [item for item in race.laps if item.lap_number <= lap and item.compound]
		compound = row.compound if row and row.compound else (previous[-1].compound if previous else "UNKNOWN")
		tyre_age = row.tyre_life if row and row.tyre_life is not None else max(0, lap - (previous[-1].lap_number if previous else 1))
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
		)

	def _pitsense_decision(self, car: CarSimulationState, lap: int) -> StrategyDecision:
		lap_times = [item.lap_time_seconds for item in self.p2.laps if item.lap_time_seconds is not None]
		recommendation = optimize_strategy(
			start_lap=max(1, lap),
			end_lap=max(lap + 1, self.end_lap),
			current_compound=car.compound or "MEDIUM",
			current_tyre_age=car.tyre_age,
			lap_time_seconds=lap_times or [90.0, 90.0],
			uncertainty_events=(self.shock_event.value,) if self.shock_event else (),
		)
		return StrategyDecision(
			car="P2",
			lap=lap,
			action={"pit_now": "PIT", "stay_out": "STAY_OUT", "extend_stint": "EXTEND"}[recommendation.action],
			target_lap=recommendation.pit_lap,
			confidence=recommendation.confidence.upper,
			projected_time_cost=recommendation.projected_total_time_seconds,
			projected_position=car.position,
			explanation=f"PitSense projects {recommendation.projected_total_time_seconds:.2f}s total cost with a {recommendation.undercut_risk_tier} undercut risk.",
			model_type="PITSENSE",
			recommendation=recommendation,
		)

	def tick(self, lap: int) -> SimulationTick:
		if self.fork_lap is not None and lap >= self.fork_lap:
			return self.projected_tick(lap)
		p1 = self._historical_car(self.p1, "P1", lap)
		p2 = self._historical_car(self.p2, "P2", lap)
		decisions: list[StrategyDecision] = []
		if self.shock_lap == lap:
			decisions = [
				baseline_decision(car=p1, end_lap=self.end_lap, shock_event=self.shock_event.value if self.shock_event else None, pit_lane_loss_seconds=self.pit_lane_loss_seconds),
				self._pitsense_decision(p2, lap),
			]
		return SimulationTick(
			lap=lap,
			mode="HISTORICAL",
			scenario_id=self.scenario_id,
			shock_event=self.shock_event.value if self.shock_event else None,
			cars=[p1, p2],
			decisions=decisions,
		)

	def inject_shock(self, lap: int, event_type: ShockEventType) -> SimulationTick:
		if lap < 1 or lap > self.end_lap:
			raise ValueError("Shock lap must be within the loaded race")
		self.shock_event = event_type
		self.shock_lap = lap
		self.scenario_id = f"shock-{uuid4().hex[:8]}"
		return self.tick(lap)

	def accept_decision(self, lap: int, action: str) -> SimulationTick:
		if action not in {"PIT", "STAY_OUT", "EXTEND"}:
			raise ValueError("Action must be PIT, STAY_OUT, or EXTEND")
		self.fork_lap = lap
		self.user_action = action
		if self.scenario_id == "historical":
			self.scenario_id = f"decision-{uuid4().hex[:8]}"
		return self.projected_tick(lap)

	def projected_tick(self, lap: int) -> SimulationTick:
		p1 = self._historical_car(self.p1, "P1", lap)
		p2 = self._historical_car(self.p2, "P2", lap)
		age_since_fork = max(0, lap - (self.fork_lap or lap))
		p1.lap_time_seconds = (p1.lap_time_seconds or 90.0) + 0.2 * age_since_fork
		p2.lap_time_seconds = (p2.lap_time_seconds or 90.0) + 0.2 * age_since_fork
		p1.tyre_age = age_since_fork + 12
		p2.tyre_age = age_since_fork + 8
		baseline = baseline_decision(car=p1, end_lap=self.end_lap, shock_event=self.shock_event.value if self.shock_event else None, pit_lane_loss_seconds=self.pit_lane_loss_seconds)
		pitsense = self._pitsense_decision(p2, lap)
		if lap == self.fork_lap and self.user_action:
			pitsense = pitsense.model_copy(update={"action": self.user_action, "target_lap": lap, "explanation": f"User selected {self.user_action} at the simulation fork."})
		p1.mode = "PROJECTED"
		p2.mode = "PROJECTED"
		if baseline.action == "PIT":
			p1.position += 1
			p1.pit_status = "PIT_IN" if lap == self.fork_lap else "PIT_OUT"
		if pitsense.action == "PIT":
			p2.position += 1
			p2.pit_status = "PIT_IN" if lap == self.fork_lap else "PIT_OUT"
		return SimulationTick(
			lap=lap,
			mode="PROJECTED",
			scenario_id=self.scenario_id,
			shock_event=self.shock_event.value if self.shock_event else None,
			cars=[p1, p2],
			decisions=[baseline, pitsense],
		)

	def summary(self) -> CounterfactualSummary:
		if self.fork_lap is None:
			raise ValueError("A decision must be accepted before requesting a counterfactual summary")
		historical = {"P1": self._historical_car(self.p1, "P1", self.end_lap).position, "P2": self._historical_car(self.p2, "P2", self.end_lap).position}
		last = self.projected_tick(self.end_lap)
		p1 = next(car for car in last.cars if car.car == "P1")
		p2 = next(car for car in last.cars if car.car == "P2")
		historical_gap = self._historical_car(self.p2, "P2", self.end_lap).gap_to_leader_seconds
		projected_gap = abs(p2.gap_to_leader_seconds - p1.gap_to_leader_seconds)
		return CounterfactualSummary(
			historical_finish=historical,
			pitsense_projected_finish=p2.position,
			baseline_projected_finish=p1.position,
			projected_finishing_gap_seconds=projected_gap,
			projected_advantage_seconds=historical_gap - projected_gap,
			projected_gain_loss_vs_historical=historical["P2"] - p2.position,
			assumptions=[
				f"Pit-lane loss approximated as {self.pit_lane_loss_seconds:.1f}s.",
				"Projected lap times use the historical lap time plus a deterministic tyre-age adjustment.",
				"Results are a counterfactual projection, not a claim about the historical race.",
			],
		)