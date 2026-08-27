"""Domain objects for the Fly-In simulation.
Holds the three "live state" classes that Zone/Connection/Drone-level
rules from the subject map onto directly:
* Zone       - a node: identity, position, live occupancy.
* Connection - an edge: two endpoints, live traversal load.
* Drone      - one agent: identity, position, assigned path, transit state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

ZONE_ENTRY_COST = {
    "normal": 1,
    "priority": 1,
    "restricted": 2,
}


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
        """Store zone identity/position/metadata and reset live occupancy.

        max_drones of None means unlimited capacity (used for start/end
        hubs, where MapParser forces this regardless of file metadata).
        """
        self.name = name
        self.x = x
        self.y = y
        self.zone_type = zone_type
        self.color = color
        self.max_drones = max_drones
        self.occupants: set[int] = set()
        # Set by Graph.start / Graph.end setters, not by the constructor,
        # so a Zone never has to know about the Graph that owns it.
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
            f"zone '{zone.name}' is not an endpoint of connection '{self.name}'"
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
    """An in-progress, committed 2-turn restricted-zone move.

    Created the turn a drone departs toward a restricted zone; the drone
    lands unconditionally on arrival_turn (its slot was reserved by the
    Simulator at departure time), and cannot idle or turn back midway.
    """

    connection: Connection
    destination: Zone
    arrival_turn: int


class Drone:
    """One agent: identity, current position, and its assigned path.

    `path` is the ordered list of zone names produced by PathFinder for
    this drone; `path_index` is how far along it the drone currently is
    (path[path_index] == current_zone.name once placed).
    """

    def __init__(self, drone_id: int, start_zone: Zone, path: list[str]) -> None:
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
