from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from app.ingestion.normalizer import normalize_race
from app.schemas.circuit import FastF1CircuitData, PitLaneGeometry
from app.schemas.race_state import RaceState


DEFAULT_CACHE_DIR = Path(__file__).resolve().parents[3] / "data" / "fastf1"

SUPPORTED_RACES = [
	{"year": 2024, "event": "Canadian Grand Prix"},
	{"year": 2023, "event": "Dutch Grand Prix"},
	{"year": 2024, "event": "Australian Grand Prix"},
	{"year": 2024, "event": "British Grand Prix"},
	{"year": 2024, "event": "Azerbaijan Grand Prix"},
]

# Positional samples needed before a racing line counts as usable.
MIN_TRACK_SAMPLES = 100

_geometry_flags: dict[str, tuple[bool, str]] = {}


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
	# Median green-lap time across the whole field, per lap number. Fuel burn,
	# track evolution, and weather hit every car on track at once, so they all
	# move this baseline together. Measuring a car against it leaves tyre age as
	# the difference that is actually specific to that car (see app.tyre_model).
	field_median_lap_times: dict[int, float] = field(default_factory=dict)



# Laps beyond this multiple of the field median for that lap are pit, damage, or
# incident laps and are excluded from the baseline.
FIELD_BASELINE_OUTLIER_MULTIPLE = 1.15
# Cars that must have a usable time on a lap before it gets a baseline at all.
MIN_CARS_FOR_FIELD_BASELINE = 6



def _leader_session_times(session) -> dict[int, float]:
	"""Session clock of the race leader at the end of each lap.

	FastF1 exposes no gap-to-leader column, but it does expose each lap's session
	time. The leader on a lap is whoever reached the end of it first, so the
	minimum session time across the field is the leader's, and every car's gap is
	its own session time minus that. This is measured, not modelled.
	"""
	leader: dict[int, float] = {}
	try:
		laps = session.laps
	except Exception:  # noqa: BLE001
		return leader
	for _, row in laps.iterrows():
		lap_number = row.get("LapNumber")
		stamp = row.get("Time")
		if lap_number is None or lap_number != lap_number or stamp is None:
			continue
		seconds = float(stamp.total_seconds()) if hasattr(stamp, "total_seconds") else None
		if seconds is None or seconds != seconds or seconds <= 0:
			continue
		key = int(lap_number)
		if key not in leader or seconds < leader[key]:
			leader[key] = seconds
	return leader


def _apply_gaps_to_leader(race: RaceState, leader: dict[int, float]) -> RaceState:
	"""Fill each lap's gap to the leader from real session timestamps.

	A lap with no leader time, or no time of its own, keeps a gap of None and is
	reported as unmeasured rather than being given a fabricated zero.
	"""
	for lap in race.laps:
		reference = leader.get(lap.lap_number)
		if reference is None or lap.session_time_seconds is None:
			continue
		lap.gap_to_leader_seconds = round(max(0.0, lap.session_time_seconds - reference), 3)
	return race


def _field_median_lap_times(session) -> dict[int, float]:
	"""Median green-lap time across the whole field, per lap number.

	This is the reference that separates tyre wear from everything else. Fuel
	burn, a rubbering-in track, and changing weather all act on every car at the
	same lap, so they move this baseline rather than showing up as one car's
	degradation. A lap the field cannot support gets no baseline, and callers
	fall back to the stated fuel correction instead.
	"""
	from statistics import median

	try:
		laps = session.laps
	except Exception:  # noqa: BLE001 - a session without laps simply has no baseline
		return {}

	by_lap: dict[int, list[float]] = {}
	for _, row in laps.iterrows():
		lap_number = row.get("LapNumber")
		lap_time = row.get("LapTime")
		if lap_number is None or lap_number != lap_number:
			continue
		seconds = float(lap_time.total_seconds()) if hasattr(lap_time, "total_seconds") else None
		if seconds is None or seconds != seconds or seconds <= 0:
			continue
		by_lap.setdefault(int(lap_number), []).append(seconds)

	baseline: dict[int, float] = {}
	for lap_number, times in by_lap.items():
		if len(times) < MIN_CARS_FOR_FIELD_BASELINE:
			continue
		rough = median(times)
		green = [value for value in times if value <= rough * FIELD_BASELINE_OUTLIER_MULTIPLE]
		if len(green) >= MIN_CARS_FOR_FIELD_BASELINE:
			baseline[lap_number] = round(median(green), 3)
	return baseline


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
	field_baseline = _field_median_lap_times(session)
	leader_times = _leader_session_times(session)
	return HistoricalSession(
		p1=_apply_gaps_to_leader(load_driver(str(finishers.iloc[0]["Abbreviation"])), leader_times),
		p2=_apply_gaps_to_leader(load_driver(str(finishers.iloc[1]["Abbreviation"])), leader_times),
		historical_events=events,
		p1_name=result_text(finishers.iloc[0], "FullName", "Abbreviation"),
		p1_team=result_text(finishers.iloc[0], "TeamName", "Team"),
		p2_name=result_text(finishers.iloc[1], "FullName", "Abbreviation"),
		p2_team=result_text(finishers.iloc[1], "TeamName", "Team"),
		field_median_lap_times=field_baseline,
	)


