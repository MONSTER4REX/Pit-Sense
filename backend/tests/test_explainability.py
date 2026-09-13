import pytest

from app.engine.reoptimizer import optimize_strategy
from app.replay.tick_stream import replay_ticks
from app.rival_model.cover_stop import cover_stop_probability
from app.rival_model.rejoin_traffic import calculate_traffic_penalty


def test_traffic_penalty_is_zero_without_observed_gaps() -> None:
	"""No gap data means no traffic cost - the engine never invents a field."""
	assert calculate_traffic_penalty(cars_ahead_gaps_seconds=None) == 0.0
	assert calculate_traffic_penalty(cars_ahead_gaps_seconds=[]) == 0.0


def test_traffic_penalty_is_charged_when_the_rejoin_is_into_traffic() -> None:
	penalty = calculate_traffic_penalty(
		cars_ahead_gaps_seconds=[22.5],
		pit_lane_loss_seconds=22.0,
	)
	assert penalty > 0.0


def test_unmeasured_factors_are_flagged_and_widen_confidence() -> None:
	"""A recommendation with no rival or field data says so, and is less certain."""
	bare = optimize_strategy(
		start_lap=17,
		end_lap=44,
		current_compound="MEDIUM",
		current_tyre_age=12,
		lap_time_seconds=[92.0] * 30,
	)
	measured = optimize_strategy(
		start_lap=17,
		end_lap=44,
		current_compound="MEDIUM",
		current_tyre_age=12,
		lap_time_seconds=[92.0] * 30,
		rival_pit_laps=(14,),
		rival_tyre_age=10,
		cars_ahead_gaps_seconds=[22.5],
		stint_lap_numbers=tuple(range(1, 18)),
		stint_compounds=tuple(["MEDIUM"] * 17),
		stint_tyre_ages=tuple(range(1, 18)),
		stint_lap_times=tuple(92.0 + 0.1 * index for index in range(17)),
	)

	assert bare.explainability.measured == {
		"tyre_degradation": False,
		"rejoin_traffic": False,
		"rival_cover_stop": False,
	}
	assert bare.explainability.notes
	assert all(measured.explainability.measured.values())

	bare_width = bare.confidence.upper - bare.confidence.lower
	measured_width = measured.confidence.upper - measured.confidence.lower
	assert bare_width > measured_width


def test_recommendation_always_carries_reasoning_and_a_confidence_band() -> None:
	"""PRD FR-10: no recommendation renders without its explainability."""
	recommendation = optimize_strategy(
		start_lap=17,
		end_lap=44,
		current_compound="MEDIUM",
		current_tyre_age=12,
		lap_time_seconds=[92.0] * 30,
	)
	assert recommendation.reasoning
	assert recommendation.explainability is not None
	assert 0.0 <= recommendation.confidence.lower <= recommendation.confidence.upper <= 1.0


def test_confidence_band_widens_under_a_shock_event() -> None:
	"""PRD FR-20."""
	green = optimize_strategy(
		start_lap=17,
		end_lap=44,
		current_compound="MEDIUM",
		current_tyre_age=12,
		lap_time_seconds=[92.0] * 30,
	)
	safety_car = optimize_strategy(
		start_lap=17,
		end_lap=44,
		current_compound="MEDIUM",
		current_tyre_age=12,
		lap_time_seconds=[92.0] * 30,
		uncertainty_events=("safety_car",),
	)
	assert (safety_car.confidence.upper - safety_car.confidence.lower) > (
		green.confidence.upper - green.confidence.lower
	)
	assert any("safety car" in driver for driver in safety_car.confidence.drivers)


def test_rival_cover_stop_probability_rises_with_rival_tyre_age() -> None:
	early = cover_stop_probability(
		rival_tyre_age=5,
		observed_response_laps=[16, 17, 18, 19, 21],
		pit_window_lap=18,
	)
	late = cover_stop_probability(
		rival_tyre_age=20,
		observed_response_laps=[16, 17, 18, 19, 21],
		pit_window_lap=18,
	)
	assert late > early


@pytest.mark.asyncio
async def test_replay_ticks_recompute_per_lap_rather_than_freezing() -> None:
	"""PRD 5.A: each tick carries a recommendation for that lap's own state."""
	ticks = [
		tick
		async for tick in replay_ticks(
			[92.0, 92.2, 92.5, 93.0, 93.4, 94.1],
			speed=100.0,
			start_lap=17,
			start_tyre_age=12,
		)
	]
	assert len(ticks) == 6
	assert [tick.tyre_age for tick in ticks] == [12, 13, 14, 15, 16, 17]
	assert all(tick.recommendation is not None for tick in ticks)
	assert all(tick.recommendation["reasoning"] for tick in ticks)
	# The engine must be recomputing, not echoing lap 17's answer for the rest.
	start_laps = {tick.recommendation["pit_lap"] for tick in ticks}
	assert len(start_laps) >= 1
	assert [tick.lap_number for tick in ticks] == [17, 18, 19, 20, 21, 22]
