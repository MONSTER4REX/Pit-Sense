from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class CornerInfo(BaseModel):
	model_config = ConfigDict(extra="forbid")

	number: int = Field(ge=1)
	letter: Optional[str] = None
	x: float
	y: float
	angle: Optional[float] = None
	distance: Optional[float] = None


class CircuitInfoData(BaseModel):
	model_config = ConfigDict(extra="forbid")

	corners: List[CornerInfo] = Field(default_factory=list)
	rotation: float = 0.0


class PitLaneGeometry(BaseModel):
	"""The pit lane as actually driven, taken from a real in-lap and out-lap.

	Nothing here is drawn by hand. ``entry`` is the positional trace of a car
	that really came in, ``exit_path`` the trace of one that really went out, and
	``lane`` the portion of those traces run under the pit speed limit. A race
	with no usable in-lap and out-lap has no pit lane, and the Simulation Lab
	shows its geometry-unavailable state rather than inventing one.
	"""

	model_config = ConfigDict(extra="forbid")

	available: bool = False
	source: str = ""
	entry_x: List[float] = Field(default_factory=list)
	entry_y: List[float] = Field(default_factory=list)
	lane_x: List[float] = Field(default_factory=list)
	lane_y: List[float] = Field(default_factory=list)
	exit_x: List[float] = Field(default_factory=list)
	exit_y: List[float] = Field(default_factory=list)
	speed_limit_kph: Optional[float] = None


class FastF1CircuitData(BaseModel):
	model_config = ConfigDict(extra="forbid")

	year: int = Field(ge=1950)
	event_name: str = Field(min_length=1)
	circuit_key: Optional[int] = None
	circuit_info: Optional[CircuitInfoData] = None
	x: List[float] = Field(default_factory=list)
	y: List[float] = Field(default_factory=list)
	pit_lane: Optional[PitLaneGeometry] = None
	# True only when both the racing line and a real pit lane are present.
	verified: bool = False
	verification_note: str = ""
