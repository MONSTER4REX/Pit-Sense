"""Head-to-head scoring of the two tyre-degradation models (PRD 5.J / 13).

Ground truth is computed independently of both models so that neither is scored
against its own assumptions: the observed drop-off lap is the first lap whose
three-lap rolling mean sits, for two consecutive windows, above a threshold set
by the stint's own rolling-mean noise rather than by a fixed constant.

Known limitation, stated rather than corrected away: these are raw lap times. A
race stint gets faster as fuel burns off, which partly masks tyre degradation, so
a drop-off detected here is a lower bound on real wear. Separating fuel effect
from tyre effect is the next modelling step named in PRD 13.1, not something this
module pretends to have done.

The winning model is the one that gets closer to that observed drop-off across
the validated race set, and it is the model whose degradation rate feeds the
engine cost function (``app.tyre_model.active``). Both scores are always
reported - the losing model is not hidden.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import fmean, median
from typing import Iterable, Sequence

from app.tyre_model.models import (
	RegressionDegradationModel,
	StatisticalThresholdModel,
	StintObservation,
	fresh_phase_length,
)

# Floor on what counts as a drop-off, so timing noise alone cannot trip it.
MIN_DROP_OFF_SECONDS = 0.3
# Multiple of the stint's own rolling-mean MAD that defines its drop-off margin.
DROP_OFF_MAD_MULTIPLE = 2.0
# Consecutive rolling windows that must stay above the margin to confirm onset.
DROP_OFF_CONFIRMATION_WINDOWS = 2
ROLLING_WINDOW = 3
# PRD 13 success criterion: cliff prediction within +/- 2 laps of observed onset.
ACCURACY_TOLERANCE_LAPS = 2

# The comparison decides which model feeds the engine, so it has to travel with
# the code. It used to live only under docs/, which is outside the deployed image
# entirely - so a deployed instance silently fell back to the incumbent model and
# told the user to go and run a script. The packaged copy is the one the app
# reads; the docs copy is written alongside it for humans.
PACKAGED_REPORT_PATH = Path(__file__).resolve().parents[1] / "data" / "tyre_model_comparison.json"
DOCS_REPORT_PATH = Path(__file__).resolve().parents[3] / "docs" / "tyre_model_comparison.json"


@dataclass(frozen=True)
class StintScore:
	compound: str
	stint_start_lap: int
	observed_drop_off_lap: int | None
	predicted_cliff_lap: int | None
	absolute_error_laps: int | None
	within_tolerance: bool


@dataclass(frozen=True)
class ModelAccuracy:
	model_name: str
	stints_evaluated: int
	stints_supported: int
	scorable_stints: int
	hits_within_tolerance: int
	mean_absolute_error_laps: float | None
	stint_scores: tuple[StintScore, ...] = ()

	@property
	def hit_rate(self) -> float | None:
		if not self.scorable_stints:
			return None
		return round(self.hits_within_tolerance / self.scorable_stints, 4)


def observed_drop_off_lap(stint: StintObservation) -> int | None:
	"""Empirical cliff onset, derived without reference to either model."""
	pairs = [
		(lap, value)
		for lap, value in zip(stint.lap_numbers, stint.lap_times_seconds)
		if value is not None and value > 0
	]
	if len(pairs) < ROLLING_WINDOW * 2:
		return None

	rolling: list[tuple[int, float]] = []
	for index in range(len(pairs) - ROLLING_WINDOW + 1):
		window = pairs[index : index + ROLLING_WINDOW]
		rolling.append((window[-1][0], fmean(value for _lap, value in window)))

	means = [value for _lap, value in rolling]
	centre = median(means)
	noise = median([abs(value - centre) for value in means])
	# Reference is fresh-tyre pace, not the stint's outright best window: fuel
	# burn pushes the outright best toward the stint end, where anchoring there
	# would leave no laps to detect wear in.
	fresh_windows = fresh_phase_length(len(means))
	reference = min(means[:fresh_windows])
	threshold = reference + max(DROP_OFF_MAD_MULTIPLE * noise, MIN_DROP_OFF_SECONDS)

	for position in range(fresh_windows, len(rolling) - DROP_OFF_CONFIRMATION_WINDOWS + 1):
		window = rolling[position : position + DROP_OFF_CONFIRMATION_WINDOWS]
		if all(value >= threshold for _lap, value in window):
			return window[0][0]
	return None


def _score_model(model, stints: Sequence[StintObservation]) -> ModelAccuracy:
	scores: list[StintScore] = []
	supported = 0
	errors: list[int] = []
	hits = 0

	for stint in stints:
		fit = model.fit(stint)
		if fit.supported:
			supported += 1
		observed = observed_drop_off_lap(stint)
		predicted = fit.predicted_cliff_lap
		error = abs(observed - predicted) if observed is not None and predicted is not None else None
		within = error is not None and error <= ACCURACY_TOLERANCE_LAPS
		if error is not None:
			errors.append(error)
		if within:
			hits += 1
		scores.append(
			StintScore(
				compound=stint.compound,
				stint_start_lap=stint.lap_numbers[0],
				observed_drop_off_lap=observed,
				predicted_cliff_lap=predicted,
				absolute_error_laps=error,
				within_tolerance=within,
			)
		)

	return ModelAccuracy(
		model_name=model.name,
		stints_evaluated=len(stints),
		stints_supported=supported,
		scorable_stints=len(errors),
		hits_within_tolerance=hits,
		mean_absolute_error_laps=round(fmean(errors), 3) if errors else None,
		stint_scores=tuple(scores),
	)


def compare_models(stints: Iterable[StintObservation]) -> dict[str, object]:
	"""Score both models over the same stints and name the winner."""
	observations = list(stints)
	accuracies = [
		_score_model(StatisticalThresholdModel(), observations),
		_score_model(RegressionDegradationModel(), observations),
	]

	def rank(accuracy: ModelAccuracy) -> tuple[int, float, float]:
		# More hits first; then lower mean error; then more supported stints.
		return (
			-accuracy.hits_within_tolerance,
			accuracy.mean_absolute_error_laps if accuracy.mean_absolute_error_laps is not None else 1e9,
			-accuracy.stints_supported,
		)

	ranked = sorted(accuracies, key=rank)
	winner = ranked[0]
	decisive = ranked[0].scorable_stints > 0 and rank(ranked[0]) != rank(ranked[1])

	return {
		"stints_evaluated": len(observations),
		"tolerance_laps": ACCURACY_TOLERANCE_LAPS,
		"drop_off_definition": {
			"rolling_window_laps": ROLLING_WINDOW,
			"reference": "best rolling mean inside the stint's opening third (fresh-tyre pace)",
				"margin": "max(2.0 x rolling-mean MAD, 0.30s) above that reference",
			"confirmation_windows": DROP_OFF_CONFIRMATION_WINDOWS,
			"limitation": (
				"Raw lap times: fuel burn partly masks degradation, so a detected "
				"drop-off is a lower bound on real tyre wear."
			),
		},
		"models": [asdict(accuracy) | {"hit_rate": accuracy.hit_rate} for accuracy in accuracies],
		"winning_model": winner.model_name,
		"winner_is_decisive": decisive,
		"selection_criterion": (
			"Most correct calls in absolute terms, then lowest mean error. This "
			"favours a model that answers more often over one that answers rarely "
			"but precisely, because a model that declines to predict leaves the "
			"engine with no degradation input at all."
		),
		"selection_note": _selection_note(ranked, decisive),
	}


def _selection_note(ranked: Sequence[ModelAccuracy], decisive: bool) -> str:
	"""State what each model actually achieved, not just which one won.

	The two models trade coverage against precision, and reporting only the
	winner's headline would hide that. Both lines are always printed.
	"""
	if not decisive:
		return (
			"Neither model separated from the other on this stint set, so the "
			"statistical detector is retained as the incumbent and the tie is "
			"reported rather than resolved by preference."
		)

	lines = [
		(
			f"{accuracy.model_name}: {accuracy.hits_within_tolerance} correct of "
			f"{accuracy.scorable_stints} scorable stints"
			+ (
				f" ({accuracy.hit_rate * 100:.0f}%)"
				if accuracy.hit_rate is not None
				else ""
			)
			+ (
				f", mean error {accuracy.mean_absolute_error_laps} laps"
				if accuracy.mean_absolute_error_laps is not None
				else ", no scorable stints"
			)
		)
		for accuracy in ranked
	]
	return f"{ranked[0].model_name} selected. " + " | ".join(lines)


def load_comparison_report() -> dict[str, object] | None:
	"""Read the most recent recorded comparison, or None if none has been run."""
	for path in (PACKAGED_REPORT_PATH, DOCS_REPORT_PATH):
		if not path.exists():
			continue
		try:
			return json.loads(path.read_text(encoding="utf-8"))
		except (OSError, ValueError):
			continue
	return None


def save_comparison_report(report: dict[str, object]) -> Path:
	"""Write the report where the app reads it, and where a human reads it."""
	body = json.dumps(report, indent=2)
	for path in (PACKAGED_REPORT_PATH, DOCS_REPORT_PATH):
		path.parent.mkdir(parents=True, exist_ok=True)
		path.write_text(body, encoding="utf-8")
	return PACKAGED_REPORT_PATH
