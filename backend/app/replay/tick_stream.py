from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, AsyncIterator, Iterable

from app.rival_model.cover_stop import cover_stop_probability
from app.rival_model.rejoin_traffic import calculate_traffic_penalty
from app.replay.fastf1_live import extract_lap_dynamic_data
from app.engine.reoptimizer import optimize_strategy

@dataclass(frozen=True)
class ReplayTick:
	lap_number: int
	timestamp_seconds: float
	lap_time_seconds: float | None
	rival_cover_stop_probability: float = 0.0
	traffic_rejoin_risk: float = 0.0
	tyre_age: int = 0
	distance_to_driver_ahead: float = 0.0
	recommendation: dict[str, Any] | None = None


async def replay_ticks(
	lap_times: Iterable[float | None],
	*,
	speed: float = 1.0,
	start_lap: int = 1,
	start_tyre_age: int = 12,
	observed_response_laps: tuple[int, ...] = (16, 17, 18, 19, 21),
	pit_window_lap: int = 18,
) -> AsyncIterator[ReplayTick]:
	if speed <= 0:
		raise ValueError("Replay speed must be positive")
	lap_values = list(lap_times)
	elapsed = 0.0
	for offset, lap_time in enumerate(lap_values):
		lap_number = start_lap + offset
		current_tyre_age = max(1, start_tyre_age + offset)
		
		dyn_data = extract_lap_dynamic_data(lap_number)
		fastf1_rival_age = dyn_data['rival_tyre_age']
		fastf1_gaps = dyn_data['gaps_to_ahead']
		dist_ahead = dyn_data['distance_to_driver_ahead']
		
		rival_age_to_use = fastf1_rival_age if fastf1_rival_age > 0 else current_tyre_age
		
		rival_cover = cover_stop_probability(
			rival_tyre_age=rival_age_to_use,
			observed_response_laps=list(observed_response_laps),
			pit_window_lap=pit_window_lap,
		)
		
		gaps_to_use = fastf1_gaps if len(fastf1_gaps) > 0 else None
		traffic_risk = calculate_traffic_penalty(
			lap_number=lap_number,
			cars_ahead_gaps_seconds=gaps_to_use
		)
		recommendation = optimize_strategy(
			start_lap=lap_number,
			end_lap=max(lap_number + 1, start_lap + len(lap_values) - 1),
			current_compound="MEDIUM",
			current_tyre_age=current_tyre_age,
			lap_time_seconds=[value for value in [lap_time] if value is not None] or [90.0, 90.0],
			uncertainty_events=(),
			rival_cover_stop_probability=rival_cover,
		)
		
		duration = (lap_time or 0.0) / speed
		await asyncio.sleep(min(duration, 0.01))
		elapsed += duration
		yield ReplayTick(
			lap_number=lap_number,
			timestamp_seconds=elapsed,
			lap_time_seconds=lap_time,
			rival_cover_stop_probability=rival_cover,
			traffic_rejoin_risk=traffic_risk,
			tyre_age=current_tyre_age,
			distance_to_driver_ahead=round(dist_ahead, 2),
			recommendation=recommendation.model_dump(mode="json")
		)
