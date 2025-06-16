from collections import defaultdict

import geopandas as gpd
import pandas as pd
from LoopStructural import GeologicalModel
from LoopStructural.datatypes import BoundingBox

from loopstructural.main.stratigraphic_column import StratigraphicColumn


class AllSampler:
    def __call__(self, line: gpd.GeoDataFrame) -> pd.DataFrame:
        return


class GeologicalModelManager:
    def __init__(self):
        self.model = GeologicalModel([0, 0, 0], [1, 1, 1])
        self.stratigraphy = {}
        self.groups = []
        self.faults = defaultdict(dict)

    def update_bounding_box(self, bounding_box: BoundingBox):
        self.model.bounding_box = bounding_box

    def update_fault_points(self, fault_trace: gpd.GeoDataFrame, *, sampler=AllSampler):
        """Add fault trace data to the geological model."""
        # sample fault trace
        fault_points = sampler(fault_trace)

        for fault_name in fault_points['fault_name'].unique():
            self.faults[fault_name]['data'] = fault_points.loc[
                fault_points['fault_name'] == fault_name, ['X', 'Y', 'Z']
            ]

    def update_contact_traces(self, basal_contacts: gpd.GeoDataFrame, *, sampler=AllSampler):
        unit_points = sampler(basal_contacts)
        for unit_name in unit_points['unit_name'].unique():
            self.stratigraphy[unit_name] = unit_points.loc[
                unit_points['unit_name'] == unit_name, [['X', 'Y', 'Z']]
            ]

    def update_structural_data(self, structural_orientations: gpd.GeoDataFrame):
        """Add structural orientation data to the geological model."""
        for unit_name in structural_orientations['unit_name'].unique():
            orientations = structural_orientations.loc[
                structural_orientations['unit_name'] == unit_name, ['X', 'Y', 'Z', 'dip', 'strike']
            ]
            self.stratigraphy[unit_name]['orientations'] = orientations

    def update_stratigraphic_column(self, stratigraphic_column: StratigraphicColumn):
        # new_groups = stratigraphic_column.get_groups()
        # old_groups = self.groups.copy()
        # would be nice to check if the groups have changed
        # and if the contents of the group have changed
        # but for now just update groups when the stratigraphic column is updated
        #        # Update the model with the new stratigraphic column
        self.groups = stratigraphic_column.get_groups()
        self.update_foliation_features()

    def update_foliation_features(self):
        for i, units in enumerate(self.groups):
            val = 0
            data = []
            groupname = f"Group_{i + 1}"
            for u in reversed(units):
                unit_data = self.stratigraphy.get(u, None)
                if unit_data is None:
                    continue
                else:
                    unit_data = unit_data.copy()
                    unit_data['val'] = val
                    unit_data['feature_name'] = groupname
                    data.append(unit_data)
                val += u.thickness

            data = pd.concat(data, ignore_index=True)
            self.model.create_and_add_foliation(groupname, series_surface_data=data)

    def update_fault_features(self):
        """Update the fault features in the geological model."""
        for fault_name, fault_data in self.faults.items():
            if 'data' in fault_data and not fault_data['data'].empty:
                data = fault_data['data'].copy()
                data['feature_name'] = fault_name
                data['val'] = 0
                # need to have a way of specifying the displacement from the trace
                # or maybe the model should calculate it
                self.model.create_and_add_fault(fault_name, displacement=10, fault_data=data)

    @property
    def valid(self):
        valid = True
        if len(self.groups) == 0:
            valid = False
        if len(self.stratigraphy) == 0:
            valid = False
        if len(self.faults) > 0:
            for fault_name, fault_data in self.faults.items():
                if 'data' in fault_data and not fault_data['data'].empty:
                    valid = True
                else:
                    valid = False
        return valid

    def update_model(self):
        """Update the geological model with the current stratigraphy and faults."""
        if not self.valid:
            raise ValueError("Model is not valid. Please check the data.")

        # Update the model with stratigraphy
        for unit_name, unit_data in self.stratigraphy.items():
            self.model.add_stratigraphic_unit(unit_name, unit_data)

        # Update the model with faults
        for fault_name, fault_data in self.faults.items():
            if 'data' in fault_data and not fault_data['data'].empty:
                self.model.add_fault(fault_name, fault_data['data'])

        # Finalize the model
        self.model.finalize()
