"""Strategy optimisation entry point (PRD FR-6).

Builds the strategy graph for the car's current state, finds the minimum
total-race-time path through it, and returns that path as an explainable,
confidence-banded recommendation.

Every input that can be measured is measured: the degradation rate comes from the
active tyre model fitted to this car's current stint, the rejoin traffic cost from
observed gaps to the cars ahead, and the rival cover-stop probability from the
rival's own recorded pit laps. Inputs that cannot be measured are flagged through
the breakdown and widen the confidence band - they are never defaulted to a
plausible-looking number.
"""
from __future__ import annotations

from typing import Mapping, Sequence

from app.confidence.risk_tier import score_undercut_risk_tier
from app.confidence.scorer import score_confidence
from app.engine.dijkstra import shortest_path
from app.engine.graph_builder import build_strategy_graph
from app.explainability.factor_breakdown import explain_path
from app.explainability.reasoning import describe_recommendation
from app.rival_model.cover_stop import cover_stop_probability
from app.schemas.recommendation import StrategyRecommendation
from app.tyre_model.active import (
	active_model_selection,
	degradation_rate_or_none,
	fit_current_stint,
	normalisation_note,
)


def optimize_strategy(
	*,
	start_lap: int,
	end_lap: int,
	current_compound: str,
	current_tyre_age: int,
	lap_time_seconds: list[float],
	uncertainty_events: tuple[str, ...] = (),
	rival_cover_stop_probability: float | None = None,
	rival_pit_laps: Sequence[int] = (),
	rival_tyre_age: int | None = None,
	cars_ahead_gaps_seconds: list[float] | None = None,
	stint_lap_numbers: Sequence[int] = (),
	stint_compounds: Sequence[str | None] = (),
	stint_tyre_ages: Sequence[int | None] = (),
	stint_lap_times: Sequence[float | None] = (),
	field_baseline: Mapping[int, float] | None = None,
	pit_lane_loss_seconds: float = 22.0,
) -> StrategyRecommendation:
	# 1. Measure this car's tyre degradation from its own stint history.
	fit = None
	fuel_note: str | None = None
	if stint_lap_numbers:
		stint_history = {
			"lap_numbers": stint_lap_numbers,
			"compounds": stint_compounds,
			"tyre_ages": stint_tyre_ages,
			"lap_times": stint_lap_times,
			"field_baseline": field_baseline,
		}
		fit = fit_current_stint(**stint_history)
		# How the lap times were normalised sits underneath the degradation
		# number, so it travels with the recommendation rather than staying buried.
		fuel_note = normalisation_note(**stint_history)
	degradation_rate = degradation_rate_or_none(fit)

	# 2. Build and solve the graph.
	build = build_strategy_graph(
		start_lap=start_lap,
		end_lap=end_lap,
		current_compound=current_compound,
		current_tyre_age=current_tyre_age,
		lap_time_seconds=lap_time_seconds,
		degradation_rate_seconds_per_lap=degradation_rate,
		cars_ahead_gaps_seconds=cars_ahead_gaps_seconds,
		uncertainty_events=uncertainty_events,
		pit_lane_loss_seconds=pit_lane_loss_seconds,
	)
	start = next(node for node in build.edges if node.lap == start_lap)
	total, path = shortest_path(start, build.edges, end_lap)

	pit_edge = next((edge for edge in path if edge.action == "pit_now"), None)
	action = "pit_now" if pit_edge else "stay_out"
	pit_lap = pit_edge.source.lap if pit_edge else end_lap

	# 3. Rival cover-stop probability from the rival's own recorded behaviour.
	if rival_cover_stop_probability is not None:
		rival_cover = rival_cover_stop_probability
		rival_measured = True
	elif rival_pit_laps:
		rival_cover = cover_stop_probability(
			rival_tyre_age=rival_tyre_age if rival_tyre_age is not None else current_tyre_age,
			observed_response_laps=list(rival_pit_laps),
			pit_window_lap=pit_lap,
		)
		rival_measured = True
	else:
		# No recorded rival stops yet in this session - the probability is not
		# knowable, so it is reported as unmeasured rather than assumed.
		rival_cover = 0.0
		rival_measured = False

	measured = {**build.measured_factors, "rival_cover_stop": rival_measured}
	notes = list(build.notes)
	if fuel_note and degradation_rate is not None:
		notes.append(fuel_note)
	if not rival_measured:
		notes.append(
			"The rival has no recorded pit stops yet this session, so cover-stop "
			"probability is not measurable at this lap."
		)

	confidence = score_confidence(uncertainty_events=uncertainty_events, measured_factors=measured)
	explainability = explain_path(path, rival_cover, measured=measured, notes=notes)
	selection = active_model_selection()

	return StrategyRecommendation(
		action=action,
		pit_lap=pit_lap,
		projected_total_time_seconds=total,
		undercut_risk_tier=score_undercut_risk_tier(
			rival_cover_stop_probability=rival_cover,
			confidence=confidence,
		),
		explainability=explainability,
		confidence=confidence,
		reasoning=describe_recommendation(
			action=action,
			pit_lap=pit_lap,
			start_lap=start_lap,
			explainability=explainability,
			confidence=confidence,
		),
		degradation_model=selection.model_name if degradation_rate is not None else None,
		degradation_rate_seconds_per_lap=degradation_rate,
	)
