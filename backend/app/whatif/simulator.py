"""What-If branch comparison (PRD FR-14 / FR-15).

Three branches are compared side by side from the same race state: pit now, stay
out, and extend the stint. Each is a real optimisation run, so each carries its
own projected time, its own factor breakdown, and its own confidence band.

The branches differ only in when the car is assumed to act. ``EXTEND_STINT_LAPS``
is the horizon that separates "stay out" from "extend" and is stated here rather
than buried in the engine.
"""
from __future__ import annotations

from typing import Mapping, Sequence

from app.engine.reoptimizer import optimize_strategy
from app.schemas.recommendation import StrategyRecommendation

# Laps of additional running each branch assumes before the car acts.
BRANCH_OFFSET_LAPS = {"pit_now": 0, "stay_out": 1, "extend_stint": 3}


def compare_branches(
	*,
	current_lap: int,
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
) -> dict[str, StrategyRecommendation]:
	branches: dict[str, StrategyRecommendation] = {}
	for name, offset in BRANCH_OFFSET_LAPS.items():
		recommendation = optimize_strategy(
			start_lap=min(end_lap - 1, current_lap + offset),
			end_lap=end_lap,
			current_compound=current_compound,
			current_tyre_age=current_tyre_age + offset,
			lap_time_seconds=lap_time_seconds,
			uncertainty_events=uncertainty_events,
			rival_cover_stop_probability=rival_cover_stop_probability,
			rival_pit_laps=rival_pit_laps,
			rival_tyre_age=rival_tyre_age,
			cars_ahead_gaps_seconds=cars_ahead_gaps_seconds,
			stint_lap_numbers=stint_lap_numbers,
			stint_compounds=stint_compounds,
			stint_tyre_ages=stint_tyre_ages,
			stint_lap_times=stint_lap_times,
			field_baseline=field_baseline,
		)
		# The branch name is the decision being evaluated; the engine's own action
		# for that branch stays visible in its reasoning and factor breakdown.
		branches[name] = recommendation.model_copy(update={"action": name})
	return branches
