from __future__ import annotations

from app.engine.graph_builder import StrategyEdge
from app.schemas.recommendation import ExplainabilityBreakdown


def explain_path(path: list[StrategyEdge], rival_cover_stop_probability: float = 0.0) -> ExplainabilityBreakdown:
    return ExplainabilityBreakdown(
        tyre_delta_risk=sum(edge.factors.get("degradation", 0.0) for edge in path),
        traffic_rejoin_risk=sum(edge.factors.get("traffic", 0.0) for edge in path),
        rival_cover_stop_probability=rival_cover_stop_probability,
        pit_lane_time_loss=sum(edge.factors.get("pit_lane_loss", 0.0) for edge in path),
    )