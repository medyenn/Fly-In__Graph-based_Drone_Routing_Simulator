"""Graph: owns all Zones and Connections, answers adjacency queries.

Kept deliberately dumb: Graph knows nothing about drones, turns, or
capacity rules over time - it is pure static network structure plus the
live Zone/Connection occupancy objects it holds references to. PathFinder
and Simulator query it; only MapParser mutates it (via add_zone /
add_connection and the start/end setters).
"""

from __future__ import annotations

from typing import Optional

from domain import Connection, Zone


class GraphError(Exception):
    """Raised when the graph is queried for an unknown zone or connection."""


class Graph:
    """Owns all zones/connections; answers adjacency queries."""

    def __init__(self) -> None:
        self.zones: dict[str, Zone] = {}
        self.connections: list[Connection] = []
        # Precomputed adjacency: zone name -> connections touching it.
        # Built incrementally in add_zone/add_connection for O(1)-ish
        # neighbor lookups without any external graph library.
        self._adjacency: dict[str, list[Connection]] = {}
        self._start: Optional[Zone] = None
        self._end: Optional[Zone] = None

    @property
    def start(self) -> Optional[Zone]:
        """The unique start_hub zone, once set."""
        return self._start

    @start.setter
    def start(self, zone: Zone) -> None:
        """Set the start hub, keeping Zone.is_start in sync automatically."""
        if self._start is not None:
            self._start.is_start = False
        self._start = zone
        zone.is_start = True

    @property
    def end(self) -> Optional[Zone]:
        """The unique end_hub zone, once set."""
        return self._end

    @end.setter
    def end(self, zone: Zone) -> None:
        """Set the end hub, keeping Zone.is_end in sync automatically."""
        if self._end is not None:
            self._end.is_end = False
        self._end = zone
        zone.is_end = True

    def add_zone(self, zone: Zone) -> None:
        """Register a new zone. Called by MapParser while building the map."""
        self.zones[zone.name] = zone
        self._adjacency.setdefault(zone.name, [])

    def add_connection(self, connection: Connection) -> None:
        """Register a new connection and index it on both its endpoints."""
        self.connections.append(connection)
        self._adjacency.setdefault(connection.zone_a.name, []).append(connection)
        self._adjacency.setdefault(connection.zone_b.name, []).append(connection)

    def neighbors(self, zone_name: str) -> list[Connection]:
        """All connections touching zone_name."""
        if zone_name not in self.zones:
            raise GraphError(f"unknown zone '{zone_name}'")
        return self._adjacency.get(zone_name, [])

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

    def __repr__(self) -> str:
        return (
            f"Graph(zones={len(self.zones)}, "
            f"connections={len(self.connections)})"
        )
