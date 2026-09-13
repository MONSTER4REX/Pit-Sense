"""Strategy graph construction (PRD FR-4 / FR-5).

Each node is a (lap, compound, tyre age) state; each edge is a decision whose
weight is the projected time cost of taking it. Edge weights carry the factor
breakdown that the explainability layer later reports, so every second charged to
a decision is traceable to a named cause.

Degradation cost is measured from the car's current stint by the active tyre
model (PRD 5.J), not from a fixed constant. When the stint cannot support a fit
the graph says so through ``measured_factors`` rather than substituting a guess.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from app.rival_model.rejoin_traffic import calculate_traffic_penalty

# Pit-lane loss when the field is running to a safety car or VSC. The gain is
# real - the pack is slowed, so the time given up entering the pits shrinks.
SAFETY_CAR_PIT_LOSS_SECONDS = 12.0
# Wet running multiplies the cost of an aged tyre. Applied to the measured rate,
# never used as a substitute for one.
RAIN_DEGRADATION_MULTIPLIER = 1.6
# Laps a set has to run before the car may stop again. Without this the graph can
# find a nonsensical path that pits on consecutive laps, which no car can do and
# no strategist would propose.
MIN_LAPS_BETWEEN_STOPS = 8


@dataclass(frozen=True)
class StrategyNode:
	lap: int
	compound: str
	tyre_age: int


@dataclass(frozen=True)
class StrategyEdge:
	source: StrategyNode
	target: StrategyNode
	action: str
	cost_seconds: float
	factors: dict[str, float]


@dataclass(frozen=True)
class GraphBuild:
	"""The graph plus an honest record of which inputs were actually measured."""

	nodes: set[StrategyNode]
	edges: dict[StrategyNode, list[StrategyEdge]]
	measured_factors: dict[str, bool] = field(default_factory=dict)
	notes: tuple[str, ...] = ()


def build_strategy_graph(
	*,
	start_lap: int,
	end_lap: int,
	current_compound: str,
	current_tyre_age: int,
	lap_time_seconds: Iterable[float],
	degradation_rate_seconds_per_lap: float | None = None,
	cars_ahead_gaps_seconds: list[float] | None = None,
	available_compounds: Iterable[str] = ("SOFT", "MEDIUM", "HARD"),
	pit_lane_loss_seconds: float = 22.0,
	uncertainty_events: Iterable[str] = (),
) -> GraphBuild:
	lap_times = list(lap_time_seconds)
	compounds = tuple(dict.fromkeys(available_compounds))
	events = {event.lower() for event in uncertainty_events}

	effective_pit_loss = (
		SAFETY_CAR_PIT_LOSS_SECONDS
		if ("safety_car" in events or "vsc" in events)
		else pit_lane_loss_seconds
	)
	deg_multiplier = RAIN_DEGRADATION_MULTIPLIER if "rain" in events else 1.0

	notes: list[str] = []
	degradation_measured = degradation_rate_seconds_per_lap is not None
	if degradation_measured:
		deg_rate = max(0.0, float(degradation_rate_seconds_per_lap)) * deg_multiplier
	else:
		# No fit means no degradation charge. A stay-out edge then costs only the
		# lap itself, and the recommendation is reported as resting on unmeasured
		# degradation rather than on an invented wear rate.
		deg_rate = 0.0
		notes.append(
			"Tyre degradation was not measurable from the current stint, so no "
			"degradation cost is charged to staying out."
		)

	traffic_measured = bool(cars_ahead_gaps_seconds)
	if not traffic_measured:
		notes.append("No gap data to cars ahead was available, so rejoin traffic cost is zero.")

	traffic_cost = calculate_traffic_penalty(
		cars_ahead_gaps_seconds=cars_ahead_gaps_seconds,
		pit_lane_loss_seconds=effective_pit_loss,
	)

	start = StrategyNode(start_lap, current_compound, current_tyre_age)
	nodes: set[StrategyNode] = {start}
	edges: dict[StrategyNode, list[StrategyEdge]] = {start: []}
	frontier = [start]

	while frontier:
		source = frontier.pop()
		if source.lap >= end_lap:
			continue
		base = lap_times[min(source.lap - 1, len(lap_times) - 1)] if lap_times else 90.0

		stay_target = StrategyNode(source.lap + 1, source.compound, source.tyre_age + 1)
		degradation_cost = source.tyre_age * deg_rate
		edges.setdefault(source, []).append(
			StrategyEdge(
				source,
				stay_target,
				"stay_out",
				base + degradation_cost,
				{"degradation": degradation_cost},
			)
		)
		if stay_target not in nodes:
			nodes.add(stay_target)
			edges[stay_target] = []
			frontier.append(stay_target)

		# A stop is only offered once the current set has run its minimum stint.
		if source.tyre_age < MIN_LAPS_BETWEEN_STOPS:
			continue

		for compound in compounds:
			if compound == source.compound:
				continue
			pit_target = StrategyNode(source.lap + 1, compound, 1)
			edges.setdefault(source, []).append(
				StrategyEdge(
					source,
					pit_target,
					"pit_now",
					base + effective_pit_loss + traffic_cost,
					{"pit_lane_loss": effective_pit_loss, "traffic": traffic_cost},
				)
			)
			if pit_target not in nodes:
				nodes.add(pit_target)
				edges[pit_target] = []
				frontier.append(pit_target)

	return GraphBuild(
		nodes=nodes,
		edges=edges,
		measured_factors={
			"tyre_degradation": degradation_measured,
			"rejoin_traffic": traffic_measured,
		},
		notes=tuple(notes),
	)
