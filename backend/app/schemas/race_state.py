from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class DataGap(BaseModel):
	"""An observed omission in source data; missing values are never inferred."""

	model_config = ConfigDict(extra="forbid")

	field: str
	lap_number: Optional[int] = Field(default=None, ge=1)
	reason: str


class LapState(BaseModel):
	model_config = ConfigDict(extra="forbid")

	lap_number: int = Field(ge=1)
	lap_time_seconds: Optional[float] = Field(default=None, gt=0)
	compound: Optional[str] = None
	tyre_life: Optional[int] = Field(default=None, ge=0)
	position: Optional[int] = Field(default=None, ge=1)
	# Session clock at the end of this lap. FastF1 provides this directly, and it
	# is what the gap below is computed from - FastF1 exposes no gap column.
	session_time_seconds: Optional[float] = Field(default=None, gt=0)
	gap_to_leader_seconds: Optional[float] = Field(default=None, ge=0)
	sector_times_seconds: Dict[str, Optional[float]] = Field(default_factory=dict)


class PitStop(BaseModel):
	model_config = ConfigDict(extra="forbid")

	lap_number: int = Field(ge=1)
	duration_seconds: Optional[float] = Field(default=None, gt=0)
	compound_before: Optional[str] = None
	compound_after: Optional[str] = None


class RaceState(BaseModel):
	model_config = ConfigDict(extra="forbid")

	year: int = Field(ge=1950)
	event_name: str = Field(min_length=1)
	session_name: str = Field(min_length=1)
	driver: str = Field(min_length=1)
	total_laps: Optional[int] = Field(default=None, ge=1)
	loaded_at: datetime
	source: str = "FastF1 historical replay"
	laps: List[LapState] = Field(default_factory=list)
	pit_stops: List[PitStop] = Field(default_factory=list)
	data_gaps: List[DataGap] = Field(default_factory=list)

	@property
	def complete_lap_count(self) -> int:
		return sum(lap.lap_time_seconds is not None for lap in self.laps)
