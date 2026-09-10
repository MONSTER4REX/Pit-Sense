from datetime import datetime, timezone

from app.ingestion.normalizer import normalize_race
from app.ingestion.validator import validate_race_state
from app.schemas.race_state import RaceState


def test_normalizer_preserves_missing_values_and_flags_gaps() -> None:
	race = normalize_race(
		year=2024,
		event_name="Test Grand Prix",
		session_name="R",
		driver="TEST",
		lap_rows=[
			{
				"LapNumber": 1,
				"LapTime": 90.5,
				"Compound": "MEDIUM",
				"Sector1Time": 30.0,
				"Sector2Time": 30.2,
				"Sector3Time": 30.3,
			},
			{"LapNumber": 2, "LapTime": None, "Compound": None},
		],
		total_laps=3,
	)

	assert race.laps[1].lap_time_seconds is None
	assert race.laps[1].compound is None
	assert any(g.field == "lap_time_seconds" and g.lap_number == 2 for g in race.data_gaps)
	assert any(g.field == "compound" and g.lap_number == 2 for g in race.data_gaps)
	assert len(validate_race_state(race)) >= 3


def test_schema_rejects_invalid_lap_values() -> None:
	try:
		RaceState(
			year=2024,
			event_name="Test Grand Prix",
			session_name="R",
			driver="TEST",
			loaded_at=datetime.now(timezone.utc),
			laps=[{"lap_number": 0}],
		)
	except ValueError:
		pass
	else:
		raise AssertionError("Invalid lap number must be rejected")
