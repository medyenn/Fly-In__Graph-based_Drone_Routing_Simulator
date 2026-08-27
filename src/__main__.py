from orchestrator import FlyInApp
from parser import MapParser
from pathfinder import PathFinder
from simulator import Simulator
from visualizer import Visualizer


def main():
    FlyInApp.parse_args()

    try:
        MapParser.parse()
    except Exception:
        exit(1)

    PathFinder.find_path()

    Simulator.run()

    Visualizer.render_turn()

    Visualizer.render_map()


if __name__ == '__main__':
    main()
