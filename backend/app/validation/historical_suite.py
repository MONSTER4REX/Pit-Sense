from __future__ import annotations

from dataclasses import dataclass
import asyncio
from time import perf_counter
from typing import Callable, Iterable

from app.engine.reoptimizer import optimize_strategy
from app.ingestion.normalizer import normalize_race
from app.replay.tick_stream import replay_ticks


@dataclass(frozen=True)
class ValidationResult:
    race_name: str
    recommendation_present: bool
    explainability_present: bool
    confidence_present: bool


@dataclass(frozen=True)
class RealRaceValidationResult:
    race_name: str
    year: int
    driver: str
    total_laps: int
    actual_pit_laps: tuple[int, ...]
    recommended_pit_lap: int
    directionally_consistent: bool
    tyre_cliff_results: tuple[dict[str, object], ...]
    shock_event_count: int
    max_reoptimization_seconds: float | None
    wet_or_intermediate_evidence: bool
    safety_car_or_vsc_evidence: bool
    data_gap_count: int
    replay_tick_count: int


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


def _seconds(value: object) -> float | None:
    if value is None:
        return None
    if hasattr(value, "total_seconds"):
        result = float(value.total_seconds())
        return result if result == result else None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result == result else None


def _actual_pit_laps(laps) -> tuple[int, ...]:
    previous_compound = None
    pit_laps: list[int] = []
    for _, row in laps.sort_values("LapNumber").iterrows():
        compound = row.get("Compound")
        lap_number = row.get("LapNumber")
        if compound is not None and compound == compound and previous_compound is not None and compound != previous_compound:
            pit_laps.append(int(lap_number))
        if compound is not None and compound == compound:
            previous_compound = compound
    return tuple(pit_laps)


def _cliff_for_stint(laps) -> dict[str, object]:
    clean_times = [_seconds(value) for value in laps["LapTime"].tolist()]
    clean_times = [value for value in clean_times if value is not None]
    if len(clean_times) < 5:
        return {"stint_start": int(laps["LapNumber"].min()), "actual_lap": None, "within_two_laps": False}
    baseline = sorted(clean_times)[len(clean_times) // 2]
    deviations = [abs(value - baseline) for value in clean_times]
    mad = sorted(deviations)[len(deviations) // 2]
    threshold = baseline + max(3.0 * mad, baseline * 0.03)
    actual_lap = None
    for index in range(2, len(clean_times)):
        if all(value >= threshold for value in clean_times[index - 2:index + 1]):
            actual_lap = int(laps.iloc[index]["LapNumber"])
            break
    return {
        "stint_start": int(laps["LapNumber"].min()),
        "actual_lap": actual_lap,
        "within_two_laps": actual_lap is not None,
    }


def _contiguous_stints(laps) -> list:
    stints = []
    current_rows = []
    current_compound = None
    for _, row in laps.sort_values("LapNumber").iterrows():
        compound = row.get("Compound")
        if current_rows and compound != current_compound:
            stints.append(laps.loc[[item.name for item in current_rows]])
            current_rows = []
        current_compound = compound
        current_rows.append(row)
    if current_rows:
        stints.append(laps.loc[[item.name for item in current_rows]])
    return stints


def _event_text(messages) -> list[str]:
    values: list[str] = []
    for _, row in messages.iterrows():
        values.append(" ".join(str(row.get(column, "")) for column in ("Category", "Message")).lower())
    return values


async def _replay_race(lap_times: list[float | None]) -> int:
    tick_count = 0
    async for _ in replay_ticks(lap_times, speed=5.0):
        tick_count += 1
    return tick_count


def run_real_race_suite(
    races: Iterable[tuple[int, str]],
    *,
    cache_dir: str,
) -> list[RealRaceValidationResult]:
    """Run Section 9 measurements against completed FastF1 Race sessions."""
    try:
        import fastf1
    except ImportError as exc:
        raise RuntimeError("FastF1 must be installed for real-race validation") from exc

    fastf1.Cache.enable_cache(cache_dir)
    results: list[RealRaceValidationResult] = []
    for year, event_name in races:
        session = fastf1.get_session(year, event_name, "R")
        session.load(telemetry=False, weather=False, messages=True)
        winner_row = session.results.loc[session.results["Position"] == 1].iloc[0]
        driver = str(winner_row["Abbreviation"])
        laps = session.laps.pick_drivers(driver).sort_values("LapNumber")
        lap_rows = laps.to_dict("records")
        race = normalize_race(
            year=year,
            event_name=event_name,
            session_name="R",
            driver=driver,
            lap_rows=lap_rows,
            total_laps=int(session.total_laps),
        )
        usable_times = [_seconds(value) for value in laps["LapTime"].tolist()]
        model_times = [value for value in usable_times if value is not None]
        replay_tick_count = asyncio.run(_replay_race(usable_times))
        recommendation = optimize_strategy(
            start_lap=1,
            end_lap=int(session.total_laps),
            current_compound=str(laps.iloc[0].get("Compound") or "MEDIUM"),
            current_tyre_age=0,
            lap_time_seconds=model_times,
        )
        actual_pits = _actual_pit_laps(laps)
        nearest_actual = min(actual_pits, key=lambda lap: abs(lap - recommendation.pit_lap), default=None)
        control_messages = session.race_control_messages
        event_text = _event_text(control_messages)
        wet_evidence = any("wet" in text or "rain" in text for text in event_text) or any(
            str(compound).upper() in {"INTERMEDIATE", "WET"} for compound in laps["Compound"].dropna()
        )
        shock_evidence = [
            text for text in event_text if any(token in text for token in ("safety car", "virtual safety", "vsc"))
        ]
        shock_latencies: list[float] = []
        for text in shock_evidence:
            started = perf_counter()
            optimize_strategy(
                start_lap=1,
                end_lap=int(session.total_laps),
                current_compound=str(laps.iloc[0].get("Compound") or "MEDIUM"),
                current_tyre_age=0,
                lap_time_seconds=model_times,
                uncertainty_events=("safety_car",) if "safety" in text or "vsc" in text else (),
            )
            shock_latencies.append(perf_counter() - started)
        stints = _contiguous_stints(laps)
        cliff_results = tuple(_cliff_for_stint(stint) for stint in stints)
        for result in cliff_results:
            if result["actual_lap"] is not None:
                predicted = recommendation.pit_lap
                result["predicted_lap"] = predicted
                result["within_two_laps"] = abs(int(result["actual_lap"]) - predicted) <= 2
        results.append(
            RealRaceValidationResult(
                race_name=event_name,
                year=year,
                driver=driver,
                total_laps=int(session.total_laps),
                actual_pit_laps=actual_pits,
                recommended_pit_lap=recommendation.pit_lap,
                directionally_consistent=nearest_actual is not None and abs(nearest_actual - recommendation.pit_lap) <= max(2, int(session.total_laps * 0.12)),
                tyre_cliff_results=cliff_results,
                shock_event_count=len(shock_evidence),
                max_reoptimization_seconds=max(shock_latencies, default=None),
                wet_or_intermediate_evidence=wet_evidence,
                safety_car_or_vsc_evidence=bool(shock_evidence),
                data_gap_count=len(race.data_gaps),
                replay_tick_count=replay_tick_count,
            )
        )
    return results