from __future__ import annotations

from app.schemas.simulation import CarSimulationState, StrategyDecision


def baseline_decision(
	*,
	car: CarSimulationState,
	end_lap: int,
	shock_event: str | None,
	pit_lane_loss_seconds: float = 20.0,
) -> StrategyDecision:
	"""Deterministic conventional comparator; it does not use the PitSense graph."""
	if shock_event in {"safety_car", "vsc"} and car.tyre_age >= 12:
		action = "PIT"
		target_lap = car.lap
		reason = "A conventional pit-window rule treats the reduced pit loss as an opportunity."
	elif car.tyre_age >= 24 or (shock_event == "rain" and car.compound not in {"INTERMEDIATE", "WET"}):
		action = "PIT"
		target_lap = car.lap
		reason = "Tyre age or weather pressure exceeds the baseline pit-window rule."
	else:
		action = "STAY_OUT"
		target_lap = min(end_lap, car.lap + 3)
		reason = "The baseline model keeps the current tyre within its conventional window."

	return StrategyDecision(
		car=car.car,
		lap=car.lap,
		action=action,
		target_lap=target_lap,
		confidence=None,
		projected_time_cost=pit_lane_loss_seconds if action == "PIT" else 0.0,
		projected_position=car.position + (1 if action == "PIT" else 0),
		explanation=reason,
		model_type="BASELINE",
	)