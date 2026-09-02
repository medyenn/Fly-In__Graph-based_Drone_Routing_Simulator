"""Arcade visualizer for the Fly-In simulation."""

from __future__ import annotations
import math
import arcade

from graph import Graph

WIDTH = 1400
HEIGHT = 750
MARGIN = 120
MOVE_R = 12
MOVE_TIME = 0.6
HOLD_TIME = 0.9
PAN_SPEED = 350
ROTATION = math.pi / 2

BG = (16, 20, 28)
LINE = (70, 76, 90)
LINE_ACTIVE = (99, 179, 237)
TEXT = (230, 233, 240)
WHITE = (245, 246, 250)

TYPE_COLOR = {
    "normal": (120, 126, 138),
    "priority": (52, 211, 153),
    "restricted": (167, 139, 250),
    "blocked": (60, 64, 74),
}
NAMED_COLOR = {
    "red": (239, 68, 68), "green": (34, 197, 94), "blue": (59, 130, 246),
    "yellow": (250, 204, 21), "orange": (249, 115, 22),
    "purple": (168, 85, 247), "gray": (120, 126, 138),
    "grey": (120, 126, 138), "cyan": (45, 212, 191),
}
START_COLOR = (56, 189, 248)
END_COLOR = (250, 204, 21)

ARROWS = {
    arcade.key.LEFT: (-1, 0), arcade.key.RIGHT: (1, 0),
    arcade.key.UP: (0, 1), arcade.key.DOWN: (0, -1),
}


def _ngon_point(
    cx: float, cy: float, radius: float, angle: float, sides: int,
    rotation: float = ROTATION,
) -> tuple[float, float]:
    """Point on a regular polygon's boundary at a given angle from its
    center (angle need not land on a vertex)."""
    seg = 2 * math.pi / sides
    local = ((angle - rotation + seg / 2) % seg) - seg / 2
    r = radius * math.cos(seg / 2) / math.cos(local)
    return cx + r * math.cos(angle), cy + r * math.sin(angle)


def _ngon_vertices(
    cx: float, cy: float, radius: float, sides: int,
    rotation: float = ROTATION,
) -> list[tuple[float, float]]:
    """The `sides` corner points of a regular polygon."""
    step = 2 * math.pi / sides
    return [
        _ngon_point(cx, cy, radius, rotation + i * step, sides, rotation)
        for i in range(sides)
    ]


class _TextPool:
    """Reuse arcade.Text objects instead of calling arcade.draw_text() every
    frame, which arcade flags as too slow for per-frame rendering."""

    def __init__(self) -> None:
        self._items: dict[str, arcade.Text] = {}

    def draw(
        self, key: str, text: str, x: float, y: float,
        color: tuple[int, int, int], size: int,
        anchor_x: str = "left", bold: bool = False,
    ) -> None:
        item = self._items.get(key)
        if item is None:
            item = arcade.Text(
                text, x, y, color, size, anchor_x=anchor_x, bold=bold)
            self._items[key] = item
        else:
            item.text, item.x, item.y, item.color = text, x, y, color
        item.draw()


