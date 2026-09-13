import pytest

from app.ingestion.normalizer import normalize_race
from app.replay.session_context import SessionReplayContext, lap_context
from app.replay.tick_stream import replay_session_ticks


def _race(driver: str, position: int, gap: float):
	return normalize_race(
		year=2024,
		event_name="Test Grand Prix",
		session_name="R",
		driver=driver,
		total_laps=5,
		lap_rows=[
			{
				"LapNumber": lap,
				"LapTime": 90.0 + lap / 10,
				"Compound": "MEDIUM",
				"TyreLife": lap,
				"Position": position,
				"GapToLeader": gap,
			}
			for lap in range(1, 6)
		],
	)


@pytest.mark.asyncio
async def test_session_replay_uses_loaded_lap_state_not_hardcoded_defaults() -> None:
	ctx = SessionReplayContext(p1=_race("P1DRV", 1, 0.0), p2=_race("P2DRV", 2, 4.0), end_lap=5)
	ticks = [tick async for tick in replay_session_ticks(ctx, speed=100.0, start_lap=1)]

	assert [tick.lap_number for tick in ticks] == [1, 2, 3, 4, 5]
	assert ticks[0].tyre_age == 1
	assert ticks[0].recommendation is not None
	assert ticks[0].recommendation["action"] in {"pit_now", "stay_out", "extend_stint"}


def test_lap_context_derives_rival_gap_from_session() -> None:
	ctx = SessionReplayContext(p1=_race("P1DRV", 1, 0.0), p2=_race("P2DRV", 2, 4.0), end_lap=5)
	context = lap_context(ctx, 3)

	assert context["compound"] == "MEDIUM"
	assert context["tyre_age"] == 3
	assert context["gaps_to_ahead"]
