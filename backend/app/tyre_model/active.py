"""The degradation model the strategy engine actually uses (PRD 5.J).

The engine must not carry a hardcoded seconds-per-lap constant: the penalty for
an extra lap of tyre age is measured from the stint the car is actually on. This
module picks which of the two models does that measuring, based on the recorded
head-to-head comparison, and says plainly which one it picked and why.

When no stint is long enough to fit, the caller is told so - it does not silently
receive an invented rate.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Mapping, Sequence

from app.tyre_model.comparison import load_comparison_report
from app.tyre_model.fuel import FuelEffect, estimate_fuel_effect, fuel_correct
from app.tyre_model.field_pace import normalise_stints, normalisation_basis
from app.tyre_model.models import (
	DegradationFit,
	RegressionDegradationModel,
	StatisticalThresholdModel,
	StintObservation,
	build_stints,
)

_MODELS = {
	StatisticalThresholdModel.name: StatisticalThresholdModel,
	RegressionDegradationModel.name: RegressionDegradationModel,
}
# Incumbent per PRD 13.1 until a recorded comparison says otherwise.
_DEFAULT_MODEL_NAME = StatisticalThresholdModel.name


@dataclass(frozen=True)
class ActiveModelSelection:
	model_name: str
	source: str
	note: str


def active_model_selection() -> ActiveModelSelection:
	report = load_comparison_report()
	if not report:
		return ActiveModelSelection(
			_DEFAULT_MODEL_NAME,
			source="default",
			note=(
				"No recorded two-model comparison was found, so the incumbent "
				"median/MAD detector is in use. Run scripts.tyre_model_report to "
				"score both models against the validated race set."
			),
		)
	name = str(report.get("winning_model") or _DEFAULT_MODEL_NAME)
	if name not in _MODELS:
		name = _DEFAULT_MODEL_NAME
	return ActiveModelSelection(
		name,
		source="recorded_comparison",
		note=str(report.get("selection_note") or ""),
	)


def active_model():
	return _MODELS[active_model_selection().model_name]()


def fit_current_stint(
	*,
	lap_numbers: Sequence[int],
	compounds: Sequence[str | None],
	tyre_ages: Sequence[int | None],
	lap_times: Sequence[float | None],
	field_baseline: Mapping[int, float] | None = None,
) -> DegradationFit | None:
	"""Measure the car's current wear rate, widening the window only if needed.

	Early in a stint there are not yet enough laps to fit anything, but the car
	has usually already run laps this race that do support a fit. Rather than
	reporting nothing, the window widens in a stated order, and every step stays
	inside this same car's own real data:

		1. the stint the car is on now
		2. its most recent completed stint on the same compound
		3. its longest completed stint this race

	The fit that succeeds carries the step it came from in its ``reason``, so a
	rate measured from an earlier stint is never presented as a live measurement.
	Nothing fittable at any step returns None, and the caller reports the factor
	as unmeasured.
	"""
	raw_stints = build_stints(lap_numbers, compounds, tyre_ages, lap_times)
	if not raw_stints:
		return None

	stints, _basis = normalise_stints(raw_stints, field_baseline)
	model = active_model()
	current = stints[-1]
	fit = model.fit(current)
	if fit.supported:
		return fit

	earlier = stints[:-1]
	same_compound = [stint for stint in earlier if stint.compound == current.compound]
	candidates = [
		(same_compound[-1], "its most recent completed stint on this compound") if same_compound else None,
		(max(earlier, key=lambda stint: len(stint.lap_times_seconds)), "its longest completed stint this race")
		if earlier
		else None,
	]
	for candidate in candidates:
		if candidate is None:
			continue
		stint, description = candidate
		fallback = model.fit(stint)
		if fallback.supported:
			return replace(
				fallback,
				reason=(
					f"The current stint cannot support a fit, so the rate is measured from "
					f"{description} (laps {stint.lap_numbers[0]}-{stint.lap_numbers[-1]}). "
					f"{fallback.reason}"
				),
			)
	return fit


def fit_stint(stint: StintObservation) -> DegradationFit:
	return active_model().fit(stint)


def degradation_rate_or_none(fit: DegradationFit | None) -> float | None:
	"""The measured seconds-per-lap penalty, or None when nothing was measurable."""
	if fit is None or not fit.supported:
		return None
	return fit.degradation_rate_seconds_per_lap


def normalisation_note(
	*,
	lap_numbers: Sequence[int],
	compounds: Sequence[str | None],
	tyre_ages: Sequence[int | None],
	lap_times: Sequence[float | None],
	field_baseline: Mapping[int, float] | None = None,
) -> str:
	"""How this car's lap times were normalised before its wear was measured."""
	stints = build_stints(lap_numbers, compounds, tyre_ages, lap_times)
	return normalisation_basis(stints, field_baseline)
