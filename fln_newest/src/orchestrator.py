"""Application coordinator for the Fly-In simulation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from domain import Drone
from parser import MapParseError, MapParser
from pathfinder import PathFinder
from simulator import SimulationError, Simulator
from visualizer import show_simulation


class FlyInApp:
    """Coordinate parsing, routing, simulation, and display."""

    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args

    @classmethod
    def from_argv(cls, argv: Sequence[str] | None = None) -> "FlyInApp":
        """Build the application from command-line arguments."""
        return cls(cls._parse_args(argv))

    @staticmethod
    def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
        """Parse the small command-line interface."""
        parser = argparse.ArgumentParser(
            description="Route a fleet of drones through a Fly-In map."
        )
        parser.add_argument("map", type=Path, help="path to the map file")
        parser.add_argument(
            "--no-color",
            action="store_true",
            help="disable colored terminal output",
        )
        parser.add_argument(
            "--map-info",
            action="store_true",
            help="show the map before the simulation",
        )
        parser.add_argument(
            "--summary",
            action="store_true",
            help="show simulation statistics after the movements",
        )
        parser.add_argument(
            "--visual",
            action="store_true",
            help="show the simulation in an Arcade window",
        )
        return parser.parse_args(argv)

    def run(self) -> int:
        """Run the complete Fly-In application."""
        try:
            graph, nb_drones = MapParser(self.args.map).parse()
            pathfinder = PathFinder(graph)
            start = graph.start
            end = graph.end
            if start is None or end is None:
                raise MapParseError("start or end hub is missing", 0)

            paths = pathfinder.get_drones_paths(nb_drones)
            if len(paths) != nb_drones:
                print("Error: no valid paths for all drones.")
                return 1

            drones = [
                Drone(i, start, paths[i - 1])
                for i in range(1, nb_drones + 1)
            ]
            simulator = Simulator(graph, drones)
            log = simulator.run()

            for line in log:
                print(line)
            if self.args.summary:
                print(f"Total turns: {len(log)}")
            if self.args.visual:
                show_simulation(graph, log)
            return 0
        except MapParseError as exc:
            print(exc, file=sys.stderr)
            return 1
        except (OSError, SimulationError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
