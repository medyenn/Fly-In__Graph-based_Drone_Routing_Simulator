# Fly-In Test Maps

These maps are provided to test the simulation at different difficulty levels.

## Maps

### Easy
- `01_linear_path.txt` — simple linear route
- `02_simple_fork.txt` — two possible routes
- `03_basic_capacity.txt` — zone capacity handling

### Medium
- `01_dead_end_trap.txt` — dead-end handling
- `02_circular_loop.txt` — loop and restricted-zone handling
- `03_priority_puzzle.txt` — priority-zone tie-breaking

### Hard
- `01_maze_nightmare.txt` — maze with traps and loops
- `02_capacity_hell.txt` — strong capacity constraints
- `03_ultimate_challenge.txt` — combined constraints

### Challenger
- `01_the_impossible_dream.txt` — optional stress test

## Recommended order

Run the maps from Easy to Hard. Use the Challenger only after the
mandatory functionality is stable.

The subject provides these optimization targets:

| Level | Target |
|---|---:|
| Easy | under 10 turns |
| Medium | 10–30 turns |
| Hard | under 60 turns |
| Challenger | optional, reference 45 turns |
