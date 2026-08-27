"""Reservation-aware Dijkstra path finder for Fly-In."""

from __future__ import annotations
import heapq
import math
from typing import Optional

from domain import Connection
from graph import Graph

State = tuple[str, int]


class PathFinder:
    """Find and reserve useful paths one drone at a time."""

    def __init__(self, graph: Graph) -> None:
        self.graph = graph
        self.zone_reservations: dict[tuple[str, int], int] = {}
        self.link_reservations: dict[tuple[str, str, int], int] = {}
        self._last_schedule: list[State] = []

    def find_path(self, start_name: str, end_name: str) -> Optional[list[str]]:
        """Find the best path while respecting current reservations."""
        start_state = (start_name, 0)
        distances: dict[State, tuple[int, int]] = {start_state: (0, 0)}
        parents: dict[State, Optional[State]] = {start_state: None}
        heap: list[tuple[int, int, int, str, int]] = [
            (0, 0, 0, start_name, 0)
        ]
        visited: set[State] = set()
        counter = 0

        while heap:
            cost, neg_priority, _, name, turn = heapq.heappop(heap)
            state = (name, turn)
            if state in visited:
                continue
            visited.add(state)

            if name == end_name:
                self._last_schedule = self._build_schedule(parents, state)
                return self._names(self._last_schedule)

            zone = self.graph.get_zone(name)
            priority = -neg_priority
            for connection in self.graph.neighbors(name):
                neighbor = connection.other_end(zone)
                move_cost = neighbor.entry_cost()
                if move_cost is None:
                    continue

                arrival = turn + move_cost
                if not self._zone_available(neighbor.name, arrival):
                    continue
                if not self._link_available(
                    connection, name, neighbor.name, turn, arrival
                ):
                    continue

                next_state = (neighbor.name, arrival)
                next_priority = priority + (1 if neighbor.is_priority else 0)
                candidate = (arrival, -next_priority)
                current = distances.get(next_state, (math.inf, 0))
                if candidate >= current:
                    continue

                distances[next_state] = candidate
                parents[next_state] = state
                counter += 1
                heapq.heappush(
                    heap,
                    (
                        arrival,
                        -next_priority,
                        counter,
                        neighbor.name,
                        arrival,
                    ),
                )

            wait_state = (name, turn + 1)
            wait_key = (turn + 1, -priority)
            current = distances.get(wait_state, (math.inf, 0))
            if wait_key < current and turn < self._wait_limit():
                distances[wait_state] = wait_key
                parents[wait_state] = state
                counter += 1
                heapq.heappush(
                    heap,
                    (turn + 1, -priority, counter, name, turn + 1),
                )

        self._last_schedule = []
        return None

    def find_paths(self, nb_drones: int) -> list[list[str]]:
        """Find and reserve one useful path for each drone."""
        paths: list[list[str]] = []
        if self.graph.start is None or self.graph.end is None:
            return paths

        for _ in range(nb_drones):
            path = self.find_path(
                self.graph.start.name,
                self.graph.end.name,
            )
            if path is None:
                break
            paths.append(path)
            self._reserve_schedule(self._last_schedule)
        return paths

    def get_drones_paths(self, nb_drones: int) -> list[list[str]]:
        """Return one reservation-aware path for every drone."""
        return self.find_paths(nb_drones)

    def reserve(self, path: list[str]) -> None:
        """Reserve a path using its current route timing."""
        schedule = self._schedule(path)
        self._reserve_schedule(schedule)

    def _zone_available(self, name: str, turn: int) -> bool:
        zone = self.graph.get_zone(name)
        if zone.is_end or zone.max_drones is None:
            return True
        return self.zone_reservations.get((name, turn), 0) < zone.max_drones

    def _link_available(
        self,
        connection: Connection,
        current_name: str,
        next_name: str,
        start_turn: int,
        end_turn: int,
    ) -> bool:
        z1, z2 = sorted((current_name, next_name))
        capacity = connection.max_link_capacity
        for turn in range(start_turn, end_turn):
            used = self.link_reservations.get((z1, z2, turn), 0)
            if used >= capacity:
                return False
        return True

    def _reserve_schedule(self, schedule: list[State]) -> None:
        for index, (name, turn) in enumerate(schedule):
            zone = self.graph.get_zone(name)
            if not zone.is_start and not zone.is_end:
                key = (name, turn)
                self.zone_reservations[key] = (
                    self.zone_reservations.get(key, 0) + 1
                )

            if index + 1 >= len(schedule):
                continue
            next_name, next_turn = schedule[index + 1]
            if name == next_name:
                continue
            z1, z2 = sorted((name, next_name))
            for current_turn in range(turn, next_turn):
                key = (z1, z2, current_turn)
                self.link_reservations[key] = (
                    self.link_reservations.get(key, 0) + 1
                )

    def _build_schedule(
        self,
        parents: dict[State, Optional[State]],
        state: State,
    ) -> list[State]:
        schedule: list[State] = []
        current: Optional[State] = state
        while current is not None:
            schedule.append(current)
            current = parents[current]
        schedule.reverse()
        return schedule

    def _names(self, schedule: list[State]) -> list[str]:
        names: list[str] = []
        for name, _ in schedule:
            if not names or names[-1] != name:
                names.append(name)
        return names

    def _schedule(self, path: list[str]) -> list[State]:
        schedule: list[State] = [(path[0], 0)]
        turn = 0
        for name in path[1:]:
            cost = self.graph.get_zone(name).entry_cost() or 1
            turn += cost
            schedule.append((name, turn))
        return schedule

    def _wait_limit(self) -> int:
        return max(100, len(self.graph.zones) * 20)
