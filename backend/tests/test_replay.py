import pytest

from app.replay.tick_stream import replay_ticks


@pytest.mark.asyncio
async def test_replay_emits_laps_at_configured_speed() -> None:
    ticks = [tick async for tick in replay_ticks([90.0, None, 91.0], speed=5)]

    assert [tick.lap_number for tick in ticks] == [1, 2, 3]
    assert ticks[1].lap_time_seconds is None
    assert ticks[-1].timestamp_seconds == pytest.approx(36.2)
    assert ticks[0].recommendation is not None
    assert ticks[-1].recommendation is not None


@pytest.mark.asyncio
async def test_replay_rejects_invalid_speed() -> None:
    with pytest.raises(ValueError):
        async for _ in replay_ticks([90.0], speed=0):
            pass