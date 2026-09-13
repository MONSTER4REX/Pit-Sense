"""Two independent tyre-degradation models (PRD 5.J).

Both consume the same input - one contiguous stint of real lap times - and both
answer the same two questions:

	1. How much time does each additional lap of tyre age cost? (degradation rate)
	2. On which lap does the stint cross into the tyre cliff?    (cliff onset)

Model A (``StatisticalThresholdModel``) is the median/MAD hard-threshold detector
carried over from the original build and reported in PRD 13.1.
Model B (``RegressionDegradationModel``) is the candidate fix: a least-squares fit
of lap time against tyre age, with the cliff read off the fitted curve.

Neither model invents data. A stint too short to support a model returns a fit
with ``supported=False`` and a stated reason, and callers must handle that rather
than substitute a default rate.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median
from typing import Sequence

# A stint shorter than this cannot support either model's assumptions.
MIN_STINT_LAPS = 5
# Laps that must consecutively exceed the threshold before a cliff is declared.
CLIFF_CONFIRMATION_LAPS = 3
# Lap times beyond this multiple of the stint median are traffic, safety-car, or
# pit laps rather than degradation laps, and are excluded from every fit. The
# margin has to stay wide enough that genuine cliff laps survive the filter.
OUTLIER_MULTIPLE = 1.12
# Floor on the pace loss that counts as a cliff, so timing noise cannot trip it.
MIN_CLIFF_MARGIN_SECONDS = 0.5
# Multiple of each stint's own robust noise that sets its cliff margin.
CLIFF_NOISE_MULTIPLE = 3.0
# Degradation outside this band is not a tyre wearing out - it is a fit latching
# onto traffic, weather, or a curve extrapolated past the data that constrains it.
# A rate outside the band is reported as unsupported rather than used.
PLAUSIBLE_DEGRADATION_SECONDS_PER_LAP = (0.0, 0.40)  # exclusive lower bound
# Fraction of a stint treated as its fresh-tyre phase. The reference pace is the
# best lap inside that phase: degradation is measured as loss against a fresh
# tyre, not against the stint's outright best lap, which fuel burn pushes toward
# the end of the stint and which would hide wear rather than expose it.
FRESH_PHASE_FRACTION = 1 / 3


@dataclass(frozen=True)
class StintObservation:
	"""One contiguous run on a single set of tyres, from real session data."""

	compound: str
	lap_numbers: tuple[int, ...]
	tyre_ages: tuple[int, ...]
	lap_times_seconds: tuple[float, ...]

	def __post_init__(self) -> None:
		if not (len(self.lap_numbers) == len(self.tyre_ages) == len(self.lap_times_seconds)):
			raise ValueError("Stint lap numbers, tyre ages, and lap times must align")


@dataclass(frozen=True)
class DegradationFit:
	"""What a model concluded about one stint, including when it concluded nothing."""

	model_name: str
	compound: str
	supported: bool
	reason: str
	laps_used: int = 0
	baseline_lap_time_seconds: float | None = None
	degradation_rate_seconds_per_lap: float | None = None
	predicted_cliff_lap: int | None = None
	quality: dict[str, float] = field(default_factory=dict)



def _plausible_rate(rate: float) -> tuple[float | None, str | None]:
	"""The rate if it is a usable measurement, otherwise None and the reason why.

	A rate at or below zero is not a measurement of a tyre that does not wear. It
	means this stint's lap times, even after the fuel correction, do not show wear
	- a drying track, traffic, or a driver managing pace can all produce that. It
	is reported as not measured, which widens the confidence band, rather than as
	a confident zero that would quietly remove degradation from the cost function.
	"""
	low, high = PLAUSIBLE_DEGRADATION_SECONDS_PER_LAP
	if rate <= low:
		return None, (
			f"Fitted {rate:.3f}s/lap shows no net wear across this stint, so degradation "
			"is reported as not measurable here rather than as zero."
		)
	if rate > high:
		return None, (
			f"Fitted {rate:.3f}s/lap exceeds the plausible degradation band, which a curve "
			"extrapolated past its data can do; not used."
		)
	return round(rate, 4), None


def fresh_phase_length(sample_count: int) -> int:
	"""How many opening laps count as the fresh-tyre reference phase."""
	return max(1, int(sample_count * FRESH_PHASE_FRACTION))


def _clean(stint: StintObservation) -> tuple[list[int], list[int], list[float]]:
	"""Drop laps that are clearly not green-flag degradation laps.

	Outliers are removed rather than smoothed over: an excluded lap is excluded,
	never replaced with an interpolated value (PRD FR-3).
	"""
	times = [value for value in stint.lap_times_seconds if value is not None and value > 0]
	if not times:
		return [], [], []
	ceiling = median(times) * OUTLIER_MULTIPLE
	laps: list[int] = []
	ages: list[int] = []
	kept: list[float] = []
	for lap, age, value in zip(stint.lap_numbers, stint.tyre_ages, stint.lap_times_seconds):
		if value is None or value <= 0 or value > ceiling:
			continue
		laps.append(lap)
		ages.append(age)
		kept.append(value)
	return laps, ages, kept


class StatisticalThresholdModel:
	"""Median baseline plus MAD hard threshold - the PRD 13.1 detector."""

	name = "statistical_median_mad"

	def fit(self, stint: StintObservation) -> DegradationFit:
		laps, _ages, times = _clean(stint)
		if len(times) < MIN_STINT_LAPS:
			return DegradationFit(
				self.name,
				stint.compound,
				supported=False,
				reason=f"Stint has {len(times)} usable green laps; {MIN_STINT_LAPS} are required.",
				laps_used=len(times),
			)

		baseline = median(times)
		deviations = [abs(value - baseline) for value in times]
		mad = median(deviations)
		# The cliff is pace given away against this stint's own fresh-tyre pace, by
		# a margin scaled to its noise. A fixed percentage of lap time would be
		# unreachable at one circuit and trivial at another.
		fresh_laps = fresh_phase_length(len(times))
		reference = min(times[:fresh_laps])
		threshold = reference + max(CLIFF_NOISE_MULTIPLE * mad, MIN_CLIFF_MARGIN_SECONDS)

		cliff_lap: int | None = None
		for index in range(max(fresh_laps, CLIFF_CONFIRMATION_LAPS - 1), len(times)):
			window = times[index - CLIFF_CONFIRMATION_LAPS + 1 : index + 1]
			if all(value >= threshold for value in window):
				cliff_lap = laps[index - CLIFF_CONFIRMATION_LAPS + 1]
				break

		# Robust rate: the median successive lap-time delta across the stint.
		deltas = [later - earlier for earlier, later in zip(times, times[1:])]
		rate = median(deltas) if deltas else 0.0

		plausible, rejection = _plausible_rate(rate)
		return DegradationFit(
			self.name,
			stint.compound,
			supported=plausible is not None,
			reason=rejection or "Median baseline with MAD-derived hard threshold.",
			laps_used=len(times),
			baseline_lap_time_seconds=round(baseline, 3),
			degradation_rate_seconds_per_lap=plausible,
			predicted_cliff_lap=cliff_lap,
			quality={"mad_seconds": round(mad, 4), "threshold_seconds": round(threshold, 3)},
		)


class RegressionDegradationModel:
	"""Least-squares lap time against tyre age, with the cliff read off the fit.

	A quadratic term captures the accelerating wear that a flat threshold misses;
	the fitted slope at the end of the stint is the degradation rate.
	"""

	name = "regression_curve_fit"

	def fit(self, stint: StintObservation) -> DegradationFit:
		laps, ages, times = _clean(stint)
		if len(times) < MIN_STINT_LAPS:
			return DegradationFit(
				self.name,
				stint.compound,
				supported=False,
				reason=f"Stint has {len(times)} usable green laps; {MIN_STINT_LAPS} are required.",
				laps_used=len(times),
			)

		import numpy as np

		x = np.asarray(ages, dtype=float)
		y = np.asarray(times, dtype=float)
		# Quadratic where the stint is long enough to constrain three parameters,
		# linear otherwise. Never fit more parameters than the data supports.
		degree = 2 if len(times) >= 8 else 1
		coefficients = np.polyfit(x, y, degree)
		fitted = np.polyval(coefficients, x)
		residual = float(np.sum((y - fitted) ** 2))
		total = float(np.sum((y - y.mean()) ** 2))
		r_squared = 1.0 - residual / total if total > 0 else 0.0

		# Average slope across the observed age range, not the slope at the final
		# point: a quadratic's endpoint gradient swings wildly on a short or noisy
		# stint, and the average stays inside the data that constrains the fit.
		baseline = float(np.polyval(coefficients, x[0]))
		age_span = float(x[-1] - x[0])
		rate_at_end = (
			(float(np.polyval(coefficients, x[-1])) - baseline) / age_span if age_span > 0 else 0.0
		)

		# Cliff onset: the first lap past the fresh-tyre phase at which the fitted
		# curve has given away more than a noise-scaled margin. Reading the onset
		# off the fit rather than off raw laps is what separates this model from
		# the threshold detector - a smooth curve crosses before any single lap does.
		fitted_values = fitted.tolist()
		fresh_laps = fresh_phase_length(len(fitted_values))
		reference = min(fitted_values[:fresh_laps])
		cliff_threshold = reference + max(
			CLIFF_NOISE_MULTIPLE * float(np.std(y - fitted)), MIN_CLIFF_MARGIN_SECONDS
		)
		cliff_lap: int | None = None
		for lap, value in zip(laps[fresh_laps:], fitted_values[fresh_laps:]):
			if value >= cliff_threshold:
				cliff_lap = lap
				break

		plausible, rejection = _plausible_rate(rate_at_end)
		return DegradationFit(
			self.name,
			stint.compound,
			supported=plausible is not None,
			reason=rejection or f"Degree-{degree} least-squares fit of lap time against tyre age.",
			laps_used=len(times),
			baseline_lap_time_seconds=round(baseline, 3),
			degradation_rate_seconds_per_lap=plausible,
			predicted_cliff_lap=cliff_lap,
			quality={"r_squared": round(r_squared, 4), "degree": float(degree)},
		)


def build_stints(
	lap_numbers: Sequence[int],
	compounds: Sequence[str | None],
	tyre_ages: Sequence[int | None],
	lap_times: Sequence[float | None],
) -> list[StintObservation]:
	"""Split a driver's race into contiguous single-compound stints.

	A stint break is a compound change or a tyre-age reset, both of which are
	observed facts in the source data rather than inferences.
	"""
	stints: list[StintObservation] = []
	current: list[tuple[int, int, float]] = []
	current_compound: str | None = None
	previous_age: int | None = None

	def flush() -> None:
		if current_compound and len(current) >= 2:
			stints.append(
				StintObservation(
					compound=current_compound,
					lap_numbers=tuple(item[0] for item in current),
					tyre_ages=tuple(item[1] for item in current),
					lap_times_seconds=tuple(item[2] for item in current),
				)
			)

	for lap, compound, age, lap_time in zip(lap_numbers, compounds, tyre_ages, lap_times):
		if compound is None or age is None or lap_time is None or lap_time <= 0:
			continue
		age_reset = previous_age is not None and age < previous_age
		if current and (compound != current_compound or age_reset):
			flush()
			current = []
		current_compound = compound
		previous_age = age
		current.append((int(lap), int(age), float(lap_time)))
	flush()
	return stints
