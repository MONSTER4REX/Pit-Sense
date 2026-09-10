from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from time import monotonic


class ShockEventType(StrEnum):
	SAFETY_CAR = "safety_car"
	VSC = "vsc"
	RAIN = "rain"
	PUNCTURE = "puncture"


@dataclass(frozen=True)
class ShockEvent:
	event_type: ShockEventType
	lap_number: int
	injected_at: float


@dataclass(frozen=True)
class ReoptimizationStatus:
	state: str
	elapsed_seconds: float
	error: str | None = None


def record_reoptimization(started_at: float, error: str | None = None) -> ReoptimizationStatus:
	elapsed = monotonic() - started_at
	if error:
		return ReoptimizationStatus("error", elapsed, error)
	if elapsed > 1.0:
		return ReoptimizationStatus("stale", elapsed, "Re-optimization exceeded the 1 second budget")
	return ReoptimizationStatus("fresh", elapsed)
