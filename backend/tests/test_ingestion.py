from datetime import datetime, timezone

from app.ingestion.normalizer import normalize_race
from app.ingestion.validator import validate_race_state
from app.schemas.race_state import RaceState
from app.ingestion.fastf1_client import _has_valid_time


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


def test_invalid_pit_timestamp_is_not_treated_as_a_pit_stop() -> None:
	assert _has_valid_time(None) is False
	assert _has_valid_time(float("nan")) is False
	assert _has_valid_time(22.0) is True


def test_fastf1_circuit_data_schema() -> None:
	from app.schemas.circuit import CircuitInfoData, CornerInfo, FastF1CircuitData

	data = FastF1CircuitData(
		year=2024,
		event_name="Bahrain Grand Prix",
		circuit_info=CircuitInfoData(
			corners=[CornerInfo(number=1, x=42.4, y=8329.2, angle=-246.6)],
			rotation=92.0,
		),
		x=[1.0, 2.0, 3.0],
		y=[4.0, 5.0, 6.0],
	)

	assert data.year == 2024
	assert len(data.circuit_info.corners) == 1
	assert data.circuit_info.corners[0].number == 1
	assert data.x == [1.0, 2.0, 3.0]

