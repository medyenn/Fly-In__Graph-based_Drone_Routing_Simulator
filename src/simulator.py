class Simulator:
    def __init__(self, graph, drones, turn, reservations, log):
        self.graph = graph
        self.drones = drones
        self.turn = turn
        self.reservations = reservations
        self.log = log

    def run(self):
        i = 0
        for drone in self.drones:
            if self.is_finished(drone):
                i += 1
            if i == len(self.drones):
                break
            self.propose_moves()
            self.resolve_conflicts()
            self.apply_moves()
            self.record_turn()

    def step(self):
        ...

    def propose_moves(self):
        ...

    def resolve_conflicts(self, proposals):
        ...

    def apply_moves(self, approved):
        ...

    def record_turn(self, approved):
        ...

    def is_finished(self):
        ...
