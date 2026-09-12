from __future__ import annotations

from app.engine.graph_builder import StrategyEdge
from app.schemas.recommendation import ExplainabilityBreakdown


def explain_path(
    path: list[StrategyEdge],
    rival_cover_stop_probability: float = 0.0,
    rejoin_traffic_risk: float | None = None,
) -> ExplainabilityBreakdown:
    path_traffic = sum(edge.factors.get("traffic", 0.0) for edge in path)
    effective_traffic = path_traffic if path_traffic > 0 else (rejoin_traffic_risk or 0.0)
    return ExplainabilityBreakdown(
        tyre_delta_risk=round(sum(edge.factors.get("degradation", 0.0) for edge in path), 2),
        traffic_rejoin_risk=round(effective_traffic, 2),
        rival_cover_stop_probability=round(rival_cover_stop_probability, 4),
        pit_lane_time_loss=round(sum(edge.factors.get("pit_lane_loss", 0.0) for edge in path), 2),
    )