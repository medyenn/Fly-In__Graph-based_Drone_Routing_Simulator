"""Reservation-aware Dijkstra path finder for Fly-In."""

from __future__ import annotations
import heapq
import math
from typing import Optional

from graph import Graph

State = tuple[str, int]


class PathFinder:
    """Find and reserve one time-aware shortest path per drone."""

    def __init__(self, graph: Graph) -> None:
        self.graph = graph
        self.zone_reservations: dict[tuple[str, int], int] = {}
        self.link_reservations: dict[tuple[str, str, int], int] = {}

    def zone_available(self, name: str, turn: int) -> bool:
        """Whether name still has a free slot at turn, given reservations."""
        zone = self.graph.get_zone(name)
        if zone.is_end or zone.max_drones is None:
            return True
        return self.zone_reservations.get((name, turn), 0) < zone.max_drones

    def link_available(
        self, name_a: str, name_b: str,
            capacity: int, start_turn: int, end_turn: int) -> bool:
        """Whether the connection between name_a/name_b is free for every
        turn in [start_turn, end_turn)."""
        z1, z2 = sorted((name_a, name_b))
        for turn in range(start_turn, end_turn):
            if self.link_reservations.get((z1, z2, turn), 0) >= capacity:
                return False
        return True

    def find_path(self, start_name: str, end_name: str) -> Optional[list[str]]:
        """Find the best path while respecting current reservations."""
        if not self.graph.reachable(start_name, end_name):
            return None

        start_state = (start_name, 0)
        distances: dict[State, tuple[int, int]] = {start_state: (0, 0)}
        parents: dict[State, Optional[State]] = {start_state: None}
        heap: list[tuple[int, int, int, str, int]] = [(0, 0, 0, start_name, 0)]
        visited: set[State] = set()
        wait_limit = max(100, len(self.graph.zones) * 20)
        counter = 0

        while heap:
            cost, neg_priority, _, name, turn = heapq.heappop(heap)
            state = (name, turn)
            if state in visited:
                continue
            visited.add(state)

            if name == end_name:
                schedule = self.build_schedule(parents, state)
                self.reserve_schedule(schedule)
                return self.names(schedule)

            zone = self.graph.get_zone(name)
            priority = -neg_priority

            for connection in self.graph.neighbors(name):
                neighbor = connection.other_end(zone)
                move_cost = neighbor.entry_cost()
                if move_cost is None:
                    continue

                arrival = turn + move_cost
                if not self.zone_available(neighbor.name, arrival):
                    continue
                if not self.link_available(
                        name, neighbor.name,
                        connection.max_link_capacity, turn, arrival):
                    continue

                next_state = (neighbor.name, arrival)
                next_priority = priority + (1 if neighbor.is_priority else 0)
                candidate = (arrival, -next_priority)
                if candidate >= distances.get(next_state, (math.inf, 0)):
                    continue

                distances[next_state] = candidate
                parents[next_state] = state
                counter += 1
                heapq.heappush(
                    heap,
                    (arrival, -next_priority, counter, neighbor.name, arrival))

            wait_state = (name, turn + 1)
            wait_key = (turn + 1, -priority)
            if turn < wait_limit and wait_key < distances.get(
                    wait_state, (math.inf, 0)):
                distances[wait_state] = wait_key
                parents[wait_state] = state
                counter += 1
                heapq.heappush(
                    heap, (turn + 1, -priority, counter, name, turn + 1))

        return None

    def get_drones_paths(self, nb_drones: int) -> list[list[str]]:
        """Return one reservation-aware path for every drone."""
        paths: list[list[str]] = []
        if self.graph.start is None or self.graph.end is None:
            return paths
        for _ in range(nb_drones):
            path = self.find_path(self.graph.start.name, self.graph.end.name)
            if path is None:
                break
            paths.append(path)
        return paths

    def build_schedule(
        self, parents: dict[State, Optional[State]], state: State
    ) -> list[State]:
        """Walk the came-from map back to the start, then reverse it."""
        schedule: list[State] = []
        current: Optional[State] = state
        while current is not None:
            schedule.append(current)
            current = parents[current]
        schedule.reverse()
        return schedule

    def names(self, schedule: list[State]) -> list[str]:
        """Collapse a turn-stamped schedule into distinct consecutive zones."""
        names: list[str] = []
        for name, _ in schedule:
            if not names or names[-1] != name:
                names.append(name)
        return names

    def reserve_schedule(self, schedule: list[State]) -> None:
        """Lock in every zone/link slot a schedule uses, for later drones."""
        for index, (name, turn) in enumerate(schedule):
            zone = self.graph.get_zone(name)
            if not zone.is_start and not zone.is_end:
                key = (name, turn)
                self.zone_reservations[key] = self.zone_reservations.get(
                    key, 0) + 1

            if index + 1 >= len(schedule):
                continue
            next_name, next_turn = schedule[index + 1]
            if name == next_name:
                continue
            z1, z2 = sorted((name, next_name))
            for current_turn in range(turn, next_turn):
                key = (z1, z2, current_turn)
                self.link_reservations[key] = self.link_reservations.get(
                    key, 0) + 1
