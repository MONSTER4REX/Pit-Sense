"""Forward race projection for both cars after the counterfactual fork (PRD 5.F).

Before the fork, both cars replay real recorded history. After it, neither car
can: the shock changed the environment for both, so replaying the opponent's real
future would be exactly as dishonest as ignoring the shock. Both cars are
therefore propagated forward by the same stated model.

The model is deliberately simple and every parameter is measured from real data:

	reference pace   that car's measured offset to the field's median lap,
	                 applied to the field's pace at the fork
	degradation      the active tyre model fitted to that car's own stint
	pit-lane loss    measured from that car's real in-lap and out-lap penalty
	race time        each car's real gap to the leader at the fork, advanced by
	                 its projected laps
	position         derived by comparing accumulated race times

No parameter here is tuned to make either car look better. The opponent uses the
same propagation as our car; the two differ only in which strategy drives them.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from statistics import median
from typing import Sequence

from app.schemas.race_state import RaceState
from app.tyre_model.active import active_model_selection, degradation_rate_or_none, fit_current_stint

# Laps whose time exceeds this multiple of a car's median lap are pit, safety-car,
# or incident laps, and are excluded from that car's clean-pace reference.
CLEAN_LAP_MULTIPLE = 1.10
# Fallback pit-lane loss, used only when a car made no measurable stop in the
# race. Reported as unmeasured wherever it is used.
NOMINAL_PIT_LANE_LOSS_SECONDS = 22.0
# A measured pit-lane loss outside this band is not a pit stop being measured -
# it is a lap contaminated by a red flag, damage, or a long delay in the box.
PLAUSIBLE_PIT_LANE_LOSS_SECONDS = (12.0, 35.0)
# Per-lap pace difference between two front-running cars that a projection can
# credibly carry all the way to the flag. A measured delta is capped at this and
# the cap is disclosed, because a raw delta of a second a lap - which two cars in
# different traffic and conditions can easily show over a sample of laps -
# compounds into a finishing gap of well over a minute, which no real race
# produces between the top two. Capping bounds the error; hiding it would not.
MAX_CREDIBLE_PACE_DELTA_SECONDS = 0.25
# Pit-lane loss while the field is neutralised (safety car or VSC).
NEUTRALISED_PIT_LANE_LOSS_SECONDS = 12.0
# Wet running multiplies a measured degradation rate.
RAIN_DEGRADATION_MULTIPLIER = 1.6
# A fresh set starts at age 1 on the lap after the stop.
FRESH_TYRE_AGE = 1
# A stint shorter than this was not a strategy call - it is a car stopping for
# rain, damage, or a red flag - and it does not describe how the car races.
MIN_CREDIBLE_STINT_LAPS = 8
# Outer limit on how long any set can be run. Past this a tyre is not "a little
# slower", it is finished, and no car completes a race distance on one set. A car
# reaching it must stop, whatever the compound rules say about the conditions.
MAX_TYRE_LIFE_LAPS = 40
# Absolute ceiling on the per-lap time a worn tyre can cost, matching the strategy
# graph's. It bounds a steep fitted rate without ever letting an older tyre cost
# less than a younger one.
MAX_DEGRADATION_PENALTY_SECONDS = 8.0


@dataclass(frozen=True)
class CarPaceModel:
	"""Everything measured about one car, and what could not be measured."""

	car: str
	driver: str
	reference_lap_seconds: float | None
	degradation_seconds_per_lap: float | None
	pit_lane_loss_seconds: float
	pit_loss_measured: bool
	degradation_model: str | None
	clean_laps_used: int
	typical_stint_laps: int | None
	# Oldest tyre age the degradation rate was actually fitted over. The rate is
	# not applied beyond it (see project_lap_time).
	max_fitted_tyre_age: int | None = None

	def assumptions(self) -> list[str]:
		lines: list[str] = []
		if self.reference_lap_seconds is not None:
			lines.append(
				f"{self.driver} projected pace {self.reference_lap_seconds:.2f}s, its measured "
				f"offset to the field's median lap over {self.clean_laps_used} clean green laps "
				"before the fork, applied to the field's pace at the fork."
			)
		else:
			lines.append(f"{self.driver} has no clean green laps before the fork; pace is not measurable.")
		if self.degradation_seconds_per_lap is not None:
			lines.append(
				f"{self.driver} loses {self.degradation_seconds_per_lap:.3f}s per lap of tyre age, "
				f"fitted by the {self.degradation_model} model to its own stint"
				+ (
					f", charged up to the {self.max_fitted_tyre_age}-lap tyre age that rate was "
					"measured over and not extrapolated beyond it."
					if self.max_fitted_tyre_age is not None
					else "."
				)
			)
		else:
			lines.append(f"{self.driver} stint is too short to fit a degradation rate; none is assumed.")
		if self.pit_loss_measured:
			lines.append(
				f"{self.driver} pit-lane loss {self.pit_lane_loss_seconds:.1f}s, measured from its own "
				"in-lap and out-lap penalty in this race."
			)
		else:
			lines.append(
				f"{self.driver} made no measurable stop in this race, so a nominal "
				f"{self.pit_lane_loss_seconds:.1f}s pit-lane loss is used and flagged as unmeasured."
			)
		return lines


@dataclass
class ProjectedCarState:
	car: str
	driver: str
	lap: int
	compound: str
	tyre_age: int
	lap_time_seconds: float | None
	cumulative_time_seconds: float
	position: int
	gap_to_leader_seconds: float
	pit_status: str = "NONE"
	pit_laps: list[int] = field(default_factory=list)


def _clean_lap_times(race: RaceState, up_to_lap: int) -> list[float]:
	times = [
		lap.lap_time_seconds
		for lap in race.laps
		if lap.lap_number <= up_to_lap and lap.lap_time_seconds is not None and lap.lap_time_seconds > 0
	]
	if not times:
		return []
	ceiling = median(times) * CLEAN_LAP_MULTIPLE
	return [value for value in times if value <= ceiling]


def measure_pit_lane_loss(
	race: RaceState,
	field_baseline: dict[int, float] | None = None,
) -> tuple[float, bool]:
	"""Measure a car's real pit-lane loss from its own stops.

	The loss is the excess of the in-lap and the following out-lap over what those
	laps should have taken. The comparison is against the field's median for the
	*same* laps where that is available: a stop taken under a safety car or in the
	wet would otherwise be scored against the car's dry green-flag median and come
	out at twice its true cost, because the whole field was slow on those laps too.

	A car with no usable stop returns the nominal figure and ``False``, so callers
	can report it as unmeasured. A measured loss outside the plausible band is
	also rejected rather than used.
	"""
	if not race.pit_stops:
		return NOMINAL_PIT_LANE_LOSS_SECONDS, False

	by_lap = {lap.lap_number: lap.lap_time_seconds for lap in race.laps}
	own_clean = _clean_lap_times(race, up_to_lap=10**6)
	own_reference = median(own_clean) if own_clean else None

	losses: list[float] = []
	for stop in race.pit_stops:
		in_lap = by_lap.get(stop.lap_number)
		out_lap = by_lap.get(stop.lap_number + 1)
		if in_lap is None or out_lap is None:
			continue
		in_reference = (field_baseline or {}).get(stop.lap_number, own_reference)
		out_reference = (field_baseline or {}).get(stop.lap_number + 1, own_reference)
		if in_reference is None or out_reference is None:
			continue
		excess = (in_lap - in_reference) + (out_lap - out_reference)
		low, high = PLAUSIBLE_PIT_LANE_LOSS_SECONDS
		if low <= excess <= high:
			losses.append(excess)

	if not losses:
		return NOMINAL_PIT_LANE_LOSS_SECONDS, False
	return round(median(losses), 2), True


def _typical_stint_laps(race: RaceState) -> int | None:
	"""How long a stint this car actually runs, in laps.

	Very short stints are not strategy - they are a car stopping for rain, damage,
	or under a red flag. Including them drags the median down hard: Verstappen's
	2023 Dutch race contains one- and two-lap stints, and taking the plain median
	of every stint returns five, which as a pit-window rule makes a car stop eleven
	times in a race. Only stints long enough to have been a deliberate stop count,
	and the answer is held inside a plausible range.
	"""
	stops = sorted(stop.lap_number for stop in race.pit_stops)
	if not stops:
		return None
	boundaries = [0, *stops, race.total_laps or stops[-1]]
	lengths = [later - earlier for earlier, later in zip(boundaries, boundaries[1:])]
	deliberate = [length for length in lengths if length >= MIN_CREDIBLE_STINT_LAPS]
	if not deliberate:
		return None
	return int(min(max(median(deliberate), MIN_CREDIBLE_STINT_LAPS), MAX_TYRE_LIFE_LAPS))


def bound_relative_pace(
	first: CarPaceModel, second: CarPaceModel
) -> tuple[CarPaceModel, CarPaceModel, str | None]:
	"""Cap the pace difference between the two projected cars.

	Returns both models and, when the cap bit, a plain-language note for the
	assumption trail so the cap is never applied silently.
	"""
	if first.reference_lap_seconds is None or second.reference_lap_seconds is None:
		return first, second, None

	delta = second.reference_lap_seconds - first.reference_lap_seconds
	if abs(delta) <= MAX_CREDIBLE_PACE_DELTA_SECONDS:
		return first, second, None

	midpoint = (first.reference_lap_seconds + second.reference_lap_seconds) / 2
	half = MAX_CREDIBLE_PACE_DELTA_SECONDS / 2
	direction = 1.0 if delta > 0 else -1.0
	note = (
		f"The measured pace difference between {first.driver} and {second.driver} over the "
		f"shared pre-fork laps was {abs(delta):.2f}s per lap. Carried to the flag that would "
		f"compound into a gap no real race produces between these two cars, so it is capped at "
		f"{MAX_CREDIBLE_PACE_DELTA_SECONDS:.2f}s per lap for the projection. The cap bounds the "
		"projected margin; it is a stated modelling choice, not a measurement."
	)
	return (
		replace(first, reference_lap_seconds=round(midpoint - direction * half, 3)),
		replace(second, reference_lap_seconds=round(midpoint + direction * half, 3)),
		note,
	)


def shared_clean_laps(first: RaceState, second: RaceState, fork_lap: int) -> set[int]:
	"""Laps before the fork on which both cars set a clean, comparable time.

	Comparing two cars over different laps measures the laps as much as the cars,
	so the projection only ever compares them where both were actually running.
	"""

	def clean(race: RaceState) -> set[int]:
		times = [
			lap.lap_time_seconds
			for lap in race.laps
			if lap.lap_number <= fork_lap and lap.lap_time_seconds is not None and lap.lap_time_seconds > 0
		]
		if not times:
			return set()
		ceiling = median(times) * CLEAN_LAP_MULTIPLE
		return {
			lap.lap_number
			for lap in race.laps
			if lap.lap_number <= fork_lap
			and lap.lap_time_seconds is not None
			and 0 < lap.lap_time_seconds <= ceiling
		}

	return clean(first) & clean(second)


def _reference_pace(
	race: RaceState,
	fork_lap: int,
	field_baseline: dict[int, float] | None,
	shared_laps: set[int] | None = None,
) -> tuple[float | None, int]:
	"""This car's projected lap pace, anchored to the field where possible.

	Taking each car's own median clean lap and projecting the difference forward
	compounds every circumstance that median happens to contain - traffic, a
	safety car stint, a lap in clear air - into a gap that grows without bound
	over a race distance. Two front-running cars end up tens of seconds apart,
	which is not a projection, it is an artefact.

	So pace is measured as each car's offset to the field's median lap over the
	same laps. That offset is the part genuinely specific to the car, and the
	field median at the fork is the shared reference both cars are projected from.
	"""
	clean_laps = [
		lap
		for lap in race.laps
		if lap.lap_number <= fork_lap and lap.lap_time_seconds is not None and lap.lap_time_seconds > 0
	]
	if not clean_laps:
		return None, 0

	ceiling = median([lap.lap_time_seconds for lap in clean_laps]) * CLEAN_LAP_MULTIPLE
	clean_laps = [lap for lap in clean_laps if lap.lap_time_seconds <= ceiling]
	if shared_laps:
		matched = [lap for lap in clean_laps if lap.lap_number in shared_laps]
		if matched:
			clean_laps = matched
	if not clean_laps:
		return None, 0

	if field_baseline:
		offsets = [
			lap.lap_time_seconds - field_baseline[lap.lap_number]
			for lap in clean_laps
			if lap.lap_number in field_baseline
		]
		anchors = [
			value for lap, value in field_baseline.items() if abs(lap - fork_lap) <= 5
		] or list(field_baseline.values())
		if offsets and anchors:
			return round(median(anchors) + median(offsets), 3), len(clean_laps)

	# No field baseline: fall back to this car's own median clean lap, which is
	# the weaker basis described above.
	return round(median([lap.lap_time_seconds for lap in clean_laps]), 3), len(clean_laps)


def build_pace_model(
	race: RaceState,
	car: str,
	fork_lap: int,
	field_baseline: dict[int, float] | None = None,
	shared_laps: set[int] | None = None,
) -> CarPaceModel:
	"""Measure one car's pace, wear, and pit loss from its own pre-fork race."""
	reference, clean_count = _reference_pace(race, fork_lap, field_baseline, shared_laps)
	history = [lap for lap in race.laps if lap.lap_number <= fork_lap]
	fit = fit_current_stint(
		lap_numbers=[lap.lap_number for lap in history],
		compounds=[lap.compound for lap in history],
		tyre_ages=[lap.tyre_life for lap in history],
		lap_times=[lap.lap_time_seconds for lap in history],
		field_baseline=field_baseline,
	)
	rate = degradation_rate_or_none(fit)
	fitted_ages = [lap.tyre_life for lap in history if lap.tyre_life is not None]
	pit_loss, pit_measured = measure_pit_lane_loss(race, field_baseline)

	return CarPaceModel(
		car=car,
		driver=race.driver,
		reference_lap_seconds=reference,
		degradation_seconds_per_lap=rate,
		pit_lane_loss_seconds=pit_loss,
		pit_loss_measured=pit_measured,
		degradation_model=active_model_selection().model_name if rate is not None else None,
		clean_laps_used=clean_count,
		typical_stint_laps=_typical_stint_laps(race),
		max_fitted_tyre_age=max(fitted_ages) if fitted_ages and rate is not None else None,
	)


