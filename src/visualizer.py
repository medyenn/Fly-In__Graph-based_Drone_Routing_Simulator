class Visualizer:
    def __init__(self, graph, color_map):
        self.graph = graph
        self.color = color_map

    def render_turn(self, turn_number, line):
        ...

    def render_summary(self, total_turns, drones):
        ...

    def render_map(self):
        ...
