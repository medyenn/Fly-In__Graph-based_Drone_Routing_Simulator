"""Fly-In entry point: parses the CLI, then runs the full pipeline."""

from __future__ import annotations
import argparse
import sys
from pathlib import Path
from typing import Sequence

from graph import Drone
from parser import MapParseError, MapParser
from pathfinder import PathFinder
from simulator import SimulationError, Simulator
from visualizer import show_simulation


class Pipeline:
    """Parse a map, route the drones, run the simulation, and show it."""

    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args

    @classmethod
    def from_argv(cls, argv: Sequence[str] | None = None) -> "Pipeline":
        """Build the pipeline from command-line arguments."""
        parser = argparse.ArgumentParser(
            description="Route a fleet of drones through a Fly-In map."
        )
        parser.add_argument("map", type=Path, help="path to the map file")
        parser.add_argument(
            "--no-color",
            action="store_true", help="disable colored terminal output")
        parser.add_argument(
            "--map-info", action="store_true",
            help="show the map before the simulation")
        parser.add_argument(
            "--summary",
            action="store_true",
            help="show simulation statistics after the movements")
        parser.add_argument(
            "--visual",
            action="store_true",
            help="show the simulation in an Arcade window")
        return cls(parser.parse_args(argv))

    def run(self) -> int:
        """Run the complete Fly-In pipeline."""
        try:
            graph, nb_drones = MapParser(self.args.map).parse()
            if graph.start is None or graph.end is None:
                raise MapParseError("start or end hub is missing", 0)

            paths = PathFinder(graph).get_drones_paths(nb_drones)
            if len(paths) != nb_drones:
                print("Error: No valid paths for all drones.")
                return 1

            drones = [
                Drone(i, graph.start, paths[i - 1])
                for i in range(1, nb_drones + 1)
            ]
            log = Simulator(graph, drones).run()

            for line in log:
                print(line)
            if self.args.summary:
                print(f"Total turns: {len(log)}")
            if self.args.visual:
                show_simulation(graph, log)
            return 0
        except MapParseError as e:
            print(e, file=sys.stderr)
            return 1
        except (OSError, SimulationError) as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1


def main() -> int:
    """Create the pipeline and run it."""
    return Pipeline.from_argv().run()


if __name__ == "__main__":
    main()
