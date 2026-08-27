class Graph:
    def __init__(self, zones, connections, start, end):
        self.zones = zones
        self.connections = connections
        self.start = start
        self.end = end

    def add_zone(self, zone):
        ...

    def add_connection(self, connection):
        ...

    def neighbors(self, zone_name):
        ...

    def get_zone(self, name):
        ...

    def get_connection(self, name1, name2):
        ...
