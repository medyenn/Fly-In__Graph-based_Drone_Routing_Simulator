"""PathFinder: cheapest, priority-aware route for a single drone.

Deliberately ignorant of everything Simulator owns: other drones, current
occupancy, turns. Mixing those concerns in here is the most common way
this project gets over-engineered - resist it. One job: given a start and
an end zone name, return the cheapest path, preferring routes that touch
more priority zones when two routes cost exactly the same.
"""

from __future__ import annotations

import heapq
import math
from typing import Optional

from graph import Graph


class PathFinder:
    """Self-written Dijkstra over a Graph, with a priority-zone tie-break."""

    def __init__(self, graph: Graph) -> None:
        self.graph = graph

    def find_path(self, start_name: str, end_name: str) -> Optional[list[str]]:
        """Return the cheapest route from start_name to end_name.

        Cost of entering a zone is its entry_cost() (1 for normal/priority,
        2 for restricted); blocked zones are never traversable. Among
        equal-cost routes, the one passing through more priority zones
        wins. Returns None if end_name is unreachable from start_name.
        """
        start = self.graph.get_zone(start_name)

        # Best known (cost, priority_count) reaching each zone so far.
        best_cost: dict[str, float] = {start_name: 0}
        best_priority: dict[str, int] = {
            start_name: 1 if start.is_priority else 0
        }
        came_from: dict[str, str] = {}
        visited: set[str] = set()

        # Heap items: (cost, -priority_count, zone_name). Cost sorts first;
        # among equal cost, higher priority_count (i.e. more negative)
        # sorts first; zone_name only breaks a true tie deterministically.
        heap: list[tuple[int, int, str]] = [
            (0, -best_priority[start_name], start_name)
        ]

        while heap:
            cost, neg_priority, name = heapq.heappop(heap)
            if name in visited:
                continue
            visited.add(name)

            if name == end_name:
                return self._reconstruct_path(came_from, start_name, end_name)

            zone = self.graph.get_zone(name)
            priority_count = -neg_priority

            for connection in self.graph.neighbors(name):
                neighbor = connection.other_end(zone)
                entry_cost = neighbor.entry_cost()
                if entry_cost is None:
                    continue  # blocked: never a valid step

                candidate_cost = cost + entry_cost
                candidate_priority = priority_count + (
                    1 if neighbor.is_priority else 0
                )
                candidate_key = (candidate_cost, -candidate_priority)

                existing_key = (
                    best_cost.get(neighbor.name, math.inf),
                    -best_priority.get(neighbor.name, -1),
                )
                if candidate_key < existing_key:
                    best_cost[neighbor.name] = candidate_cost
                    best_priority[neighbor.name] = candidate_priority
                    came_from[neighbor.name] = name
                    heapq.heappush(
                        heap, (candidate_cost, -candidate_priority, neighbor.name)
                    )

        return None  # end_name is unreachable from start_name

    def _reconstruct_path(
        self, came_from: dict[str, str], start_name: str, end_name: str
    ) -> list[str]:
        """Walk the came-from map backward from end_name to start_name."""
        path = [end_name]
        while path[-1] != start_name:
            path.append(came_from[path[-1]])
        path.reverse()
        return path
