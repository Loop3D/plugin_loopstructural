from collections import defaultdict
from typing import Callable

import geopandas as gpd
import numpy as np
import pandas as pd

from LoopStructural import GeologicalModel
from LoopStructural.datatypes import BoundingBox
from LoopStructural.modelling.core.fault_topology import FaultRelationshipType
from LoopStructural.modelling.core.stratigraphic_column import StratigraphicColumn
from LoopStructural.modelling.features import FeatureType
from loopstructural.toolbelt.preferences import PlgSettingsStructure


class AllSampler:
    """This is a simple sampler that just returns all the points, or all of the vertices
    of a line. It will also copy the elevation from the DEM or the elevation set in the data manager.
    """

    def __call__(self, line: gpd.GeoDataFrame, dem: Callable, use_z: bool) -> pd.DataFrame:
        """Sample the line and return a DataFrame with X, Y, Z coordinates and attributes."""
        points = []
        feature_id = 0
        if line is None:
            return pd.DataFrame(points, columns=['X', 'Y', 'Z', 'feature_id'])
        for geom in line.geometry:
            attributes = line.iloc[feature_id].to_dict()
            attributes.pop('geometry', None)  # Remove geometry from attributes
            if geom.geom_type == 'LineString':
                coords = list(geom.coords)
                for coord in coords:
                    x, y = coord[0], coord[1]
                    # Use Z from geometry if available, otherwise use DEM
                    if use_z and len(coord) > 2:
                        z = coord[2]
                    else:
                        z = dem(x, y)
                    points.append({'X': x, 'Y': y, 'Z': z, 'feature_id': feature_id, **attributes})
            elif geom.geom_type == 'MultiLineString':
                for l in geom.geoms:
                    coords = list(l.coords)
                    for coord in coords:
                        x, y = coord[0], coord[1]
                        # Use Z from geometry if available, otherwise use DEM
                        if use_z and len(coord) > 2:
                            z = coord[2]
                        else:
                            z = dem(x, y)
                        points.append(
                            {'X': x, 'Y': y, 'Z': z, 'feature_id': feature_id, **attributes}
                        )
            elif geom.geom_type == 'Point':
                x, y = geom.x, geom.y
                # Use Z from geometry if available, otherwise use DEM
                if use_z and hasattr(geom, 'z'):
                    z = geom.z
                else:
                    z = dem(x, y)
                points.append({'X': x, 'Y': y, 'Z': z, 'feature_id': feature_id, **attributes})
            feature_id += 1
        df = pd.DataFrame(points)
        return df