class Visualizer(arcade.Window):
    """Play back a Fly-In simulation log over its graph."""

    def __init__(self, graph: Graph, log: list[str]) -> None:
        super().__init__(WIDTH, HEIGHT, "Fly-In", resizable=True)
        arcade.set_background_color(BG)
        self.graph = graph
        self.log = log
        self.zoom, self.origin = self._fit()
        self.cam = [0.0, 0.0]
        self.keys_held: set[int] = set()

        self.turn = 0
        self.timer = 0.0
        self.holding = False
        self.paused = False

        self.zone_of = self._start_positions()
        self.pos = {d: self._layout(z) for d, z in self.zone_of.items()}
        self.moves: dict[
            int, tuple[tuple[float, float], tuple[float, float], str | None]
        ] = {}
        self.midway: set[int] = set()
        self.edge_of: dict[int, tuple[str, str]] = {}
        self.zone_r = 20
        self.labels = _TextPool()
        self._zone_number = {
            name: i for i, name in enumerate(self.graph.zones, 1)}

    def _fit(self) -> tuple[tuple[float, float], tuple[float, float]]:
        """Independent X/Y scales that stretch the map to fill the window,
        so zones sit as far apart as the window allows on each axis."""
        zones = list(self.graph.zones.values())
        xs = [z.x for z in zones] or [0]
        ys = [z.y for z in zones] or [0]
        span_x = max(max(xs) - min(xs), 1)
        span_y = max(max(ys) - min(ys), 1)
        sx = (self.width - 2 * MARGIN) / span_x
        sy = (self.height - 2 * MARGIN) / span_y
        offset = (MARGIN - min(xs) * sx, MARGIN - min(ys) * sy)
        return (sx, sy), offset

    def _layout(self, zone_name: str) -> tuple[float, float]:
        """World position of a zone, before the camera pan is applied."""
        zone = self.graph.zones[zone_name]
        sx, sy = self.zoom
        ox, oy = self.origin
        return zone.x * sx + ox, zone.y * sy + oy

    def _place(self, x: float, y: float) -> tuple[float, float]:
        """Apply the current camera pan to a world position."""
        return x + self.cam[0], y + self.cam[1]

    def _screen_pos(self, zone_name: str) -> tuple[float, float]:
        """Screen position of a zone: world layout plus the camera pan."""
        return self._place(*self._layout(zone_name))

    def _start_positions(self) -> dict[int, str]:
        """Every drone begins the replay parked at the start hub."""
        if self.graph.start is None:
            return {}
        highest = 0
        for line in self.log:
            for token in line.split():
                highest = max(highest, int(token[1:].split("-", 1)[0]))
        return {d: self.graph.start.name for d in range(1, highest + 1)}

    def _start_turn(self) -> None:
        """Begin animating every drone movement listed in this turn."""
        self.moves.clear()
        for token in self.log[self.turn].split():
            drone_id = int(token[1:].split("-", 1)[0])
            target = token.split("-", 1)[1]
            start = self.pos[drone_id]
            if target in self.graph.zones:
                self.moves[drone_id] = (start, self._layout(target), target)
                self.midway.discard(drone_id)
            else:
                a, b = target.split("-", 1)
                pa, pb = self._layout(a), self._layout(b)
                mid = ((pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2)
                self.moves[drone_id] = (start, mid, None)
                self.midway.add(drone_id)
                self.edge_of[drone_id] = (a, b)

    def _finish_turn(self) -> None:
        """Land every animated drone and advance to the next turn."""
        for drone_id, (_, end, target) in self.moves.items():
            self.pos[drone_id] = end
            if target is not None:
                self.zone_of[drone_id] = target
        self.moves.clear()
        self.turn += 1
        self.timer = 0.0
        self.holding = False

    def _arrived(self) -> dict[int, str]:
        """Drones that finished animating into a zone this turn: they merge
        into that zone's wedge instead of floating above it."""
        if not self.holding:
            return {}
        return {
            drone_id: target for drone_id, (_, _, target) in self.moves.items()
            if target is not None
        }

    def _reset(self) -> None:
        """Restart the replay from the very first turn."""
        self.turn = 0
        self.timer = 0.0
        self.holding = False
        self.paused = False
        self.zone_of = self._start_positions()
        self.pos = {d: self._layout(z) for d, z in self.zone_of.items()}
        self.moves.clear()
        self.midway.clear()

    def _drone_screen_pos(self, drone_id: int) -> tuple[float, float]:
        """Interpolated screen position of a drone mid-animation."""
        start, end, _ = self.moves[drone_id]
        t = 1.0 if self.holding else min(self.timer / MOVE_TIME, 1.0)
        return self._place(
            start[0] + (end[0] - start[0]) * t,
            start[1] + (end[1] - start[1]) * t,
        )

    def on_update(self, dt: float) -> None:
        for key in self.keys_held:
            dx, dy = ARROWS[key]
            self.cam[0] += dx * PAN_SPEED * dt
            self.cam[1] += dy * PAN_SPEED * dt

        if self.paused or self.turn >= len(self.log):
            return

        if not self.moves and not self.holding:
            self._start_turn()
        self.timer += dt
        if not self.holding and self.timer >= MOVE_TIME:
            self.timer, self.holding = 0.0, True
        elif self.holding and self.timer >= HOLD_TIME:
            self._finish_turn()

    def on_key_press(self, key: int, modifiers: int) -> None:
        if key in ARROWS:
            self.keys_held.add(key)
        elif key == arcade.key.SPACE:
            self.paused = not self.paused
        elif key == arcade.key.R:
            self._reset()

    def on_key_release(self, key: int, modifiers: int) -> None:
        self.keys_held.discard(key)

    def on_resize(self, width: int, height: int) -> None:
        super().on_resize(width, height)
        self.zone_r = (
            ((self.width / (2500 + self.width))
                + (self.height / (1500 + self.height))) * 20)
        self.zoom, self.origin = self._fit()

    def on_draw(self) -> None:
        self.clear()
        self._draw_connections()
        self._draw_zones()
        self._draw_moving_drones()
        self._draw_hud()

    def _draw_connections(self) -> None:
        """Draw every edge, highlighting the ones currently in use."""
        active = {
            frozenset(self.edge_of[d])
            for d in self.midway if d in self.edge_of
        }
        for conn in self.graph.connections:
            a = self._screen_pos(conn.zone_a.name)
            b = self._screen_pos(conn.zone_b.name)
            is_active = (
                frozenset((conn.zone_a.name, conn.zone_b.name)) in active)
            color, width = (LINE_ACTIVE, 3) if is_active else (LINE, 2)
            arcade.draw_line(*a, *b, color, width)

    def _name_label_y(self, y: float, idx: int) -> float:
        """Odd-numbered zones (by file order) get their name above; even
        get it below, so neighboring labels don't collide."""
        offset = self.zone_r + 18
        return y + offset if idx % 2 else y - offset

    def _draw_zones(self) -> None:
        """Draw every zone as a hexagon (pentagon for start/end): a type
        letter when empty, drone wedges once occupied."""
        moving = set(self.moves)
        arrived = self._arrived()
        for name, idx in self._zone_number.items():
            zone = self.graph.zones[name]
            x, y = self._screen_pos(name)
            ring = self._zone_color(zone)
            sides = 5 if (zone.is_start or zone.is_end) else 6
            arcade.draw_polygon_outline(
                _ngon_vertices(x, y, self.zone_r + 2, sides), ring, 2)

            occupants = sorted(
                [
                    d
                    for d, z in self.zone_of.items()
                    if z == name and d not in moving]
                + [d for d, z in arrived.items() if z == name]
            )
            if occupants:
                self._draw_occupants(x, y, sides, occupants)
            else:
                fill = tuple(max(c // 5, 20) for c in ring)
                arcade.draw_polygon_filled(
                    _ngon_vertices(x, y, self.zone_r, sides), fill)
                letter = ("S" if zone.is_start else
                          "E" if zone.is_end else
                          zone.zone_type[0].upper())
                self.labels.draw(f"letter-{name}", letter, x, y - 8, ring, 16,
                                 anchor_x="center", bold=True)

            self.labels.draw(
                f"name-{name}", name, x, self._name_label_y(y, idx),
                TEXT, 9, anchor_x="center")

    def _draw_occupants(
        self, x: float, y: float, sides: int, drones: list[int]
    ) -> None:
        """Split the zone polygon into one wedge per occupying drone."""
        n = len(drones)
        step = 2 * math.pi / n
        for i in range(n):
            a0, a1 = i * step, (i + 1) * step
            samples = max(2, int(math.degrees(step) / 10))
            arc = [
                _ngon_point(
                    x, y, self.zone_r, a0 + (a1 - a0) * k / samples, sides)
                for k in range(samples + 1)
            ]
            arcade.draw_polygon_filled([(x, y), *arc], WHITE)
        for i in range(n if n > 1 else 0):
            ax, ay = _ngon_point(x, y, self.zone_r, i * step, sides)
            arcade.draw_line(x, y, ax, ay, BG, 2)
        if n <= 6:
            r = self.zone_r * 0.55 if n > 1 else 0
            for i, drone_id in enumerate(drones):
                mid = (i + 0.5) * step
                self.labels.draw(
                    f"d{drone_id}", f"D{drone_id}",
                    x + r * math.cos(mid), y + r * math.sin(mid) - 6,
                    BG, 10, anchor_x="center", bold=True,
                )

    def _draw_moving_drones(self) -> None:
        """Draw drones still traveling: not yet merged into a zone's wedge."""
        arrived = self._arrived()
        for drone_id in self.moves:
            if drone_id in arrived:
                continue
            x, y = self._drone_screen_pos(drone_id)
            arcade.draw_circle_filled(x, y, MOVE_R, WHITE)
            arcade.draw_circle_outline(x, y, MOVE_R + 1, BG, 2)
            self.labels.draw(f"d{drone_id}", f"D{drone_id}", x, y - 5, BG, 9,
                             anchor_x="center", bold=True)

    def _draw_hud(self) -> None:
        self.labels.draw(
            "title", "FLY-IN", 30, self.height - 40, TEXT, 20, bold=True)
        status = "paused" if self.paused else "running"
        self.labels.draw(
            "status",
            f"turn {min(self.turn + 1, len(self.log))}/{len(self.log)} "
            f" {status}", self.width - 260, self.height - 38, TEXT, 13,)
        self.labels.draw(
            "controls", "arrows: pan camera   space: pause   r: replay",
            30, 28, TEXT, 12)

    @staticmethod
    def _zone_color(zone) -> tuple[int, int, int]:
        """Ring color: role first (start/end), then custom color, then type."""
        if zone.is_start:
            return START_COLOR
        if zone.is_end:
            return END_COLOR
        if zone.color:
            return NAMED_COLOR.get(zone.color.lower(), TYPE_COLOR["normal"])
        return TYPE_COLOR[zone.zone_type]


def show_simulation(graph: Graph, log: list[str]) -> None:
    """Open the graphical simulation."""
    Visualizer(graph, log)
    arcade.run()
