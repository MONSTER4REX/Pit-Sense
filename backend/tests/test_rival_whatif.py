from app.rival_model.cover_stop import cover_stop_probability
from app.rival_model.rejoin_traffic import project_rejoin
from app.whatif.simulator import compare_branches


def test_rejoin_projection_flags_traffic() -> None:
    projection = project_rejoin(
        current_position=4,
        cars_ahead_gaps_seconds=[18.0, 22.0, 24.0],
        pit_lane_loss_seconds=21.0,
    )
    assert projection.into_traffic is True
    assert projection.projected_position == 5


def test_cover_stop_probability_uses_observed_response_pattern() -> None:
    probability = cover_stop_probability(
        rival_tyre_age=16,
        observed_response_laps=[17, 18, 19],
        pit_window_lap=17,
    )
    assert 0 < probability <= 1


def test_what_if_has_three_explained_branches() -> None:
    branches = compare_branches(
        current_lap=10,
        end_lap=20,
        current_compound="MEDIUM",
        current_tyre_age=6,
        lap_time_seconds=[90.0] * 20,
    )
    assert set(branches) == {"pit_now", "stay_out", "extend_stint"}
    assert all(branch.explainability is not None for branch in branches.values())