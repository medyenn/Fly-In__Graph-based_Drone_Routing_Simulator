*This project has been created as part of the 42 curriculum by mennih.*

# Fly-In

## Description

Fly-In is a Python simulation that routes a fleet of drones from a
`start_hub` to an `end_hub` through a network of connected zones.

The goal is to finish the simulation in as few turns as possible while
respecting:

- zone occupancy limits;
- connection capacities;
- blocked zones;
- restricted zones with two-turn movement;
- priority zones used as a pathfinding tie-break;
- simultaneous movement and waiting.

The project is completely object-oriented and does not use a graph library.
The graph, parser, pathfinding algorithm, scheduler, terminal output,
and optional graphical visualization are implemented directly in Python.

## Project structure

```text
Fly_In/
├── src/
│   ├── __main__.py
│   ├── main.py
│   ├── orchestrator.py
│   ├── parser.py
│   ├── domain.py
│   ├── graph.py
│   ├── pathfinder.py
│   ├── simulator.py
│   └── visualizer.py
├── maps/
│   ├── easy/
│   ├── medium/
│   ├── hard/
│   └── challenger/
├── tests/
├── Makefile
├── requirements.txt
├── .gitignore
└── README.md
```

## Architecture

The application follows a simple flow:

```text
MapParser
    ↓
Graph + Zone + Connection
    ↓
PathFinder
    ↓
Drone paths
    ↓
Simulator
    ↓
Visualizer
```

Each class has one main responsibility:

| Class | Responsibility |
|---|---|
| `Zone` | Store zone data and occupancy |
| `Connection` | Store an edge and transit capacity |
| `Drone` | Store one drone's state and path |
| `Graph` | Store the network and answer adjacency queries |
| `MapParser` | Validate a map file and build the graph |
| `PathFinder` | Find a cheapest route with Dijkstra |
| `Simulator` | Schedule all drones turn by turn |
| `Visualizer` | Display the simulation graphically with Arcade |
| `FlyInApp` | Connect all components |

## Algorithm

### 1. Parsing

`MapParser` reads the map line by line and validates the format.

It checks:

- positive drone count;
- exactly one start and one end;
- unique zone names;
- integer coordinates;
- valid zone types;
- positive capacities;
- known zones in connections;
- duplicate connections;
- valid metadata;
- comments beginning with `#`.

Parsing errors are reported with the line number.

### 2. Pathfinding

`PathFinder` uses a self-written Dijkstra algorithm. It keeps the same
Dijkstra approach for every search, but searches in `(zone, turn)` states
so it can also consider waiting and existing reservations.

The cost of entering a zone is:

- normal: `1`;
- priority: `1`;
- restricted: `2`;
- blocked: impossible.

When two routes have the same cost, the route containing more priority
zones is preferred.

After a path is found, the pathfinder reserves its zone and connection
capacity. It then runs Dijkstra again for the next drone. This naturally
allows drones to use different routes when a previous route is full, or
to wait when using the same route is still the best choice.

The result is therefore a list of paths instead of one path copied to
every drone. The pathfinder stays simple: Dijkstra finds the route,
reservations describe already planned traffic, and the simulator remains
responsible for the final turn-by-turn execution.

### 3. Simulation

`Simulator` is responsible for the multi-drone problem.

For every turn it:

1. completes restricted movements whose arrival turn has been reached;
2. collects the next requested move of each active drone;
3. frees the origin zones of departing drones;
4. resolves proposals in drone-ID order;
5. checks destination and connection capacities;
6. starts restricted movements only when their future destination slot
   is available;
7. makes rejected drones wait;
8. records the movements for that turn.

A restricted movement is committed when it starts and arrives on the
next simulation turn. This represents the movement's two-turn cost:
one turn is spent entering/traversing the connection and the next turn
completes the arrival. The destination slot is reserved when the
movement starts, so the drone cannot be stranded in the connection.

The simulation stops as soon as every drone reaches the end hub.

### Complexity

For one Dijkstra search:

`O((V + E) log V)`

where `V` is the number of zones and `E` is the number of connections.

The simulator processes every drone once per turn, so turn resolution is
approximately `O(D)` apart from graph lookups, where `D` is the number of
drones.

Paths are cached in the `Drone` objects and are not recalculated every
turn.

## Visualization

The project includes a small Arcade graphical view. It is deliberately simple:

