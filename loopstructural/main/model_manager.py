from collections import defaultdict
from typing import Callable

import geopandas as gpd
import numpy as np
import pandas as pd

from LoopStructural import GeologicalModel
from LoopStructural.datatypes import BoundingBox
from LoopStructural.modelling.core.fault_topology import FaultRelationshipType
from LoopStructural.modelling.core.stratigraphic_column import StratigraphicColumn
from LoopStructural.modelling.features import FeatureType, StructuralFrame
from LoopStructural.modelling.features.fold import FoldFrame
from loopstructural.toolbelt.preferences import PlgOptionsManager, PlgSettingsStructure
from loopstructural.main.utils import process_gdf_for_faults
from loopstructural.main.samplers import AllSampler



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
        fault_points, cols = process_gdf_for_faults(
            fault_trace=fault_trace,
            sampler=sampler,
            dem_function=self.dem_function,
            use_z_coordinate=use_z_coordinate,
            fault_name_field=fault_name_field,
            fault_dip_field=fault_dip_field,
            fault_displacement_field=fault_displacement_field,
            fault_pitch_field=fault_pitch_field,
        )
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
            opts = PlgOptionsManager.get_plg_settings()
            foliation = self.model.create_and_add_foliation(
                groupname,
                data=data,
                force_constrained=True,
                nelements=opts.interpolator_nelements,
                npw=opts.interpolator_npw,
                cpw=opts.interpolator_cpw,
                regularisation=opts.interpolator_regularisation,
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

                opts = PlgOptionsManager.get_plg_settings()
                self.model.create_and_add_fault(
                    fault_name,
                    displacement=displacement,
                    fault_dip=dip,
                    fault_pitch=pitch,
                    data=data,
                    nelements=opts.interpolator_nelements,
                    npw=opts.interpolator_npw,
                    cpw=opts.interpolator_cpw,
                    regularisation=opts.interpolator_regularisation,
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

    def add_foliation(
        self,
        name: str,
        data: dict,
        folded_feature_name=None,
        sampler=AllSampler(),
        use_z_coordinate=False,
    ):
        # for z
        dfs = []
        for layer_data in data.values():
            if layer_data['type'] == 'Orientation':
                df = sampler(layer_data['df'], self.dem_function, use_z_coordinate)
                df['strike'] = df[layer_data['strike_field']]
                df['dip'] = df[layer_data['dip_field']]
                df['feature_name'] = name
                dfs.append(df[['X', 'Y', 'Z', 'strike', 'dip', 'feature_name']])
            elif layer_data['type'] == 'Formline':
                pass
            elif layer_data['type'] == 'Value':
                df = sampler(layer_data['df'], self.dem_function, use_z_coordinate)
                df['val'] = df[layer_data['value_field']]
                df['feature_name'] = name
                dfs.append(df[['X', 'Y', 'Z', 'val', 'feature_name']])

            elif layer_data['type'] == 'Inequality':
                df = sampler(layer_data['df'], self.dem_function, use_z_coordinate)
                df['l'] = df[layer_data['lower_field']]
                df['u'] = df[layer_data['upper_field']]
                df['feature_name'] = name
                dfs.append(df[['X', 'Y', 'Z', 'l', 'u', 'feature_name']])

            else:
                raise ValueError(f"Unknown layer type: {layer_data['type']}")
        self.model.create_and_add_foliation(name, data=pd.concat(dfs, ignore_index=True))
        # if folded_feature_name is not None:
        #     from LoopStructural.modelling.features._feature_converters import add_fold_to_feature

        #     folded_feature = self.model.get_feature_by_name(folded_feature_name)
        #     folded_feature_name = add_fold_to_feature(frame, folded_feature)
        #     self.model[folded_feature_name] = folded_feature
        for observer in self.observers:
            observer()
    def add_unconformity(self, foliation_name: str, value: float, type: FeatureType = FeatureType.UNCONFORMITY):
        foliation = self.model.get_feature_by_name(foliation_name)
        if foliation is None:
            raise ValueError(f"Foliation '{foliation_name}' not found in the model.")
        if type == FeatureType.UNCONFORMITY:
            self.model.add_unconformity(foliation, value)
        elif type == FeatureType.ONLAPUNCONFORMITY:
            self.model.add_onlap_unconformity(foliation, value)

    def add_fold_to_feature(self, feature_name: str, fold_frame_name: str, fold_weights={}):

        from LoopStructural.modelling.features._feature_converters import add_fold_to_feature

        fold_frame = self.model.get_feature_by_name(fold_frame_name)
        if isinstance(fold_frame,StructuralFrame):
            fold_frame = FoldFrame(fold_frame.name,fold_frame.features, None, fold_frame.model)
        if fold_frame is None:
            raise ValueError(f"Fold frame '{fold_frame_name}' not found in the model.")
        feature = self.model.get_feature_by_name(feature_name)
        if feature is None:
            raise ValueError(f"Feature '{feature_name}' not found in the model.")
        folded_feature = add_fold_to_feature(feature, fold_frame)
        self.model[feature_name] = folded_feature

    def convert_feature_to_structural_frame(self, feature_name: str):
        from LoopStructural.modelling.features.builders import StructuralFrameBuilder

        builder = self.model.get_feature_by_name(feature_name).builder
        new_builder = StructuralFrameBuilder.from_feature_builder(builder)
        self.model[feature_name] = new_builder.frame

    @property
    def fold_frames(self):
        """Return the fold frames in the model."""
        return [f for f in self.model.features if f.type == FeatureType.STRUCTURALFRAME]
