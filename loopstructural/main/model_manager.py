"""Geological model manager utilities used by the LoopStructural plugin.

This module exposes the `GeologicalModelManager` which wraps a LoopStructural
`GeologicalModel` and provides helpers to ingest GeoDataFrames, update
stratigraphy and faults, evaluate features on point clouds or meshes, and
export results to GeoDataFrames or VTK meshes.

The goal of the manager is to isolate data transformation, sampling and
interaction with the LoopStructural model from the GUI code.
"""

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
        """Ingest basal contact traces and populate internal stratigraphy.

        Parameters
        ----------
        basal_contacts : geopandas.GeoDataFrame
            GeoDataFrame containing basal contact geometries and attributes.
        sampler : callable, optional
            Callable used to sample geometries to point rows (default: AllSampler()).
        unit_name_field : str or None
            Field name in `basal_contacts` giving the stratigraphic unit name. If
            None the function returns early.
        use_z_coordinate : bool
            If True, use Z values from geometries when available; otherwise use
            the manager's DEM function.

        Notes
        -----
        This method clears existing stratigraphy and replaces contact entries
        keyed by unit name. It does not notify observers; callers should call
        `update_model` or trigger observers as required.
        """
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
                data=data,
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
                    data=data,
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
        """Return the list of features currently held by the internal model.

        Returns
        -------
        list
            List-like collection of feature objects contained in the wrapped
            LoopStructural `GeologicalModel`.
        """
        return self.model.features

    def add_foliation(
        self,
        name: str,
        data: dict,
        folded_feature_name=None,
        sampler=AllSampler(),
        use_z_coordinate=False,
    ):
        """Create and add a foliation feature from grouped input layers.

        Parameters
        ----------
        name : str
            Name for the new foliation feature.
        data : dict
            Mapping of layer identifiers to dicts describing each layer. Each
            layer dict must include a 'type' key (one of 'Orientation',
            'Formline', 'Value', 'Inequality') and the fields required by that
            type (e.g. 'strike_field', 'dip_field', 'value_field', ...).
        folded_feature_name : str or None
            Optional name of a feature to which the foliation should be
            associated/converted (currently unused in this helper).
        sampler : callable, optional
            Callable used to sample provided GeoDataFrames into plain pandas
            rows (default: AllSampler()).
        use_z_coordinate : bool
            Whether to use Z coordinates from input geometries when present.

        Raises
        ------
        ValueError
            If a layer uses an unknown 'type' value.
        """
        # for z
        dfs = []
        kwargs={}
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
                kwargs['solver']='admm'
            else:
                raise ValueError(f"Unknown layer type: {layer_data['type']}")
        self.model.create_and_add_foliation(name, data=pd.concat(dfs, ignore_index=True),   **kwargs)
        # if folded_feature_name is not None:
        #     from LoopStructural.modelling.features._feature_converters import add_fold_to_feature

        #     folded_feature = self.model.get_feature_by_name(folded_feature_name)
        #     folded_feature_name = add_fold_to_feature(frame, folded_feature)
        #     self.model[folded_feature_name] = folded_feature
        for observer in self.observers:
            observer()

    def add_unconformity(self, foliation_name: str, value: float, type: FeatureType = FeatureType.UNCONFORMITY):
        """Add an unconformity (or onlap unconformity) to a named foliation.

        Parameters
        ----------
        foliation_name : str
            Name of an existing foliation feature in the model.
        value : float
            Value (level) at which the unconformity should be inserted.
        type : FeatureType
            Type of unconformity (default: FeatureType.UNCONFORMITY). Use
            FeatureType.ONLAPUNCONFORMITY for onlap-type behaviour.

        Raises
        ------
        ValueError
            If the foliation named by `foliation_name` cannot be found in the model.
        """
        foliation = self.model.get_feature_by_name(foliation_name)
        if foliation is None:
            raise ValueError(f"Foliation '{foliation_name}' not found in the model.")
        if type == FeatureType.UNCONFORMITY:
            self.model.add_unconformity(foliation, value)
        elif type == FeatureType.ONLAPUNCONFORMITY:
            self.model.add_onlap_unconformity(foliation, value)

    def add_fold_to_feature(self, feature_name: str, fold_frame_name: str, fold_weights={}):
        """Apply a FoldFrame to an existing feature, producing a folded feature.

        Parameters
        ----------
        feature_name : str
            Name of the feature to fold.
        fold_frame_name : str
            Name of an existing fold frame feature in the model to use for
            folding.
        fold_weights : dict
            Optional weights passed to the fold conversion; currently forwarded
            to the converter implementation.

        Raises
        ------
        ValueError
            If either the fold frame or the target feature cannot be found.
        """

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
        """Convert an interpolated feature into a StructuralFrame.

        This helper constructs a StructuralFrameBuilder from the existing
        feature's builder and replaces the feature in the model with the new
        frame instance.

        Parameters
        ----------
        feature_name : str
            Name of the feature to convert.
        """
        from LoopStructural.modelling.features.builders import StructuralFrameBuilder

        builder = self.model.get_feature_by_name(feature_name).builder
        new_builder = StructuralFrameBuilder.from_feature_builder(builder)
        self.model[feature_name] = new_builder.frame

    @property
    def fold_frames(self):
        """Return the fold frames in the model."""
        return [f for f in self.model.features if f.type == FeatureType.STRUCTURALFRAME]

    def evaluate_feature_on_points(self, feature_name: str, points: np.ndarray, scalar_type: str = 'scalar') -> np.ndarray:
        """Evaluate a model feature at the provided points.

        :param feature_name: Name of the feature to evaluate.
        :param points: Nx3 numpy array of points [x, y, z].
        :param scalar_type: 'scalar' or 'gradient'.
        :returns: numpy array of evaluated values. For 'scalar' an (N,) array is returned. For 'gradient' an (N,3) array is returned if supported.
        """
        if self.model is None:
            raise RuntimeError('No model available for evaluation')
        pts = np.asarray(points)
        if pts.ndim != 2 or pts.shape[1] < 3:
            raise ValueError('points must be an Nx3 array')

        try:
            if scalar_type == 'gradient':
                # Prefer a dedicated gradient evaluation method if available
                if hasattr(self.model, 'evaluate_feature_gradient'):
                    vals = self.model.evaluate_feature_gradient(feature_name, pts)
                else:
                    # Some models may support a gradient flag on the value evaluator
                    try:
                        vals = self.model.evaluate_feature_value(feature_name, pts, gradient=True)
                    except TypeError:
                        # Not supported by the model
                        raise RuntimeError('Model does not support gradient evaluation')
            else:
                vals = self.model.evaluate_feature_value(feature_name, pts)
            return np.asarray(vals)
        except Exception:
            # Re-raise with context preserved for the caller/UI to handle
            raise

    def export_feature_values_to_geodataframe(
        self,
        feature_name: str,
        points: np.ndarray,
        scalar_type: str = 'scalar',
        attributes: 'pd.DataFrame' = None,
        crs: str | None = None,
        value_field_name: str | None = None,
    ) -> 'gpd.GeoDataFrame':
        """Evaluate a feature on points and return a GeoDataFrame with results.

        :param feature_name: Feature name to evaluate.
        :param points: Nx3 array-like of points (x,y,z).
        :param scalar_type: 'scalar' or 'gradient'.
        :param attributes: Optional pandas DataFrame with attributes to attach (must have same length as points).
        :param crs: Optional CRS for the returned GeoDataFrame (e.g. 'EPSG:4326'). If None, GeoDataFrame will be created without CRS.
        :param value_field_name: Optional name for the value field; defaults to '{feature_name}_value' or '{feature_name}_gradient'.
        :returns: GeoDataFrame with geometry and value columns (and any provided attributes).
        """
        import pandas as _pd
        import geopandas as _gpd
        try:
            from shapely.geometry import Point as _Point
        except Exception:
            print("Shapely not available; geometry column will be omitted." )
            _Point = None
        
        pts = np.asarray(points)
        if pts.ndim != 2 or pts.shape[1] < 3:
            raise ValueError('points must be an Nx3 array')

        values = self.evaluate_feature_on_points(feature_name, pts, scalar_type=scalar_type)

        # Build a DataFrame
        df = _pd.DataFrame({'x': pts[:, 0], 'y': pts[:, 1], 'z': pts[:, 2]})

        if scalar_type == 'gradient':
            vals = np.asarray(values)
            if vals.ndim == 2 and vals.shape[1] == 3:
                df['gx'] = vals[:, 0]
                df['gy'] = vals[:, 1]
                df['gz'] = vals[:, 2]
                # also provide magnitude
                df[f'{feature_name}_gmag'] = np.linalg.norm(vals, axis=1)
            else:
                # Unexpected shape; attempt to flatten
                df[f'{feature_name}_gradient'] = list(vals)
        else:
            df[value_field_name or f"{feature_name}_value"] = np.asarray(values)

        # Attach attributes if provided
        if attributes is not None:
            try:
                attributes = _pd.DataFrame(attributes).reset_index(drop=True)
                df = _pd.concat([df.reset_index(drop=True), attributes.reset_index(drop=True)], axis=1)
            except Exception:
                # ignore attributes if they cannot be combined
                pass

        # Create geometry column
        geoms = None
        if _Point is not None:
            geoms = [_Point(x, y, z) for x, y, z in pts]
            gdf = _gpd.GeoDataFrame(df, geometry=geoms, crs=crs)
        else:
            # shapely not available; return a regular DataFrame inside a GeoDataFrame placeholder
            gdf = _gpd.GeoDataFrame(df)

        return gdf

    def export_feature_values_to_vtk_mesh(self,  name, mesh, scalar_type='scalar'):
        """Evaluate a feature on a mesh's points and attach the values as a field.

        Parameters
        ----------
        name : str
            Feature name to evaluate.
        mesh : pyvista.PolyData or similar
            Mesh-like object exposing a `points` array and supporting item
            assignment for point data (e.g. mesh[name] = values).
        scalar_type : str
            'scalar' or 'gradient' to control what is computed and attached.

        Returns
        -------
        mesh
            The same mesh instance with added/updated point data named `name`.
        """
        pts = mesh.points
        values = self.evaluate_feature_on_points(name, pts, scalar_type=scalar_type)
        mesh[name] = values
        return mesh