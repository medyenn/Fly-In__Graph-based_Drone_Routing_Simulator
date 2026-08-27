"""Simulator: runs the turn loop, resolves capacity conflicts, builds the log.

This is where every rule from the subject's simulation checklist actually
gets enforced: zone/connection capacity, departures-free-before-arrivals-
checked, and the restricted-zone 2-turn atomic commitment. PathFinder
already picked each drone's route in isolation; this class is the only
place that knows about *all* drones sharing the map at the same time.

Turn-timing convention used throughout (documented here since it's the one
genuinely ambiguous point in the subject, and every method below depends
on it): a restricted-zone departure decided during turn T lands at turn
T + 1 - one committed intervening turn, matching "must arrive exactly
next turn". The destination slot for T + 1 is reserved at departure time,
which is what lets the landing happen unconditionally.
"""

from __future__ import annotations

from dataclasses import dataclass

from domain import Connection, Drone, TransitState, Zone
from graph import Graph

DEFAULT_MAX_TURNS = 10_000


class SimulationError(Exception):
    """Raised if the schedule cannot converge within the configured turn cap."""


@dataclass
class Proposal:
    """One drone's desired action for the turn currently being resolved."""

    drone: Drone
    move_type: str  # "normal" (includes priority zones) or "restricted"
    connection: Connection
    destination: Zone


@dataclass
class ApprovedMove:
    """A proposal that passed capacity checks and was applied this turn."""

    drone: Drone
    move_type: str
    connection: Connection
    token: str  # what _format_turn should print after "D<id>-"


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
        # (zone_name, arrival_turn) -> drone ids already promised that slot.
        self.reservations: dict[tuple[str, int], set[int]] = {}
        self.log: list[str] = []

        # Make sure every drone is actually registered as an occupant of
        # its starting zone, regardless of what the caller already did.
        for drone in self.drones:
            drone.current_zone.add_occupant(drone.drone_id)

    def run(self) -> list[str]:
        """Advance turn by turn until every drone has arrived; return log."""
        while not self.is_finished():
            if self.turn >= self.max_turns:
                raise SimulationError(
                    f"simulation did not converge within {self.max_turns} turns"
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

    # -- Step A: unconditional landings ----------------------------------

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
            self._release_reservation(state.destination.name, self.turn, drone.drone_id)
            state.destination.add_occupant(drone.drone_id)
            drone.advance(state.destination)
            landed.append((drone, state.destination.name))
        return landed

    # -- Proposal gathering -------------------------------------------------

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
            connection = self.graph.get_connection(drone.current_zone.name, next_name)
            move_type = "restricted" if destination.is_restricted else "normal"
            proposals.append(Proposal(drone, move_type, connection, destination))
        return proposals

    # -- Steps B/C: departures-first, then capacity-gated approval ---------

    def _resolve_and_apply(self, proposals: list[Proposal]) -> list[ApprovedMove]:
        """Free every proposing drone's origin, then approve in ID order.

        Departing is unconditional (freeing a slot never fails); a
        proposal only fails on its *destination's* capacity, in which
        case the drone is rolled back into the zone it just left.
        """
        for proposal in proposals:
            proposal.drone.current_zone.remove_occupant(proposal.drone.drone_id)

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
                drone.begin_transit(TransitState(connection, destination, arrival_turn))
                approved.append(
                    ApprovedMove(drone, "restricted", connection, connection.name)
                )
            else:
                destination.add_occupant(drone.drone_id)
                drone.advance(destination)
                approved.append(
                    ApprovedMove(drone, "normal", connection, destination.name)
                )

        # Normal-move connection usage only lasts this turn; free it now
        # that every proposal for this turn has been resolved. Restricted
        # departures stay in transit until they land (see _process_arrivals).
        for move in approved:
            if move.move_type == "normal":
                move.connection.leave(move.drone.drone_id)

        return approved

    def _restricted_slot_available(self, zone: Zone) -> bool:
        """Whether zone will have room for one more drone next turn.

        Conservative on purpose: counts current occupants as if they
        stay, plus anyone already promised that same future slot, plus
        this candidate - never over-commits, may rarely under-use a slot
        that would in fact free up in time. That trade-off is the right
        one for a simple, defendable scheduler.
        """
        if zone.max_drones is None:
            return True
        reserved = len(self.reservations.get((zone.name, self.turn + 1), set()))
        return len(zone.occupants) + reserved + 1 <= zone.max_drones

    def _reserve(self, zone_name: str, turn: int, drone_id: int) -> None:
        self.reservations.setdefault((zone_name, turn), set()).add(drone_id)

    def _release_reservation(self, zone_name: str, turn: int, drone_id: int) -> None:
        key = (zone_name, turn)
        slots = self.reservations.get(key)
        if slots is None:
            return
        slots.discard(drone_id)
        if not slots:
            del self.reservations[key]

    # -- Output --------------------------------------------------------------

    def _format_turn(
        self, landed: list[tuple[Drone, str]], approved: list[ApprovedMove]
    ) -> str:
        """Build one output line: 'D<id>-<zone_or_connection> ...', by id order."""
        tokens: list[tuple[int, str]] = []
        for drone, zone_name in landed:
            tokens.append((drone.drone_id, f"{drone.label}-{zone_name}"))
        for move in approved:
            tokens.append((move.drone.drone_id, f"{move.drone.label}-{move.token}"))
        tokens.sort(key=lambda pair: pair[0])
        return " ".join(text for _, text in tokens)
