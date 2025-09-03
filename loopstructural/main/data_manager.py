import json
from collections import defaultdict

import numpy as np
from qgis.core import QgsPointXY, QgsProject, QgsVectorLayer

from LoopStructural import FaultTopology, StratigraphicColumn
from LoopStructural.datatypes import BoundingBox

from .vectorLayerWrapper import qgsLayerToGeoDataFrame

__title__ = "LoopStructural"
default_bounding_box = {
    'xmin': 0,
    'xmax': 1000,
    'ymin': 0,
    'ymax': 1000,
    'zmin': -7000,
    'zmax': 1000,
}


class ModellingDataManager:
    def __init__(self, *, project=None, mapCanvas=None, logger=None):
        if project is None:
            raise ValueError("project cannot be None")
        if mapCanvas is None:
            raise ValueError("mapCanvas cannot be None")
        if logger is None:
            raise ValueError("logger cannot be None")
        self.project = project
        self.project.readProject.connect(self.onLoadProject)
        self.project.writeProject.connect(self.onSaveProject)
        self.project.cleared.connect(self.onNewProject)
        self._bounding_box = BoundingBox(
            origin=[
                default_bounding_box['xmin'],
                default_bounding_box['ymin'],
                default_bounding_box['zmin'],
            ],
            maximum=[
                default_bounding_box['xmax'],
                default_bounding_box['ymax'],
                default_bounding_box['zmax'],
            ],
        )

        self._basal_contacts = None
        self._fault_traces = None
        self._structural_orientations = None
        self._unique_basal_units = []
        self.map_canvas = mapCanvas
        self.logger = logger
        self._stratigraphic_column = StratigraphicColumn()
        self._fault_topology = FaultTopology(self._stratigraphic_column)
        self._model_manager = None
        self.bounding_box_callback = None
        self.basal_contacts_callback = None
        self.fault_traces_callback = None
        self.structural_orientations_callback = None
        self.stratigraphic_column_callback = None
        self.fault_adjacency = None
        self.fault_stratigraphy_adjacency = None
        self.elevation = np.nan
        self.dem_layer = None
        self.use_dem = True
        self.dem_callback = None
        self.feature_data = defaultdict(dict)

    def onSaveProject(self):
        """Save project data."""
        self.logger(message="Saving project data...", log_level=3)
        datamanager_dict = self.to_dict()
        self.project.writeEntry(__title__, "data_manager", json.dumps(datamanager_dict))

    def onLoadProject(self):
        """Load project data."""
        self.logger(message="Loading project data...", log_level=3)
        datamanager_json, flag = self.project.readEntry(__title__, "data_manager", "")
        if datamanager_json and flag:
            try:
                datamanager_dict = json.loads(datamanager_json)
                self.update_from_dict(datamanager_dict)

            except json.JSONDecodeError as e:
                self.logger(message=f"Error loading data manager: {e}", log_level=2)
    def onNewProject(self):
        self.logger(message="New project created, clearing data...", log_level=3)
        self.update_from_dict({})
    def set_model_manager(self, model_manager):
        """Set the model manager for the data manager."""
        if model_manager is None:
            raise ValueError("model_manager cannot be None")
        self._model_manager = model_manager
        self._model_manager.set_stratigraphic_column(self._stratigraphic_column)
        self._model_manager.set_fault_topology(self._fault_topology)
        self._model_manager.update_bounding_box(self._bounding_box)

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
        self._model_manager.update_bounding_box(self._bounding_box)
        if self.bounding_box_callback:
            self.bounding_box_callback(self._bounding_box)

    def set_bounding_box_update_callback(self, callback):
        self.bounding_box_callback = callback
        self.bounding_box_callback(self._bounding_box)

    def set_fault_trace_layer_callback(self, callback):
        """Set the callback for when the fault trace layer is updated."""
        self.fault_traces_callback = callback

    def set_structural_orientations_callback(self, callback):
        """Set the callback for when the structural orientations are updated."""
        self.structural_orientations_callback = callback

    def set_basal_contacts_callback(self, callback):
        """Set the callback for when the basal contacts are updated."""
        self.basal_contacts_callback = callback

    def set_stratigraphic_column_callback(self, callback):
        """Set the callback for when the stratigraphic column is updated."""
        self.stratigraphic_column_callback = callback

    def set_dem_callback(self, callback):
        """Set the callback for when the DEM layer is updated."""
        self.dem_callback = callback
        if self.dem_layer:
            self.dem_callback(self.dem_layer)

    def get_bounding_box(self):
        """Get the current bounding box."""
        return self._bounding_box

    def set_elevation(self, elevation):
        """Set the elevation for the model."""
        self.elevation = elevation
        self.dem_function = lambda x, y: self.elevation
        self._model_manager.set_dem_function(self.dem_function)

    def set_dem_layer(self, dem_layer):
        self.dem_layer = dem_layer
        if dem_layer is None:
            self.dem_function = lambda x, y: 0.0
            self.logger(
                message="DEM layer is None, using 0.0 for elevation. Choose a valid layer or specify a constant value",
                log_level=2,
            )
        else:

            def dem_function(x, y):
                if not self.dem_layer.isValid():
                    self.logger(
                        message="DEM layer is not valid, using 0.0 for elevation.",
                        log_level=2,
                    )
                    return 0.0
                return (
                    self.dem_layer.dataProvider().sample(QgsPointXY(x, y), 1)[0]
                    if self.dem_layer
                    else np.nan
                )

            self.dem_function = dem_function
            self._model_manager.set_dem_function(self.dem_function)
        if self.dem_callback:
            self.dem_callback(self.dem_layer)

    def set_use_dem(self, use_dem):
        self.use_dem = use_dem
        self._model_manager.set_dem_function(self.dem_function)
        
    def set_basal_contacts(self, basal_contacts, unitname_field=None, use_z_coordinate=False):
        """Set the basal contacts for the model."""
        self._basal_contacts = {
            'layer': basal_contacts,
            'unitname_field': unitname_field,
            'use_z_coordinate': use_z_coordinate,
        }
        # self._unitname_field = unitname_field
        self.calculate_unique_basal_units()
        # if stratigraphic column is not empty, update contacts
        if len(self._stratigraphic_column.order) > 0:
            self.update_stratigraphy()
        if self.basal_contacts_callback:
            self.basal_contacts_callback(**self._basal_contacts)

    def calculate_unique_basal_units(self):
        if (
            self._basal_contacts is not None
            and self._basal_contacts['unitname_field'] is not None
            and self._basal_contacts['layer'] is not None
        ):
            self._unique_basal_units.clear()
            for feature in self._basal_contacts['layer'].getFeatures():
                unit_name = feature[self._basal_contacts['unitname_field']]
                if unit_name not in self._unique_basal_units:
                    self._unique_basal_units.append(unit_name)
        return len(self._unique_basal_units)

    def init_stratigraphic_column_from_basal_contacts(self):
        if len(self._unique_basal_units) == 0:
            self.logger(message="No basal contacts set, cannot initialise stratigraphic column.")
            return
        else:
            for unit_name in self._unique_basal_units:
                if not self._stratigraphic_column.get_unit_by_name(name=unit_name):
                    # Add the unit to the stratigraphic column if it does not already exist
                    self._stratigraphic_column.add_unit(name=unit_name, colour=None)
        self.update_stratigraphy()

    def add_to_stratigraphic_column(self, unit_data):
        """Add a unit or unconformity to the stratigraphic column."""
        stratigraphic_element = None
        if isinstance(unit_data, dict):
            if unit_data.get('type') == 'unit':
                stratigraphic_element = self._stratigraphic_column.add_unit(
                    name=unit_data.get('name'), colour=unit_data.get('colour')
                )
            elif unit_data.get('type') == 'unconformity':
                stratigraphic_element = self._stratigraphic_column.add_unconformity(
                    name=unit_data.get('name')
                )
        else:
            raise ValueError("unit_data must be a dictionary with 'type' key.")
        if stratigraphic_element is None:
            self.logger(message="Failed to add unit or unconformity to the stratigraphic column.")
        else:
            self.logger(
                message=f"Added {unit_data.get('type')} '{unit_data.get('name')}' to the stratigraphic column."
            )
            self.update_stratigraphy()
            return stratigraphic_element

    def remove_from_stratigraphic_column(self, unit_uuid):
        """Remove a unit or unconformity from the stratigraphic column."""
        self._stratigraphic_column.remove_unit(uuid=unit_uuid)
        self.update_stratigraphy()

    def update_stratigraphic_column_order(self, new_order):
        """Update the order of units in the stratigraphic column."""
        if not isinstance(new_order, list):
            raise ValueError("new_order must be a list of unit uuids.")
        self._stratigraphic_column.update_order(new_order)
        self.update_stratigraphy()

    def get_basal_contacts(self):
        """Get the basal contacts."""
        return self._basal_contacts

    def get_unique_faults(self):
        """Get the unique faults from the fault traces."""
        if self._fault_traces is None or self._fault_traces['layer'] is None:
            return []
        unique_faults = set()
        for feature in self._fault_traces['layer'].getFeatures():
            fault_name = feature[self._fault_traces['fault_name_field']]
            unique_faults.add(str(fault_name))
        return list(unique_faults)

    def set_fault_trace_layer(
        self,
        fault_trace_layer,
        *,
        fault_name_field=None,
        fault_dip_field=None,
        fault_displacement_field=None,
        use_z_coordinate=False,
    ):
        """Set the fault traces for the model."""

        self._fault_traces = {
            'layer': fault_trace_layer,
            'fault_name_field': fault_name_field,
            'fault_dip_field': fault_dip_field,
            'fault_displacement_field': fault_displacement_field,
            'use_z_coordinate': use_z_coordinate,
        }
        self.update_faults()
        if self.fault_traces_callback:
            self.fault_traces_callback(**self._fault_traces)

    def get_fault_traces(self):
        """Get the fault traces."""
        return self._fault_traces

    def set_structural_orientations(
        self,
        structural_orientations,
        strike_field=None,
        dip_field=None,
        unitname_field=None,
        orientation_type=None,
        use_z_coordinate=False,
    ):
        """Set the structural orientations for the model."""
        self._structural_orientations = {}
        self._structural_orientations['layer'] = structural_orientations
        self._structural_orientations['strike_field'] = strike_field
        self._structural_orientations['dip_field'] = dip_field
        self._structural_orientations['unitname_field'] = unitname_field
        self._structural_orientations['orientation_type'] = orientation_type
        self._structural_orientations['use_z_coordinate'] = use_z_coordinate
        if self.structural_orientations_callback:
            self.structural_orientations_callback(**self._structural_orientations)
        self.update_stratigraphy()

    def get_structural_orientations(self):
        """Get the structural orientations."""
        return self._structural_orientations

    def get_stratigraphic_column(self):
        """Get the stratigraphic column."""
        return self._stratigraphic_column

    def update_stratigraphy(self):
        """Update the foliation features in the model manager."""
        print("Updating stratigraphy...")
        if self._model_manager is not None:
            if self._basal_contacts is not None:
                self._model_manager.update_contact_traces(
                    qgsLayerToGeoDataFrame(self._basal_contacts['layer']),
                    unit_name_field=self._basal_contacts['unitname_field'],
                )
            if self._structural_orientations is not None:
                print("Updating structural orientations...")
                self._model_manager.update_structural_data(
                    qgsLayerToGeoDataFrame(self._structural_orientations['layer']),
                    strike_field=self._structural_orientations['strike_field'],
                    dip_field=self._structural_orientations['dip_field'],
                    unit_name_field=self._structural_orientations['unitname_field'],
                    dip_direction=(
                        True
                        if self._structural_orientations['orientation_type'] == "Dip Direction/Dip"
                        else False
                    ),
                )
        else:
            self.logger(message="Model manager is not set, cannot update foliation features.")

    def update_faults(self):
        """Update the faults in the model manager."""
        unique_faults = self.get_unique_faults()
        for f in unique_faults:
            print(f"Adding fault {f} to fault topology")
            if f not in self._fault_topology.faults:
                self._fault_topology.add_fault(f)
        faults_to_remove = list(set(self._fault_topology.faults) - set(unique_faults))
        for fault in faults_to_remove:
            print(f"Removing fault {fault} from fault topology")
            self._fault_topology.remove_fault(fault)
        self.fault_adjacency = np.zeros((len(unique_faults), len(unique_faults)), dtype=int)
        if self._model_manager is not None:
            self._model_manager.update_fault_points(
                qgsLayerToGeoDataFrame(self._fault_traces['layer']),
                fault_name_field=self._fault_traces['fault_name_field'],
                fault_dip_field=self._fault_traces['fault_dip_field'],
                fault_pitch_field=self._fault_traces.get('fault_pitch_field', None),
                fault_displacement_field=self._fault_traces['fault_displacement_field'],
                use_z_coordinate=self._fault_traces['use_z_coordinate'],
            )
        else:
            self.logger(message="Model manager is not set, cannot update faults.")

    def update_stratigraphic_column(self):
        """Update the stratigraphic column in the model manager."""
        if self._model_manager is not None:
            self._model_manager.groups = self._stratigraphic_column.get_groups()
        else:
            self.logger(message="Model manager is not set, cannot update stratigraphic column.")

    def clear_data(self):
        """Clear all data in the manager."""
        self._bounding_box = BoundingBox()
        self._basal_contacts = None
        self._fault_traces = None
        self._structural_orientations = None

    def to_dict(self):
        """Convert the data manager to a dictionary."""
        # Create copies of the dictionaries to avoid modifying the originals
        basal_contacts = dict(self._basal_contacts) if self._basal_contacts else None
        fault_traces = dict(self._fault_traces) if self._fault_traces else None
        structural_orientations = (
            dict(self._structural_orientations) if self._structural_orientations else None
        )

        # Replace layer objects with layer names
        if basal_contacts and 'layer' in basal_contacts and basal_contacts['layer'] is not None:
            basal_contacts['layer'] = basal_contacts['layer'].name()
        if fault_traces and 'layer' in fault_traces and fault_traces['layer'] is not None:
            fault_traces['layer'] = fault_traces['layer'].name()
        if (
            structural_orientations
            and 'layer' in structural_orientations
            and structural_orientations['layer'] is not None
        ):
            structural_orientations['layer'] = structural_orientations['layer'].name()
        if self.dem_layer is not None:
            try:
                dem_layer_name = self.dem_layer.name()
            except RuntimeError as e:
                self.logger(message=f"Error getting DEM layer name: {e}", log_level=2)

        return {
            'bounding_box': self._bounding_box.to_dict(),
            'basal_contacts': basal_contacts,
            'fault_traces': fault_traces,
            'structural_orientations': structural_orientations,
            'stratigraphic_column': (
                self._stratigraphic_column.to_dict() if self._stratigraphic_column else None
            ),
            'dem_layer': dem_layer_name if self.dem_layer else None,
            'use_dem': self.use_dem,
            'elevation': self.elevation,
        }

    def from_dict(self, data):
        """Load data from a dictionary."""
        if 'bounding_box' in data:
            self.set_bounding_box(
                xmin=data['bounding_box']['origin'][0],
                xmax=data['bounding_box']['maximum'][0],
                ymin=data['bounding_box']['origin'][1],
                ymax=data['bounding_box']['maximum'][1],
                zmin=data['bounding_box']['origin'][2],
                zmax=data['bounding_box']['maximum'][2],
            )
        if 'dem_layer' in data and data['dem_layer'] is not None:
            dem_layer = QgsProject.instance().mapLayersByName(data['dem_layer'])
            if dem_layer:
                self.set_dem_layer(dem_layer[0])
            else:
                self.logger(
                    message=f"DEM layer '{data['dem_layer']}' not found in project.",
                    log_level=2,
                )
        if 'use_dem' in data:
            self.set_use_dem(data['use_dem'])
        if 'elevation' in data:
            self.set_elevation(data['elevation'])
        if 'basal_contacts' in data:
            self._basal_contacts = data['basal_contacts']
        if 'fault_traces' in data:
            self._fault_traces = data['fault_traces']
        if 'structural_orientations' in data:
            self._structural_orientations = data['structural_orientations']
        if 'stratigraphic_column' in data:
            self._stratigraphic_column = StratigraphicColumn.from_dict(data['stratigraphic_column'])
            print([o.name for o in self._stratigraphic_column.order])
            self.stratigraphic_column_callback()

    def update_from_dict(self, data):
        """Update the data manager from a dictionary."""
        if 'bounding_box' in data:
            self.set_bounding_box(
                xmin=data['bounding_box']['origin'][0],
                xmax=data['bounding_box']['maximum'][0],
                ymin=data['bounding_box']['origin'][1],
                ymax=data['bounding_box']['maximum'][1],
                zmin=data['bounding_box']['origin'][2],
                zmax=data['bounding_box']['maximum'][2],
            )
        else:
            self.set_bounding_box(**default_bounding_box)
        if 'dem_layer' in data and data['dem_layer'] is not None:
            dem_layer = QgsProject.instance().mapLayersByName(data['dem_layer'])
            if dem_layer:
                self.set_dem_layer(dem_layer[0])
            else:
                self.logger(
                    message=f"DEM layer '{data['dem_layer']}' not found in project.",
                    log_level=2,
                )
        if 'use_dem' in data:
            self.set_use_dem(data['use_dem'])
        if 'elevation' in data:
            self.set_elevation(data['elevation'])
        if (
            'basal_contacts' in data
            and data['basal_contacts'] is not None
            and 'layer' in data['basal_contacts']
        ):
            layer = self.find_layer_by_name(data['basal_contacts']['layer'])
            if layer:
                self.set_basal_contacts(
                    layer, unitname_field=data['basal_contacts'].get('unitname_field', None)
                )
        if (
            'fault_traces' in data
            and data['fault_traces'] is not None
            and 'layer' in data['fault_traces']
        ):
            layer = self.find_layer_by_name(data['fault_traces']['layer'])
            if layer:
                self.set_fault_trace_layer(
                    layer,
                    fault_name_field=data['fault_traces'].get('fault_name_field', None),
                    fault_dip_field=data['fault_traces'].get('fault_dip_field', None),
                    fault_displacement_field=data['fault_traces'].get(
                        'fault_displacement_field', None
                    ),
                )
        if (
            'structural_orientations' in data
            and data['structural_orientations'] is not None
            and 'layer' in data['structural_orientations']
        ):
            layer = self.find_layer_by_name(data['structural_orientations']['layer'])
            if layer:
                self.set_structural_orientations(
                    layer,
                    strike_field=data['structural_orientations'].get('strike_field', None),
                    dip_field=data['structural_orientations'].get('dip_field', None),
                    unitname_field=data['structural_orientations'].get('unitname_field', None),
                    orientation_type=data['structural_orientations'].get('orientation_type', None),
                )
        if 'stratigraphic_column' in data:
            self._stratigraphic_column.update_from_dict(data['stratigraphic_column'])
        else:
            self._stratigraphic_column = StratigraphicColumn()

        if self.stratigraphic_column_callback:
            self.stratigraphic_column_callback()
        print([o.name for o in self._stratigraphic_column.order])


    def find_layer_by_name(self, layer_name):
        """Find a layer by name in the project."""
        if layer_name is None:
            return None
        if issubclass(type(layer_name), str):
            layers = self.project.mapLayersByName(layer_name)
        else:
            layers = [layer_name]
        if layers:
            if len(layers) > 1:
                self.logger(
                    message=f"Multiple layers found with name '{layer_name}', returning the first one.",
                    log_level=2,
                )
            i = 0
            while i < len(layers) and not issubclass(type(layers[i]), QgsVectorLayer):

                i += 1

            if issubclass(type(layers[i]), QgsVectorLayer):
                return layers[i]
            else:
                self.logger(message=f"Layer '{layer_name}' is not a vector layer.", log_level=2)
                return None

    def update_feature_data(self, feature_name: str, feature_data: dict):
        """Update the feature data in the data manager."""
        if not isinstance(feature_data, dict):
            raise ValueError("feature_data must be a dictionary.")
        self.feature_data[feature_name][feature_data['layer_name']] = feature_data
        self.logger(message=f"Updated feature data for '{feature_name}'.")

    def add_foliation_to_model(self, foliation_name: str, *, folded_feature_name=None):
        """Add a foliation to the model."""
        if foliation_name not in self.feature_data:
            raise ValueError(f"Foliation '{foliation_name}' does not exist in the data manager.")
        foliation_data = self.feature_data[foliation_name]
        for layer in foliation_data.values():
            layer['df'] = qgsLayerToGeoDataFrame(
                layer['layer']
            )  # Convert QgsVectorLayer to GeoDataFrame
        if self._model_manager:
            self._model_manager.add_foliation(
                foliation_name, foliation_data, folded_feature_name=folded_feature_name
            )
            self.logger(message=f"Added foliation '{foliation_name}' to the model.")
        else:
            raise RuntimeError("Model manager is not set.")
