"""Arcade visualizer for the Fly-In simulation."""

from __future__ import annotations

import math
from typing import Optional

import arcade

from domain import Connection, Zone
from graph import Graph


WIDTH = 1300
HEIGHT = 600
MARGIN_X = 80
MARGIN_Y = 75
ZONE_RADIUS = 11
DRONE_RADIUS = 9
MOVE_TIME = 0.65
TURN_PAUSE = 1.0

BACKGROUND = (18, 22, 30)
LINE_COLOR = (75, 82, 95)
TEXT_COLOR = (235, 238, 242)
DRONE_COLOR = (255, 255, 255)
ACTIVE_LINE = (110, 200, 255)

COLORS = {
    "red": (239, 68, 68),
    "green": (34, 197, 94),
    "blue": (59, 130, 246),
    "yellow": (250, 204, 21),
    "orange": (249, 115, 22),
    "purple": (168, 85, 247),
    "gray": (120, 126, 138),
    "grey": (120, 126, 138),
    "cyan": (45, 212, 191),
}

ZONE_COLORS = {
    "normal": (120, 126, 138),
    "priority": (34, 197, 94),
    "restricted": (168, 85, 247),
    "blocked": (65, 70, 80),
}


class Visualizer(arcade.Window):
    """Display and animate the Fly-In network."""

    def __init__(self, graph: Graph, log: list[str]) -> None:
        super().__init__(WIDTH, HEIGHT, "Fly-In", resizable=True)
        arcade.set_background_color(BACKGROUND)
        self.graph = graph
        self.log = log
        self.turn = 0
        self.timer = 0.0
        self.turn_pause = False
        self.turn_started = False
        self.paused = False
        self.replaying = False
        self.positions = self._start_positions()
        self.visual_positions: dict[int, tuple[float, float]] = {}
        self.transit: dict[int, str] = {}
        self.animations: dict[
            int, tuple[tuple[float, float], tuple[float, float]]
        ] = {}
        self.active_connections: set[str] = set()
        self.layout = self._layout()
        self._sync_visual_positions()

    def _layout(self) -> tuple[float, float, float, float, float, float]:
        """Build independent X/Y scales so the network fills the window."""
        zones = list(self.graph.zones.values())
        if not zones:
            return 1.0, 1.0, 0.0, 0.0, 0.0, 0.0

        min_x = min(zone.x for zone in zones)
        max_x = max(zone.x for zone in zones)
        min_y = min(zone.y for zone in zones)
        max_y = max(zone.y for zone in zones)
        span_x = max(max_x - min_x, 1)
        span_y = max(max_y - min_y, 1)

        left = MARGIN_X
        right = self.width - MARGIN_X
        bottom = MARGIN_Y + 30
        top = self.height - MARGIN_Y
        scale_x = max((right - left) / span_x, 1.0)
        scale_y = max((top - bottom) / span_y, 1.0)
        offset_x = left - min_x * scale_x
        offset_y = bottom - min_y * scale_y
        return scale_x, scale_y, offset_x, offset_y, min_x, min_y

    def _point(self, zone_name: str) -> tuple[float, float]:
        """Convert a map coordinate to the current window coordinate."""
        zone = self.graph.zones[zone_name]
        scale_x, scale_y, offset_x, offset_y, _, _ = self.layout
        return (
            zone.x * scale_x + offset_x,
            zone.y * scale_y + offset_y,
        )

    def _radius(self) -> float:
        """Keep zone markers compact while adapting slightly to window size."""
        return max(8.0, min(13.0, min(self.width, self.height) * 0.018))

    def on_resize(self, width: int, height: int) -> None:
        """Recalculate the stretched map after a window resize."""
        super().on_resize(width, height)
        self.layout = self._layout()
        for drone_id, zone_name in self.positions.items():
            if (
                drone_id not in self.animations
                    and drone_id not in self.transit):
                self.visual_positions[drone_id] = self._point(zone_name)

    def _sync_visual_positions(self) -> None:
        """Keep a concrete screen position for every drone between turns."""
        for drone_id, zone_name in self.positions.items():
            if drone_id not in self.visual_positions:
                self.visual_positions[drone_id] = self._point(zone_name)

    def _current_visual_position(self, drone_id: int) -> tuple[float, float]:
        """Return the drone's exact position before starting a movement."""
        if drone_id in self.visual_positions:
            return self.visual_positions[drone_id]
        return self._point(self.positions[drone_id])

    def _start_positions(self) -> dict[int, str]:
        """Put every drone at the start zone."""
        if self.graph.start is None:
            return {}
        return {
            drone_id: self.graph.start.name
            for drone_id in range(1, self._drone_count() + 1)
        }

    def _drone_count(self) -> int:
        """Find the highest drone ID appearing in the simulation log."""
        highest = 0
        for line in self.log:
            for token in line.split():
                if not token.startswith("D"):
                    continue
                try:
                    drone_id = int(token[1:].split("-", 1)[0])
                except ValueError:
                    continue
                highest = max(highest, drone_id)
        return highest

    def _connection(self, name: str) -> Optional[Connection]:
        """Find a connection by its output name."""
        return next(
            (connection for connection in self.graph.connections
             if connection.name == name),
            None,
        )

    def _start_turn(self) -> None:
        """Start animations for every movement recorded in this turn."""
        if self.turn >= len(self.log):
            return
        self.active_connections.clear()
        self.animations.clear()

        for token in self.log[self.turn].split():
            drone_text, target = token.split("-", 1)
            drone_id = int(drone_text[1:])
            if target in self.graph.zones:
                self._animate_to_zone(drone_id, target)
                continue
            connection = self._connection(target)
            if connection is not None:
                self.active_connections.add(target)
                self._animate_on_connection(drone_id, connection)
        self.replaying = True

    def _animate_to_zone(self, drone_id: int, target: str) -> None:
        """Animate a drone from its current visual position into a zone."""
        self.animations[drone_id] = (
            self._current_visual_position(drone_id),
            self._point(target),
        )

    def _animate_on_connection(
        self, drone_id: int, connection: Connection
    ) -> None:
        """Move a restricted-zone drone onto the edge midpoint."""
        current = self.positions.get(drone_id)
        if current is None:
            return
        start = self._current_visual_position(drone_id)
        a = self._point(connection.zone_a.name)
        b = self._point(connection.zone_b.name)
        midpoint = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        self.animations[drone_id] = (start, midpoint)
        self.transit[drone_id] = connection.name

    def _drone_position(self, drone_id: int) -> tuple[float, float]:
        """Return the exact current visual position of a drone."""
        animation = self.animations.get(drone_id)
        if animation is not None:
            start_pos, end_pos = animation
            if self.turn_pause:
                progress = 1.0
            else:
                progress = min(self.timer / MOVE_TIME, 1.0)
            return (
                start_pos[0] + (end_pos[0] - start_pos[0]) * progress,
                start_pos[1] + (end_pos[1] - start_pos[1]) * progress,
            )

        return self.visual_positions.get(
            drone_id,
            self._point(self.positions[drone_id]),
        )

    def _finish_turn(self) -> None:
        """Commit this turn, freeze every drone at its new position, and
        hand control back to on_update"""
        if self.turn < len(self.log):
            tokens = self.log[self.turn].split()

        for drone_id, animation in list(self.animations.items()):
            _, final_position = animation
            self.visual_positions[drone_id] = final_position

            target = next(
                (
                    token.split("-", 1)[1]
                    for token in tokens
                    if token.startswith(f"D{drone_id}-")
                ),
                None,
            )

            if target in self.graph.zones:
                self.positions[drone_id] = target
                self.transit.pop(drone_id, None)

        self.animations.clear()
        self.turn += 1
        self.timer = 0.0
        self.turn_pause = False
        self.turn_started = False

        if self.turn >= len(self.log):
            self.replaying = False
            self.active_connections.clear()

    def _reset(self) -> None:
        """Restart the visual replay from turn one."""
        self.turn = 0
        self.timer = 0.0
        self.turn_pause = False
        self.turn_started = False
        self.paused = False
        self.replaying = False
        self.positions = self._start_positions()
        self.visual_positions.clear()
        self._sync_visual_positions()
        self.transit.clear()
        self.animations.clear()
        self.active_connections.clear()

    def on_update(self, delta_time: float) -> None:
        """Advance one turn, then pause visibly before the next turn."""
        if self.paused:
            return
        if not self.turn_started:
            self._start_turn()
            self.turn_started = True
            self.timer = 0.0
            self.turn_pause = False
            return
        self.timer += delta_time
        if not self.turn_pause and self.timer >= MOVE_TIME:
            self.timer = 0.0
            self.turn_pause = True
            return
        if self.turn_pause and self.timer >= TURN_PAUSE:
            self._finish_turn()

    def on_key_press(self, key: int, modifiers: int) -> None:
        """Handle pause and replay shortcuts."""
        if key == arcade.key.SPACE:
            self.paused = not self.paused
        elif key == arcade.key.R:
            self._reset()

    def on_mouse_press(
        self, x: float, y: float, button: int, modifiers: int
    ) -> None:
        """Handle the replay button."""
        if self.width - 160 <= x <= self.width - 40 and 25 <= y <= 65:
            self._reset()

    def on_draw(self) -> None:
        """Draw the complete simulation view."""
        self.clear()
        self._draw_header()
        self._draw_connections()
        self._draw_zones()
        self._draw_drones()
        self._draw_replay_button()

    def _draw_header(self) -> None:
        """Draw title and simulation status."""
        arcade.draw_text("FLY-IN", 35, self.height - 45, TEXT_COLOR, 22,
                         bold=True)
        status = "PAUSED" if self.paused else "RUNNING"
        arcade.draw_text(
            f"Turn {min(self.turn + 1, len(self.log))} / {len(self.log)}  "
            f"{status}",
            self.width - 270,
            self.height - 42,
            TEXT_COLOR,
            14,
        )

    def _draw_connections(self) -> None:
        """Draw network edges and highlight drones currently in transit."""
        visible_active = (
            set(self.active_connections) | set(self.transit.values()))
        for connection in self.graph.connections:
            start = self._point(connection.zone_a.name)
            end = self._point(connection.zone_b.name)
            active = connection.name in visible_active
            arcade.draw_line(
                *start, *end, ACTIVE_LINE if active else LINE_COLOR,
                4 if active else 2,
            )
            if active:
                middle = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
                arcade.draw_circle_outline(*middle, 7, ACTIVE_LINE, 2)

    def _label_positions(self) -> dict[str, tuple[float, float]]:
        """Place labels on or under zones"""
        radius = self._radius()
        gap = radius + 13
        labels: dict[str, tuple[float, float]] = {}
        ordered = sorted(
            self.graph.zones.values(),
            key=lambda zone: (
                self._point(zone.name)[1], self._point(zone.name)[0]),
        )
        for index, zone in enumerate(ordered, start=1):
            x, y = self._point(zone.name)
            above = (x, y + gap)
            below = (x, y - gap)
            primary, secondary = (
                (above, below) if index % 2 == 1 else (below, above))
            candidates = [
                primary,
                (primary[0] - gap, primary[1]),
                (primary[0] + gap, primary[1]),
                secondary,
            ]
            chosen = candidates[0]
            for candidate in candidates:
                if all(
                    math.dist(candidate, previous) > 34
                    for previous in labels.values()
                ):
                    chosen = candidate
                    break
            labels[zone.name] = chosen
        return labels

    def _draw_zones(self) -> None:
        """Draw compact zones and separated names."""
        radius = self._radius()
        labels = self._label_positions()
        for zone in self.graph.zones.values():
            x, y = self._point(zone.name)
            arcade.draw_circle_filled(x, y, radius, self._zone_color(zone))
            arcade.draw_circle_outline(x, y, radius + 1, TEXT_COLOR, 2)
            label_x, label_y = labels[zone.name]
            arcade.draw_text(zone.name, label_x, label_y - 5, TEXT_COLOR,
                             11, anchor_x="center")

    def _draw_drones(self) -> None:
        """Draw drones grouped in zones and individually while moving."""
        groups: dict[str, list[int]] = {}
        moving = set(self.animations) | set(self.transit)
        for drone_id, zone_name in self.positions.items():
            if drone_id not in moving:
                groups.setdefault(zone_name, []).append(drone_id)

        for zone_name, drone_ids in groups.items():
            x, y = self._point(zone_name)
            label = (
                str(len(drone_ids))
                if len(drone_ids) > 1 else f"D{drone_ids[0]}")
            self._draw_drone(x, y, label)

        for drone_id in moving:
            x, y = self._drone_position(drone_id)
            self._draw_drone(x, y, f"D{drone_id}")

    def _draw_drone(self, x: float, y: float, label: str) -> None:
        """Draw one compact drone marker."""
        arcade.draw_circle_filled(x, y, DRONE_RADIUS, DRONE_COLOR)
        arcade.draw_circle_outline(x, y, DRONE_RADIUS + 1, BACKGROUND, 2)
        arcade.draw_text(label, x, y - 4, BACKGROUND, 7, anchor_x="center")

    def _draw_replay_button(self) -> None:
        """Draw a replay button anchored to the current window width."""
        x = self.width - 160
        arcade.draw_lbwh_rectangle_filled(x, 25, 120, 40, (45, 55, 70))
        arcade.draw_text(
            "REPLAY", x + 60, 39, TEXT_COLOR, 11, anchor_x="center")
        arcade.draw_text("SPACE: pause   R: replay", 35, 35, TEXT_COLOR, 11)

    @staticmethod
    def _zone_color(zone: Zone) -> tuple[int, int, int]:
        """Return the configured display color for a zone."""
        if zone.is_start:
            return COLORS["cyan"]
        if zone.is_end:
            return COLORS["yellow"]
        if zone.color:
            return COLORS.get(zone.color.lower(), ZONE_COLORS["normal"])
        return ZONE_COLORS[zone.zone_type]


def show_simulation(graph: Graph, log: list[str]) -> None:
    """Open the graphical simulation."""
    Visualizer(graph, log)
    arcade.run()
