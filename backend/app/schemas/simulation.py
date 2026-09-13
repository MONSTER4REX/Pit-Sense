from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.recommendation import StrategyRecommendation


SimulationMode = Literal["HISTORICAL", "PROJECTED"]
CarRole = Literal["P1", "P2"]
ModelType = Literal["PITSENSE", "BASELINE"]
SimulationAction = Literal["PIT", "STAY_OUT", "EXTEND"]

# Exhaustive set of reasons a strategic recomputation is allowed to fire.
# A tick with no triggers must not carry new decisions (no timer-based recompute).
ReoptimizationTrigger = Literal[
	"SHOCK_EVENT",
	"USER_DECISION",
	"TARGET_LAP_REACHED",
	"P1_PIT",
	"P2_PIT",
	"TYRE_STATE_CHANGE",
	"TRAFFIC_CHANGE",
	"GAP_CHANGE",
	"OTHER_MATERIAL_EVENT",
]


class StrategyDecision(BaseModel):
	model_config = ConfigDict(extra="forbid")

	car: CarRole
	lap: int = Field(ge=1)
	action: SimulationAction
	target_lap: int = Field(ge=1)
	confidence: float | None = Field(default=None, ge=0, le=1)
	projected_time_cost: float = Field(ge=0)
	projected_position: int = Field(ge=1)
	explanation: str = Field(min_length=1)
	model_type: ModelType
	recommendation: StrategyRecommendation | None = None


class CarSimulationState(BaseModel):
	model_config = ConfigDict(extra="forbid")

	car: CarRole
	driver: str
	lap: int = Field(ge=1)
	mode: SimulationMode
	compound: str | None = None
	tyre_age: int = Field(ge=0)
	position: int = Field(ge=1)
	gap_to_leader_seconds: float = Field(ge=0)
	lap_time_seconds: float | None = Field(default=None, gt=0)
	pit_status: Literal["NONE", "PIT_IN", "PIT_STOP", "PIT_OUT"] = "NONE"


class SimulationTick(BaseModel):
	model_config = ConfigDict(extra="forbid")

	lap: int = Field(ge=1)
	session_id: str = Field(min_length=1)
	mode: SimulationMode
	scenario_id: str
	shock_event: str | None = None
	cars: list[CarSimulationState] = Field(min_length=2)
	decisions: list[StrategyDecision] = Field(default_factory=list)
	decision_lap: int | None = Field(default=None, ge=1)
	next_review_lap: int | None = Field(default=None, ge=1)
	triggers: list[ReoptimizationTrigger] = Field(default_factory=list)


class ReoptimizationRecord(BaseModel):
	model_config = ConfigDict(extra="forbid")

	lap: int = Field(ge=1)
	triggers: list[ReoptimizationTrigger] = Field(min_length=1)
	p1_decision: StrategyDecision
	p2_decision: StrategyDecision
	state_summary: dict[str, float | int | str | None]
	# Unique per computation, so the UI can prove a re-optimisation is genuinely
	# new rather than a relabelled earlier value (PRD FR-27).
	computation_id: str = Field(default="", max_length=32)
	reason: str = Field(default="", max_length=400)


class DecisionRecord(BaseModel):
	model_config = ConfigDict(extra="forbid")

	lap: int = Field(ge=1)
	action: SimulationAction
	model_type: Literal["USER_DECISION"] = "USER_DECISION"
	mode: Literal["PROJECTED"] = "PROJECTED"


class CounterfactualSummary(BaseModel):
	model_config = ConfigDict(extra="forbid")

	session_id: str = Field(min_length=1)
	historical_finish: dict[CarRole, int]
	pitsense_projected_finish: int = Field(ge=1)
	baseline_projected_finish: int = Field(ge=1)
	projected_finishing_gap_seconds: float = Field(ge=0)
	historical_finishing_gap_seconds: float = Field(default=0.0, ge=0)
	projected_advantage_seconds: float | None = None
	projected_gain_loss_vs_historical: int
	decision_history: list[DecisionRecord] = Field(default_factory=list)
	assumptions: list[str] = Field(min_length=1)
	historical_vs_projected: Literal["COUNTERFACTUAL_PROJECTION"] = "COUNTERFACTUAL_PROJECTION"
