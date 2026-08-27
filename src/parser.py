class MapParser:
    def __ini__(self, filepath, graph, nb_drones, line_number):
        self.filepath = filepath  # path to the map file.
        self.graph = graph  # the Graph being built.
        self.nb_drones = nb_drones  # parsed drone count.
        self.line_number = line_number  # tracked for error messages.

    def parse():
        ...

    def strip_comment(line):
        ...

    def parse_drone_count(line):
        ...

    def parse_zone_line(line, kind):
        ...

    def parse_connection_line(line):
        ...

    def parse_metadata(raw):
        ...

    def validate_zone_type(value):
        ...

    def validate_positive_int(value, field_name):
        ...

    def error(message):
        ...