def project_lap_time(
	model: CarPaceModel,
	*,
	tyre_age: int,
	pitting: bool,
	shock_event: str | None,
) -> float | None:
	"""One projected lap for one car under the stated model."""
	if model.reference_lap_seconds is None:
		return None

	lap_time = model.reference_lap_seconds
	if model.degradation_seconds_per_lap is not None:
		multiplier = RAIN_DEGRADATION_MULTIPLIER if shock_event == "rain" else 1.0
		# An old tyre must never stop costing more than a younger one. Holding the
		# charge at the oldest age observed made a fifty-lap-old set cost exactly
		# what a sixteen-lap-old one did, which let a car run a whole race without
		# stopping and pay nothing for it. The charge therefore keeps rising with
		# age, under an absolute ceiling that stops a steep fitted rate producing
		# lap times no car has ever run.
		penalty = model.degradation_seconds_per_lap * tyre_age * multiplier
		lap_time += min(penalty, MAX_DEGRADATION_PENALTY_SECONDS)
	if pitting:
		lap_time += (
			NEUTRALISED_PIT_LANE_LOSS_SECONDS
			if shock_event in {"safety_car", "vsc"}
			else model.pit_lane_loss_seconds
		)
	return round(lap_time, 3)


def elapsed_time_at(race: RaceState, lap_number: int) -> float:
	"""A car's race time at a lap, relative to the leader.

	The recorded gap to the leader is used rather than a sum of that car's lap
	times: a car missing even one lap row would otherwise appear to have spent
	less time on track than it really did, and would be projected to gain places
	it never gained. The gap is the measured relative race time, so both cars are
	placed in the same frame regardless of gaps in either car's lap data.
	"""
	row = next((lap for lap in race.laps if lap.lap_number == lap_number), None)
	if row is None or row.gap_to_leader_seconds is None:
		# Fall back to the most recent lap that does carry a gap.
		earlier = [
			lap
			for lap in race.laps
			if lap.lap_number <= lap_number and lap.gap_to_leader_seconds is not None
		]
		if not earlier:
			return 0.0
		row = earlier[-1]
	return round(float(row.gap_to_leader_seconds or 0.0), 3)


def rank_by_race_time(states: Sequence[ProjectedCarState]) -> None:
	"""Assign positions and gaps from accumulated race time, in place.

	Position is not asserted - it falls out of which car has spent less time on
	track, which is what actually decides a race.
	"""
	ordered = sorted(states, key=lambda state: state.cumulative_time_seconds)
	leader_time = ordered[0].cumulative_time_seconds if ordered else 0.0
	for index, state in enumerate(ordered, start=1):
		state.position = index
		state.gap_to_leader_seconds = round(max(0.0, state.cumulative_time_seconds - leader_time), 3)
