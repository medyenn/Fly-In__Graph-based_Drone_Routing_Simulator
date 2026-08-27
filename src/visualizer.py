"""Visualizer: colored terminal feedback layered on top of Simulator's log.
This class wraps each token in ANSI color codes based on
the zone it refers to. Strip the escape codes back out."""

from __future__ import annotations

import sys
from typing import Optional

from domain import Zone
from graph import Graph

RESET = "\033[0m"
BOLD = "\033[1m"

# 256-color codes, since the map files use names (orange, purple, gold,
# maroon, crimson...) that plain 8-color ANSI can't represent. "black" is
# remapped to a dark gray so it stays visible on a black terminal
# background; anything unrecognized (e.g. "rainbow") falls back to
# DEFAULT_CODE rather than raising - a cosmetic layer should never crash
# the simulation over an unusual color name.
COLOR_CODES = {
    "black": 235,
    "white": 255,
    "gray": 244,
    "grey": 244,
    "red": 196,
    "green": 46,
    "yellow": 226,
    "blue": 33,
    "magenta": 201,
    "cyan": 51,
    "orange": 208,
    "purple": 129,
    "brown": 94,
    "lime": 118,
    "gold": 220,
    "maroon": 88,
    "darkred": 124,
    "crimson": 161,
    "violet": 177,
}
DEFAULT_CODE = 250


class Visualizer:
    """Renders Simulator output and a pre-run map legend, in color."""

    def __init__(self, graph: Graph, use_color: Optional[bool] = None) -> None:
        self.graph = graph
        # Auto-disable color when stdout isn't a terminal (piped/redirected)
        # so logs and captured output stay clean plain text.
        self.use_color = sys.stdout.isatty() if use_color is None else use_color
        self._token_targets = self._build_token_targets()

    def _build_token_targets(self) -> dict[str, Zone]:
        """Map every zone name AND restricted connection name to its Zone.

        A connection only ever appears as an output token while a drone is
        mid-transit toward a *restricted* zone, so a connection token is
        always colored using that restricted destination.
        """
        targets: dict[str, Zone] = {}
        for zone in self.graph.zones.values():
            targets[zone.name] = zone
        for connection in self.graph.connections:
            if connection.zone_a.is_restricted:
                targets[connection.name] = connection.zone_a
            elif connection.zone_b.is_restricted:
                targets[connection.name] = connection.zone_b
        return targets

    def _wrap(self, text: str, color_name: Optional[str]) -> str:
        """Wrap text in an ANSI color, or return it unchanged."""
        if not self.use_color or color_name is None:
            return text
        code = COLOR_CODES.get(color_name.lower(), DEFAULT_CODE)
        return f"\033[38;5;{code}m{text}{RESET}"

    def _colorize_token(self, token: str) -> str:
        """Colorize one 'D<id>-<zone_or_connection>' token in place."""
        _drone_part, _, rest = token.partition("-")
        zone = self._token_targets.get(rest)
        if zone is None:
            return token
        return self._wrap(token, zone.color)

    def colorize_line(self, line: str) -> str:
        """Return line with each token colorized; pure, no printing."""
        if not line:
            return line
        return " ".join(self._colorize_token(token) for token in line.split())

    def render_turn(self, turn_number: int, line: str) -> None:
        """Print one turn's line, colorized. turn_number is for callers
        that want to correlate with Simulator.log; it is not printed, so
        the visible output still matches the required format exactly
        once ANSI codes are stripped."""
        del turn_number  # not rendered; kept for interface symmetry
        print(self.colorize_line(line))

    def render_map(self) -> None:
        """Print a static legend of zones and connections before the run."""
        print(self._heading("Map layout"))
        for zone in sorted(self.graph.zones.values(), key=lambda z: (z.x, z.y)):
            role = " (start)" if zone.is_start else " (end)" if zone.is_end else ""
            capacity = "unlimited" if zone.max_drones is None else str(zone.max_drones)
            name = self._wrap(zone.name, zone.color)
            print(
                f"  {name:<20} pos=({zone.x},{zone.y}) "
                f"type={zone.zone_type:<10} capacity={capacity}{role}"
            )

        print()
        print(self._heading("Connections"))
        for connection in self.graph.connections:
            print(f"  {connection.name:<30} capacity={connection.max_link_capacity}")

    def render_summary(self, total_turns: int, nb_drones: int) -> None:
        """Print a short final report once the simulation has finished."""
        print(self._heading("Simulation complete"))
        print(f"  total turns : {total_turns}")
        print(f"  drones      : {nb_drones}")
        if total_turns:
            print(f"  drones/turn : {nb_drones / total_turns:.2f}")

    def _heading(self, text: str) -> str:
        if not self.use_color:
            return text
        return f"{BOLD}{text}{RESET}"
