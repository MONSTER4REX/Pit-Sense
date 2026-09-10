from __future__ import annotations

from app.schemas.race_state import DataGap, RaceState


def validate_race_state(race: RaceState) -> list[DataGap]:
	"""Return source-quality findings without changing or filling the race state."""
	findings = list(race.data_gaps)
	seen_laps: set[int] = set()
	for lap in race.laps:
		if lap.lap_number in seen_laps:
			findings.append(DataGap(field="lap_number", lap_number=lap.lap_number, reason="Duplicate lap row"))
		seen_laps.add(lap.lap_number)

	if race.total_laps is not None:
		present = seen_laps
		for lap_number in range(1, race.total_laps + 1):
			if lap_number not in present:
				findings.append(DataGap(field="lap_row", lap_number=lap_number, reason="Lap is absent from source data"))
	return findings
