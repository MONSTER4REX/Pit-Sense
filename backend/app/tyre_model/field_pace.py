"""Normalising lap times so that what is left is tyre wear (PRD 5.J, 13.1).

Raw race lap times move for several reasons at once, and tyre wear is the
smallest of them. Over a stint a car gets faster as fuel burns off and faster
again as the track rubbers in, while the tyre makes it slower. The first two
usually win, which is why a detector reading raw laps sees a stint getting
*quicker* and reports no degradation at all - the Canada miss recorded in PRD
13.1, and the same failure repeated at Melbourne, where corrected lap times still
fall seven seconds across a stint.

Fuel burn and track evolution have one property that makes them separable: they
act on every car on track at the same lap. Tyre age does not - at any given lap
the field is spread across fresh and worn sets. So the field's own median green
lap for each lap number is the reference, and a car's pace relative to it is what
its tyres are doing.

	normalised lap = this car's lap time - the field's median for that lap

Two bases, in order of preference:

	FIELD PACE  the field median above, measured entirely from this session
	FUEL        the stated fuel correction in ``app.tyre_model.fuel``, used only
	            where the field baseline does not cover enough of a stint

Which basis was used is reported, never assumed, so a rate that rests on the
weaker fallback is never presented as one that rests on the field.
"""
from __future__ import annotations

from typing import Mapping, Sequence

from app.tyre_model.fuel import estimate_fuel_effect, fuel_correct
from app.tyre_model.models import StintObservation

# Fraction of a stint's laps the field baseline must cover before it is used.
MIN_BASELINE_COVERAGE = 0.6

FIELD_PACE_BASIS = "field_pace"
FUEL_BASIS = "fuel_correction"


def _coverage(stint: StintObservation, baseline: Mapping[int, float]) -> float:
	if not stint.lap_numbers:
		return 0.0
	covered = sum(1 for lap in stint.lap_numbers if lap in baseline)
	return covered / len(stint.lap_numbers)


def normalise_to_field(
	stint: StintObservation, baseline: Mapping[int, float]
) -> StintObservation | None:
	"""Express a stint as pace relative to the field, or None if uncovered.

	The field median for the stint's own laps is added back afterwards, so the
	result stays on the scale of a lap time rather than becoming a small delta.
	That keeps every downstream threshold - which is expressed in seconds -
	meaning the same thing it always meant.
	"""
	if _coverage(stint, baseline) < MIN_BASELINE_COVERAGE:
		return None

	covered = [baseline[lap] for lap in stint.lap_numbers if lap in baseline]
	anchor = sum(covered) / len(covered)

	laps: list[int] = []
	ages: list[int] = []
	times: list[float] = []
	for lap, age, lap_time in zip(stint.lap_numbers, stint.tyre_ages, stint.lap_times_seconds):
		reference = baseline.get(lap)
		if reference is None or lap_time is None or lap_time <= 0:
			continue
		laps.append(lap)
		ages.append(age)
		times.append(round(lap_time - reference + anchor, 3))

	if len(times) < 2:
		return None
	return StintObservation(
		compound=stint.compound,
		lap_numbers=tuple(laps),
		tyre_ages=tuple(ages),
		lap_times_seconds=tuple(times),
	)


def normalise_stints(
	stints: Sequence[StintObservation],
	baseline: Mapping[int, float] | None,
) -> tuple[list[StintObservation], str]:
	"""Normalise every stint by the best basis available, and say which it was."""
	if baseline:
		normalised = [normalise_to_field(stint, baseline) for stint in stints]
		if all(item is not None for item in normalised):
			return [item for item in normalised if item is not None], FIELD_PACE_BASIS

	# The field baseline does not cover these stints, so fall back to removing the
	# fuel effect alone. Track evolution is left in, and the basis says so.
	effect = estimate_fuel_effect(stints)
	return [fuel_correct(stint, effect) for stint in stints], FUEL_BASIS


def normalisation_basis(
	stints: Sequence[StintObservation],
	baseline: Mapping[int, float] | None,
) -> str:
	"""Plain-language statement of how the lap times were normalised."""
	if not stints:
		return "No stint was available to normalise."

	_normalised, basis = normalise_stints(stints, baseline)
	if basis == FIELD_PACE_BASIS:
		return (
			"Tyre wear is measured as this car's pace relative to the field's median "
			"lap, taken from this session. Fuel burn and track evolution move the "
			"whole field together, so measuring against it leaves tyre age as the "
			"difference specific to this car."
		)
	return (
		"The field's median lap does not cover enough of this car's stints, so wear "
		"is measured after removing the fuel effect alone. "
		f"{estimate_fuel_effect(stints).assumption} Track evolution is not separated "
		"on this basis, so the resulting rate is a lower bound."
	)
