*This project has been created as part of the 42 curriculum by mennih.*

# Fly-In

Fly-In routes a fleet of drones from a `start_hub` to an `end_hub` through a
network of connected zones, minimizing total simulation turns while
respecting:

- zone occupancy limits;
- connection capacities;
- blocked zones;
- restricted zones (2-turn movement);
- priority zones (preferred on equal-cost routes).

The project is fully object-oriented and written in plain Python — no graph
library, no external pathfinding package. The only third-party dependency is
`arcade`, used purely for the visualization window.

## Project structure

```text
FLY_IN/
├── main.py          # CLI entry point, wires the pipeline together
├── graph.py          # Zone, Connection, Drone, TransitState, Graph
├── parser.py         # MapParser: text file -> validated Graph
├── pathfinder.py      # PathFinder: reservation-aware Dijkstra
├── simulator.py       # Simulator: turn-by-turn scheduling engine
├── visualizer.py      # Arcade window + terminal summary
├── maps/
│   ├── easy/
│   ├── medium/
│   ├── hard/
│   └── challenger/
├── requirements.txt
├── Makefile
├── .gitignore
└── README.md
```

## Pipeline

```text
MapParser.parse()
    ↓
Graph (Zone + Connection)
    ↓
PathFinder.get_drones_paths()
    ↓
Drone objects
    ↓
Simulator.run()
    ↓
terminal summary + Arcade visualizer
```

| Class | Responsibility |
|---|---|
| `Zone` | Identity, position, type, and live occupancy of one node |
| `Connection` | A bidirectional edge and its transit capacity |
| `Drone` | One agent's current position and assigned path |
| `Graph` | Owns every zone/connection, answers adjacency queries |
| `MapParser` | Validates a map file and builds the `Graph` |
| `PathFinder` | Finds one collision-aware route per drone with Dijkstra |
| `Simulator` | Schedules every drone, turn by turn, under live capacity |
| `Visualizer` | Replays the simulation in an Arcade window |

## Algorithm

### Parsing

`MapParser` reads the map line by line and validates it fully before a
simulation ever runs: drone count, exactly one start/end hub, unique zone
names and coordinates, valid zone types, positive capacities, known zones in
every connection, no duplicate connections, and a fully connected graph.
Parsing errors are reported with their line number.

### Pathfinding

`PathFinder` runs a self-written Dijkstra over a *time-expanded* graph: every
search state is `(zone, turn)`, not just `zone`. Entering a zone costs:

- `normal` / `priority`: 1 turn;
- `restricted`: 2 turns;
- `blocked`: never (no edge exists).

On equal-cost routes, the one passing through more `priority` zones wins.
Each drone is routed in turn against a shared reservation table built from
every drone routed before it — this is what lets multiple drones reach the
goal on distinct, non-colliding routes (or the same route safely staggered in
time) without ever needing to re-plan one another.

### Simulation

`Simulator` is the real-time authority. Every turn it:

1. completes any restricted move whose arrival turn has been reached;
2. asks every remaining drone what it wants to do next;
3. resolves those requests in drone-ID order, checking live zone and
   connection capacity;
4. commits a restricted move as soon as it starts, reserving its destination
   slot so it can't be double-booked while the drone is mid-flight;
5. sends a rejected drone back to waiting — it simply retries next turn.

The simulation stops the instant every drone has reached the end hub.

### Complexity

One Dijkstra search: `O((V + E) log V)`, where `V` is the number of zones and
`E` the number of connections. Turn resolution is `O(D)` per turn beyond
graph lookups, where `D` is the number of drones — each drone's route is
computed once and only walked forward, never recomputed.

## Visualization

Running the program opens an Arcade window by default: zones are hexagons
(pentagons for start/end), colored by type or by their map metadata; an
occupied zone splits into one wedge per drone; connections currently in use
are highlighted.

**Controls**

| Key | Effect |
|---|---|
| `space` | pause / resume |
| `←` / `→` | while paused, step to the previous / next turn |
| mouse drag | pan the camera |
| `r` | replay from the first turn |

Alongside the window, a short summary is always printed to the terminal:

```text
Drones: 4
Turns: 6
Restricted-zone crossings: 2
Priority-zone visits: 3
```

Pass `--no-visual` to skip the window entirely and only print that summary —
useful in a headless environment.

## Installation

```bash
python3 -m pip install -r requirements.txt
```

or:

```bash
make install
```

## Usage

```bash
python3 main.py maps/easy/01_linear_path.txt
```

Terminal-only:

```bash
python3 main.py --no-visual maps/easy/01_linear_path.txt
```

Via the Makefile:

```bash
make run ARGS="maps/easy/01_linear_path.txt"
make debug ARGS="maps/easy/01_linear_path.txt"   # run under pdb
make lint                                         # flake8 + mypy
make clean                                        # remove caches
```

## Input format

```text
nb_drones: 5

start_hub: start 0 0 [color=green]
end_hub: goal 10 10 [color=yellow]

hub: roof1 3 4 [zone=restricted color=red]
hub: corridorA 4 3 [zone=priority color=green max_drones=2]

connection: start-roof1
connection: start-corridorA [max_link_capacity=2]
connection: roof1-goal
connection: corridorA-goal
```

Zone metadata (`[zone=... color=... max_drones=...]`) and connection metadata
(`[max_link_capacity=...]`) are both optional and default to
`zone=normal`, no color, `max_drones=1`, and `max_link_capacity=1`. Zone names
cannot contain spaces or dashes. Lines starting with `#` are comments.

## Resources

- 42 Fly-In subject — project requirements and constraints.
- Python standard library documentation.
- Dijkstra's algorithm.
- The Arcade library documentation.
- PEP 8 / PEP 257 — style and docstring conventions.
- Flake8 / Mypy documentation — static checking.

### AI usage

AI was used as a development assistant for reviewing the project against the
subject, identifying integration gaps, discussing parser/pathfinding/
scheduling logic, reviewing edge cases, and preparing this documentation.
