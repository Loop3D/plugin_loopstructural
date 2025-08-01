import enum
from typing import Dict


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

    def __init__(self, uuid=None):
        """
        Initializes the StratigraphicColumnElement with a name and an optional description.
        """
        if uuid is None:
            import uuid as uuid_module

            uuid = str(uuid_module.uuid4())
        self.uuid = uuid


class StratigraphicUnit(StratigraphicColumnElement):
    """
    A class to represent a stratigraphic unit, which is a distinct layer of rock with specific characteristics.
    """

    def __init__(self, *, uuid=None, name=None, colour=None, thickness=None):
        """
        Initializes the StratigraphicUnit with a name and an optional description.
        """
        super().__init__(uuid)
        self.name = name
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
        uuid = data.get("uuid", None)
        return cls(uuid=uuid, name=name, colour=colour, thickness=thickness)

    def __str__(self):
        """
        Returns a string representation of the stratigraphic unit.
        """
        return (
            f"StratigraphicUnit(name={self.name}, colour={self.colour}, thickness={self.thickness})"
        )


class StratigraphicUnconformity(StratigraphicColumnElement):
    """
    A class to represent a stratigraphic unconformity, which is a surface of discontinuity in the stratigraphic record.
    """

    def __init__(
        self, *, uuid=None, name=None, unconformity_type: UnconformityType = UnconformityType.ERODE
    ):
        """
        Initializes the StratigraphicUnconformity with a name and an optional description.
        """
        super().__init__(uuid)
        self.name = name
        if unconformity_type not in [UnconformityType.ERODE, UnconformityType.ONLAP]:
            raise ValueError("Invalid unconformity type")
        self.unconformity_type = unconformity_type
        self.element_type = StratigraphicColumnElementType.UNCONFORMITY

    def to_dict(self):
        """
        Converts the stratigraphic unconformity to a dictionary representation.
        """
        return {
            "uuid": self.uuid,
            "name": self.name,
            "unconformity_type": self.unconformity_type.value,
        }

    def __str__(self):
        """
        Returns a string representation of the stratigraphic unconformity.
        """
        return (
            f"StratigraphicUnconformity(name={self.name}, "
            f"unconformity_type={self.unconformity_type.value})"
        )

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
        uuid = data.get("uuid", None)
        return cls(uuid=uuid, name=name, unconformity_type=unconformity_type)


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
        unit = StratigraphicUnit(name=name, colour=colour, thickness=thickness)

        self.order.append(unit)
        return unit

    def remove_unit(self, uuid):
        """
        Removes a unit or unconformity from the stratigraphic column by its uuid.
        """
        for i, element in enumerate(self.order):
            if element.uuid == uuid:
                del self.order[i]
                return True
        return False

    def add_unconformity(self, name, unconformity_type=UnconformityType.ERODE):
        unconformity = StratigraphicUnconformity(
            uuid=None, name=name, unconformity_type=unconformity_type
        )

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
            if isinstance(unit, StratigraphicUnit) and unit.name == name:
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

    def get_unitname_groups(self):
        groups = []
        group = []
        for e in self.order:
            if isinstance(e, StratigraphicUnit):
                group.append(e.name)
            else:
                if group:
                    groups.append(group)
                    group = []
        if group:
            groups.append(group)
        return groups

    def __getitem__(self, uuid):
        """
        Retrieves an element by its uuid from the stratigraphic column.
        """
        for element in self.order:
            if element.uuid == uuid:
                return element
        raise KeyError(f"No element found with uuid: {uuid}")

    def update_order(self, new_order):
        """
        Updates the order of elements in the stratigraphic column based on a new order list.
        """
        if not isinstance(new_order, list):
            raise TypeError("New order must be a list")
        self.order = [
            self.__getitem__(uuid) for uuid in new_order if self.__getitem__(uuid) is not None
        ]

    def update_element(self, unit_data: Dict):
        """
        Updates an existing element in the stratigraphic column with new data.
        :param unit_data: A dictionary containing the updated data for the element.
        """
        if not isinstance(unit_data, dict):
            raise TypeError("unit_data must be a dictionary")
        element = self.__getitem__(unit_data['uuid'])
        if isinstance(element, StratigraphicUnit):
            element.name = unit_data.get('name', element.name)
            element.colour = unit_data.get('colour', element.colour)
            element.thickness = unit_data.get('thickness', element.thickness)
        elif isinstance(element, StratigraphicUnconformity):
            element.name = unit_data.get('name', element.name)
            element.unconformity_type = UnconformityType(
                unit_data.get('unconformity_type', element.unconformity_type.value)
            )

    def clear(self):
        """
        Clears the stratigraphic column, removing all elements.
        """
        self.order.clear()

    def __str__(self):
        """
        Returns a string representation of the stratigraphic column, listing all elements.
        """
        return "\n".join([f"{i+1}. {element}" for i, element in enumerate(self.order)])

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
