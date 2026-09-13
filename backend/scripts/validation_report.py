"""Run the PRD section 13 validation suite and write its report.

	python -m scripts.validation_report

Writes docs/validation_report.json and prints the summary. Blocking criteria are
marked PASS/FAIL; reported-only criteria are printed with their real values
whether or not they meet target.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.validation.historical_suite import run_suite  # noqa: E402


def main() -> int:
	report = run_suite()
	out_path = Path(__file__).resolve().parents[2] / "docs" / "validation_report.json"
	out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

	print(f"Races validated: {report['races_validated']}\n")
	print(f"{'RACE':<32} {'DIRECTIONAL':>12} {'VARIES':>8} {'MAX REOPT':>10} {'CLIFF':>8} {'GAPS':>6}")
	for result in report["results"]:
		name = f"{result['year']} {result['event']}"
		cliff = f"{result['cliff_within_tolerance']}/{result['cliff_predictions']}"
		print(
			f"{name:<32} {str(result['directionally_consistent']):>12} "
			f"{str(result['recommendation_varies_across_laps']):>8} "
			f"{result['max_reoptimization_seconds']:>10} {cliff:>8} {result['data_gap_count']:>6}"
		)

	summary = report["summary"]
	print("\nBLOCKING CRITERIA")
	for label, key in (
		("Explainability on every recommendation", "explainability_on_every_recommendation"),
		("Confidence band on every recommendation", "confidence_on_every_recommendation"),
		("Recommendation updates per lap", "recommendation_updates_per_lap"),
		("Re-optimisation within the 1s budget", "reoptimization_within_budget"),
	):
		print(f"  {'PASS' if summary[key] else 'FAIL'}  {label}")

	print("\nREPORTED (not blocking)")
	print(f"  Directional pit-window agreement : {summary['directional_agreement']} (target 3/5)")
	print(f"  Tyre-cliff within +/-2 laps      : {summary['cliff_within_two_laps']}/{summary['cliff_predictions_scored']}")
	print(f"  Max re-optimisation              : {summary['max_reoptimization_seconds']}s")
	print(f"  Safety car / VSC evidence        : {summary['safety_car_evidence']}")
	print(f"  Wet / intermediate evidence      : {summary['wet_evidence']}")
	print(f"  Source data gaps flagged         : {summary['total_data_gaps_flagged']}")
	print(f"\nWritten to {out_path}")

	blocking_ok = all(
		summary[key]
		for key in (
			"explainability_on_every_recommendation",
			"confidence_on_every_recommendation",
			"recommendation_updates_per_lap",
			"reoptimization_within_budget",
		)
	)
	return 0 if blocking_ok else 1


if __name__ == "__main__":
	raise SystemExit(main())
