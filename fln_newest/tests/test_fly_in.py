import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from domain import Drone
from parser import MapParseError, MapParser
from pathfinder import PathFinder
from simulator import Simulator


ROOT = Path(__file__).parents[1]


class FlyInTests(unittest.TestCase):
    def test_parser(self) -> None:
        graph, count = MapParser(
            ROOT / "maps/easy/02_simple_fork.txt"
        ).parse()
        self.assertEqual(count, 4)
        self.assertEqual(len(graph.zones), 5)
        self.assertEqual(len(graph.connections), 5)
        self.assertEqual(graph.start.name, "start")
        self.assertEqual(graph.end.name, "goal")

    def test_pathfinder_avoids_blocked_zone(self) -> None:
        graph, _ = MapParser(
            ROOT / "maps/hard/01_maze_nightmare.txt"
        ).parse()
        path = PathFinder(graph).find_path("start", "goal")
        self.assertIsNotNone(path)
        assert path is not None
        self.assertNotIn("dead_end1", path)

    def test_simulation_finishes(self) -> None:
        graph, count = MapParser(
            ROOT / "maps/easy/03_basic_capacity.txt"
        ).parse()
        path = PathFinder(graph).find_path("start", "goal")
        self.assertIsNotNone(path)
        assert path is not None
        start = graph.start
        self.assertIsNotNone(start)
        assert start is not None
        drones = [
            Drone(i, start, path.copy())
            for i in range(1, count + 1)
        ]
        log = Simulator(graph, drones).run()
        self.assertEqual(len(log), 4)
        self.assertTrue(all(drone.has_arrived() for drone in drones))

    def test_invalid_map_reports_line(self) -> None:
        content = (
            "nb_drones: 2\n"
            "start_hub: start 0 0\n"
            "hub: middle 1 0 [zone=wrong]\n"
            "end_hub: goal 2 0\n"
        )
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".txt", delete=False
        ) as handle:
            handle.write(content)
            path = Path(handle.name)
        try:
            with self.assertRaises(MapParseError) as context:
                MapParser(path).parse()
            self.assertIn("line 3", str(context.exception))
        finally:
            path.unlink()

    def test_cli_integration(self) -> None:
        from main import main

        old_argv = sys.argv
        sys.argv = [
            "fly_in",
            "--no-color",
            str(ROOT / "maps/easy/01_linear_path.txt"),
        ]
        stdout = io.StringIO()
        try:
            with redirect_stdout(stdout):
                code = main()
        finally:
            sys.argv = old_argv
        self.assertEqual(code, 0)
        self.assertIn("D1-goal", stdout.getvalue())


    def test_pathfinder_uses_multiple_paths(self) -> None:
        graph, count = MapParser(
            ROOT / "maps/easy/02_simple_fork.txt"
        ).parse()
        paths = PathFinder(graph).get_drones_paths(count)
        self.assertEqual(len(paths), count)
        self.assertTrue(any("path_a" in path for path in paths))
        self.assertTrue(any("path_b" in path for path in paths))

    def test_multipath_improves_simple_fork(self) -> None:
        graph, count = MapParser(
            ROOT / "maps/easy/02_simple_fork.txt"
        ).parse()
        paths = PathFinder(graph).get_drones_paths(count)
        start = graph.start
        self.assertIsNotNone(start)
        assert start is not None
        drones = [
            Drone(i, start, paths[i - 1])
            for i in range(1, count + 1)
        ]
        log = Simulator(graph, drones).run()
        self.assertEqual(len(log), 4)


if __name__ == "__main__":
    unittest.main()
