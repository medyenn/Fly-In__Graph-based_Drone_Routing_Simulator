class Zone:
    def __init__(self, name, x, y, zone_type, color, max_drones, occupants):
        self.name = name
        self.x = x
        self.y = y
        self.type = zone_type
        self.color = color
        self.max_dr = max_drones
        self.occupants = occupants

    def is_start(self, ):
        ...

    def is_end(self):
        ...

    def entry_cost(self, ):
        ...

    def has_space(self, n=1):
        ...

    def add_occupant(self, drone_id):
        ...

    def remove_occupant(self, drone_id):
        ...


class Connection:
    def __init__(self, zone_a, zone_b, max_link_capacity, in_transit):
        self.a = zone_a
        self.b = zone_b
        self.max = max_link_capacity
        self.in_transit = in_transit

    def other_end(self, zone):
        ...

    def has_space(self, ):
        ...

    def enter(self, drone_id):
        ...

    def leave(self, drone_id):
        ...


class Drone:
    def __init__(
            self, dr_id, zone, path, path_index, transit_state, arrived):
        self.id = dr_id
        self.zone = zone
        self.path = path
        self.path_ndx = path_index
        self.transit_state = transit_state
        self.arrived = arrived

    def next_zone(self):
        ...

    def advance(self):
        ...

    def has_arrived(self):
        ...
