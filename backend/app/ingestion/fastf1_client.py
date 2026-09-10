from __future__ import annotations

from typing import Any, Optional

from app.ingestion.normalizer import normalize_race
from app.schemas.race_state import RaceState


def load_historical_race(
	year: int,
	event_name: str,
	driver: str,
	session_name: str = "R",
	cache_dir: Optional[str] = None,
) -> RaceState:
	"""Load one driver's completed historical session through FastF1."""
	try:
		import fastf1
	except ImportError as exc:
		raise RuntimeError("FastF1 is required to load historical race data") from exc

	if cache_dir:
		fastf1.Cache.enable_cache(cache_dir)
	session = fastf1.get_session(year, event_name, session_name)
	session.load()
	laps = session.laps.pick_drivers(driver)
	lap_rows = laps.to_dict("records")

	pit_rows: list[dict[str, Any]] = []
	if "PitInTime" in laps.columns:
		for row in lap_rows:
			if row.get("PitInTime") is not None:
				pit_rows.append({"Lap": row.get("LapNumber"), "PitDuration": row.get("PitInTime")})

	total_laps = None
	if getattr(session, "total_laps", None) is not None:
		total_laps = int(session.total_laps)
	return normalize_race(
		year=year,
		event_name=event_name,
		session_name=session_name,
		driver=driver,
		lap_rows=lap_rows,
		pit_rows=pit_rows,
		total_laps=total_laps,
	)
