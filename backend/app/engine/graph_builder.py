from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.rival_model.rejoin_traffic import calculate_traffic_penalty


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


def build_strategy_graph(
    *,
    start_lap: int,
    end_lap: int,
    current_compound: str,
    current_tyre_age: int,
    lap_time_seconds: Iterable[float],
    available_compounds: Iterable[str] = ("SOFT", "MEDIUM", "HARD"),
    pit_lane_loss_seconds: float = 22.0,
) -> tuple[set[StrategyNode], dict[StrategyNode, list[StrategyEdge]]]:
    lap_times = list(lap_time_seconds)
    compounds = tuple(dict.fromkeys(available_compounds))
    start = StrategyNode(start_lap, current_compound, current_tyre_age)
    nodes: set[StrategyNode] = {start}
    edges: dict[StrategyNode, list[StrategyEdge]] = {start: []}
    frontier = [start]
    while frontier:
        source = frontier.pop()
        if source.lap >= end_lap:
            continue
        base = lap_times[min(source.lap - start_lap, len(lap_times) - 1)] if lap_times else 90.0
        stay_target = StrategyNode(source.lap + 1, source.compound, source.tyre_age + 1)
        stay_cost = base + (source.tyre_age * 0.18)
        edge = StrategyEdge(source, stay_target, "stay_out", stay_cost, {"degradation": source.tyre_age * 0.18})
        edges.setdefault(source, []).append(edge)
        if stay_target not in nodes:
            nodes.add(stay_target)
            edges[stay_target] = []
            frontier.append(stay_target)

        for compound in compounds:
            if compound == source.compound:
                continue
            pit_target = StrategyNode(source.lap + 1, compound, 1)
            traffic = calculate_traffic_penalty(
                lap_number=source.lap,
                pit_lane_loss_seconds=pit_lane_loss_seconds,
            )
            pit_cost = base + pit_lane_loss_seconds + traffic
            pit_edge = StrategyEdge(
                source,
                pit_target,
                "pit_now",
                pit_cost,
                {"pit_lane_loss": pit_lane_loss_seconds, "traffic": traffic},
            )
            edges.setdefault(source, []).append(pit_edge)
            if pit_target not in nodes:
                nodes.add(pit_target)
                edges[pit_target] = []
                frontier.append(pit_target)
    return nodes, edges