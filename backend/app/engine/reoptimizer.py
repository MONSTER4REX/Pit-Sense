from __future__ import annotations

from app.confidence.risk_tier import score_undercut_risk_tier
from app.confidence.scorer import score_confidence
from app.engine.dijkstra import shortest_path
from app.engine.graph_builder import build_strategy_graph
from app.schemas.recommendation import StrategyRecommendation
from app.explainability.factor_breakdown import explain_path
from app.rival_model.cover_stop import cover_stop_probability
from app.rival_model.rejoin_traffic import calculate_traffic_penalty


def optimize_strategy(
    *,
    start_lap: int,
    end_lap: int,
    current_compound: str,
    current_tyre_age: int,
    lap_time_seconds: list[float],
    uncertainty_events: tuple[str, ...] = (),
    rival_cover_stop_probability: float = 0.0,
    observed_response_laps: tuple[int, ...] = (16, 17, 18, 19, 21),
) -> StrategyRecommendation:
    _, graph = build_strategy_graph(
        start_lap=start_lap,
        end_lap=end_lap,
        current_compound=current_compound,
        current_tyre_age=current_tyre_age,
        lap_time_seconds=lap_time_seconds,
    )
    start = next(node for node in graph if node.lap == start_lap)
    total, path = shortest_path(start, graph, end_lap)
    pit_edge = next((edge for edge in path if edge.action == "pit_now"), None)
    action = "pit_now" if pit_edge else "stay_out"
    pit_lap = pit_edge.source.lap if pit_edge else end_lap
    confidence = score_confidence(uncertainty_events=uncertainty_events)

    if rival_cover_stop_probability == 0.0:
        rival_cover_prob = cover_stop_probability(
            rival_tyre_age=current_tyre_age,
            observed_response_laps=list(observed_response_laps),
            pit_window_lap=pit_lap,
        )
    else:
        rival_cover_prob = rival_cover_stop_probability

    rejoin_traffic = calculate_traffic_penalty(
        lap_number=start_lap if action == "stay_out" else pit_lap,
    )

    return StrategyRecommendation(
        action=action,
        pit_lap=pit_lap,
        projected_total_time_seconds=total,
        undercut_risk_tier=score_undercut_risk_tier(
            rival_cover_stop_probability=rival_cover_prob,
            confidence=confidence,
        ),
        explainability=explain_path(path, rival_cover_prob, rejoin_traffic),
        confidence=confidence,
    )