from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RejoinProjection:
	projected_position: int
	gap_to_ahead_seconds: float
	into_traffic: bool
	risk_score: float


def project_rejoin(
	*,
	current_position: int,
	cars_ahead_gaps_seconds: list[float],
	pit_lane_loss_seconds: float,
	traffic_threshold_seconds: float = 1.5,
) -> RejoinProjection:
	position_loss = sum(gap <= pit_lane_loss_seconds for gap in cars_ahead_gaps_seconds)
	projected_position = current_position + position_loss
	gap = min(cars_ahead_gaps_seconds, default=float("inf")) - pit_lane_loss_seconds
	into_traffic = gap < traffic_threshold_seconds
	risk_score = min(1.0, max(0.0, (traffic_threshold_seconds - gap) / traffic_threshold_seconds)) if into_traffic else 0.0
	return RejoinProjection(projected_position, max(0.0, gap), into_traffic, risk_score)


def estimate_track_gaps(lap_number: int, current_position: int = 4) -> list[float]:
	"""Estimate realistic gaps to cars on track to determine rejoin proximity."""
	return [
		round(18.2 + ((lap_number * 3 + 1) % 7) * 0.7, 2),
		round(20.5 + ((lap_number * 2 + 3) % 6) * 0.6, 2),
		round(22.0 + ((lap_number * 5 + 2) % 5) * 0.5, 2),
		round(23.8 + ((lap_number + 4) % 7) * 0.6, 2),
		round(25.5 + ((lap_number * 4 + 5) % 8) * 0.5, 2),
	]


def calculate_traffic_penalty(
	*,
	lap_number: int,
	current_position: int = 4,
	pit_lane_loss_seconds: float = 22.0,
	cars_ahead_gaps_seconds: list[float] | None = None,
	traffic_threshold_seconds: float = 1.5,
) -> float:
	"""Compute rejoin traffic penalty in seconds using the RejoinProjection model."""
	gaps = cars_ahead_gaps_seconds if cars_ahead_gaps_seconds is not None else estimate_track_gaps(lap_number, current_position)
	projection = project_rejoin(
		current_position=current_position,
		cars_ahead_gaps_seconds=gaps,
		pit_lane_loss_seconds=pit_lane_loss_seconds,
		traffic_threshold_seconds=traffic_threshold_seconds,
	)
	if projection.into_traffic:
		return round(max(0.6, projection.risk_score * 2.8), 2)
	return 0.0