- zones are coloured circles using their map metadata when available;
- connections are drawn as lines and active ones are highlighted;
- drones are shown as small labelled circles;
- restricted-zone drones are shown in the middle of their connection;
- the current turn and total turns are displayed.

The simulation starts automatically. Press `SPACE` to pause or resume, and
use `LEFT` / `RIGHT` to step through the turns manually.

Run it with:

```bash
python3 src maps/easy/02_simple_fork.txt --visual
```

Or:

```bash
make gui ARGS="maps/easy/02_simple_fork.txt"
```

Arcade is only a display layer. It does not perform pathfinding or simulation
logic.

## Instructions

### Requirements

- Python 3.10 or later
- `flake8`
- `mypy`

The simulation itself uses only the Python standard library.

### Installation

Create a virtual environment if needed, then:

```bash
make install
```

Or install the development tools directly:

```bash
python3 -m pip install -r requirements.txt
```

### Run

Run a map with:

```bash
make run ARGS="maps/easy/01_linear_path.txt"
```

or:

```bash
python3 src maps/easy/01_linear_path.txt
```

For a plain, non-colored run:

```bash
python3 src --no-color maps/easy/01_linear_path.txt
```

To display the map before the simulation:

```bash
python3 src --map-info maps/easy/01_linear_path.txt
```

To display final statistics:

```bash
python3 src --summary maps/easy/01_linear_path.txt
```

The default output contains only the required movement lines. Map
information and statistics are optional.

### Debug

```bash
make debug ARGS="maps/easy/01_linear_path.txt"
```

### Lint

```bash
make lint
```

This runs the mandatory Flake8 and Mypy checks.

### Clean

```bash
make clean
```

## Testing

The `tests/` directory contains small unit and integration tests for the
parser, pathfinder, simulator, and command-line integration.

Run them with:

```bash
python3 -m unittest discover -s tests -v
```

A useful manual test sequence is:

```bash
make run ARGS="maps/easy/01_linear_path.txt"
make run ARGS="maps/easy/02_simple_fork.txt"
make run ARGS="maps/easy/03_basic_capacity.txt"
make run ARGS="maps/medium/03_priority_puzzle.txt"
```

Then test the harder maps:

```bash
make run ARGS="maps/hard/01_maze_nightmare.txt"
make run ARGS="maps/hard/02_capacity_hell.txt"
make run ARGS="maps/hard/03_ultimate_challenge.txt"
```

The challenger map is optional:

```bash
make run ARGS="maps/challenger/01_the_impossible_dream.txt"
```

The subject gives the following reference targets:

| Map | Target |
|---|---:|
| Linear path | ≤ 6 turns |
| Simple fork | ≤ 8 turns |
| Basic capacity | ≤ 6 turns |
| Dead-end trap | ≤ 12 turns |
| Circular loop | ≤ 15 turns |
| Priority puzzle | ≤ 12 turns |
| Maze nightmare | ≤ 30 turns |
| Capacity hell | ≤ 35 turns |
| Ultimate challenge | ≤ 45 turns |
| Impossible Dream | ≤ 45 turns (optional) |

These are optimization targets, not mandatory grading gates.

## Input format

Example:

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

Zone metadata is optional:

```text
[zone=normal color=blue max_drones=2]
```

Connection metadata is optional:

```text
[max_link_capacity=2]
```

Zone names cannot contain spaces or dashes.

## Output

The required movement format is:

```text
D1-zone
D1-connection
```

Multiple movements in one turn are space-separated:

```text
D1-roof1 D2-corridorA
D1-roof2 D2-tunnelB
D1-goal D2-goal
```

Stationary drones are omitted.

For restricted zones, the connection name is displayed while the drone
is in transit.

## Resources

- 42 Fly-In subject — project requirements and constraints.
- The Fly-In master course included with the project — project
  architecture and implementation roadmap.
- Python documentation — standard library reference.
- Dijkstra's algorithm — fundamental shortest-path algorithm.
- PEP 8 — Python style guidelines.
- PEP 257 — Python docstring conventions.
- Flake8 documentation — static style checking.
- Mypy documentation — static type checking.

### AI usage

AI was used as a development assistant for:

- reviewing the project structure against the subject and roadmap;
- identifying missing integration code;
- discussing parser, pathfinding, scheduling, and testing logic;
- reviewing implementation decisions and edge cases;
- helping prepare project documentation.

All project code should be understood, reviewed, tested, and defended by
the student. The subject explicitly requires critical checking of
AI-generated material and peer review.
