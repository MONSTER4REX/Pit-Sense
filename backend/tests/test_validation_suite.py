from app.validation.historical_suite import (
	DIRECTIONAL_TOLERANCE_FRACTION,
	REOPTIMIZATION_BUDGET_SECONDS,
	SAMPLE_FRACTIONS,
	_sample_laps,
	_session_evidence,
)
from app.ingestion.normalizer import normalize_race


def test_sampled_laps_spread_across_the_race_and_stay_inside_it() -> None:
	"""The suite must probe several points in a race, not just one."""
	laps = _sample_laps(60)

	assert len(laps) >= 3
	assert laps == sorted(set(laps))
	assert all(2 <= lap < 60 for lap in laps)


def test_sampled_laps_degrade_gracefully_on_a_very_short_race() -> None:
	laps = _sample_laps(5)
	assert all(2 <= lap < 5 for lap in laps)


def test_session_evidence_reads_real_race_control_messages() -> None:
	race = normalize_race(
		year=2024,
		event_name="Test Grand Prix",
		session_name="R",
		driver="TST",
		total_laps=3,
		lap_rows=[
			{"LapNumber": 1, "LapTime": 90.0, "Compound": "MEDIUM"},
			{"LapNumber": 2, "LapTime": 90.0, "Compound": "INTERMEDIATE"},
			{"LapNumber": 3, "LapTime": 90.0, "Compound": "INTERMEDIATE"},
		],
	)
	safety_car, wet = _session_evidence(
		[{"message": "Race Control SAFETY CAR DEPLOYED"}], race
	)

	assert safety_car is True
	# Intermediates actually fitted are wet evidence on their own.
	assert wet is True


def test_session_evidence_reports_absence_rather_than_assuming_it() -> None:
	race = normalize_race(
		year=2024,
		event_name="Test Grand Prix",
		session_name="R",
		driver="TST",
		total_laps=2,
		lap_rows=[
			{"LapNumber": 1, "LapTime": 90.0, "Compound": "HARD"},
			{"LapNumber": 2, "LapTime": 90.0, "Compound": "HARD"},
		],
	)
	safety_car, wet = _session_evidence([{"message": "Race Control GREEN FLAG"}], race)

	assert safety_car is False
	assert wet is False


def test_prd_budgets_are_the_documented_ones() -> None:
	"""These constants are the PRD's targets; a silent change would make the
	suite report a pass against a moved goalpost."""
	assert REOPTIMIZATION_BUDGET_SECONDS == 1.0
	assert 0 < DIRECTIONAL_TOLERANCE_FRACTION <= 0.2
	assert len(SAMPLE_FRACTIONS) >= 3
