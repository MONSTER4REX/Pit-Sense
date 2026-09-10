from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Optional

from app.schemas.race_state import DataGap, LapState, PitStop, RaceState


def _value(row: Mapping[str, Any], *names: str) -> Any:
	for name in names:
		if name in row:
			return row[name]
	return None


def _seconds(value: Any) -> Optional[float]:
	if value is None:
		return None
	if hasattr(value, "total_seconds"):
		seconds = float(value.total_seconds())
		return None if seconds != seconds else seconds
	if isinstance(value, float) and value != value:
		return None
	seconds = float(value)
	return None if seconds != seconds else seconds


def _optional_int(value: Any) -> Optional[int]:
	if value is None:
		return None
	if isinstance(value, float) and value != value:
		return None
	return int(value)


def normalize_laps(rows: Iterable[Mapping[str, Any]]) -> tuple[list[LapState], list[DataGap]]:
	laps: list[LapState] = []
	gaps: list[DataGap] = []

	for raw_row in rows:
		lap_number = _optional_int(_value(raw_row, "LapNumber", "lap_number"))
		if lap_number is None:
			gaps.append(DataGap(field="lap_number", reason="Source row has no lap number"))
			continue

		lap_time = _seconds(_value(raw_row, "LapTime", "lap_time_seconds"))
		compound = _value(raw_row, "Compound", "compound")
		tyre_life = _optional_int(_value(raw_row, "TyreLife", "tyre_life"))
		position = _optional_int(_value(raw_row, "Position", "position"))
		gap = _seconds(_value(raw_row, "GapToLeader", "gap_to_leader_seconds"))
		sectors = {
			key: _seconds(_value(raw_row, key, f"{key}_seconds"))
			for key in ("Sector1Time", "Sector2Time", "Sector3Time")
		}

		if lap_time is None:
			gaps.append(DataGap(field="lap_time_seconds", lap_number=lap_number, reason="Lap time is missing"))
		if compound is None:
			gaps.append(DataGap(field="compound", lap_number=lap_number, reason="Tyre compound is missing"))
		for sector, value in sectors.items():
			if value is None:
				gaps.append(DataGap(field=sector, lap_number=lap_number, reason="Sector time is missing"))

		laps.append(
			LapState(
				lap_number=lap_number,
				lap_time_seconds=lap_time,
				compound=str(compound) if compound is not None else None,
				tyre_life=tyre_life,
				position=position,
				gap_to_leader_seconds=gap,
				sector_times_seconds=sectors,
			)
		)

	return laps, gaps


def normalize_race(
	*,
	year: int,
	event_name: str,
	session_name: str,
	driver: str,
	lap_rows: Iterable[Mapping[str, Any]],
	pit_rows: Iterable[Mapping[str, Any]] = (),
	total_laps: Optional[int] = None,
) -> RaceState:
	laps, data_gaps = normalize_laps(lap_rows)
	pit_stops: list[PitStop] = []
	for raw_row in pit_rows:
		lap_number = _optional_int(_value(raw_row, "Lap", "LapNumber", "lap_number"))
		if lap_number is None:
			data_gaps.append(DataGap(field="pit_stop.lap_number", reason="Pit-stop row has no lap number"))
			continue
		pit_stops.append(
			PitStop(
				lap_number=lap_number,
				duration_seconds=_seconds(_value(raw_row, "PitDuration", "duration_seconds")),
				compound_before=_value(raw_row, "CompoundBefore", "compound_before"),
				compound_after=_value(raw_row, "CompoundAfter", "compound_after"),
			)
		)

	return RaceState(
		year=year,
		event_name=event_name,
		session_name=session_name,
		driver=driver,
		total_laps=total_laps,
		loaded_at=datetime.now(timezone.utc),
		laps=laps,
		pit_stops=pit_stops,
		data_gaps=data_gaps,
	)
