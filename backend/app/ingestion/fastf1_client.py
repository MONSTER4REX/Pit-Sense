from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from app.ingestion.normalizer import normalize_race
from app.schemas.race_state import RaceState


DEFAULT_CACHE_DIR = Path(__file__).resolve().parents[3] / "data" / "fastf1"


def _has_valid_time(value: Any) -> bool:
	if value is None:
		return False
	try:
		seconds = float(value.total_seconds()) if hasattr(value, "total_seconds") else float(value)
	except (TypeError, ValueError):
		return False
	return seconds == seconds


@dataclass(frozen=True)
class HistoricalSession:
	p1: RaceState
	p2: RaceState
	historical_events: list[dict[str, str]]
	p1_name: str
	p1_team: str
	p2_name: str
	p2_team: str


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
			if _has_valid_time(row.get("PitInTime")):
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


def load_historical_session(
	year: int,
	event_name: str,
	session_name: str = "R",
	cache_dir: Optional[str] = None,
) -> HistoricalSession:
	"""Load the actual P1 and P2 trajectories for a race session."""
	try:
		import fastf1
	except ImportError as exc:
		raise RuntimeError("FastF1 is required to load historical sessions") from exc

	cache_path = Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR
	cache_path.mkdir(parents=True, exist_ok=True)
	fastf1.Cache.enable_cache(str(cache_path))
	session = fastf1.get_session(year, event_name, session_name)
	session.load(telemetry=False, weather=False, messages=True)
	results = session.results.sort_values("Position")
	finishers = results.dropna(subset=["Position"]).head(2)
	if len(finishers) < 2:
		raise ValueError("FastF1 session does not contain both P1 and P2 finishers")

	def load_driver(driver: str) -> RaceState:
		laps = session.laps.pick_drivers(driver)
		lap_rows = laps.to_dict("records")
		pit_rows = [
			{"Lap": row.get("LapNumber"), "PitDuration": row.get("PitInTime")}
			for row in lap_rows
			if _has_valid_time(row.get("PitInTime"))
		]
		return normalize_race(
			year=year,
			event_name=event_name,
			session_name=session_name,
			driver=driver,
			lap_rows=lap_rows,
			pit_rows=pit_rows,
			total_laps=int(session.total_laps) if session.total_laps is not None else None,
		)

	def result_text(row, field: str, fallback_field: str) -> str:
		value = row.get(field)
		if value is None or str(value).lower() == "nan":
			value = row.get(fallback_field)
		return str(value)

	events = [
		{"message": " ".join(str(row.get(column, "")) for column in ("Category", "Message")).strip()}
		for _, row in session.race_control_messages.iterrows()
	]
	return HistoricalSession(
		p1=load_driver(str(finishers.iloc[0]["Abbreviation"])),
		p2=load_driver(str(finishers.iloc[1]["Abbreviation"])),
		historical_events=events,
		p1_name=result_text(finishers.iloc[0], "FullName", "Abbreviation"),
		p1_team=result_text(finishers.iloc[0], "TeamName", "Team"),
		p2_name=result_text(finishers.iloc[1], "FullName", "Abbreviation"),
		p2_team=result_text(finishers.iloc[1], "TeamName", "Team"),
	)
