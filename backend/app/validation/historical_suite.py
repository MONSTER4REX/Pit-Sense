"""The historical validation suite (PRD section 13).

Replays real completed races through the real engine and measures what it
actually did, then reports every figure including the ones that fall short. A
target that is missed is recorded as missed - PRD section 14 forbids skipping
this suite before calling the build complete, and forbids hiding its results.

Measured per race:

	- directional agreement between the engine's pit window and the team's
	  actual stop
	- tyre-cliff onset against the independently-derived observed drop-off
	- re-optimisation latency after a real shock event, against the 1s budget
	- explainability and confidence present on every recommendation
	- safety-car / VSC and wet-weather evidence actually found in the session
	- source data gaps, counted rather than silently filled
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from statistics import fmean
from time import perf_counter
from typing import Iterable, Sequence

from app.engine.reoptimizer import optimize_strategy
from app.ingestion.fastf1_client import DEFAULT_CACHE_DIR, SUPPORTED_RACES, load_historical_session
from app.replay.session_context import SessionReplayContext, lap_context
from app.replay.shock_events import ShockEventType
from app.schemas.race_state import RaceState
from app.simulation.engine import SimulationEngine
from app.tyre_model.comparison import ACCURACY_TOLERANCE_LAPS, observed_drop_off_lap
from app.tyre_model.field_pace import normalise_stints
from app.tyre_model.models import build_stints

# PRD FR-7: the hard re-optimisation budget after a shock event.
REOPTIMIZATION_BUDGET_SECONDS = 1.0
# Laps sampled across each race to prove the recommendation moves with state.
SAMPLE_FRACTIONS = (0.15, 0.35, 0.55, 0.75, 0.9)
# A recommended pit window is "directionally consistent" if it lands within this
# fraction of race distance of a stop the team actually made.
DIRECTIONAL_TOLERANCE_FRACTION = 0.12
MIN_DIRECTIONAL_TOLERANCE_LAPS = 2


@dataclass
class LapSample:
	lap: int
	action: str
	pit_lap: int
	confidence_lower: float
	confidence_upper: float
	tyre_delta_risk: float
	degradation_measured: bool
	has_explainability: bool
	has_reasoning: bool


@dataclass
class RaceValidation:
	year: int
	event: str
	our_car: str
	opponent: str
	total_laps: int
	actual_pit_laps: tuple[int, ...]
	recommended_pit_laps: tuple[int, ...]
	directionally_consistent: bool
	lap_samples: list[LapSample] = field(default_factory=list)
	recommendation_varies_across_laps: bool = False
	explainability_on_every_recommendation: bool = False
	confidence_on_every_recommendation: bool = False
	cliff_predictions: int = 0
	cliff_within_tolerance: int = 0
	max_reoptimization_seconds: float | None = None
	reoptimization_within_budget: bool = True
	shock_events_tested: int = 0
	safety_car_or_vsc_evidence: bool = False
	wet_or_intermediate_evidence: bool = False
	data_gap_count: int = 0
	notes: list[str] = field(default_factory=list)


def _actual_pit_laps(race: RaceState) -> tuple[int, ...]:
	return tuple(sorted(stop.lap_number for stop in race.pit_stops))


def _sample_laps(total_laps: int) -> list[int]:
	laps = sorted({max(2, int(total_laps * fraction)) for fraction in SAMPLE_FRACTIONS})
	return [lap for lap in laps if lap < total_laps]


def _session_evidence(events: Sequence[dict[str, str]], race: RaceState) -> tuple[bool, bool]:
	text = " ".join(event.get("message", "") for event in events).lower()
	safety_car = any(token in text for token in ("safety car", "virtual safety", "vsc"))
	wet = "rain" in text or "wet" in text or any(
		(lap.compound or "").upper() in {"INTERMEDIATE", "WET"} for lap in race.laps
	)
	return safety_car, wet


def validate_race(year: int, event: str, *, cache_dir: str | None = None) -> RaceValidation:
	session = load_historical_session(year, event, cache_dir=cache_dir or str(DEFAULT_CACHE_DIR))
	engine = SimulationEngine(
		session.p1, session.p2, field_median_lap_times=session.field_median_lap_times
	)
	ctx = SessionReplayContext(
		p1=session.p1,
		p2=session.p2,
		end_lap=engine.end_lap,
		field_median_lap_times=session.field_median_lap_times,
	)

	actual_pits = _actual_pit_laps(session.p2)
	result = RaceValidation(
		year=year,
		event=event,
		our_car=session.p2.driver,
		opponent=session.p1.driver,
		total_laps=engine.end_lap,
		actual_pit_laps=actual_pits,
		recommended_pit_laps=(),
		directionally_consistent=False,
		data_gap_count=len(session.p2.data_gaps),
	)

	# 1. Sample laps across the race and record what the engine actually said.
	recommended: list[int] = []
	for lap in _sample_laps(engine.end_lap):
		context = lap_context(ctx, lap)
		recommendation = optimize_strategy(
			start_lap=lap,
			end_lap=max(lap + 1, engine.end_lap),
			current_compound=str(context["compound"]),
			current_tyre_age=int(context["tyre_age"]),
			lap_time_seconds=list(context["lap_times"]) or [90.0, 90.0],
			rival_pit_laps=tuple(context["rival_pit_laps"]),
			rival_tyre_age=int(context["rival_tyre_age"]),
			cars_ahead_gaps_seconds=list(context["gaps_to_ahead"]) or None,
			stint_lap_numbers=tuple(context["stint_lap_numbers"]),
			stint_compounds=tuple(context["stint_compounds"]),
			stint_tyre_ages=tuple(context["stint_tyre_ages"]),
			stint_lap_times=tuple(context["stint_lap_times"]),
			field_baseline=context["field_baseline"],
		)
		recommended.append(recommendation.pit_lap)
		result.lap_samples.append(
			LapSample(
				lap=lap,
				action=recommendation.action,
				pit_lap=recommendation.pit_lap,
				confidence_lower=round(recommendation.confidence.lower, 4),
				confidence_upper=round(recommendation.confidence.upper, 4),
				tyre_delta_risk=recommendation.explainability.tyre_delta_risk,
				degradation_measured=bool(
					recommendation.explainability.measured.get("tyre_degradation")
				),
				has_explainability=recommendation.explainability is not None,
				has_reasoning=bool(recommendation.reasoning),
			)
		)

	result.recommended_pit_laps = tuple(recommended)
	# PRD FR-10 and FR-19 are blocking: every recommendation carries both.
	result.explainability_on_every_recommendation = all(
		sample.has_explainability and sample.has_reasoning for sample in result.lap_samples
	)
	result.confidence_on_every_recommendation = all(
		0.0 <= sample.confidence_lower <= sample.confidence_upper <= 1.0
		for sample in result.lap_samples
	)
	# PRD 5.A: the recommendation has to be recomputed from each lap's own state
	# rather than frozen from initial load. What proves that is the payload moving
	# with the lap - not the call flipping. A genuinely stable race should keep
	# producing the same call, and requiring it to change would be requiring the
	# engine to be wrong, so the confidence band and factor values are what is
	# checked here alongside the call itself.
	result.recommendation_varies_across_laps = (
		len(
			{
				(
					sample.action,
					sample.pit_lap,
					sample.confidence_lower,
					sample.confidence_upper,
					sample.tyre_delta_risk,
				)
				for sample in result.lap_samples
			}
		)
		> 1
	)

	# 2. Directional agreement with the team's real calls.
	tolerance = max(
		MIN_DIRECTIONAL_TOLERANCE_LAPS, int(engine.end_lap * DIRECTIONAL_TOLERANCE_FRACTION)
	)
	if actual_pits and recommended:
		result.directionally_consistent = any(
			abs(suggested - actual) <= tolerance
			for suggested in recommended
			for actual in actual_pits
		)
	else:
		result.notes.append("No recorded pit stop for our car, so directional agreement is not scorable.")

	# 3. Tyre-cliff onset against the independently-derived observed drop-off.
	for race in (session.p1, session.p2):
		laps = sorted(race.laps, key=lambda lap: lap.lap_number)
		raw = build_stints(
			[lap.lap_number for lap in laps],
			[lap.compound for lap in laps],
			[lap.tyre_life for lap in laps],
			[lap.lap_time_seconds for lap in laps],
		)
		stints, _basis = normalise_stints(raw, session.field_median_lap_times)
		from app.tyre_model.active import active_model

		model = active_model()
		for stint in stints:
			fit = model.fit(stint)
			observed = observed_drop_off_lap(stint)
			if fit.predicted_cliff_lap is None or observed is None:
				continue
			result.cliff_predictions += 1
			if abs(fit.predicted_cliff_lap - observed) <= ACCURACY_TOLERANCE_LAPS:
				result.cliff_within_tolerance += 1

	# 4. Real shock injections, timed against the FR-7 budget.
	latencies: list[float] = []
	for shock_lap in _sample_laps(engine.end_lap)[:3]:
		probe = SimulationEngine(
			session.p1, session.p2, field_median_lap_times=session.field_median_lap_times
		)
		started = perf_counter()
		probe.inject_shock(shock_lap, ShockEventType.SAFETY_CAR)
		latencies.append(perf_counter() - started)
	if latencies:
		result.shock_events_tested = len(latencies)
		result.max_reoptimization_seconds = round(max(latencies), 5)
		result.reoptimization_within_budget = max(latencies) <= REOPTIMIZATION_BUDGET_SECONDS

	result.safety_car_or_vsc_evidence, result.wet_or_intermediate_evidence = _session_evidence(
		session.historical_events, session.p2
	)
	return result


def run_suite(
	races: Iterable[tuple[int, str]] | None = None,
	*,
	cache_dir: str | None = None,
) -> dict[str, object]:
	"""Run the suite and summarise it against the PRD section 13 targets."""
	targets = races or [(int(race["year"]), str(race["event"])) for race in SUPPORTED_RACES]
	results = [validate_race(year, event, cache_dir=cache_dir) for year, event in targets]

	directional = sum(result.directionally_consistent for result in results)
	cliff_predictions = sum(result.cliff_predictions for result in results)
	cliff_hits = sum(result.cliff_within_tolerance for result in results)
	latencies = [
		result.max_reoptimization_seconds
		for result in results
		if result.max_reoptimization_seconds is not None
	]

	return {
		"races_validated": len(results),
		"results": [asdict(result) for result in results],
		"summary": {
			# Blocking criteria.
			"explainability_on_every_recommendation": all(
				result.explainability_on_every_recommendation for result in results
			),
			"confidence_on_every_recommendation": all(
				result.confidence_on_every_recommendation for result in results
			),
			"recommendation_updates_per_lap": all(
				result.recommendation_varies_across_laps for result in results
			),
			"max_reoptimization_seconds": round(max(latencies), 5) if latencies else None,
			"mean_reoptimization_seconds": round(fmean(latencies), 5) if latencies else None,
			"reoptimization_within_budget": all(
				result.reoptimization_within_budget for result in results
			),
			# Reported, not blocking.
			"directional_agreement": f"{directional}/{len(results)}",
			"directional_target_met": directional >= 3,
			"cliff_predictions_scored": cliff_predictions,
			"cliff_within_two_laps": cliff_hits,
			"safety_car_evidence": f"{sum(r.safety_car_or_vsc_evidence for r in results)}/{len(results)}",
			"wet_evidence": f"{sum(r.wet_or_intermediate_evidence for r in results)}/{len(results)}",
			"total_data_gaps_flagged": sum(result.data_gap_count for result in results),
		},
	}
