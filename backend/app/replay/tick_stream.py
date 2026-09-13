"""Lap-by-lap replay tick stream (PRD FR-16 / 5.A).

Each tick carries the recommendation freshly computed for that lap's real state,
embedded directly in the payload. The frontend renders what arrives; it never
recomputes a lap, tyre, gap, or recommendation of its own, and nothing stays
frozen from initial load.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, AsyncIterator, Iterable

from app.engine.reoptimizer import optimize_strategy
from app.replay.session_context import SessionReplayContext, lap_context

# Ceiling on real wall-clock time spent sleeping between ticks, so a replay stays
# interactive regardless of the race's real lap times.
MAX_TICK_SLEEP_SECONDS = 0.01


@dataclass(frozen=True)
class ReplayTick:
	lap_number: int
	timestamp_seconds: float
	lap_time_seconds: float | None
	rival_cover_stop_probability: float = 0.0
	traffic_rejoin_risk: float = 0.0
	tyre_age: int = 0
	compound: str | None = None
	position: int | None = None
	gap_to_leader_seconds: float | None = None
	distance_to_driver_ahead: float = 0.0
	recommendation: dict[str, Any] | None = None


async def replay_session_ticks(
	ctx: SessionReplayContext,
	*,
	speed: float = 1.0,
	start_lap: int = 1,
) -> AsyncIterator[ReplayTick]:
	"""Replay the loaded historical session - no hardcoded race, lap, or tyre state."""
	if speed <= 0:
		raise ValueError("Replay speed must be positive")

	elapsed = 0.0
	for lap_number in range(start_lap, ctx.end_lap + 1):
		context = lap_context(ctx, lap_number)
		gaps_ahead = list(context["gaps_to_ahead"]) or None

		recommendation = optimize_strategy(
			start_lap=lap_number,
			end_lap=max(lap_number + 1, ctx.end_lap),
			current_compound=str(context["compound"]),
			current_tyre_age=int(context["tyre_age"]),
			lap_time_seconds=list(context["lap_times"]) or [90.0, 90.0],
			uncertainty_events=ctx.uncertainty_events,
			rival_pit_laps=tuple(context["rival_pit_laps"]),
			rival_tyre_age=int(context["rival_tyre_age"]),
			cars_ahead_gaps_seconds=gaps_ahead,
			stint_lap_numbers=tuple(context["stint_lap_numbers"]),
			stint_compounds=tuple(context["stint_compounds"]),
			stint_tyre_ages=tuple(context["stint_tyre_ages"]),
			stint_lap_times=tuple(context["stint_lap_times"]),
			field_baseline=context["field_baseline"],
		)

		lap_time = context["lap_time"]
		duration = (lap_time or 0.0) / speed
		await asyncio.sleep(min(duration, MAX_TICK_SLEEP_SECONDS))
		elapsed += duration

		yield ReplayTick(
			lap_number=lap_number,
			timestamp_seconds=elapsed,
			lap_time_seconds=lap_time,
			rival_cover_stop_probability=recommendation.explainability.rival_cover_stop_probability,
			traffic_rejoin_risk=recommendation.explainability.traffic_rejoin_risk,
			tyre_age=int(context["tyre_age"]),
			compound=str(context["compound"]),
			position=context["position"],
			gap_to_leader_seconds=context["gap_to_leader"],
			distance_to_driver_ahead=round(float(context["distance_to_driver_ahead"]), 2),
			recommendation=recommendation.model_dump(mode="json"),
		)


async def replay_ticks(
	lap_times: Iterable[float | None],
	*,
	speed: float = 1.0,
	start_lap: int = 1,
	start_tyre_age: int = 1,
	compound: str = "MEDIUM",
) -> AsyncIterator[ReplayTick]:
	"""Replay a bare sequence of lap times, for callers without a loaded session.

	This path has no rival, no field, and no stint history, so the factors that
	need them are reported as unmeasured rather than filled in from elsewhere.
	"""
	if speed <= 0:
		raise ValueError("Replay speed must be positive")

	lap_values = list(lap_times)
	end_lap = start_lap + len(lap_values) - 1
	elapsed = 0.0
	observed: list[tuple[int, int, float | None]] = []

	for offset, lap_time in enumerate(lap_values):
		lap_number = start_lap + offset
		tyre_age = max(1, start_tyre_age + offset)
		observed.append((lap_number, tyre_age, lap_time))

		recommendation = optimize_strategy(
			start_lap=lap_number,
			end_lap=max(lap_number + 1, end_lap),
			current_compound=compound,
			current_tyre_age=tyre_age,
			lap_time_seconds=[value for value in lap_values if value is not None] or [90.0, 90.0],
			stint_lap_numbers=tuple(row[0] for row in observed),
			stint_compounds=tuple(compound for _ in observed),
			stint_tyre_ages=tuple(row[1] for row in observed),
			stint_lap_times=tuple(row[2] for row in observed),
		)

		duration = (lap_time or 0.0) / speed
		await asyncio.sleep(min(duration, MAX_TICK_SLEEP_SECONDS))
		elapsed += duration

		yield ReplayTick(
			lap_number=lap_number,
			timestamp_seconds=elapsed,
			lap_time_seconds=lap_time,
			rival_cover_stop_probability=recommendation.explainability.rival_cover_stop_probability,
			traffic_rejoin_risk=recommendation.explainability.traffic_rejoin_risk,
			tyre_age=tyre_age,
			compound=compound,
			recommendation=recommendation.model_dump(mode="json"),
		)
