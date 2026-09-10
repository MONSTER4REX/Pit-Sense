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
