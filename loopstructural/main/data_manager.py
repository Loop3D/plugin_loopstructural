from LoopStructural.datatypes import BoundingBox

from .stratigraphic_column import StratigraphicColumn


class ModellingDataManager:
    def __init__(self, *, mapCanvas=None, logger=None):
        if mapCanvas is None:
            raise ValueError("mapCanvas cannot be None")
        if logger is None:
            raise ValueError("logger cannot be None")
        self._bounding_box = BoundingBox(origin=[0, 0, 0], maximum=[1000, 1000, 1000])
        self._basal_contacts = None
        self._fault_traces = None
        self._structural_orientations = None
        self._unique_basal_units = []
        self.map_canvas = mapCanvas
        self.logger = logger
        self._stratigraphic_column = StratigraphicColumn()
        self._model_manager = None

    def set_model_manager(self, model_manager):
        """Set the model manager for the data manager."""
        if model_manager is None:
            raise ValueError("model_manager cannot be None")
        self._model_manager = model_manager
        self._model_manager.update_bounding_box(self._bounding_box)
        self._model_manager.update_stratigraphic_column(self._stratigraphic_column)

    def set_bounding_box(self, xmin=None, xmax=None, ymin=None, ymax=None, zmin=None, zmax=None):
        """Set the bounding box for the model."""
        origin = self._bounding_box.origin
        maximum = self._bounding_box.maximum

        if xmin is not None:
            origin[0] = xmin
        if xmax is not None:
            maximum[0] = xmax
        if ymin is not None:
            origin[1] = ymin
        if ymax is not None:
            maximum[1] = ymax
        if zmin is not None:
            origin[2] = zmin
        if zmax is not None:
            maximum[2] = zmax
        self._bounding_box.origin = origin
        self._bounding_box.maximum = maximum
        self._bounding_box.origin = origin
        self._bounding_box.maximum = maximum
        # self._bounding_box.update([west, south, bottom], [east, north, top])
        self._model_manager.update_bounding_box(self._bounding_box)

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

    def init_stratigraphic_column_from_basal_contacts(self):
        if len(self._unique_basal_units) == 0:
            self.logger(message="No basal contacts set, cannot initialise stratigraphic column.")
            return
        else:
            for unit_name in self._unique_basal_units:
                self._stratigraphic_column.add_unit(name=unit_name, colour=None)

    def add_to_stratigraphic_column(self, unit_data):
        """Add a unit or unconformity to the stratigraphic column."""

        if isinstance(unit_data, dict):
            if unit_data.get('type') == 'unit':
                return self._stratigraphic_column.add_unit(
                    name=unit_data.get('name'), colour=unit_data.get('colour')
                )
            elif unit_data.get('type') == 'unconformity':
                return self._stratigraphic_column.add_unconformity(name=unit_data.get('name'))
        else:
            raise ValueError("unit_data must be a dictionary with 'type' key.")

    def remove_from_stratigraphic_column(self, unit_uuid):
        """Remove a unit or unconformity from the stratigraphic column."""
        self._stratigraphic_column.remove_unit(uuid=unit_uuid)

    def update_stratigraphic_column_order(self, new_order):
        """Update the order of units in the stratigraphic column."""
        if not isinstance(new_order, list):
            raise ValueError("new_order must be a list of unit uuids.")
        self._stratigraphic_column.update_order(new_order)

    def get_basal_contacts(self):
        """Get the basal contacts."""
        return self._basal_contacts

    def set_fault_traces(self, fault_traces):
        """Set the fault traces for the model."""
        self._fault_traces = fault_traces
        self.update_faults()

    def get_fault_traces(self):
        """Get the fault traces."""
        return self._fault_traces

    def set_structural_orientations(self, structural_orientations):
        """Set the structural orientations for the model."""
        self._structural_orientations = structural_orientations

    def get_structural_orientations(self):
        """Get the structural orientations."""
        return self._structural_orientations

    def update_stratigraphic_column(self, stratigraphic_column):
        """Set the stratigraphic column for the model."""
        self._stratigraphic_column = stratigraphic_column

    def get_stratigraphic_column(self):
        """Get the stratigraphic column."""
        return self._stratigraphic_column

    def update_stratigraphys(self):
        """Update the foliation features in the model manager."""
        if self._model_manager is not None:
            self._model_manager.update_foliation_features()
        else:
            self.logger(message="Model manager is not set, cannot update foliation features.")

    def update_faults(self):
        """Update the faults in the model manager."""
        if self._model_manager is not None:
            self._model_manager.update_fault_points(self._fault_traces)
        else:
            self.logger(message="Model manager is not set, cannot update faults.")

    def clear_data(self):
        """Clear all data in the manager."""
        self._bounding_box = BoundingBox()
        self._basal_contacts = None
        self._fault_traces = None
        self._structural_orientations = None
