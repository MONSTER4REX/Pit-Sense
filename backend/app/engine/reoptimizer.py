from __future__ import annotations

from app.confidence.risk_tier import score_undercut_risk_tier
from app.confidence.scorer import score_confidence
from app.engine.dijkstra import shortest_path
from app.engine.graph_builder import build_strategy_graph
from app.schemas.recommendation import StrategyRecommendation
from app.explainability.factor_breakdown import explain_path


def optimize_strategy(
    *,
    start_lap: int,
    end_lap: int,
    current_compound: str,
    current_tyre_age: int,
    lap_time_seconds: list[float],
    uncertainty_events: tuple[str, ...] = (),
    rival_cover_stop_probability: float = 0.0,
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
    return StrategyRecommendation(
        action=action,
        pit_lap=pit_lap,
        projected_total_time_seconds=total,
        undercut_risk_tier=score_undercut_risk_tier(
            rival_cover_stop_probability=rival_cover_stop_probability,
            confidence=confidence,
        ),
        explainability=explain_path(path, rival_cover_stop_probability),
        confidence=confidence,
    )