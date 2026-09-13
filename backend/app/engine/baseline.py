"""The opponent's post-fork baseline model (PRD 5.F, FR-24, FR-25).

After the fork the opponent must not coast along its recorded historical future -
the shock changed its race too. It runs this model instead, and the model has a
name and stated assumptions that travel with every projection it produces.

MEASURED STINT-LENGTH BASELINE
	The opponent keeps running until one of two things is true:

	1. Its tyre reaches the stint length it actually used earlier in this race
	   (the median of its own completed stints). This is a conventional
	   pit-window rule, calibrated to this specific car rather than to a
	   generic number.
	2. The field is neutralised by a safety car or VSC while its tyre is already
	   past half that stint length - the cheap stop a real team would take.

	Under rain on dry tyres it stops immediately, which is what the opponent's
	own race would force regardless of strategy.

This is a comparator, not a claim about what the real team would have decided. It
is also deliberately not the PitSense graph: the two sides of the comparison have
to be computed by different logic for the comparison to mean anything.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.schemas.simulation import CarSimulationState, StrategyDecision

MODEL_NAME = "Measured stint-length baseline"
# Stint length assumed when the opponent completed no stint we can measure.
NOMINAL_STINT_LAPS = 20
# Fraction of the opponent's typical stint after which a neutralisation is worth
# taking as a cheap stop.
NEUTRALISED_STOP_STINT_FRACTION = 0.5
DRY_COMPOUNDS = {"SOFT", "MEDIUM", "HARD"}


@dataclass(frozen=True)
class BaselineContext:
	"""What the baseline knows about the opponent, all of it measured."""

	typical_stint_laps: int | None
	pit_lane_loss_seconds: float
	pit_loss_measured: bool

	@property
	def stint_target(self) -> int:
		return self.typical_stint_laps or NOMINAL_STINT_LAPS

	def assumptions(self) -> list[str]:
		if self.typical_stint_laps is not None:
			stint_line = (
				f"The opponent is assumed to run stints of about {self.typical_stint_laps} laps, "
				"the median length of the stints it actually completed in this race."
			)
		else:
			stint_line = (
				f"The opponent completed no measurable stint in this race, so a nominal "
				f"{NOMINAL_STINT_LAPS}-lap stint is assumed and flagged as unmeasured."
			)
		return [
			f"Opponent model: {MODEL_NAME}.",
			stint_line,
			(
				"A safety car or VSC is taken as a pit opportunity once its tyre is past "
				f"{int(NEUTRALISED_STOP_STINT_FRACTION * 100)}% of that stint length."
			),
			"Rain on dry tyres forces an immediate stop.",
			"The opponent does not replay its recorded historical future after the fork.",
		]


def baseline_decision(
	*,
	car: CarSimulationState,
	end_lap: int,
	shock_event: str | None,
	context: BaselineContext,
) -> StrategyDecision:
	"""Decide what the opponent does at this lap, and say why in plain language."""
	stint_target = context.stint_target
	neutralised = shock_event in {"safety_car", "vsc"}
	on_dry = (car.compound or "").upper() in DRY_COMPOUNDS

	if shock_event == "rain" and on_dry:
		action, reason = "PIT", (
			f"{MODEL_NAME}: rain on a dry compound forces an immediate stop."
		)
	elif neutralised and car.tyre_age >= stint_target * NEUTRALISED_STOP_STINT_FRACTION:
		action, reason = "PIT", (
			f"{MODEL_NAME}: the field is neutralised and the tyre is {car.tyre_age} laps old, "
			f"past half of its measured {stint_target}-lap stint, so the cheap stop is taken."
		)
	elif car.tyre_age >= stint_target:
		action, reason = "PIT", (
			f"{MODEL_NAME}: the tyre has reached {car.tyre_age} laps, its measured "
			f"{stint_target}-lap stint length."
		)
	else:
		action, reason = "STAY_OUT", (
			f"{MODEL_NAME}: at {car.tyre_age} laps the tyre is still inside its measured "
			f"{stint_target}-lap stint, so the opponent stays out."
		)

	if action == "PIT":
		target_lap = car.lap
		projected_cost = context.pit_lane_loss_seconds
	else:
		# Next scheduled opportunity is the lap its stint target comes due.
		target_lap = min(end_lap, car.lap + max(1, stint_target - car.tyre_age))
		projected_cost = 0.0

	return StrategyDecision(
		car=car.car,
		lap=car.lap,
		action=action,
		target_lap=target_lap,
		confidence=None,
		projected_time_cost=projected_cost,
		projected_position=car.position,
		explanation=reason,
		model_type="BASELINE",
	)
