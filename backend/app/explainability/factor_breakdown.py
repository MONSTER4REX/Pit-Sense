from __future__ import annotations

from typing import Mapping, Sequence

from app.engine.graph_builder import StrategyEdge
from app.schemas.recommendation import ExplainabilityBreakdown


def explain_path(
	path: Sequence[StrategyEdge],
	rival_cover_stop_probability: float = 0.0,
	*,
	measured: Mapping[str, bool] | None = None,
	notes: Sequence[str] = (),
) -> ExplainabilityBreakdown:
	"""Sum the chosen path's edge factors into the four reported factors.

	Only the four factors PRD FR-8 names are produced. Nothing is added here that
	the graph did not actually charge to the path.
	"""
	return ExplainabilityBreakdown(
		tyre_delta_risk=round(sum(edge.factors.get("degradation", 0.0) for edge in path), 2),
		traffic_rejoin_risk=round(sum(edge.factors.get("traffic", 0.0) for edge in path), 2),
		rival_cover_stop_probability=round(rival_cover_stop_probability, 4),
		pit_lane_time_loss=round(sum(edge.factors.get("pit_lane_loss", 0.0) for edge in path), 2),
		measured=dict(measured or {}),
		notes=list(notes),
	)
