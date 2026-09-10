from app.engine.reoptimizer import optimize_strategy


def test_optimizer_returns_explainability_and_confidence_together() -> None:
    recommendation = optimize_strategy(
        start_lap=1,
        end_lap=8,
        current_compound="MEDIUM",
        current_tyre_age=3,
        lap_time_seconds=[90.0] * 8,
        uncertainty_events=("rain",),
        rival_cover_stop_probability=0.4,
    )

    assert recommendation.explainability is not None
    assert recommendation.confidence is not None
    assert recommendation.explainability.rival_cover_stop_probability == 0.4
    assert recommendation.confidence.upper - recommendation.confidence.lower > 0.08