"""Turn-by-turn scheduling engine for the Fly-In simulation."""

from __future__ import annotations
from dataclasses import dataclass

from graph import Graph, Connection, Drone, TransitState, Zone

DEFAULT_MAX_TURNS = 10_000


class SimulationError(Exception):
    """Raised when a simulation cannot finish within the turn limit."""


@dataclass
class Proposal:
    """One drone's desired move for the current turn."""

    drone: Drone
    connection: Connection
    destination: Zone


@dataclass
class ApprovedMove:
    """One move accepted by the scheduler."""

    drone: Drone
    connection: Connection
    destination: Zone
    restricted: bool


class Simulator:
    """Run the fleet while enforcing zone and connection capacities."""

    def __init__(
        self, graph: Graph,
            drones: list[Drone], max_turns: int = DEFAULT_MAX_TURNS) -> None:
        self.graph = graph
        self.drones = drones
        self.max_turns = max_turns
        self.turn = 0
        self.reservations: dict[tuple[str, int], set[int]] = {}
        self.log: list[str] = []
        for drone in drones:
            drone.current_zone.add_occupant(drone.drone_id)

    def run(self) -> list[str]:
        """Run turns until every drone reaches the end hub."""
        while not self.is_finished():
            if self.turn >= self.max_turns:
                raise SimulationError(
                    f"simulation did not finish within {self.max_turns} turns"
                )
            self.step()
        return self.log

    def is_finished(self) -> bool:
        """Return whether all drones have been delivered."""
        return all(drone.has_arrived() for drone in self.drones)

    def step(self) -> None:
        """Resolve one complete simulation turn."""
        self.turn += 1
        landed = self.process_arrivals()
        landed_ids = {drone.drone_id for drone, _ in landed}
        proposals = self.propose_moves(landed_ids)
        approved = self.resolve_moves(proposals)
        self.log.append(self.record_turn(landed, approved))

    def process_arrivals(self) -> list[tuple[Drone, str]]:
        """Finish restricted moves scheduled for this turn."""
        landed: list[tuple[Drone, str]] = []
        for drone in self.drones:
            state = drone.transit_state
            if state is None or state.arrival_turn != self.turn:
                continue

            state.connection.leave(drone.drone_id)
            slots = self.reservations.get((state.destination.name, self.turn))
            if slots is not None:
                slots.discard(drone.drone_id)
                if not slots:
                    del self.reservations[(state.destination.name, self.turn)]

            state.destination.add_occupant(drone.drone_id)
            drone.advance(state.destination)
            landed.append((drone, state.destination.name))
        return landed

    def propose_moves(self, landed_ids: set[int]) -> list[Proposal]:
        """Build one desired next move for each active drone."""
        proposals: list[Proposal] = []
        for drone in self.drones:
            if (
                drone.has_arrived()
                or drone.transit_state is not None
                or drone.drone_id in landed_ids
            ):
                continue
            next_name = drone.next_zone_name()
            if next_name is None:
                continue
            destination = self.graph.get_zone(next_name)
            connection = self.graph.get_connection(
                drone.current_zone.name, next_name)
            proposals.append(Proposal(drone, connection, destination))
        return proposals

    def resolve_moves(self, proposals: list[Proposal]) -> list[ApprovedMove]:
        """Approve legal moves in drone-ID order."""
        for proposal in proposals:
            proposal.drone.current_zone.remove_occupant(
                proposal.drone.drone_id)

        approved: list[ApprovedMove] = []
        for proposal in sorted(
                proposals, key=lambda item: item.drone.drone_id):
            drone = proposal.drone
            destination = proposal.destination
            connection = proposal.connection
            restricted = destination.is_restricted

            if restricted:
                reserved = len(
                    self.reservations.get(
                        (destination.name, self.turn + 1), set()))
                space = destination.max_drones is None or (
                    len(destination.occupants) + reserved + 1 <= (
                         destination.max_drones))
            else:
                space = destination.has_space()

            if not (space and connection.has_space()):
                drone.current_zone.add_occupant(drone.drone_id)
                continue

            connection.enter(drone.drone_id)
            if restricted:
                arrival_turn = self.turn + 1
                self.reservations.setdefault(
                    (destination.name, arrival_turn), set()
                ).add(drone.drone_id)
                drone.begin_transit(
                    TransitState(connection, destination, arrival_turn))
            else:
                destination.add_occupant(drone.drone_id)
                drone.advance(destination)
                connection.leave(drone.drone_id)

            approved.append(
                ApprovedMove(drone, connection, destination, restricted))
        return approved

    def record_turn(
        self, landed: list[tuple[Drone, str]], approved: list[ApprovedMove]
    ) -> str:
        """Format all movements for one turn."""
        tokens: list[tuple[int, str]] = []
        for drone, zone_name in landed:
            tokens.append((drone.drone_id, f"{drone.label}-{zone_name}"))
        for move in approved:
            target = (
                move.connection.name
                if move.restricted else move.destination.name)
            tokens.append(
                (move.drone.drone_id, f"{move.drone.label}-{target}"))
        tokens.sort(key=lambda item: item[0])
        return " ".join(token for _, token in tokens)
