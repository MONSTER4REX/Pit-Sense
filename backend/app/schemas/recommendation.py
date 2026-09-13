from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class ExplainabilityBreakdown(BaseModel):
	"""The four real, currently-implemented factors - no more (PRD FR-8).

	``measured`` records, per factor, whether it came from actual session data.
	A factor that could not be measured is reported as unmeasured rather than
	rendered as a confident zero.
	"""

	model_config = ConfigDict(extra="forbid")

	tyre_delta_risk: float = Field(ge=0)
	traffic_rejoin_risk: float = Field(ge=0)
	rival_cover_stop_probability: float = Field(ge=0, le=1)
	pit_lane_time_loss: float = Field(ge=0)
	measured: Dict[str, bool] = Field(default_factory=dict)
	notes: List[str] = Field(default_factory=list)


class ConfidenceBand(BaseModel):
	model_config = ConfigDict(extra="forbid")

	lower: float = Field(ge=0, le=1)
	upper: float = Field(ge=0, le=1)
	uncertainty: Literal["low", "medium", "high"]
	drivers: List[str] = Field(default_factory=list)


class StrategyRecommendation(BaseModel):
	model_config = ConfigDict(extra="forbid")

	action: Literal["pit_now", "stay_out", "extend_stint"]
	pit_lap: int = Field(ge=1)
	projected_total_time_seconds: float = Field(gt=0)
	undercut_risk_tier: Literal["safe", "marginal", "optimal", "critical"] = "safe"
	explainability: ExplainabilityBreakdown
	confidence: ConfidenceBand
	# Plain-language reasoning generated from the factors above, so the UI never
	# has to author its own explanation for a decision it did not compute.
	reasoning: str = Field(default="", max_length=600)
	degradation_model: Optional[str] = None
	degradation_rate_seconds_per_lap: Optional[float] = Field(default=None, ge=0)
