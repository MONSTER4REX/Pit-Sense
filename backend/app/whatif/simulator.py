from __future__ import annotations

from app.engine.reoptimizer import optimize_strategy
from app.schemas.recommendation import StrategyRecommendation


def compare_branches(
	*,
	current_lap: int,
	end_lap: int,
	current_compound: str,
	current_tyre_age: int,
	lap_time_seconds: list[float],
	uncertainty_events: tuple[str, ...] = (),
	rival_cover_stop_probability: float = 0.0,
) -> dict[str, StrategyRecommendation]:
	branches: dict[str, StrategyRecommendation] = {}
	for name, offset in (("pit_now", 0), ("stay_out", 1), ("extend_stint", 3)):
		recommendation = optimize_strategy(
			start_lap=min(end_lap - 1, current_lap + offset),
			end_lap=end_lap,
			current_compound=current_compound,
			current_tyre_age=current_tyre_age + offset,
			lap_time_seconds=lap_time_seconds,
			uncertainty_events=uncertainty_events,
			rival_cover_stop_probability=rival_cover_stop_probability,
		)
		branches[name] = recommendation.model_copy(update={"action": name})
	return branches
