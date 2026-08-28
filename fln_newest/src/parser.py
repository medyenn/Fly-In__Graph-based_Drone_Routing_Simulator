"""Parser for Fly-In map description files. Turns the map's
text format into a validated Graph and drone count."""

from __future__ import annotations

from pathlib import Path
from typing import NoReturn

from domain import Connection, Zone
from graph import Graph, GraphError

ALLOWED_ZONE_TYPES = {"normal", "priority", "restricted", "blocked"}
ZONE_METADATA_KEYS = {"zone", "color", "max_drones"}
CONNECTION_METADATA_KEYS = {"max_link_capacity"}
ZONE_PREFIXES = ("start_hub:", "end_hub:", "hub:")


class MapParseError(Exception):
    """Raised when a map file line is structurally or semantically invalid."""

    def __init__(self, message: str, line_number: int) -> None:
        self.message = message
        self.line_number = line_number
        super().__init__(f"Error at line {line_number}: {message}")


class MapParser:
    """Turn a Fly-In map text file into a validated Graph and drone count."""

    def __init__(self, filepath: str | Path) -> None:
        self.map_path = Path(filepath)
        self.graph = Graph()
        self.nb_drones = 0
        self.line_number = 0
        self.drone_count_seen = False
        self.start_seen = False
        self.end_seen = False
        self.connection_keys: set[frozenset[str]] = set()

    def parse(self) -> tuple[Graph, int]:
        """Read map_path fully; return (graph, nb_drones) or raise."""
        with self.map_path.open(encoding="utf-8") as handle:
            for self.line_number, raw_line in enumerate(handle, start=1):
                line = self.strip_comment(raw_line)
                if line:
                    self.dispatch_line(line)

        if not self.drone_count_seen:
            self.error("missing required 'nb_drones:' line")
        if not self.start_seen:
            self.error("map must define exactly one start_hub")
        if not self.end_seen:
            self.error("map must define exactly one end_hub")

        return self.graph, self.nb_drones

    def dispatch_line(self, line: str) -> None:
        """Route one non-empty, comment-stripped line to its handler."""
        if line.startswith("nb_drones:"):
            self.nb_drones = self.parse_drone_count(line)
            self.drone_count_seen = True
            return

        if not self.drone_count_seen:
            self.error(
                "the first instruction in the map must be "
                "'nb_drones: <count>'"
            )

        for prefix in ZONE_PREFIXES:
            if line.startswith(prefix):
                kind = prefix[:-1]
                self.parse_zone_line(line[len(prefix):], kind)
                return

        if line.startswith("connection:"):
            self.parse_connection_line(line[len("connection:"):])
            return

        self.error(f"unrecognized line type: '{line}'")

    def strip_comment(self, line: str) -> str:
        """Drop everything from '#' onward, then strip whitespace."""
        return line.split("#", 1)[0].strip()

    def parse_drone_count(self, line: str) -> int:
        """Parse and validate the 'nb_drones: <int>' line."""
        _, _, value = line.partition(":")
        return self.validate_positive_int(value.strip(), "nb_drones")

    def parse_zone_line(self, remainder: str, kind: str) -> None:
        """Parse a start_hub/end_hub/hub line body (after the prefix)."""
        head, meta_raw = self.split_metadata(remainder)
        tokens = head.split()
        if len(tokens) != 3:
            self.error("expected '<name> <x> <y>' after zone prefix")
        name, x_str, y_str = tokens

        if "-" in name:
            self.error(f"zone name '{name}' must not contain '-'")
        if name in self.graph.zones:
            self.error(f"duplicate zone name '{name}'")

        x = self.validate_integer(x_str, "x coordinate")
        y = self.validate_integer(y_str, "y coordinate")

        metadata = self.parse_metadata(meta_raw, ZONE_METADATA_KEYS)

        zone_type = metadata.get("zone", "normal")
        self.validate_zone_type(zone_type)

        max_drones_raw = metadata.get("max_drones", "1")
        max_drones: int | None = self.validate_positive_int(
            max_drones_raw, "max_drones"
        )
        color = metadata.get("color")

        if kind == "start_hub":
            if self.start_seen:
                self.error("only one start_hub is allowed")
            self.start_seen = True
            max_drones = None
        elif kind == "end_hub":
            if self.end_seen:
                self.error("only one end_hub is allowed")
            self.end_seen = True
            max_drones = None

        zone = Zone(
            name=name,
            x=x,
            y=y,
            zone_type=zone_type,
            color=color,
            max_drones=max_drones,
        )
        self.graph.add_zone(zone)
        try:
            if kind == "start_hub":
                self.graph.start = zone
            elif kind == "end_hub":
                self.graph.end = zone
        except GraphError as exc:
            self.error(str(exc))

    def parse_connection_line(self, remainder: str) -> None:
        """Parse a 'connection: <a>-<b> [metadata]' line body."""
        head, meta_raw = self.split_metadata(remainder)

        if head.count("-") != 1:
            self.error("expected 'connection: <name1>-<name2>'")
        name_a, name_b = (part.strip() for part in head.split("-", 1))

        if name_a == name_b:
            self.error(f"connection cannot link '{name_a}' to itself")
        if name_a not in self.graph.zones:
            self.error(f"connection references unknown zone '{name_a}'")
        if name_b not in self.graph.zones:
            self.error(f"connection references unknown zone '{name_b}'")

        key = frozenset({name_a, name_b})
        if key in self.connection_keys:
            self.error(f"connection '{name_a}-{name_b}' already defined")
        self.connection_keys.add(key)

        metadata = self.parse_metadata(meta_raw, CONNECTION_METADATA_KEYS)
        capacity = self.validate_positive_int(
            metadata.get("max_link_capacity", "1"), "max_link_capacity"
        )

        connection = Connection(
            zone_a=self.graph.zones[name_a],
            zone_b=self.graph.zones[name_b],
            max_link_capacity=capacity,
        )
        self.graph.add_connection(connection)

    def split_metadata(self, remainder: str) -> tuple[str, str]:
        """Split 'head [key=value ...]' into (head, raw_metadata_or_empty)."""
        start = remainder.find("[")
        if start == -1:
            return remainder.strip(), ""
        if not remainder.rstrip().endswith("]"):
            self.error("unterminated metadata block, missing ']'")
        end = remainder.rfind("]")
        return remainder[:start].strip(), remainder[start + 1:end].strip()

    def parse_metadata(
        self, raw: str, allowed_keys: set[str]
    ) -> dict[str, str]:
        """Parse a '[key=value ...]' body, enforcing allowed_keys."""
        metadata: dict[str, str] = {}
        if not raw:
            return metadata

        for token in raw.split():
            if token.count("=") != 1:
                self.error(f"malformed metadata token '{token}'")
            key, value = token.split("=", 1)
            if key not in allowed_keys:
                self.error(
                    f"unknown metadata key '{key}' for this line type"
                )
            if key in metadata:
                self.error(f"duplicate metadata key '{key}'")
            metadata[key] = value

        return metadata

    def validate_zone_type(self, value: str) -> str:
        """Ensure value is one of the four legal zone types."""
        if value not in ALLOWED_ZONE_TYPES:
            allowed = ", ".join(sorted(ALLOWED_ZONE_TYPES))
            self.error(f"'zone' must be one of: {allowed} (got '{value}')")
        return value

    def validate_integer(self, value: str, field_name: str) -> int:
        """Parse value as an int, or raise naming field_name."""
        try:
            return int(value)
        except ValueError:
            self.error(f"{field_name} must be an integer (got '{value}')")

    def validate_positive_int(self, value: str, field_name: str) -> int:
        """Parse value as a strictly positive int, or raise."""
        parsed = self.validate_integer(value, field_name)
        if parsed <= 0:
            self.error(
                f"{field_name} must be a positive integer (got {parsed})"
            )
        return parsed

    def error(self, message: str) -> NoReturn:
        """Raise MapParseError with the current line number attached."""
        raise MapParseError(message, self.line_number)
