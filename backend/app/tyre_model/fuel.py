"""Separating fuel effect from tyre effect (the PRD 13.1 next modelling step).

A race stint gets faster as fuel burns off and slower as the tyre wears. In raw
lap times these two run in opposite directions and the fuel gain usually wins, so
a degradation detector reading raw laps sees a stint that is getting *quicker*
and reports no cliff. That is the documented Canada miss in PRD 13.1.

Within a single stint the two effects cannot be told apart - lap number and tyre
age advance together, differing only by a constant. Across stints they can: a
second stint restarts tyre age at one while lap number keeps climbing, so at the
same tyre age a later stint carries less fuel.

That identification only survives if the fit does not absorb it. A per-stint
intercept would do exactly that - it would soak up each stint's fuel level and
leave the lap-number column an exact combination of the others. So the design
carries one intercept per *compound* (compounds have genuinely different pace),
plus one shared fuel coefficient on lap number and one shared degradation
coefficient on tyre age.

That identification succeeds on some races and not others - a race whose stints
are all the same length, or run in changing weather, will not separate the two
effects, and this module says so rather than reporting a number it did not earn.

Where it fails, a nominal era figure stands in, exactly as a nominal pit-lane
loss stands in for a car that never stopped. The distinction is carried on the
``measured`` flag and repeated in the assumption text, so a correction that was
assumed is never presented as one that was measured.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.tyre_model.models import StintObservation

# Stints needed before lap number and tyre age are separable at all.
MIN_STINTS_FOR_IDENTIFICATION = 2
# Usable green laps required across those stints for a stable solve.
MIN_LAPS_FOR_IDENTIFICATION = 20
# A fuel effect outside this range is not physically plausible for an F1 car and
# indicates the solve latched onto something else (weather, damage, traffic).
PLAUSIBLE_FUEL_SECONDS_PER_LAP = (0.01, 0.20)


# When a race's stint structure will not identify the effect, this nominal figure
# is used instead and flagged as an assumption, never as a measurement. It is the
# standard arithmetic for this car era rather than a number picked to look right:
# roughly 100 kg of fuel burned over a race distance, at roughly 0.03 s per lap
# per 10 kg carried, spread across a typical ~55-lap race.
NOMINAL_FUEL_SECONDS_PER_LAP = 0.055


@dataclass(frozen=True)
class FuelEffect:
	"""Seconds per lap that the car gains purely from burning fuel.

	``measured`` is the field that matters for honesty. True means this race's own
	laps identified the effect; False means the nominal figure above is standing
	in, and every consumer has to report it as an assumption.
	"""

	supported: bool
	reason: str
	measured: bool = False
	seconds_per_lap: float | None = None
	degradation_seconds_per_lap: float | None = None
	r_squared: float | None = None
	stints_used: int = 0
	laps_used: int = 0

	@property
	def assumption(self) -> str:
		if self.seconds_per_lap is None:
			return "No fuel-burn correction was applied."
		if self.measured:
			return (
				f"Fuel burn worth {self.seconds_per_lap:.3f}s per lap, solved from this race's own "
				f"laps across {self.stints_used} stints, is removed before measuring tyre wear."
			)
		return (
			f"Fuel burn is assumed to be worth {self.seconds_per_lap:.3f}s per lap - a nominal "
			"figure for this car era, not a measurement from this race - and is removed before "
			"measuring tyre wear. Without it, fuel burn masks degradation in raw lap times."
		)


def nominal_fuel_effect(reason: str, *, stints: int = 0, laps: int = 0) -> FuelEffect:
	"""The stated fallback, used when a race cannot identify its own fuel effect."""
	return FuelEffect(
		supported=True,
		measured=False,
		reason=reason,
		seconds_per_lap=NOMINAL_FUEL_SECONDS_PER_LAP,
		stints_used=stints,
		laps_used=laps,
	)


def estimate_fuel_effect(stints: Sequence[StintObservation]) -> FuelEffect:
	"""Solve one driver's race for a shared fuel slope and degradation slope."""
	usable = [stint for stint in stints if len(stint.lap_times_seconds) >= 4]
	if len(usable) < MIN_STINTS_FOR_IDENTIFICATION:
		return nominal_fuel_effect(
			f"{len(usable)} usable stints; at least {MIN_STINTS_FOR_IDENTIFICATION} "
			"are required before fuel and tyre effects are separable.",
			stints=len(usable),
		)

	import numpy as np

	rows: list[list[float]] = []
	targets: list[float] = []
	stint_count = len(usable)
	compounds = sorted({stint.compound for stint in usable})
	for stint in usable:
		compound_index = compounds.index(stint.compound)
		for lap, age, lap_time in zip(stint.lap_numbers, stint.tyre_ages, stint.lap_times_seconds):
			if lap_time is None or lap_time <= 0:
				continue
			intercepts = [0.0] * len(compounds)
			intercepts[compound_index] = 1.0
			rows.append([*intercepts, float(lap), float(age)])
			targets.append(float(lap_time))

	if len(rows) < MIN_LAPS_FOR_IDENTIFICATION:
		return nominal_fuel_effect(
			f"{len(rows)} usable green laps; at least {MIN_LAPS_FOR_IDENTIFICATION} are required.",
			stints=stint_count,
			laps=len(rows),
		)

	design = np.asarray(rows, dtype=float)
	observed = np.asarray(targets, dtype=float)
	# Rank-deficient races (for example every stint the same length) fall out of
	# lstsq with an unusable solution rather than an exception, so the plausibility
	# check below is what actually rejects them.
	solution, _residuals, rank, _singular = np.linalg.lstsq(design, observed, rcond=None)
	if rank < design.shape[1]:
		return nominal_fuel_effect(
			"This race's stint structure does not separate lap number from tyre age.",
			stints=stint_count,
			laps=len(rows),
		)

	lap_coefficient = float(solution[-2])
	age_coefficient = float(solution[-1])
	fitted = design @ solution
	residual = float(np.sum((observed - fitted) ** 2))
	total = float(np.sum((observed - observed.mean()) ** 2))
	r_squared = 1.0 - residual / total if total > 0 else 0.0

	# Fuel burn makes the car quicker, so the lap-number coefficient must be
	# negative and of a plausible size.
	gain_per_lap = -lap_coefficient
	low, high = PLAUSIBLE_FUEL_SECONDS_PER_LAP
	if not low <= gain_per_lap <= high:
		return nominal_fuel_effect(
			f"Solved fuel effect of {gain_per_lap:.3f}s/lap falls outside the plausible "
			f"{low}-{high}s/lap range, so the fit is not attributed to fuel.",
			stints=stint_count,
			laps=len(rows),
		)

	return FuelEffect(
		supported=True,
		measured=True,
		reason=(
			f"Shared fuel and degradation slopes solved across {stint_count} stints "
			f"of this driver's own race."
		),
		seconds_per_lap=round(gain_per_lap, 4),
		degradation_seconds_per_lap=round(age_coefficient, 4),
		r_squared=round(r_squared, 4),
		stints_used=stint_count,
		laps_used=len(rows),
	)


def fuel_correct(stint: StintObservation, effect: FuelEffect) -> StintObservation:
	"""Add the fuel gain back so only the tyre effect is left in the times.

	Later laps are corrected upward by the fuel the car is no longer carrying,
	which is what exposes wear that raw lap times hide. Whether the correction was
	measured or assumed travels with the effect, not with the corrected stint.
	"""
	if not effect.supported or effect.seconds_per_lap is None:
		return stint
	corrected = tuple(
		(lap_time + effect.seconds_per_lap * lap) if lap_time is not None and lap_time > 0 else lap_time
		for lap, lap_time in zip(stint.lap_numbers, stint.lap_times_seconds)
	)
	return StintObservation(
		compound=stint.compound,
		lap_numbers=stint.lap_numbers,
		tyre_ages=stint.tyre_ages,
		lap_times_seconds=corrected,
	)