# Cars run the pit lane under a speed limiter. Sustained running below this
# speed on an in-lap or out-lap is the pit lane itself, and that is how the lane
# is located - from the car's real telemetry, not from a drawn path.
PIT_SPEED_LIMIT_KPH = 100.0
# Minimum samples before a low-speed run counts as the pit lane rather than a
# slow corner or a formation crawl.
MIN_PIT_LANE_SAMPLES = 15


def _trace_xy(lap) -> tuple[list[float], list[float], list[float]]:
	"""Positional and speed channels for one lap, or empty lists."""
	try:
		telemetry = lap.get_telemetry()
	except Exception:  # noqa: BLE001 - one unusable lap is not fatal
		return [], [], []
	if not {"X", "Y", "Speed"}.issubset(telemetry.columns):
		return [], [], []
	return (
		[float(value) for value in telemetry["X"].tolist()],
		[float(value) for value in telemetry["Y"].tolist()],
		[float(value) for value in telemetry["Speed"].tolist()],
	)


def _slowest_run(x: list[float], y: list[float], speed: list[float]) -> tuple[list[float], list[float]]:
	"""The longest run of consecutive samples below the pit speed limit."""
	best_start = best_length = 0
	current_start = current_length = 0
	for index, value in enumerate(speed):
		if value <= PIT_SPEED_LIMIT_KPH:
			if current_length == 0:
				current_start = index
			current_length += 1
			if current_length > best_length:
				best_start, best_length = current_start, current_length
		else:
			current_length = 0
	if best_length < MIN_PIT_LANE_SAMPLES:
		return [], []
	return x[best_start : best_start + best_length], y[best_start : best_start + best_length]


def load_pit_lane_geometry(session) -> PitLaneGeometry:
	"""Locate the pit lane from a real in-lap and out-lap in this session."""
	from app.schemas.circuit import PitLaneGeometry

	laps = session.laps
	in_laps = laps[laps["PitInTime"].notna()] if "PitInTime" in laps.columns else laps.iloc[0:0]
	out_laps = laps[laps["PitOutTime"].notna()] if "PitOutTime" in laps.columns else laps.iloc[0:0]

	entry_x = entry_y = lane_x = lane_y = exit_x = exit_y = []
	source_parts: list[str] = []

	for _, lap in in_laps.iterrows():
		x, y, speed = _trace_xy(lap)
		if not x:
			continue
		lane_x, lane_y = _slowest_run(x, y, speed)
		if lane_x:
			entry_x, entry_y = x, y
			source_parts.append(f"in-lap {int(lap['LapNumber'])} of car {lap['Driver']}")
			break

	for _, lap in out_laps.iterrows():
		x, y, speed = _trace_xy(lap)
		if not x:
			continue
		run_x, run_y = _slowest_run(x, y, speed)
		if run_x:
			exit_x, exit_y = x, y
			source_parts.append(f"out-lap {int(lap['LapNumber'])} of car {lap['Driver']}")
			if not lane_x:
				lane_x, lane_y = run_x, run_y
			break

	available = bool(entry_x and exit_x and lane_x)
	return PitLaneGeometry(
		available=available,
		source=(
			"Traced from " + " and ".join(source_parts)
			if available
			else "No usable in-lap and out-lap telemetry was found for this session."
		),
		entry_x=entry_x,
		entry_y=entry_y,
		lane_x=lane_x,
		lane_y=lane_y,
		exit_x=exit_x,
		exit_y=exit_y,
		speed_limit_kph=PIT_SPEED_LIMIT_KPH if available else None,
	)


