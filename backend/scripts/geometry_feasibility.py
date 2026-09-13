"""PRD 5.G feasibility gate: report, per race, what circuit and pit-lane geometry
FastF1 actually exposes. Run before any Simulation Lab track rendering work.

	python -m scripts.geometry_feasibility

Writes docs/feasibility_geometry.json and prints a plain-language table. Nothing
here infers or fabricates geometry: a field is reported as found only when it is
actually present in the session data.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ingestion.fastf1_client import DEFAULT_CACHE_DIR, SUPPORTED_RACES  # noqa: E402


def _probe(year: int, event: str) -> dict[str, object]:
	import fastf1

	fastf1.Cache.enable_cache(str(DEFAULT_CACHE_DIR))
	session = fastf1.get_session(year, event, "R")
	session.load(telemetry=True, weather=False, messages=False)

	report: dict[str, object] = {"year": year, "event": event}

	# 1. Circuit shape from fastest-lap positional telemetry.
	try:
		telemetry = session.laps.pick_fastest().get_telemetry()
		has_xy = "X" in telemetry.columns and "Y" in telemetry.columns
		report["track_xy_samples"] = int(len(telemetry)) if has_xy else 0
		report["track_xy_available"] = bool(has_xy and len(telemetry) >= 100)
	except Exception as exc:  # noqa: BLE001 - report the failure rather than hide it
		report["track_xy_samples"] = 0
		report["track_xy_available"] = False
		report["track_xy_error"] = str(exc)

	# 2. CircuitInfo (corner markers + rotation).
	try:
		info = session.get_circuit_info()
		report["corner_count"] = int(len(info.corners)) if info.corners is not None else 0
		report["rotation_degrees"] = float(info.rotation)
		report["circuit_info_available"] = report["corner_count"] > 0
	except Exception as exc:  # noqa: BLE001
		report["corner_count"] = 0
		report["circuit_info_available"] = False
		report["circuit_info_error"] = str(exc)

	# 3. Pit-lane geometry, derived only from laps FastF1 marks as pit in/out.
	#    A real in-lap's positional trace leaves the racing line at pit entry and
	#    rejoins at pit exit; that trace IS the pit lane. No synthetic path.
	pit_report: dict[str, object] = {"in_lap_traces": 0, "out_lap_traces": 0}
	try:
		laps = session.laps
		in_laps = laps[laps["PitInTime"].notna()]
		out_laps = laps[laps["PitOutTime"].notna()]
		for label, frame in (("in_lap_traces", in_laps), ("out_lap_traces", out_laps)):
			count = 0
			for _, lap in frame.iterrows():
				try:
					trace = lap.get_telemetry()
				except Exception:  # noqa: BLE001 - a single unusable lap is not fatal
					continue
				if "X" in trace.columns and len(trace) >= 100:
					count += 1
				if count >= 3:
					break
			pit_report[label] = count
		pit_report["pit_lane_available"] = bool(pit_report["in_lap_traces"] and pit_report["out_lap_traces"])
	except Exception as exc:  # noqa: BLE001
		pit_report["pit_lane_available"] = False
		pit_report["error"] = str(exc)
	report["pit_lane"] = pit_report

	report["verified_for_simulation_lab"] = bool(
		report.get("track_xy_available") and pit_report.get("pit_lane_available")
	)
	return report


def main() -> int:
	reports = [_probe(int(race["year"]), str(race["event"])) for race in SUPPORTED_RACES]
	out_path = Path(__file__).resolve().parents[2] / "docs" / "feasibility_geometry.json"
	out_path.write_text(json.dumps(reports, indent=2), encoding="utf-8")

	print(f"{'RACE':<34} {'TRACK X/Y':>12} {'CORNERS':>8} {'PIT IN':>7} {'PIT OUT':>8} {'VERIFIED':>9}")
	for report in reports:
		name = f"{report['year']} {report['event']}"
		pit = report["pit_lane"]
		print(
			f"{name:<34} {report['track_xy_samples']:>12} {report['corner_count']:>8} "
			f"{pit.get('in_lap_traces', 0):>7} {pit.get('out_lap_traces', 0):>8} "
			f"{str(report['verified_for_simulation_lab']):>9}"
		)
	print(f"\nWritten to {out_path}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
