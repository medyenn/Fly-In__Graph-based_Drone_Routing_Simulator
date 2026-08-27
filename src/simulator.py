"""Simulator: runs the turn loop, resolves capacity conflicts, builds the log.
this class knows about *all* drones sharing the map at the same time."""

from __future__ import annotations

from dataclasses import dataclass

from domain import Connection, Drone, TransitState, Zone
from graph import Graph

DEFAULT_MAX_TURNS = 10_000


class SimulationError(Exception):
    """Raised if schedule can't converge within the configured turn cap."""


@dataclass
class Proposal:
    """One drone's desired action for the turn currently being resolved."""

    drone: Drone
    move_type: str
    connection: Connection
    destination: Zone


@dataclass
class ApprovedMove:
    """A proposal that passed capacity checks and was applied this turn."""

    drone: Drone
    move_type: str
    connection: Connection
    token: str


class Simulator:
    """Runs the turn loop; resolves conflicts; produces the output log."""

    def __init__(
        self,
        graph: Graph,
        drones: list[Drone],
        max_turns: int = DEFAULT_MAX_TURNS,
    ) -> None:
        self.graph = graph
        self.drones = drones
        self.max_turns = max_turns
        self.turn = 0
        self.reservations: dict[tuple[str, int], set[int]] = {}
        self.log: list[str] = []

        for drone in self.drones:
            drone.current_zone.add_occupant(drone.drone_id)

    def run(self) -> list[str]:
        """Advance turn by turn until every drone has arrived; return log."""
        while not self.is_finished():
            if self.turn >= self.max_turns:
                raise SimulationError(
                    f"simulation didn't converge within {self.max_turns} turns"
                )
            self.step()
        return self.log

    def step(self) -> None:
        """Resolve exactly one turn: land -> propose -> resolve -> record."""
        self.turn += 1
        landed = self._process_arrivals()
        landed_ids = {drone.drone_id for drone, _ in landed}
        proposals = self._propose_moves(landed_ids)
        approved = self._resolve_and_apply(proposals)
        self.log.append(self._format_turn(landed, approved))

    def is_finished(self) -> bool:
        """Whether every drone has reached the end hub."""
        return all(drone.has_arrived() for drone in self.drones)

    def _process_arrivals(self) -> list[tuple[Drone, str]]:
        """Land every drone whose committed restricted move completes now.

        Unconditional: the destination slot was already reserved when the
        drone departed, so no capacity check is needed here.
        """
        landed: list[tuple[Drone, str]] = []
        for drone in self.drones:
            state = drone.transit_state
            if state is None or state.arrival_turn != self.turn:
                continue
            state.connection.leave(drone.drone_id)
            self._release_reservation(
                state.destination.name, self.turn, drone.drone_id)
            state.destination.add_occupant(drone.drone_id)
            drone.advance(state.destination)
            landed.append((drone, state.destination.name))
        return landed

    def _propose_moves(self, landed_ids: set[int]) -> list[Proposal]:
        """Ask every other active drone what it would like to do this turn."""
        proposals: list[Proposal] = []
        for drone in self.drones:
            if drone.has_arrived() or drone.drone_id in landed_ids:
                continue
            if drone.transit_state is not None:
                continue  # already committed; resolves on its own turn

            next_name = drone.next_zone_name()
            if next_name is None:
                continue  # defensive: nothing left to do

            destination = self.graph.get_zone(next_name)
            connection = self.graph.get_connection(
                drone.current_zone.name, next_name)
            move_type = "restricted" if destination.is_restricted else "normal"
            proposals.append(
                Proposal(drone, move_type, connection, destination))
        return proposals

    def _resolve_and_apply(
            self, proposals: list[Proposal]) -> list[ApprovedMove]:
        """Free every proposing drone's origin, then approve in ID order.

        Departing is unconditional (freeing a slot never fails); a
        proposal only fails on its *destination's* capacity, in which
        case the drone is rolled back into the zone it just left.
        """
        for proposal in proposals:
            proposal.drone.current_zone.remove_occupant(
                proposal.drone.drone_id)

        approved: list[ApprovedMove] = []
        for proposal in sorted(proposals, key=lambda p: p.drone.drone_id):
            drone = proposal.drone
            destination = proposal.destination
            connection = proposal.connection

            if proposal.move_type == "restricted":
                slot_ok = self._restricted_slot_available(destination)
            else:
                slot_ok = destination.has_space()

            if not (slot_ok and connection.has_space()):
                drone.current_zone.add_occupant(drone.drone_id)  # rollback
                continue

            connection.enter(drone.drone_id)
            if proposal.move_type == "restricted":
                arrival_turn = self.turn + 1
                self._reserve(destination.name, arrival_turn, drone.drone_id)
                drone.begin_transit(
                    TransitState(connection, destination, arrival_turn))
                approved.append(
                    ApprovedMove(
                        drone, "restricted", connection, connection.name)
                )
            else:
                destination.add_occupant(drone.drone_id)
                drone.advance(destination)
                approved.append(
                    ApprovedMove(drone, "normal", connection, destination.name)
                )

        for move in approved:
            if move.move_type == "normal":
                move.connection.leave(move.drone.drone_id)

        return approved

    def _restricted_slot_available(self, zone: Zone) -> bool:
        """Whether zone will have room for one more drone next turn.
        """
        if zone.max_drones is None:
            return True
        reserved = len(
            self.reservations.get((zone.name, self.turn + 1), set()))
        return len(zone.occupants) + reserved + 1 <= zone.max_drones

    def _reserve(self, zone_name: str, turn: int, drone_id: int) -> None:
        self.reservations.setdefault((zone_name, turn), set()).add(drone_id)

    def _release_reservation(
            self, zone_name: str, turn: int, drone_id: int) -> None:
        key = (zone_name, turn)
        slots = self.reservations.get(key)
        if slots is None:
            return
        slots.discard(drone_id)
        if not slots:
            del self.reservations[key]

    def _format_turn(
        self, landed: list[tuple[Drone, str]], approved: list[ApprovedMove]
    ) -> str:
        """Build output line: 'D<id>-<zone_or_connection> ...', by id order."""
        tokens: list[tuple[int, str]] = []
        for drone, zone_name in landed:
            tokens.append((drone.drone_id, f"{drone.label}-{zone_name}"))
        for move in approved:
            tokens.append(
                (move.drone.drone_id, f"{move.drone.label}-{move.token}"))
        tokens.sort(key=lambda pair: pair[0])
        return " ".join(text for _, text in tokens)
