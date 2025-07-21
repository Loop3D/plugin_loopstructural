from collections import defaultdict
from collections.abc import Callable
from tracemalloc import start
from typing import Callable
import geopandas as gpd
import pandas as pd
from LoopStructural import GeologicalModel
from LoopStructural.datatypes import BoundingBox
from loopstructural.main.stratigraphic_column import StratigraphicColumn


class AllSampler:
    """This is a simple sampler that just returns all the points, or all of the vertices
    of a line. It will also copy the elevation from the DEM or the elevation set in the data manager.
    """
    def __call__(self, line: gpd.GeoDataFrame, dem:Callable) -> pd.DataFrame:
        """Sample the line and return a DataFrame with X, Y, Z coordinates and attributes."""
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
        self.observers = []
        self.dem_function = lambda x,y: 0
    def set_stratigraphic_column(self, stratigraphic_column: StratigraphicColumn):
        """Set the stratigraphic column for the geological model manager."""
        self.stratigraphic_column = stratigraphic_column
        
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
    def update_fault_points(self, fault_trace: gpd.GeoDataFrame, *, fault_name_field=None, fault_dip_field=None, fault_displacement_field=None, sampler=AllSampler()):
        """Add fault trace data to the geological model.
        :param fault_trace: A GeoDataFrame containing the fault trace data.
        :param fault_name_field: The field name for the fault name.
        :param fault_dip_field: The field name for the fault dip.
        :param fault_displacement_field: The field name for the fault displacement.
        :param sampler: A callable that samples the fault trace and returns a DataFrame with X, Y, Z coordinates.
        """
        # sample fault trace
        self.faults.clear()  # Clear existing faults
        fault_points = sampler(fault_trace, self.dem_function)
        if fault_name_field is not None and fault_name_field in fault_points.columns:
            fault_points['fault_name'] = fault_points[fault_name_field]
        else:
            fault_points['fault_name'] = fault_points['feature_id'].astype(str)
        if fault_dip_field is not None and fault_dip_field in fault_points.columns:
            fault_points['dip'] = fault_points[fault_dip_field]
        if fault_displacement_field is not None and fault_displacement_field in fault_points.columns:
            fault_points['displacement'] = fault_points[fault_displacement_field]
        for fault_name in fault_points['fault_name'].unique():
            self.faults[fault_name]['data'] = fault_points.loc[
                fault_points['fault_name'] == fault_name, ['X', 'Y', 'Z']
            ]


    def update_contact_traces(self, basal_contacts: gpd.GeoDataFrame, *, sampler=AllSampler(), unit_name_field=None):

        unit_points = sampler(basal_contacts,self.dem_function)
        if len(unit_points) == 0 or unit_points.empty:
            print("No basal contacts found or empty GeoDataFrame.")
            return
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
        unit_id = 0
        for i, group in enumerate(self.stratigraphic_column.get_groups()):
            val = 0
            data = []
            groupname = group.name
            stratigraphic_column[groupname] = {}
            for u in reversed(group.units):
                unit_data = self.stratigraphy.get(u.name, None)
                if unit_data is None:
                    continue
                else:
                
                    unit_data = unit_data.copy()
                    unit_data['val'] = val
                    unit_data['feature_name'] = groupname
                    data.append(unit_data)
                val += u.thickness
            if len(data) == 0:
                print(f"No data found for group {groupname}, skipping.")
                continue
            data = pd.concat(data, ignore_index=True)
            foliation = self.model.create_and_add_foliation(groupname, series_surface_data=data)
            self.model.add_unconformity(foliation,0)
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
        
        self.model.features = []
        self.model.feature_name_index={}
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
