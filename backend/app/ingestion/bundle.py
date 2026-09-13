"""Serving the validated races from the exported bundle (see
``scripts.export_race_bundle``).

A deployed instance should not depend on FastF1 at request time. FastF1 needs a
large on-disk cache, downloads heavily the first time it sees a session, and puts
an upstream API in the path of every demo. The bundle removes all three: it holds
the same values the ingestion path produces, written out once from the real data.

The bundle is preferred when it covers a race and FastF1 remains the fallback for
anything it does not, so a development machine keeps working exactly as before
and can still load races the bundle was never built for.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from app.ingestion.fastf1_client import HistoricalSession
from app.schemas.circuit import FastF1CircuitData
from app.schemas.race_state import RaceState

BUNDLE_DIR = Path(__file__).resolve().parents[1] / "data" / "races"


def _race_key(year: int, event: str) -> str:
	return f"{year}_{event.lower().replace(' ', '_')}"


@lru_cache(maxsize=1)
def bundle_index() -> tuple[dict[str, Any], ...]:
	"""Races the bundle covers, or an empty tuple when there is no bundle."""
	path = BUNDLE_DIR / "index.json"
	if not path.exists():
		return ()
	try:
		return tuple(json.loads(path.read_text(encoding="utf-8")))
	except (OSError, ValueError):
		return ()


def is_available() -> bool:
	return bool(bundle_index())


@lru_cache(maxsize=8)
def _load(key: str) -> Optional[dict[str, Any]]:
	path = BUNDLE_DIR / f"{key}.json"
	if not path.exists():
		return None
	try:
		return json.loads(path.read_text(encoding="utf-8"))
	except (OSError, ValueError):
		return None


def has_race(year: int, event: str) -> bool:
	return _load(_race_key(year, event)) is not None


def load_session(year: int, event: str) -> Optional[HistoricalSession]:
	"""The same HistoricalSession the FastF1 path builds, read from the bundle."""
	payload = _load(_race_key(year, event))
	if payload is None:
		return None

	return HistoricalSession(
		p1=RaceState.model_validate(payload["p1"]),
		p2=RaceState.model_validate(payload["p2"]),
		historical_events=list(payload.get("historical_events", [])),
		p1_name=str(payload["p1_name"]),
		p1_team=str(payload["p1_team"]),
		p2_name=str(payload["p2_name"]),
		p2_team=str(payload["p2_team"]),
		# JSON object keys are strings; lap numbers have to come back as ints or
		# every lookup against them silently misses.
		field_median_lap_times={
			int(lap): float(value)
			for lap, value in (payload.get("field_median_lap_times") or {}).items()
		},
	)


def load_circuit(year: int, event: str) -> Optional[FastF1CircuitData]:
	payload = _load(_race_key(year, event))
	if payload is None or "circuit" not in payload:
		return None
	return FastF1CircuitData.model_validate(payload["circuit"])


def availability() -> list[dict[str, object]]:
	"""Two-tier availability straight from the bundle, with no telemetry loads."""
	return [
		{
			"year": entry["year"],
			"event": entry["event"],
			"race_analysis_available": entry["race_analysis_available"],
			"simulation_geometry_available": entry["simulation_geometry_available"],
			"geometry_note": entry["geometry_note"],
		}
		for entry in bundle_index()
	]
