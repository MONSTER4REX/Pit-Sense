from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import AsyncIterator, Iterable


@dataclass(frozen=True)
class ReplayTick:
	lap_number: int
	timestamp_seconds: float
	lap_time_seconds: float | None


async def replay_ticks(
	lap_times: Iterable[float | None],
	*,
	speed: float = 1.0,
	start_lap: int = 1,
) -> AsyncIterator[ReplayTick]:
	if speed <= 0:
		raise ValueError("Replay speed must be positive")
	elapsed = 0.0
	for offset, lap_time in enumerate(lap_times):
		lap_number = start_lap + offset
		duration = (lap_time or 0.0) / speed
		await asyncio.sleep(min(duration, 0.01))
		elapsed += duration
		yield ReplayTick(lap_number, elapsed, lap_time)