class GeologicalModelManager:
    """This class manages the geological model and assembles it from the data provided by the data manager.
    It is responsible for updating the model with faults, stratigraphy, and other geological features.
    """

    def __init__(self):
        """Initialize the geological model manager."""
        self.model = GeologicalModel([0, 0, 0], [1, 1, 1])
        self.stratigraphy = {}
        self.groups = []
        self.faults = defaultdict(dict)
        self.stratigraphy = defaultdict(dict)
        self.stratigraphic_column = None
        self.fault_topology = None
        self.observers = []
        self.dem_function = lambda x, y: 0

    def set_stratigraphic_column(self, stratigraphic_column: StratigraphicColumn):
        """Set the stratigraphic column for the geological model manager."""
        self.stratigraphic_column = stratigraphic_column

    def set_fault_topology(self, fault_topology):
        """Set the fault topology for the geological model manager."""
        self.fault_topology = fault_topology

    def update_bounding_box(self, bounding_box: BoundingBox):
        """Update the bounding box of the geological model.

        :param bounding_box: The new bounding box.
        :type bounding_box: BoundingBox
        """
        self.model.bounding_box = bounding_box

    def set_dem_function(self, dem_function: Callable):
        """Set the function to get the elevation at a point.
        :param dem_function: A function that takes x and y coordinates and returns the elevation.
        """
        self.dem_function = dem_function

    def update_fault_points(
        self,
        fault_trace: gpd.GeoDataFrame,
        *,
        fault_name_field=None,
        fault_dip_field=None,
        fault_displacement_field=None,
        fault_pitch_field=None,
        sampler=AllSampler(),
        use_z_coordinate=False,
    ):
        """Add fault trace data to the geological model.
        :param fault_trace: A GeoDataFrame containing the fault trace data.
        :param fault_name_field: The field name for the fault name.
        :param fault_dip_field: The field name for the fault dip.
        :param fault_displacement_field: The field name for the fault displacement.
        :param sampler: A callable that samples the fault trace and returns a DataFrame with X, Y, Z coordinates.
        """
        # sample fault trace
        self.faults.clear()  # Clear existing faults
        fault_points = sampler(fault_trace, self.dem_function, use_z_coordinate)
        cols = ['X', 'Y', 'Z']
        if fault_name_field is not None and fault_name_field in fault_points.columns:
            fault_points['fault_name'] = fault_points[fault_name_field].astype(str)
        else:
            fault_points['fault_name'] = fault_points['feature_id'].astype(str)
        if fault_dip_field is not None and fault_dip_field in fault_points.columns:
            fault_points['dip'] = fault_points[fault_dip_field]
            cols.append('dip')
        if (
            fault_displacement_field is not None
            and fault_displacement_field in fault_points.columns
        ):
            fault_points['displacement'] = fault_points[fault_displacement_field]
            cols.append('displacement')
        if fault_pitch_field is not None and fault_pitch_field in fault_points.columns:
            fault_points['pitch'] = fault_points[fault_pitch_field]
            cols.append('pitch')
        existing_faults = set(self.fault_topology.faults)
        for fault_name in fault_points['fault_name'].unique():
            self.faults[fault_name]['data'] = fault_points.loc[
                fault_points['fault_name'] == fault_name, cols
            ]
            if fault_name not in existing_faults:
                self.fault_topology.add_fault(fault_name)
            else:
                existing_faults.remove(fault_name)

        for fault_name in existing_faults:
            self.fault_topology.remove_fault(fault_name)

    def update_contact_traces(
        self,
        basal_contacts: gpd.GeoDataFrame,
        *,
        sampler=AllSampler(),
        unit_name_field=None,
        use_z_coordinate=False,
    ):
        self.stratigraphy.clear()  # Clear existing stratigraphy
        unit_points = sampler(basal_contacts, self.dem_function, use_z_coordinate)
        if len(unit_points) == 0 or unit_points.empty:
            print("No basal contacts found or empty GeoDataFrame.")
            return
        if unit_name_field is not None:
            unit_points['unit_name'] = unit_points[unit_name_field].astype(str)
        else:
            return
        for unit_name in unit_points['unit_name'].unique():
            self.stratigraphy[unit_name]['contact'] = unit_points.loc[
                unit_points['unit_name'] == unit_name, ['X', 'Y', 'Z']
            ]

    def update_structural_data(
        self,
        structural_orientations: gpd.GeoDataFrame,
        *,
        strike_field=None,
        dip_field=None,
        unit_name_field=None,
        dip_direction=False,
        sampler=AllSampler(),
        use_z_coordinate=False,
    ):
        """Add structural orientation data to the geological model."""
        if structural_orientations is None or structural_orientations.empty:
            return
        if (
            strike_field is None
            or strike_field not in structural_orientations.columns
            or dip_field is None
            or dip_field not in structural_orientations.columns
        ):
            return
        if unit_name_field is None or unit_name_field not in structural_orientations.columns:
            return
        structural_orientations = sampler(
            structural_orientations, self.dem_function, use_z_coordinate
        )

        structural_orientations['unit_name'] = structural_orientations[unit_name_field].astype(str)

        structural_orientations['dip'] = structural_orientations[dip_field]
        structural_orientations['strike'] = structural_orientations[strike_field]
        structural_orientations = structural_orientations[
            ['X', 'Y', 'Z', 'dip', 'strike', 'unit_name']
        ]
        if dip_direction:
            structural_orientations['strike'] = structural_orientations['strike'] - 90
        for unit_name in structural_orientations['unit_name'].unique():
            orientations = structural_orientations.loc[
                structural_orientations['unit_name'] == unit_name, ['X', 'Y', 'Z', 'dip', 'strike']
            ]
            self.stratigraphy[unit_name]['orientations'] = orientations

    def update_stratigraphic_column(self, stratigraphic_column: StratigraphicColumn):
        """Update the stratigraphic column with a new stratigraphic column"""
        self.stratigraphic_column = stratigraphic_column
        self.update_foliation_features()

    # def update_stratigraphic_unit(self, unit_data):
    #     self.data

    def update_foliation_features(self):
        """Builds the stratigraphic feature from the stratigraphic column data
        and the basal contacts and structural orientations data.
        This method will automatically add unconformities based on the stratigraphic column.
        """
        stratigraphic_column = {}
        for _i, group in enumerate(reversed(self.stratigraphic_column.get_groups())):
            val = 0
            data = []
            groupname = group.name
            stratigraphic_column[groupname] = {}
            for u in group.units:
                unit_data = self.stratigraphy.get(u.name, None)
                if unit_data is None:
                    continue
                else:
                    if 'contact' in unit_data:
                        contact = unit_data['contact']
                        if not contact.empty:
                            contact['val'] = val
                            contact['feature_name'] = groupname
                            data.append(contact)
                    if 'orientations' in unit_data:
                        orientations = unit_data['orientations']
                        if not orientations.empty:
                            orientations['val'] = np.nan
                            orientations['feature_name'] = groupname
                            data.append(orientations)

                val += u.thickness
            if len(data) == 0:
                print(f"No data found for group {groupname}, skipping.")
                continue
            data = pd.concat(data, ignore_index=True)
            foliation = self.model.create_and_add_foliation(
                groupname,
                series_surface_data=data,
                force_constrained=True,
                nelements=PlgSettingsStructure.interpolator_nelements,
                npw=PlgSettingsStructure.interpolator_npw,
                cpw=PlgSettingsStructure.interpolator_cpw,
                regularisation=PlgSettingsStructure.interpolator_regularisation,
            )
            self.model.add_unconformity(foliation, 0)
        self.model.stratigraphic_column = self.stratigraphic_column

    def update_fault_features(self):
        """Update the fault features in the geological model."""
        for fault_name, fault_data in self.faults.items():
            if 'data' in fault_data and not fault_data['data'].empty:
                data = fault_data['data'].copy()
                data['feature_name'] = fault_name
                data['val'] = 0
                # need to have a way of specifying the displacement from the trace
                # or maybe the model should calculate it
                if 'displacement' in fault_data['data']:
                    displacement = fault_data['data']['displacement'].mean()
                else:
                    displacement = 10
                if 'dip' in fault_data['data']:
                    dip = fault_data['data']['dip'].mean()
                else:
                    dip = 90
                print(f"Fault {fault_name} dip: {dip}")

                if 'pitch' in fault_data['data']:
                    pitch = fault_data['data']['pitch'].mean()
                else:
                    pitch = 0

                self.model.create_and_add_fault(
                    fault_name,
                    displacement=displacement,
                    fault_dip=dip,
                    fault_pitch=pitch,
                    fault_data=data,
                    nelements=PlgSettingsStructure.interpolator_nelements,
                    npw=PlgSettingsStructure.interpolator_npw,
                    cpw=PlgSettingsStructure.interpolator_cpw,
                    regularisation=PlgSettingsStructure.interpolator_regularisation,
                )
        for f in self.fault_topology.faults:
            for f2 in self.fault_topology.faults:

                if f != f2:
                    relationship = self.fault_topology.get_fault_relationship(f, f2)

                    if relationship is FaultRelationshipType.ABUTTING:
                        self.model[f].add_abutting_fault(self.model[f2])

    @property
    def valid(self):
        valid = True
        if len(self.groups) == 0:
            valid = False
        if len(self.stratigraphy) == 0:
            valid = False
        if len(self.faults) > 0:
            for _fault_name, fault_data in self.faults.items():
                if 'data' in fault_data and not fault_data['data'].empty:
                    valid = True
                else:
                    valid = False
        return valid

    def update_model(self):
        """Update the geological model with the current stratigraphy and faults."""

        self.model.features = []
        self.model.feature_name_index = {}

        # Update the model with stratigraphy
        self.update_fault_features()
        self.update_foliation_features()

        for observer in self.observers:
            observer()

    def features(self):
        return self.model.features

    def add_fold_frame(
        self,
        name: str,
        data: dict,
        folded_feature_name=None,
        sampler=AllSampler(),
        use_z_coordinate=False,
    ):
        # for z
        dfs = []
        for layer_data in data:
            if layer_data['type'] == 'Orientation':
                df = sampler(layer_data['df'], self.dem_function, use_z_coordinate)
                df['strike'] = df[layer_data['strike_field']]
                df['dip'] = df[layer_data['dip_field']]
                df['feature_name'] = name
                dfs.append(df[['X', 'Y', 'Z', 'strike', 'dip', 'feature_name']])
            elif layer_data['type'] == 'Formline':
                pass
            else:
                pass
        self.model.create_and_add_fold_frame(
            name, fold_frame_data=pd.concat(dfs, ignore_index=True)
        )
        # if folded_feature_name is not None:
        #     from LoopStructural.modelling.features._feature_converters import add_fold_to_feature

        #     folded_feature = self.model.get_feature_by_name(folded_feature_name)
        #     folded_feature_name = add_fold_to_feature(frame, folded_feature)
        #     self.model[folded_feature_name] = folded_feature
        for observer in self.observers:
            observer()

    def add_fold_to_feature(self, feature_name: str, fold_frame_name: str, fold_weights={}):

        from LoopStructural.modelling.features._feature_converters import add_fold_to_feature

        fold_frame = self.model.get_feature_by_name(fold_frame_name)
        if fold_frame is None:
            raise ValueError(f"Fold frame '{fold_frame_name}' not found in the model.")
        feature = self.model.get_feature_by_name(feature_name)
        if feature is None:
            raise ValueError(f"Feature '{feature_name}' not found in the model.")
        folded_feature = add_fold_to_feature(feature, fold_frame)
        self.model[feature_name] = folded_feature

    @property
    def fold_frames(self):
        """Return the fold frames in the model."""
        return [f for f in self.model.features if f.type == FeatureType.STRUCTURALFRAME]
