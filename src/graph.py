"""Graph: owns all Zones and Connections, answers adjacency queries."""

from __future__ import annotations
from typing import Optional
from dataclasses import dataclass

ZONE_ENTRY_COST = {
    "normal": 1,
    "priority": 1,
    "restricted": 2,
}


class GraphError(Exception):
    """Raised when a zone or connection lookup fails."""


class Graph:
    """Owns all zones/connections; answers adjacency queries."""

    def __init__(self) -> None:
        self.zones: dict[str, Zone] = {}
        self.connections: list[Connection] = []
        self.adjacency: dict[str, list[Connection]] = {}
        self.start: Optional[Zone] = None
        self.end: Optional[Zone] = None

    def add_zone(self, zone: Zone) -> None:
        """Register a new zone. Called by MapParser while building the map."""
        self.zones[zone.name] = zone
        self.adjacency.setdefault(zone.name, [])

    def add_connection(self, connection: Connection) -> None:
        """Register a new connection and index it on both its endpoints."""
        self.connections.append(connection)
        self.adjacency[connection.zone_a.name].append(connection)
        self.adjacency[connection.zone_b.name].append(connection)

    def neighbors(self, zone_name: str) -> list[Connection]:
        """All connections touching zone_name."""
        if zone_name not in self.zones:
            raise GraphError(f"unknown zone '{zone_name}'")
        return self.adjacency[zone_name]

    def get_zone(self, name: str) -> Zone:
        """Safe zone lookup by name."""
        try:
            return self.zones[name]
        except KeyError as exc:
            raise GraphError(f"unknown zone '{name}'") from exc

    def get_connection(self, name_a: str, name_b: str) -> Connection:
        """Safe connection lookup between two (expected-adjacent) zones."""
        for connection in self.neighbors(name_a):
            if connection.connects(name_a, name_b):
                return connection
        raise GraphError(f"no connection between '{name_a}' and '{name_b}'")

    def reachable(self, start_name: str, end_name: str) -> bool:
        """Whether end_name can be reached from start_name, skipping blocked"""
        seen = {start_name}
        stack = [start_name]
        while stack:
            name = stack.pop()
            if name == end_name:
                return True
            for connection in self.neighbors(name):
                other = connection.other_end(self.zones[name])
                if other.zone_type != "blocked" and other.name not in seen:
                    seen.add(other.name)
                    stack.append(other.name)
        return False

    def connected(self) -> bool:
        """Whether every zone in the map belongs to one connected component."""
        if not self.zones:
            return True
        start = next(iter(self.zones))
        seen = {start}
        stack = [start]
        while stack:
            name = stack.pop()
            for connection in self.neighbors(name):
                other = connection.other_end(self.zones[name]).name
                if other not in seen:
                    seen.add(other)
                    stack.append(other)
        return len(seen) == len(self.zones)

    def __repr__(self) -> str:
        return f"Graph(zones={len(self.zones)}, edges={len(self.connections)})"


class Zone:
    """A single zone (node): identity, position, type, and occupancy."""

    def __init__(
        self,
        name: str,
        x: int,
        y: int,
        zone_type: str = "normal",
        color: Optional[str] = None,
        max_drones: Optional[int] = 1,
    ) -> None:
        """Store zone identity/position/metadata and reset live occupancy."""
        self.name = name
        self.x = x
        self.y = y
        self.zone_type = zone_type
        self.color = color
        self.max_drones = max_drones
        self.occupants: set[int] = set()
        self.is_start = False
        self.is_end = False

    @property
    def is_blocked(self) -> bool:
        """Whether this zone can never be entered."""
        return self.zone_type == "blocked"

    @property
    def is_restricted(self) -> bool:
        """Whether entering this zone is a committed 2-turn move."""
        return self.zone_type == "restricted"

    @property
    def is_priority(self) -> bool:
        """Whether this zone should be preferred on path-cost ties."""
        return self.zone_type == "priority"

    def entry_cost(self) -> Optional[int]:
        """Turns required to enter this zone, or None if it is blocked."""
        if self.is_blocked:
            return None
        return ZONE_ENTRY_COST[self.zone_type]

    def has_space(self, n: int = 1) -> bool:
        """Whether n more drones can fit right now."""
        if self.max_drones is None:
            return True
        return len(self.occupants) + n <= self.max_drones

    def add_occupant(self, drone_id: int) -> None:
        """Mark drone_id as physically present in this zone."""
        self.occupants.add(drone_id)

    def remove_occupant(self, drone_id: int) -> None:
        """Mark drone_id as no longer present in this zone."""
        self.occupants.discard(drone_id)

    def __repr__(self) -> str:
        return f"Zone({self.name!r}, type={self.zone_type!r})"


