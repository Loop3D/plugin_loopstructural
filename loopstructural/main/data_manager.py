from LoopStructural.datatypes import BoundingBox


class ModellingDataManager:
    def __init__(self):
        self._bounding_box = BoundingBox()
        self._basal_contacts = None
        self._fault_traces = None
        self._structural_orientations = None
        self._unique_basal_units = []

    def set_bounding_box(self, east, west, north, south, top, bottom):
        """Set the bounding box for the model."""
        self._bounding_box.update([west, south, bottom], [east, north, top])

    def get_bounding_box(self):
        """Get the current bounding box."""
        return self._bounding_box

    def set_basal_contacts(self, basal_contacts, unitname_field=None):
        """Set the basal contacts for the model."""
        self._basal_contacts = basal_contacts
        self._unitname_field = unitname_field
        self.calculate_unique_basal_units()

    def calculate_unique_basal_units(self):
        if self._basal_contacts is not None and self._unitname_field is not None:
            self._unique_basal_units.clear()
            for feature in self._basal_contacts.getFeatures():
                unit_name = feature[self._unitname_field]
                if unit_name not in self._unique_basal_units:
                    self._unique_basal_units.append(unit_name)
        return len(self._unique_basal_units)

    def get_basal_contacts(self):
        """Get the basal contacts."""
        return self._basal_contacts

    def set_fault_traces(self, fault_traces):
        """Set the fault traces for the model."""
        self._fault_traces = fault_traces

    def get_fault_traces(self):
        """Get the fault traces."""
        return self._fault_traces

    def set_structural_orientations(self, structural_orientations):
        """Set the structural orientations for the model."""
        self._structural_orientations = structural_orientations

    def get_structural_orientations(self):
        """Get the structural orientations."""
        return self._structural_orientations

    def updatestratigraphic_column(self, stratigraphic_column):
        """Set the stratigraphic column for the model."""
        self._stratigraphic_column = stratigraphic_column

    def get_stratigraphic_column(self):
        """Get the stratigraphic column."""
        return self._stratigraphic_column

    def clear_data(self):
        """Clear all data in the manager."""
        self._bounding_box = BoundingBox()
        self._basal_contacts = None
        self._fault_traces = None
        self._structural_orientations = None
