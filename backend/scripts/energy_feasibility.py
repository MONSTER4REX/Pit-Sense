"""PRD 5.K feasibility gate: does FastF1 expose usable energy / fuel / ERS data
for 2023-2024 race sessions? Run before building any energy UI.

	python -m scripts.energy_feasibility

Reports what the car telemetry channels actually contain. If a channel is absent
or constant, that is reported as a limitation - no energy model is invented.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ingestion.fastf1_client import DEFAULT_CACHE_DIR, SUPPORTED_RACES  # noqa: E402

# Channels that would be required to model energy deployment/recovery or fuel load.
CANDIDATE_CHANNELS = ("RPM", "Throttle", "Brake", "DRS", "nGear", "Speed")
ENERGY_CHANNELS = ("ERSDeployMode", "EnergyStore", "FuelLoad", "FuelRemaining", "BatteryCharge")


def _probe(year: int, event: str) -> dict[str, object]:
	import fastf1

	fastf1.Cache.enable_cache(str(DEFAULT_CACHE_DIR))
	session = fastf1.get_session(year, event, "R")
	session.load(telemetry=True, weather=False, messages=False)
	try:
		telemetry = session.laps.pick_fastest().get_car_data()
	except Exception as exc:  # noqa: BLE001
		return {"year": year, "event": event, "error": str(exc), "energy_channels_found": []}

	columns = list(telemetry.columns)
	return {
		"year": year,
		"event": event,
		"telemetry_columns": columns,
		"proxy_channels_found": [name for name in CANDIDATE_CHANNELS if name in columns],
		"energy_channels_found": [name for name in ENERGY_CHANNELS if name in columns],
	}


def main() -> int:
	reports = [_probe(int(race["year"]), str(race["event"])) for race in SUPPORTED_RACES]
	any_energy = any(report.get("energy_channels_found") for report in reports)
	verdict = (
		"AVAILABLE - energy channels present; a model may be built against them."
		if any_energy
		else (
			"UNAVAILABLE - FastF1 exposes no fuel, energy-store, or ERS-deployment channel "
			"for these 2023-2024 sessions. Per PRD 5.K this is reported as a limitation and "
			"no energy UI is built; nothing is fabricated."
		)
	)
	payload = {"verdict": verdict, "races": reports}
	out_path = Path(__file__).resolve().parents[2] / "docs" / "feasibility_energy.json"
	out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

	for report in reports:
		print(f"{report['year']} {report['event']}")
		print(f"  telemetry columns : {report.get('telemetry_columns')}")
		print(f"  energy channels   : {report.get('energy_channels_found') or 'NONE'}")
	print(f"\nVERDICT: {verdict}")
	print(f"Written to {out_path}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
