from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.engine.reoptimizer import optimize_strategy


@dataclass(frozen=True)
class ValidationResult:
    race_name: str
    recommendation_present: bool
    explainability_present: bool
    confidence_present: bool


def run_fixture_suite(fixtures: dict[str, list[float]], loader: Callable[[str, list[float]], None] | None = None) -> list[ValidationResult]:
    """Run contract checks over loaded historical fixtures; real FastF1 loading is injected by callers."""
    results: list[ValidationResult] = []
    for race_name, lap_times in fixtures.items():
        recommendation = optimize_strategy(
            start_lap=1,
            end_lap=max(2, len(lap_times)),
            current_compound="MEDIUM",
            current_tyre_age=1,
            lap_time_seconds=lap_times,
        )
        results.append(ValidationResult(race_name, True, recommendation.explainability is not None, recommendation.confidence is not None))
        if loader:
            loader(race_name, lap_times)
    return results