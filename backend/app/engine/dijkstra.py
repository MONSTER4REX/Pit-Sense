from __future__ import annotations

import heapq
from math import inf

from app.engine.graph_builder import StrategyEdge, StrategyNode


def shortest_path(
    start: StrategyNode,
    graph: dict[StrategyNode, list[StrategyEdge]],
    goal_lap: int,
) -> tuple[float, list[StrategyEdge]]:
    queue: list[tuple[float, int, StrategyNode]] = [(0.0, 0, start)]
    distances: dict[StrategyNode, float] = {start: 0.0}
    previous: dict[StrategyNode, tuple[StrategyNode, StrategyEdge]] = {}
    sequence = 1
    goal: StrategyNode | None = None
    while queue:
        distance, _, node = heapq.heappop(queue)
        if distance != distances.get(node):
            continue
        if node.lap == goal_lap:
            goal = node
            break
        for edge in graph.get(node, []):
            candidate = distance + edge.cost_seconds
            if candidate < distances.get(edge.target, inf):
                distances[edge.target] = candidate
                previous[edge.target] = (node, edge)
                heapq.heappush(queue, (candidate, sequence, edge.target))
                sequence += 1
    if goal is None:
        raise ValueError("Strategy graph has no path to the requested lap")
    path: list[StrategyEdge] = []
    while goal != start:
        parent, edge = previous[goal]
        path.append(edge)
        goal = parent
    path.reverse()
    return distances[path[-1].target] if path else 0.0, path