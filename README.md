<div align="center">

# 🚁 Fly-In

*A Drone Routing & Discrete-Event Simulation Engine*

---

*This project has been created as part of the 42 curriculum by **ENNEEX***

</div>

---

## 📖 Overview

**Fly-In** is an object-oriented, fully type-safe Python routing and discrete-event simulation engine. It models and optimizes the navigation of a fleet of autonomous drones traveling from a single start hub to a destination hub across a network of connected zones.

The primary objective is to route all drones from start to finish in the **fewest possible simulation turns**. The engine processes complex spatial constraints and dynamic zone behaviors:

### 🎯 Core Features

| Feature | Description |
|---------|-------------|
| **Zone Capacities** | Enforces dynamic limits on maximum concurrent occupancy per node (default: 1) |
| **Link Capacities** | Enforces edge traversal limits for drones moving simultaneously between zones |
| **Zone Types** | `normal` (1-turn) • `priority` (1-turn preferred) • `restricted` (2-turn) • `blocked` (inaccessible) |
| **Conflict Prevention** | Real-time capacity updates to prevent deadlocks |

---

## Instructions

### Prerequisites

- **Python:** Version 3.10 or later
- **Static Analysis Tools:** `flake8` and `mypy`
- **Package Manager:** `pip`, `uv`, `pipx`, or standard `venv` environment

### Installation

Install project dependencies using the provided Makefile:

```bash
make install
```

### Execution

Run the main simulation with a map file:

```bash
make run MAP=maps/easy_01.txt
```
Run in debug mode using Python's built-in debugger (pdb):

```bash
make debug MAP=maps/easy_01.txt
```

### Code Quality & Maintenance

This project adheres strictly to the flake8 coding standard and static type checking:

*Standard Linting: Runs flake8 and mypy checks:*

```bash
make lint
```
*Strict Type Checking (Optional): Runs strict mypy evaluation:*

```bash
make lint-strict
```
*Cleanup: Removes temporary files, bytecode, and type caches:*

```bash
make clean
```

## 🧠 Algorithm & Implementation Strategy

### 📊 Parser & Network Modeling

- **Parser**: Reads input files, builds graph objects, handles edge-case validations
  - Validates unique start/end hubs
  - Checks positive integers for capacities
  - Validates zone types
- **No External Graph Libraries**: Designed without forbidden packages (networkx, graphlib)

### 🗺️ Routing & Scheduling Strategy

#### Multi-Path Discovery
The pathfinding algorithm explores both disjoint and overlapping paths to maximize global throughput. Path costs incorporate weighted costs for node types:
- Prioritizing `priority` zones
- Accounting for 2-turn `restricted` transit delays

#### Discrete-Event Scheduling
Multi-agent collision avoidance is resolved turn-by-turn:
- Space freed by exiting drones is **immediately available** for incoming drones on the same turn
- Dynamic node state evaluation

#### Strategic Waiting & Flow Balancing
- Drones strategically wait at intermediate hubs
- Dispatching across longer secondary paths
- Prevents deadlocks and minimizes total execution turns

### 🎨 Visual Representation

#### Color-Coded Output
Highlights zone states (priority, restricted, blocked), capacity usage, and active drone locations in the terminal.

#### Step-by-Step State Tracking
Movement outputs formatted as:
- `D<ID>-<zone>` for active paths
- `D<ID>-<connection>` for transit connections

---

## 📚 Resources

### 📖 Documentation & References

- [Python Typing Module](https://docs.python.org/3/library/typing.html)
- [PEP 8 / Flake8 Documentation](https://flake8.pycqa.org/)
- [PEP 257 Docstring Conventions](https://www.python.org/dev/peps/pep-0257/)
- [Mypy Documentation](https://mypy.readthedocs.io/)

### 🤖 AI Usage Statement

AI tools were used during development in compliance with curriculum guidelines:

- **Tasks Assisted**: 
  - Drafting unit test scenarios for input validation edge cases
  - Formatting technical documentation templates
- **Parts of Project**: 
  - Test suite design (`tests/`)
  - README.md structure
- **Validation**: 
  - All code logic, custom pathfinding algorithms, parser rules, and dynamic typing implementations were **written, reviewed, and validated manually**

---

<div align="center">

### Made with ❤️ by ENNEEX

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Code Style](https://img.shields.io/badge/Code%20Style-Flake8-green.svg)](https://flake8.pycqa.org/)
[![Typing](https://img.shields.io/badge/Typing-Mypy-blueviolet.svg)](https://mypy.readthedocs.io/)

</div>