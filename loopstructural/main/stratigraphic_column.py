import enum


class UnconformityType(enum.Enum):
    """
    An enumeration for different types of unconformities in a stratigraphic column.
    """

    ERODE = 'erode'
    ONLAP = 'onlap'


class StratigraphicColumnElementType(enum.Enum):
    """
    An enumeration for different types of elements in a stratigraphic column.
    """

    UNIT = 'unit'
    UNCONFORMITY = 'unconformity'


class StratigraphicColumnElement:
    """
    A class to represent an element in a stratigraphic column, which can be a unit or a topological object
    for example unconformity.
    """

    def __init__(self, name):
        """
        Initializes the StratigraphicColumnElement with a name and an optional description.
        """
        self.name = name


class StratigraphicUnit(StratigraphicColumnElement):
    """
    A class to represent a stratigraphic unit, which is a distinct layer of rock with specific characteristics.
    """

    def __init__(self, name, colour, thickness=None):
        """
        Initializes the StratigraphicUnit with a name and an optional description.
        """
        super().__init__(name)
        self.colour = colour
        self.thickness = thickness
        self.element_type = StratigraphicColumnElementType.UNIT

    def to_dict(self):
        """
        Converts the stratigraphic unit to a dictionary representation.
        """
        return {"name": self.name, "colour": self.colour, "thickness": self.thickness}

    @classmethod
    def from_dict(cls, data):
        """
        Creates a StratigraphicUnit from a dictionary representation.
        """
        if not isinstance(data, dict):
            raise TypeError("Data must be a dictionary")
        name = data.get("name")
        colour = data.get("colour")
        thickness = data.get("thickness", None)
        return cls(name, colour, thickness)


class StratigraphicUnconformity(StratigraphicColumnElement):
    """
    A class to represent a stratigraphic unconformity, which is a surface of discontinuity in the stratigraphic record.
    """

    def __init__(self, name, unconformity_type: UnconformityType = UnconformityType.ERODE):
        """
        Initializes the StratigraphicUnconformity with a name and an optional description.
        """
        super().__init__(name)
        if unconformity_type not in [UnconformityType.ERODE, UnconformityType.ONLAP]:
            raise ValueError("Invalid unconformity type")
        self.unconformity_type = unconformity_type
        self.element_type = StratigraphicColumnElementType.UNCONFORMITY

    def to_dict(self):
        """
        Converts the stratigraphic unconformity to a dictionary representation.
        """
        return {"name": self.name, "unconformity_type": self.unconformity_type.value}

    @classmethod
    def from_dict(cls, data):
        """
        Creates a StratigraphicUnconformity from a dictionary representation.
        """
        if not isinstance(data, dict):
            raise TypeError("Data must be a dictionary")
        name = data.get("name")
        unconformity_type = UnconformityType(
            data.get("unconformity_type", UnconformityType.ERODE.value)
        )
        return cls(name, unconformity_type)


class StratigraphicColumn:
    """
    A class to represent a stratigraphic column, which is a vertical section of the Earth's crust
    showing the sequence of rock layers and their relationships.
    """

    def __init__(self):
        """
        Initializes the StratigraphicColumn with a name and a list of layers.
        """
        self.order = []

    def add_unit(self, name, colour, thickness=None):
        unit = StratigraphicUnit(name, colour, thickness)

        self.order.append(unit)
        return unit

    def remove_unit(self, name):
        """
        Removes a unit or unconformity from the stratigraphic column by its name.
        """
        for i, element in enumerate(self.order):
            if element.name == name:
                del self.order[i]
                return True
        return False

    def add_unconformity(self, name, unconformity_type=UnconformityType.ERODE):
        unconformity = StratigraphicUnconformity(name, unconformity_type)

        self.order.append(unconformity)
        return unconformity

    def get_element_by_index(self, index):
        """
        Retrieves an element by its index from the stratigraphic column.
        """
        if index < 0 or index >= len(self.order):
            raise IndexError("Index out of range")
        return self.order[index]

    def get_unit_by_name(self, name):
        """
        Retrieves a unit by its name from the stratigraphic column.
        """
        for unit in self.order:
            if unit.name == name:
                return unit
        return None

    def add_element(self, element):
        """
        Adds a StratigraphicColumnElement to the stratigraphic column.
        """
        if isinstance(element, StratigraphicColumnElement):
            self.order.append(element)
        else:
            raise TypeError("Element must be an instance of StratigraphicColumnElement")

    def get_elements(self):
        """
        Returns a list of all elements in the stratigraphic column.
        """
        return self.order

    def get_groups(self):
        groups = []
        group = []
        for e in self.order:
            if isinstance(e, StratigraphicUnit):
                group.append(e)
            else:
                if group:
                    groups.append(group)
                    group = []
        if group:
            groups.append(group)
        return groups

    def update_order(self, new_order):
        """
        Updates the order of elements in the stratigraphic column based on a new order list.
        """
        if not isinstance(new_order, list):
            raise TypeError("New order must be a list")
        self.order = [
            self.get_unit_by_name(name)
            for name in new_order
            if self.get_unit_by_name(name) is not None
        ]

    def clear(self):
        """
        Clears the stratigraphic column, removing all elements.
        """
        self.order.clear()

    def __str__(self):
        """
        Returns a string representation of the stratigraphic column, listing all elements.
        """
        return "\n".join([f"{i+1}. {element.name}" for i, element in enumerate(self.order)])

    def to_dict(self):
        """
        Converts the stratigraphic column to a dictionary representation.
        """
        return {
            "elements": [element.to_dict() for element in self.order],
        }

    @classmethod
    def from_dict(cls, data):
        """
        Creates a StratigraphicColumn from a dictionary representation.
        """
        if not isinstance(data, dict):
            raise TypeError("Data must be a dictionary")
        column = cls()
        elements_data = data.get("elements", [])
        for element_data in elements_data:
            if "unconformity_type" in element_data:
                element = StratigraphicUnconformity.from_dict(element_data)
            else:
                element = StratigraphicUnit.from_dict(element_data)
            column.add_element(element)
        return column
