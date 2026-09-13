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
from typing import Iterable, NamedTuple

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
# Stops the graph will consider over a race. Teams carry a limited tyre
# allocation and every stop costs the pit-lane loss outright, so real dry-race
# strategies are one to three stops. Without this bound a steep measured
# degradation rate - which a wet or drying race can easily produce - makes the
# shortest path a four- or five-stopper that no team would ever run.
MAX_PIT_STOPS = 3
# A fresh set starts at age 1 on the lap after the stop.
FRESH_TYRE_AGE = 1
# Safety ceiling on the per-lap degradation charge. It sits well above any rate
# the tyre model will now hand over, so in normal operation it never binds - it
# only stops a pathological input producing lap times no car has ever run. It is
# deliberately not tight: a cap close to the real penalty saturates the stay-out
# and pit paths equally, and pitting then never pays for itself.
MAX_DEGRADATION_PENALTY_SECONDS = 8.0


class StrategyNode(NamedTuple):
	"""A point in the search: which lap, how old the tyre is, how many stops made.

	A NamedTuple rather than a frozen dataclass because the search hashes these
	constantly - a quarter of the graph's cost was the generated __hash__ - and a
	tuple hashes in C.

	Compound is deliberately absent. Every pit edge costs the same whichever
	compound is fitted, and nothing downstream reads a node's compound: the path
	is consumed for its actions, its source laps and its factor breakdown only.
	Carrying it tripled the state space to distinguish states that are identical
	in cost. The two-compound rule is enforced in the reoptimizer, as a minimum
	number of stops, which is what the graph can actually see.
	"""

	lap: int
	tyre_age: int
	# Stops taken to reach this state, so the graph can bound total stops without
	# conflating a fresh tyre on lap 30 of a one-stopper with one on lap 30 of a
	# three-stopper.
	stops: int


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

	start = StrategyNode(start_lap, current_tyre_age, 0)
	nodes: set[StrategyNode] = {start}
	edges: dict[StrategyNode, list[StrategyEdge]] = {start: []}
	frontier = [start]

	while frontier:
		source = frontier.pop()
		if source.lap >= end_lap:
			continue
		base = lap_times[min(source.lap - 1, len(lap_times) - 1)] if lap_times else 90.0

		stay_target = StrategyNode(source.lap + 1, source.tyre_age + 1, source.stops)
		degradation_cost = min(source.tyre_age * deg_rate, MAX_DEGRADATION_PENALTY_SECONDS)
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

		# A stop is only offered once the current set has run its minimum stint, and
		# only while the car still has a stop left in its allocation.
		if source.tyre_age < MIN_LAPS_BETWEEN_STOPS or source.stops >= MAX_PIT_STOPS:
			continue

		# One stop edge, not one per alternative compound: they all cost the same,
		# so the extra copies only widened the search.
		pit_target = StrategyNode(source.lap + 1, FRESH_TYRE_AGE, source.stops + 1)
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
