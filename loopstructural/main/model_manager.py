from collections import defaultdict
from collections.abc import Callable
from typing import Callable
import geopandas as gpd
import pandas as pd
from LoopStructural import GeologicalModel
from LoopStructural.datatypes import BoundingBox

from loopstructural.main.stratigraphic_column import StratigraphicColumn


class AllSampler:
    def __call__(self, line: gpd.GeoDataFrame, dem:Callable) -> pd.DataFrame:
        points = []
        feature_id = 0
        if line is None:
            return pd.DataFrame(points)
        for geom in line.geometry:
            attributes = line.iloc[feature_id].to_dict()
            attributes.pop('geometry', None)  # Remove geometry from attributes
            if geom.geom_type == 'LineString':
                coords = list(geom.coords)
                for x, y in coords:
                    points.append({'X': x, 'Y': y, 'Z': dem(x, y), 'feature_id': feature_id, **attributes})
            elif geom.geom_type == 'MultiLineString':
                for l in geom.geoms:
                    coords = list(l.coords)
                    for x, y in coords:
                        points.append({'X': x, 'Y': y, 'Z': dem(x, y), 'feature_id': feature_id, **attributes})

            elif geom.geom_type == 'Point':
                points.append({'X': geom.x, 'Y': geom.y, 'Z': dem(geom.x, geom.y), 'feature_id': feature_id, **attributes})
            feature_id += 1
        return pd.DataFrame(points)


class GeologicalModelManager:
    def __init__(self):
        self.model = GeologicalModel([0, 0, 0], [1, 1, 1])
        self.stratigraphy = {}
        self.groups = []
        self.faults = defaultdict(dict)
        self.stratigraphy = defaultdict(dict)
        self.observers = []
        self.dem_function = lambda x,y: 0
    def update_bounding_box(self, bounding_box: BoundingBox):
        self.model.bounding_box = bounding_box
    def set_dem_function(self, dem_function: Callable):
        """Set the function to get the elevation at a point."""
        self.dem_function = dem_function    
    def update_fault_points(self, fault_trace: gpd.GeoDataFrame, *, fault_name_field=None, fault_dip_field=None, fault_displacement_field=None, sampler=AllSampler()):
        """Add fault trace data to the geological model."""
        # sample fault trace
        self.faults.clear()  # Clear existing faults
        fault_points = sampler(fault_trace, self.dem_function)
        if fault_name_field is not None:
            fault_points['fault_name'] = fault_points[fault_name_field]
        else:
            fault_points['fault_name'] = fault_points['feature_id'].astype(str)
        for fault_name in fault_points['fault_name'].unique():
            self.faults[fault_name]['data'] = fault_points.loc[
                fault_points['fault_name'] == fault_name, ['X', 'Y', 'Z']
            ]


    def update_contact_traces(self, basal_contacts: gpd.GeoDataFrame, *, sampler=AllSampler(), unit_name_field=None):
        unit_points = sampler(basal_contacts,self.dem_function)
        if unit_name_field is not None:
            unit_points['unit_name'] = unit_points[unit_name_field]
        else:
            return
        for unit_name in unit_points['unit_name'].unique():
            self.stratigraphy[unit_name] = unit_points.loc[
                unit_points['unit_name'] == unit_name, ['X', 'Y', 'Z']
            ]

    def update_structural_data(self, structural_orientations: gpd.GeoDataFrame, *, strike_field=None, dip_field=None, unit_name_field=None,dip_direction=False):
        """Add structural orientation data to the geological model."""
        if strike_field is None or dip_field is None:
            return
        if unit_name_field is not None:
            return
        structural_orientations = structural_orientations.copy()
        structural_orientations['unit_name'] = structural_orientations[unit_name_field]
        structural_orientations['X'] = structural_orientations.geometry.x
        structural_orientations['Y'] = structural_orientations.geometry.y
        structural_orientations['Z'] = structural_orientations.apply(
            lambda row: self.dem_function(row.geometry.x, row.geometry.y), axis=1
        )
        structural_orientations['dip'] = structural_orientations[dip_field]
        structural_orientations['strike'] = structural_orientations[strike_field]
        structural_orientations = structural_orientations[['X', 'Y', 'Z', 'dip', 'strike', 'unit_name']]
        if dip_direction:
            structural_orientations['dip'] = structural_orientations[dip_field]
            structural_orientations['strike'] = structural_orientations[strike_field]+90

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

    def update_stratigraphic_unit(self, unit_data):
        self.data

    def update_foliation_features(self):
        stratigraphic_column = {}
        unit_id = 0
        for i, units in enumerate(self.groups):
            val = 0
            data = []
            groupname = f"Group_{i + 1}"
            stratigraphic_column[groupname] = {}
            for u in reversed(units):
                unit_data = self.stratigraphy.get(u.name, None)
                if unit_data is None:
                    continue
                else:
                    stratigraphic_column[groupname][u.name] = {
                        "max": val + u.thickness,
                        "min": val,
                        "id": unit_id,
                        "colour": u.colour,
                    }
                    unit_data = unit_data.copy()
                    unit_data['val'] = val
                    unit_data['feature_name'] = groupname
                    data.append(unit_data)
                unit_id += 1
                val += u.thickness
            if len(data) == 0:
                continue
            data = pd.concat(data, ignore_index=True)
            foliation = self.model.create_and_add_foliation(groupname, series_surface_data=data)
            self.model.add_unconformity(foliation,0)
        self.model.set_stratigraphic_column(stratigraphic_column)

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
        # if not self.valid:
        #     raise ValueError("Model is not valid. Please check the data.")
        # Update the model with faults
        for fault_name, fault_data in self.faults.items():
            if 'data' in fault_data and not fault_data['data'].empty:
                data = fault_data['data'].copy()
                data['feature_name'] = fault_name
                data['val'] = 0
                self.model.create_and_add_fault(fault_name, 10,fault_data=data)     
        # Update the model with stratigraphy
        self.update_foliation_features()

        

        for observer in self.observers:
            observer()
    def features(self):
        return self.model.features
