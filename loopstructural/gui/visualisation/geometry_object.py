class GeometryObject:
    def __init__(self, name, object, options=None):
        self.name = name
        self.object = object
        self.options = options or {}

    def export(self):
        # Placeholder for export functionality
        print(f"Exporting {self.name} of type {self.object}")

    def set_option(self, key, value):
        self.options[key] = value

    def get_option(self, key):
        return self.options.get(key, None)
