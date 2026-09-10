from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ExplainabilityBreakdown(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tyre_delta_risk: float = Field(ge=0)
    traffic_rejoin_risk: float = Field(ge=0)
    rival_cover_stop_probability: float = Field(ge=0, le=1)
    pit_lane_time_loss: float = Field(ge=0)


class ConfidenceBand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lower: float = Field(ge=0, le=1)
    upper: float = Field(ge=0, le=1)
    uncertainty: Literal["low", "medium", "high"]


class StrategyRecommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["pit_now", "stay_out", "extend_stint"]
    pit_lap: int = Field(ge=1)
    projected_total_time_seconds: float = Field(gt=0)
    explainability: ExplainabilityBreakdown
    confidence: ConfidenceBand
