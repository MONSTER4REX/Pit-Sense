from app.validation.historical_suite import run_fixture_suite


def test_validation_suite_checks_five_loaded_race_fixtures() -> None:
    fixtures = {f"historical-race-{index}": [90.0] * 10 for index in range(1, 6)}
    results = run_fixture_suite(fixtures)

    assert len(results) == 5
    assert all(result.recommendation_present for result in results)
    assert all(result.explainability_present for result in results)
    assert all(result.confidence_present for result in results)