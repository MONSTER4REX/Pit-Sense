"""PRD 5.J / 13: score both tyre-degradation models against the validated races.

	python -m scripts.tyre_model_report

Builds real stints for the P1 and P2 finishers of every supported race, scores
both models against an independently-derived observed drop-off lap, writes
docs/tyre_model_comparison.json, and prints both accuracies. The written report
is what app.tyre_model.active reads to decide which model feeds the engine.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ingestion.fastf1_client import DEFAULT_CACHE_DIR, SUPPORTED_RACES, load_historical_session  # noqa: E402
from app.schemas.race_state import RaceState  # noqa: E402
from app.tyre_model.comparison import compare_models, save_comparison_report  # noqa: E402
from app.tyre_model.field_pace import normalise_stints  # noqa: E402
from app.tyre_model.models import StintObservation, build_stints  # noqa: E402


def _stints_for(race: RaceState, field_baseline: dict[int, float]) -> list[StintObservation]:
	"""This car's stints, normalised the same way the live engine normalises them.

	Scoring the models on raw laps would score them on a different problem than
	the one they actually solve in production, where fuel burn and track evolution
	are already removed (app.tyre_model.field_pace).
	"""
	laps = sorted(race.laps, key=lambda lap: lap.lap_number)
	raw = build_stints(
		[lap.lap_number for lap in laps],
		[lap.compound for lap in laps],
		[lap.tyre_life for lap in laps],
		[lap.lap_time_seconds for lap in laps],
	)
	normalised, _basis = normalise_stints(raw, field_baseline)
	return normalised


def main() -> int:
	stints: list[StintObservation] = []
	for race in SUPPORTED_RACES:
		year, event = int(race["year"]), str(race["event"])
		session = load_historical_session(year, event, cache_dir=str(DEFAULT_CACHE_DIR))
		baseline = session.field_median_lap_times
		race_stints = _stints_for(session.p1, baseline) + _stints_for(session.p2, baseline)
		stints.extend(race_stints)
		print(f"{year} {event}: {len(race_stints)} stints from {session.p1.driver} and {session.p2.driver}")

	report = compare_models(stints)
	path = save_comparison_report(report)

	print(f"\nStints evaluated: {report['stints_evaluated']}")
	for model in report["models"]:
		print(
			f"  {model['model_name']:<26} supported {model['stints_supported']:>3}/{model['stints_evaluated']:<3} "
			f"scorable {model['scorable_stints']:>3}  within +/-2 laps {model['hits_within_tolerance']:>3}  "
			f"mean abs error {model['mean_absolute_error_laps']}"
		)
	print(f"\nWinning model : {report['winning_model']} (decisive: {report['winner_is_decisive']})")
	print(f"Selection note: {report['selection_note']}")
	print(f"Written to {path}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
