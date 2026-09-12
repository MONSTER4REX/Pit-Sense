import pytest
import app.replay.fastf1_live as fastf1_live
from app.engine.reoptimizer import optimize_strategy
from app.rival_model.cover_stop import cover_stop_probability
from app.rival_model.rejoin_traffic import calculate_traffic_penalty
from app.replay.tick_stream import replay_ticks


def test_live_fastf1_enrichment_falls_back_when_session_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    def unavailable_session() -> object:
        raise RuntimeError("FastF1 cache is unavailable")

    monkeypatch.setattr(fastf1_live, "get_fastf1_session", unavailable_session)

    result = fastf1_live.extract_lap_dynamic_data(17)

    assert result["rival_tyre_age"] == 0
    assert result["gaps_to_ahead"] == []


def test_traffic_rejoin_risk_is_computed_and_nonzero() -> None:
    recommendation = optimize_strategy(
        start_lap=17,
        end_lap=44,
        current_compound="MEDIUM",
        current_tyre_age=12,
        lap_time_seconds=[92.0] * 30,
    )
    # Traffic risk in explainability breakdown must be computed and > 0
    assert recommendation.explainability.traffic_rejoin_risk > 0.0
    assert isinstance(recommendation.explainability.traffic_rejoin_risk, float)


def test_rival_cover_stop_probability_updates_with_tyre_age() -> None:
    prob_early = cover_stop_probability(
        rival_tyre_age=5,
        observed_response_laps=[16, 17, 18, 19, 21],
        pit_window_lap=18,
    )
    prob_late = cover_stop_probability(
        rival_tyre_age=20,
        observed_response_laps=[16, 17, 18, 19, 21],
        pit_window_lap=18,
    )
    # Older tyres increase rival cover-stop urgency
    assert prob_late > prob_early
    assert prob_early != 0.63 or prob_late != 0.63


@pytest.mark.asyncio
async def test_replay_tick_stream_emits_dynamic_traffic_and_rival_probability() -> None:
    ticks = [
        tick
        async for tick in replay_ticks(
            [92.0, 92.2, 92.5],
            speed=100.0,
            start_lap=17,
            start_tyre_age=12,
        )
    ]
    assert len(ticks) == 3
    # Check that ticks contain dynamic state calculations
    assert all(t.traffic_rejoin_risk > 0.0 for t in ticks)
    assert all(t.rival_cover_stop_probability > 0.0 for t in ticks)
    # Check tyre age advances per tick
    assert [t.tyre_age for t in ticks] == [12, 13, 14]
    # Check rival cover probability advances with tyre age
    assert ticks[2].rival_cover_stop_probability >= ticks[0].rival_cover_stop_probability
