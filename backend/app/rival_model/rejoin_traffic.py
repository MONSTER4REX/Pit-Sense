from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RejoinProjection:
	projected_position: int
	gap_to_ahead_seconds: float
	into_traffic: bool
	risk_score: float
	measured: bool = True
	reason: str = "Projected from observed gaps to the cars ahead."


def project_rejoin(
	*,
	current_position: int,
	cars_ahead_gaps_seconds: list[float],
	pit_lane_loss_seconds: float,
	traffic_threshold_seconds: float = 1.5,
) -> RejoinProjection:
	"""Project where a car rejoins after a stop, from real gaps to cars ahead.

	With no observed gaps there is nothing to project from. The projection then
	reports itself as unmeasured rather than inventing a field to rejoin into
	(PRD FR-3: flag gaps explicitly, never fill them silently).
	"""
	if not cars_ahead_gaps_seconds:
		return RejoinProjection(
			projected_position=current_position,
			gap_to_ahead_seconds=0.0,
			into_traffic=False,
			risk_score=0.0,
			measured=False,
			reason="No gap data to cars ahead was available for this lap.",
		)

	position_loss = sum(gap <= pit_lane_loss_seconds for gap in cars_ahead_gaps_seconds)
	projected_position = current_position + position_loss
	gap = min(cars_ahead_gaps_seconds) - pit_lane_loss_seconds
	into_traffic = gap < traffic_threshold_seconds
	risk_score = (
		min(1.0, max(0.0, (traffic_threshold_seconds - gap) / traffic_threshold_seconds))
		if into_traffic
		else 0.0
	)
	return RejoinProjection(projected_position, max(0.0, gap), into_traffic, risk_score)


def calculate_traffic_penalty(
	*,
	cars_ahead_gaps_seconds: list[float] | None,
	current_position: int = 1,
	pit_lane_loss_seconds: float = 22.0,
	traffic_threshold_seconds: float = 1.5,
) -> float:
	"""Rejoin traffic penalty in seconds, or 0.0 when no gap data exists.

	A zero here means "not measurable from this lap's data", and callers surface
	it that way. It never means "we guessed a quiet track".
	"""
	if not cars_ahead_gaps_seconds:
		return 0.0
	projection = project_rejoin(
		current_position=current_position,
		cars_ahead_gaps_seconds=cars_ahead_gaps_seconds,
		pit_lane_loss_seconds=pit_lane_loss_seconds,
		traffic_threshold_seconds=traffic_threshold_seconds,
	)
	if not projection.measured or not projection.into_traffic:
		return 0.0
	return round(projection.risk_score * 2.8, 2)