def load_circuit_data(
	year: int,
	event_name: str,
	session_name: str = "R",
	cache_dir: Optional[str] = None,
) -> "FastF1CircuitData":
	"""Load the circuit's real racing line, corner markers, and pit-lane trace.

	Every coordinate returned comes from FastF1 positional telemetry for this
	session. Where a channel is missing the field comes back empty and the data
	reports itself as unverified - no circuit is ever drawn from assumption.
	"""
	try:
		import fastf1
	except ImportError as exc:
		raise RuntimeError("FastF1 is required to load circuit data") from exc

	from app.schemas.circuit import CircuitInfoData, CornerInfo, FastF1CircuitData

	cache_path = Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR
	cache_path.mkdir(parents=True, exist_ok=True)
	fastf1.Cache.enable_cache(str(cache_path))
	session = fastf1.get_session(year, event_name, session_name)
	session.load(telemetry=True, weather=False, messages=False)

	corners: list[CornerInfo] = []
	rotation = 0.0
	try:
		raw_info = session.get_circuit_info()
		rotation = float(getattr(raw_info, "rotation", 0.0))
		if getattr(raw_info, "corners", None) is not None:
			for _, row in raw_info.corners.iterrows():
				letter = row.get("Letter")
				angle = row.get("Angle")
				distance = row.get("Distance")
				corners.append(
					CornerInfo(
						number=int(row.get("Number", 0)),
						letter=str(letter) if letter and str(letter).lower() != "nan" else None,
						x=float(row.get("X", 0.0)),
						y=float(row.get("Y", 0.0)),
						angle=float(angle) if angle is not None and str(angle).lower() != "nan" else None,
						distance=float(distance) if distance is not None and str(distance).lower() != "nan" else None,
					)
				)
	except Exception:  # noqa: BLE001 - absent circuit info is reported, not fatal
		corners = []

	x_coords: list[float] = []
	y_coords: list[float] = []
	try:
		telemetry = session.laps.pick_fastest().get_telemetry()
		if {"X", "Y"}.issubset(telemetry.columns):
			x_coords = [float(value) for value in telemetry["X"].tolist()]
			y_coords = [float(value) for value in telemetry["Y"].tolist()]
	except Exception:  # noqa: BLE001
		x_coords, y_coords = [], []

	pit_lane = load_pit_lane_geometry(session)
	racing_line_ok = len(x_coords) >= MIN_TRACK_SAMPLES and len(x_coords) == len(y_coords)
	verified = racing_line_ok and pit_lane.available

	if verified:
		note = "Racing line and pit lane both traced from this session's telemetry."
	elif not racing_line_ok:
		note = "FastF1 exposes no usable positional telemetry for this session."
	else:
		note = pit_lane.source

	return FastF1CircuitData(
		year=year,
		event_name=event_name,
		circuit_info=CircuitInfoData(corners=corners, rotation=rotation),
		x=x_coords,
		y=y_coords,
		pit_lane=pit_lane,
		verified=verified,
		verification_note=note,
	)


# Verified-geometry results are expensive to compute (a full telemetry load per
# race) and never change for a completed session, so they are cached to disk.
GEOMETRY_CACHE_PATH = DEFAULT_CACHE_DIR.parent / "geometry_verification.json"


def _load_geometry_cache() -> dict[str, tuple[bool, str]]:
	global _geometry_flags
	if _geometry_flags:
		return _geometry_flags
	try:
		raw = json.loads(GEOMETRY_CACHE_PATH.read_text(encoding="utf-8"))
		_geometry_flags = {key: (bool(value[0]), str(value[1])) for key, value in raw.items()}
	except (OSError, ValueError, TypeError, IndexError):
		_geometry_flags = {}
	return _geometry_flags


def _save_geometry_cache() -> None:
	try:
		GEOMETRY_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
		GEOMETRY_CACHE_PATH.write_text(
			json.dumps({key: list(value) for key, value in _geometry_flags.items()}, indent=2),
			encoding="utf-8",
		)
	except OSError:
		# A cache that cannot be written is a performance problem, not a
		# correctness one - verification still ran and its result is returned.
		pass


def has_verified_geometry(
	year: int,
	event_name: str,
	session_name: str = "R",
	cache_dir: Optional[str] = None,
) -> tuple[bool, str]:
	"""Whether this race has a racing line AND a real pit lane, and why or why not.

	Verification requires both, because the Simulation Lab track has to show pit
	entry, the lane, and pit exit. A race that clears the racing-line check but
	has no traceable pit lane is not verified (PRD 5.G / 9.6).
	"""
	cache = _load_geometry_cache()
	key = f"{year}/{event_name}/{session_name}"
	if key in cache:
		return cache[key]
	try:
		data = load_circuit_data(year, event_name, session_name=session_name, cache_dir=cache_dir)
		result = (data.verified, data.verification_note)
	except Exception as exc:  # noqa: BLE001 - an unavailable session is reported, not raised
		result = (False, f"Circuit data could not be loaded for this session: {exc}")
	cache[key] = result
	_save_geometry_cache()
	return result


def list_race_availability(cache_dir: Optional[str] = None) -> list[dict[str, object]]:
	"""Two-tier availability (PRD 5.C / FR-21).

	``race_analysis_available`` and ``simulation_geometry_available`` are separate
	flags: a race can be fully usable in Race Analysis while the Simulation Lab
	has no verified track to draw for it.
	"""
	entries: list[dict[str, object]] = []
	for race in SUPPORTED_RACES:
		year = int(race["year"])
		event = str(race["event"])
		verified, note = has_verified_geometry(year, event, cache_dir=cache_dir)
		entries.append(
			{
				"year": year,
				"event": event,
				"race_analysis_available": True,
				"simulation_geometry_available": verified,
				"geometry_note": note,
			}
		)
	return entries