class Connection:
    """A bidirectional edge between two zones, with its own capacity."""

    def __init__(
        self, zone_a: Zone, zone_b: Zone, max_link_capacity: int = 1
    ) -> None:
        self.zone_a = zone_a
        self.zone_b = zone_b
        self.max_link_capacity = max_link_capacity
        self.in_transit: set[int] = set()

    @property
    def name(self) -> str:
        """Display name, e.g. for the 'D<ID>-<connection>' output token."""
        return f"{self.zone_a.name}-{self.zone_b.name}"

    def other_end(self, zone: Zone) -> Zone:
        """Given one endpoint, return the zone on the other side."""
        if zone is self.zone_a:
            return self.zone_b
        if zone is self.zone_b:
            return self.zone_a
        raise ValueError(
            f"zone '{zone.name}' is not an endpoint of "
            f"connection '{self.name}'"
        )

    def connects(self, name_a: str, name_b: str) -> bool:
        """Whether this connection links exactly these two zone names."""
        return {self.zone_a.name, self.zone_b.name} == {name_a, name_b}

    def has_space(self, n: int = 1) -> bool:
        """Whether n more drones can be in transit on this link right now."""
        return len(self.in_transit) + n <= self.max_link_capacity

    def enter(self, drone_id: int) -> None:
        """Mark drone_id as currently traversing this connection."""
        self.in_transit.add(drone_id)

    def leave(self, drone_id: int) -> None:
        """Mark drone_id as no longer traversing this connection."""
        self.in_transit.discard(drone_id)

    def __repr__(self) -> str:
        return f"Connection({self.name!r}, capacity={self.max_link_capacity})"


@dataclass
class TransitState:
    """An in-progress, committed 2-turn restricted-zone move."""

    connection: Connection
    destination: Zone
    arrival_turn: int


class Drone:
    """One agent: identity, current position, and its assigned path."""

    def __init__(
        self, drone_id: int, start_zone: Zone, path: list[str]
    ) -> None:
        self.drone_id = drone_id
        self.current_zone = start_zone
        self.path = path
        self.path_index = 0
        self.transit_state: Optional[TransitState] = None
        self.arrived = False

    @property
    def label(self) -> str:
        """Display label used in output lines, e.g. 'D3'."""
        return f"D{self.drone_id}"

    def next_zone_name(self) -> Optional[str]:
        """Peek at the next step's zone name, or None if already at the end."""
        next_index = self.path_index + 1
        if next_index >= len(self.path):
            return None
        return self.path[next_index]

    def advance(self, zone: Zone) -> None:
        """Move onto `zone`: advance path_index, clear any transit state."""
        self.path_index += 1
        self.current_zone = zone
        self.transit_state = None
        if zone.is_end:
            self.arrived = True

    def begin_transit(self, state: TransitState) -> None:
        """Record that this drone has just departed on a restricted move."""
        self.transit_state = state

    def has_arrived(self) -> bool:
        """Whether this drone has reached the end hub."""
        return self.arrived

    def __repr__(self) -> str:
        return f"Drone({self.label}, at={self.current_zone.name!r})"
