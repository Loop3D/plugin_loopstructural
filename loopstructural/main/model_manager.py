"""Geological model manager utilities used by the LoopStructural plugin.

This module exposes the `GeologicalModelManager` which wraps a LoopStructural
`GeologicalModel` and provides helpers to ingest GeoDataFrames, update
stratigraphy and faults, evaluate features on point clouds or meshes, and
export results to GeoDataFrames or VTK meshes.

The goal of the manager is to isolate data transformation, sampling and
interaction with the LoopStructural model from the GUI code.
"""

from collections import defaultdict
from contextlib import contextmanager
from typing import Callable, Dict, Optional, Union

import geopandas as gpd
import numpy as np
import pandas as pd
from LoopStructural.datatypes import BoundingBox
from LoopStructural.modelling.core.fault_topology import FaultRelationshipType
from LoopStructural.modelling.core.stratigraphic_column import StratigraphicColumn
from LoopStructural.modelling.features import FeatureType, StructuralFrame
from LoopStructural.modelling.features.fold import FoldFrame
from LoopStructural.utils.observer import Observable

from LoopStructural import GeologicalModel
from loopstructural.toolbelt.preferences import PlgSettingsStructure

from ..main.data_types import FaultEntry, StratigraphyEntry
from ..main.helpers import qgisAttributeIsNone


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

                coords = list(geom.coords[0])
                # Use Z from geometry if available, otherwise use DEM
                if use_z and len(coords) > 2:
                    z = coords[2]
                elif dem is not None:
                    z = dem(coords[0], coords[1])
                else:
                    z = 0
                points.append(
                    {'X': coords[0], 'Y': coords[1], 'Z': z, 'feature_id': feature_id, **attributes}
                )
            feature_id += 1
        df = pd.DataFrame(points)
        return df


class GeologicalModelManager(Observable):
    """This class manages the geological model and assembles it from the data provided by the data manager.
    It is responsible for updating the model with faults, stratigraphy, and other geological features.
    """

    def __init__(self, debug_manager=None):
        """Initialize the geological model manager."""
        # Initialize Observable state
        super().__init__()

        self.model = GeologicalModel([0, 0, 0], [1, 1, 1])
        self.groups = []
        self.faults: Dict[str, FaultEntry] = defaultdict(dict)
        self.stratigraphy: Dict[str, StratigraphyEntry] = defaultdict(dict)
        self.stratigraphic_column = None
        self.fault_topology = None
        # Observers managed by Observable base class
        self.dem_function = lambda x, y: 0
        # internal flag to temporarily suppress notifications (used when
        # updates are performed in background threads)
        self._suppress_notifications = False
        self._debug_manager = debug_manager
        # True once the fault topology (abutting/faulted/stratigraphy
        # relationships) has changed since the model was last (re-)built by
        # Initialize Model. Those relationships are only applied while
        # constructing fault features in `update_fault_features`, so unlike a
        # parameter tweak, `update_all_features`/Solve Model can't pick them
        # up -- see `set_fault_topology`.
        self._topology_dirty = False

    @contextmanager
    def suspend_notifications(self):
        prev = getattr(self, '_suppress_notifications', False)
        self._suppress_notifications = True
        try:
            yield
        finally:
            self._suppress_notifications = prev

    def _emit(self, *args, **kwargs):
        """Emit an observer notification unless notifications are suppressed.

        This wrapper should be used instead of calling self.notify directly from
        the manager so callers can suppress notifications when running updates
        on background threads.
        """
        if getattr(self, '_suppress_notifications', False):
            return
        try:
            self.notify(*args, **kwargs)
        except Exception:
            # be tolerant of observer errors
            pass

    def reset(self):
        """Reset the geological model manager to its initial, empty state.

        Discards the wrapped LoopStructural model along with any ingested
        fault/stratigraphy data, and restores the default DEM function. The
        `stratigraphic_column` and `fault_topology` references are left
        untouched since the data manager clears those objects in place.
        """
        self._emit('model_update_started')
        self.model = GeologicalModel([0, 0, 0], [1, 1, 1])
        self.groups = []
        self.faults = defaultdict(dict)
        self.stratigraphy = defaultdict(dict)
        self.dem_function = lambda x, y: 0
        self._topology_dirty = False
        self._emit('model_updated')
        self._emit('model_update_finished')

    def save_model(self, filepath):
        """Save the wrapped geological model to `filepath`.

        Parameters
        ----------
        filepath : str
            Destination path for the pickled (dill) model file.
        """
        self.model.to_file(filepath)

    def load_model(self, filepath):
        """Load a geological model previously saved with `save_model` and
        adopt it as the manager's active model, notifying observers so the
        UI refreshes to show the loaded model.

        Parameters
        ----------
        filepath : str
            Path to a model file previously written by `save_model`.
        """
        self._emit('model_update_started')
        model = GeologicalModel.from_file(filepath)
        if model is not None:
            self.model = model
            # The loaded model is a standalone snapshot; there's no pending
            # topology edit against it yet, so don't carry over a stale flag
            # from whatever model was previously loaded.
            self._topology_dirty = False
        self._emit('model_updated')
        self._emit('model_update_finished')

    def set_stratigraphic_column(self, stratigraphic_column: StratigraphicColumn):
        """Set the stratigraphic column for the geological model manager."""
        self.stratigraphic_column = stratigraphic_column
        # changing the stratigraphic column changes model geometry
        self._emit('stratigraphic_column_changed')

    def set_fault_topology(self, fault_topology):
        """Set the fault topology for the geological model manager.

        Also attaches an observer so that editing a fault-fault (abutting/
        faulted) or fault-stratigraphy relationship -- e.g. from the Fault
        Adjacency tab -- is reflected in the model's build status. See
        `_on_fault_topology_changed`.
        """
        self.fault_topology = fault_topology
        if fault_topology is not None:
            try:
                # no event name given: fires for every notify() the topology
                # makes (fault_relationship_updated, fault_added, ...)
                fault_topology.attach(self._on_fault_topology_changed)
            except Exception:
                pass

    # Topology events that change what actually feeds the interpolator (as
    # opposed to just which side of an already-solved fault gets cropped
    # away) and therefore need Initialize Model to be re-run before Solve
    # Model can pick them up.
    _TOPOLOGY_EVENTS_REQUIRING_REINIT = {
        'faulted_relationship_added',
        'fault_added',
        'fault_removed',
        'stratigraphy_fault_relationship_added',
        'stratigraphy_fault_relationship_updated',
        'stratigraphy_fault_relationship_removed',
        'fault_topology_reset',
    }

    def _on_fault_topology_changed(self, _observable, event, *args, **kwargs):
        """React to a fault topology edit made via the Fault Adjacency tab.

        ABUTTING relationships are just a region crop applied to an
        already-solved fault (see `apply_fault_abutting_relationships`), so
        those are always reconciled immediately here -- cheap, idempotent,
        and doesn't touch the model's build status, matching the fact that
        clipping doesn't change the solved surfaces.

        FAULTED relationships (which add a fault as an interpolation
        dependency of another), fault-stratigraphy relationships, and faults
        being structurally added/removed are different: those genuinely
        change what feeds the interpolator, and are only applied while
        constructing fault features in `update_fault_features` -- part of
        Initialize Model, not Solve Model. For those we flag `_topology_dirty`
        (surfaced through `model_state`) and mark any already-built
        fault/unit named in the event as not built, so its tick turns red
        immediately rather than staying (wrongly) green until the user
        notices Solve Model didn't actually pick up the change.
        """
        payload = args[0] if args and isinstance(args[0], dict) else kwargs

        try:
            self.apply_fault_abutting_relationships()
        except Exception:
            pass

        new_relationship = payload.get('new_relationship_type')
        requires_reinit = (
            event in self._TOPOLOGY_EVENTS_REQUIRING_REINIT
            or new_relationship is FaultRelationshipType.FAULTED
        )
        if requires_reinit:
            self._topology_dirty = True
            names = {
                payload.get(key)
                for key in ('fault', 'related_fault', 'abutting_fault', 'faulted_fault', 'unit')
                if payload.get(key)
            }
            for name in names:
                feature = self.model.get_feature_by_name(name)
                builder = getattr(feature, 'builder', None) if feature is not None else None
                if builder is not None:
                    try:
                        builder.set_not_up_to_date(self)
                    except Exception:
                        pass

        self._emit('model_updated')

    def update_bounding_box(self, bounding_box: BoundingBox):
        """Update the bounding box of the geological model.

        Parameters
        ----------
        bounding_box : BoundingBox
            The new bounding box for the internal LoopStructural model.
        """
        self.model.bounding_box = bounding_box

    def set_dem_function(self, dem_function: Callable):
        """Set the function used to obtain elevation (Z) values.

        Parameters
        ----------
        dem_function : Callable
            Callable taking (x, y) and returning an elevation (z).
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

        Parameters
        ----------
        fault_trace : geopandas.GeoDataFrame
            GeoDataFrame containing the fault trace geometries and attributes.
        fault_name_field : str or None
            Field name in `fault_trace` indicating the fault identifier. If
            not provided the sampler's `feature_id` is used.
        fault_dip_field : str or None
            Optional field name providing dip values for fault points.
        fault_displacement_field : str or None
            Optional field name providing displacement values for fault points.
        fault_pitch_field : str or None
            Optional field name providing fault pitch values.
        sampler : callable, optional
            Callable used to sample geometries to point rows (default: AllSampler()).
        use_z_coordinate : bool
            If True, use Z values from geometries when available; otherwise use
            the manager's DEM function.

        Returns
        -------
        None
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
        # signal that fault point input changed
        self._emit('data_changed', 'fault_points')

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
            self._debug_manager.log("No basal contacts found or empty GeoDataFrame.", log_level=2)
            return
        if unit_name_field is not None:
            unit_points['unit_name'] = unit_points[unit_name_field].astype(str)
        else:
            return
        for unit_name in unit_points['unit_name'].unique():
            self.stratigraphy[unit_name]['contact'] = unit_points.loc[
                unit_points['unit_name'] == unit_name, ['X', 'Y', 'Z']
            ]

        # signal that input data changed — consumers may choose to rebuild the model
        self._emit('data_changed', 'contact_traces')

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

        # signal structural orientation data changed
        self._emit('data_changed', 'structural_orientations')

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
            self._report_progress(f"Building stratigraphic group '{group.name}'")
            # check if the attribute is none, if its none we want so skip as it could be an
            # ambiguous attribute and cause multiple data assocaited with different features
            # to be applied the same value.
            if qgisAttributeIsNone(group) is None:
                self._debug_manager.log(f"Group {group.name} has no data, skipping.", log_level=2)
                continue
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
                self._debug_manager.log(
                    f"No data found for group {groupname}, skipping.", log_level=2
                )
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
        # foliation features were rebuilt; let observers know
        self._emit('foliation_features_updated')

    def _report_progress(self, message: str):
        """Report progress on a long-running model update.

        `update_model`/`update_all_features` stash a `_progress_callback`/
        `_progress_total` pair for the duration of the update; this increments
        the step counter and forwards `(message, current, total)` to that
        callback, if one was given (e.g. the GUI's progress dialog).

        Always also logs the step via the debug manager (when one is
        configured), independent of whether a progress_callback was supplied.
        With the plugin's Debug Mode setting enabled this is the way to see
        which feature a long-running Initialize/Solve is currently on, e.g.
        to tell a slow solve apart from a genuine hang.
        """
        self._progress_current = getattr(self, '_progress_current', 0) + 1
        current = self._progress_current
        total = getattr(self, '_progress_total', 0)

        dbg = getattr(self, '_debug_manager', None)
        if dbg is not None:
            try:
                dbg.log(f"{message} ({current}/{total})", log_level=0)
            except Exception:
                pass

        callback = getattr(self, '_progress_callback', None)
        if callback is not None:
            try:
                callback(message, current, total)
            except Exception:
                pass

    def update_fault_features(self):
        """Update the fault features in the geological model."""
        for fault_name, fault_data in self.faults.items():
            self._report_progress(f"Building fault '{fault_name}'")
            if qgisAttributeIsNone(fault_name):
                # check if the attribute is none, if its none we want so skip as it could be an
                # ambiguous attribute and cause multiple data assocaited with different features
                # to be applied the same value.
                # The DebugManager forwards to the toolbelt logger which is safe to
                # call from background threads. Call it directly and swallow any
                # exceptions to avoid causing freezes.
                try:
                    dbg = getattr(self, '_debug_manager', None)
                    if dbg is not None and hasattr(dbg, 'log'):
                        dbg.log('Skipping fault with no name.', log_level=2)
                except Exception:
                    pass
                continue
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
        self.apply_fault_abutting_relationships()

    def apply_fault_abutting_relationships(self):
        """Re-apply fault-fault ABUTTING relationships as region crops on the
        already-built fault surfaces, for every pair currently in the topology.

        `FaultSegment.add_abutting_fault` just adds a Positive/NegativeRegion
        to the fault's coordinate-0 feature (see LoopStructural's
        `_fault_segment.py`) -- it's a post-hoc crop of an already-solved
        fault, not something that feeds into the interpolation. So unlike
        FAULTED relationships (which add a fault as an interpolation
        dependency of another) this is cheap and safe to call any time the
        fault topology changes, without needing Initialize Model or Solve
        Model, and without invalidating the model's build status.

        Idempotent: skips pairs already cropped correctly (tracked via each
        fault's `.abut` dict), and undoes a previously-applied crop for any
        pair that's no longer marked ABUTTING -- so this alone keeps abutting
        relationships in sync with the topology table, however it changed.
        """
        if self.fault_topology is None:
            return
        for f in self.fault_topology.faults:
            fault_feature = self.model.get_feature_by_name(f)
            if fault_feature is None or not hasattr(fault_feature, 'abut'):
                continue
            coord0 = fault_feature.__getitem__(0)
            for f2 in self.fault_topology.faults:
                if f == f2:
                    continue
                relationship = self.fault_topology.get_fault_relationship(f, f2)
                existing_region = fault_feature.abut.get(f2)
                if relationship is FaultRelationshipType.ABUTTING:
                    if existing_region is not None:
                        continue  # already cropped against f2
                    f2_feature = self.model.get_feature_by_name(f2)
                    if f2_feature is None:
                        continue
                    # Determine which side of f2 to keep ourselves, ignoring any
                    # regions already applied to f2 (e.g. from an earlier abutting
                    # relationship in the fault network). LoopStructural's own
                    # auto-detection inside add_abutting_fault evaluates f2 with
                    # its existing regions applied, so if f's trace falls where f2
                    # has already been cropped away, it gets an all-NaN value,
                    # nanmedian(...) > 0 silently becomes False, and the wrong side
                    # is kept -- which can crop the fault away entirely.
                    pts = coord0.builder.data[["X", "Y", "Z"]].to_numpy()
                    abut_value = np.nanmedian(f2_feature.evaluate_value(pts, ignore_regions=True))
                    positive = bool(abut_value > 0)
                    fault_feature.add_abutting_fault(f2_feature, positive=positive)
                elif existing_region is not None:
                    # relationship changed away from ABUTTING: undo the crop
                    try:
                        coord0.regions.remove(existing_region)
                    except ValueError:
                        pass
                    fault_feature.abut.pop(f2, None)

    def is_feature_built(self, feature, _seen: Optional[set] = None) -> Optional[bool]:
        """Best-effort check of whether `feature` has been solved (interpolated).

        Reads LoopStructural's internal builder `_up_to_date` flag(s) rather than
        calling `builder.up_to_date()`, since that method rebuilds as a side
        effect when the feature is stale -- not something a passive status check
        should trigger. Faults and structural frames delegate to three
        per-coordinate sub-builders and never set their own top-level flag, so
        those are checked individually.

        Also checks transitively through `builder.faults` -- the features this
        one was cut/affected by (e.g. faults a stratigraphic surface is cut
        by). LoopStructural doesn't retroactively invalidate a feature when
        something it depends on changes; a dependency becoming stale only
        matters the next time *its own* `up_to_date()` is called, which also
        rebuilds it as a side effect. So without this, editing a fault would
        only show the fault itself as "not built" while every surface it
        cuts kept showing a stale green tick.

        Returns
        -------
        bool or None
            True/False if the build state could be determined, otherwise None
            (unrecognised builder shape).
        """
        if _seen is None:
            _seen = set()
        if id(feature) in _seen:
            return True  # cycle guard: don't re-derive, assume fine
        _seen.add(id(feature))

        builder = getattr(feature, 'builder', None)
        if builder is None:
            return None
        sub_builders = getattr(builder, 'builders', None)
        if sub_builders:
            try:
                own_built = all(getattr(b, '_up_to_date', False) for b in sub_builders)
            except Exception:
                return None
        elif hasattr(builder, '_up_to_date'):
            own_built = bool(builder._up_to_date)
        else:
            return None

        if not own_built:
            return False

        for dependency in getattr(builder, 'faults', None) or []:
            if self.is_feature_built(dependency, _seen) is False:
                return False
        return True

    @property
    def model_state(self) -> str:
        """Coarse summary of the model's build state, for display in the GUI.

        Returns 'empty' (no features yet), 'stale' (fault topology changed
        since the last Initialize Model -- Solve Model alone can't apply
        that, see `_on_fault_topology_changed`), 'initialized' (features
        exist but at least one hasn't been solved) or 'solved' (everything is
        up to date).
        """
        features = [f for f in self.features() if not f.name.startswith('__')]
        if not features:
            return 'empty'
        if getattr(self, '_topology_dirty', False):
            return 'stale'
        if all(self.is_feature_built(f) for f in features):
            return 'solved'
        return 'initialized'

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

    def update_model(
        self,
        notify_observers: bool = True,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ):
        """Update the geological model with the current stratigraphy and faults.

        Parameters
        ----------
        notify_observers : bool
            If True (default) observers will be notified after the model update
            completes. If False, the caller is responsible for notifying
            observers from the main thread (useful when performing the update
            in a background thread).
        progress_callback : callable or None
            Optional callable invoked as `callback(message, current, total)` as
            each fault/stratigraphic group is built, so callers (e.g. a GUI
            progress dialog) can report what step is currently running. Safe to
            call from a background thread as long as the callback itself is
            thread-safe (e.g. it forwards to a Qt signal rather than touching
            widgets directly).
        """

        self.model.features = []
        self.model.feature_name_index = {}

        # Notify start (if requested) so UI can react
        if notify_observers:
            self._emit('model_update_started')

        group_count = (
            len(self.stratigraphic_column.get_groups()) if self.stratigraphic_column else 0
        )
        self._progress_callback = progress_callback
        self._progress_total = len(self.faults) + group_count
        self._progress_current = 0
        dbg = getattr(self, '_debug_manager', None)
        if dbg is not None:
            try:
                dbg.log(
                    f"Initialize Model: building {len(self.faults)} fault(s) and "
                    f"{group_count} stratigraphic group(s)",
                    log_level=0,
                )
            except Exception:
                pass
        try:
            # Update the model with stratigraphy
            self.update_fault_features()
            self.update_foliation_features()
            # fault topology (abutting/faulted/stratigraphy relationships) was
            # just re-applied above, so any pending topology edit is now current
            self._topology_dirty = False
        finally:
            self._progress_callback = None
        if dbg is not None:
            try:
                dbg.log("Initialize Model: finished", log_level=0)
            except Exception:
                pass

        # Notify observers using the Observable framework if requested
        if notify_observers:
            self._emit('model_updated')
            self._emit('model_update_finished')

    def update_feature(self, feature_name: str):
        """Update a specific feature in the geological model.

        Parameters
        ----------
        feature_name : str
            Name of the feature to update.
        """
        feature = self.model.get_feature_by_name(feature_name)
        if feature is None:
            raise ValueError(f"Feature '{feature_name}' not found in the model.")
        # Allow UI to react to a feature update
        self._emit('model_update_started')
        feature.builder.update()
        # Notify observers and include feature name for interested listeners
        self._emit('feature_updated', feature_name)
        self._emit('model_update_finished')

    def update_all_features(
        self,
        subset: Optional[Union[list, str]] = None,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        notify_observers: bool = True,
    ):
        """Update (solve) all features in the geological model.

        Parameters
        ----------
        subset : list, str, or None
            Optional subset of feature names (or 'faults'/'stratigraphy') to
            update; all features are solved if not provided.
        progress_callback : callable or None
            Optional callable invoked as `callback(message, current, total)` as
            each feature is solved, mirroring `update_model`'s progress
            reporting. See `update_model` for thread-safety notes.
        notify_observers : bool
            If True (default) observers will be notified via `_emit` around the
            solve. Pass False when calling from a background thread: this
            plugin's GUI observers are plain Python callbacks (not Qt signals),
            so `_emit` invokes them synchronously on whatever thread calls this
            method -- if that's a worker thread, GUI-touching observers end up
            creating/mutating Qt widgets off the GUI thread, which is undefined
            behaviour in Qt and can hang or corrupt the application. The caller
            is then responsible for notifying observers from the main thread
            once the background call returns (see `update_model` and the GUI's
            `_run_model_task`/`_on_task_finished`).
        """
        # Allow UI to react to a feature update
        if notify_observers:
            self._emit('model_update_started')
        dbg = getattr(self, '_debug_manager', None)
        self._progress_callback = progress_callback
        self._progress_current = 0
        if subset is not None:

            if isinstance(subset, str):
                if subset == 'faults':
                    subset = [f.name for f in self.model.features if f.type == FeatureType.FAULT]
                elif subset == 'stratigraphy' or subset == 'foliations':
                    subset = [
                        f.name for f in self.model.features if f.type == FeatureType.FOLIATION
                    ]
                else:
                    subset = [subset]
            self._progress_total = len(subset)
            if dbg is not None:
                try:
                    dbg.log(f"Solve Model: solving {len(subset)} feature(s)", log_level=0)
                except Exception:
                    pass
            try:
                for feature_name in subset:
                    feature = self.model.get_feature_by_name(feature_name)
                    if feature is not None:
                        self._report_progress(f"Solving '{feature_name}'")
                        feature.builder.update()
            finally:
                self._progress_callback = None
        else:
            # mirrors GeologicalModel.update(), but reports progress per visible
            # feature instead of requiring tqdm
            visible_features = [f for f in self.model.features if not f.name.startswith('__')]
            self._progress_total = len(visible_features)
            if dbg is not None:
                try:
                    dbg.log(f"Solve Model: solving {len(visible_features)} feature(s)", log_level=0)
                except Exception:
                    pass
            try:
                for f in self.model.features:
                    if not f.name.startswith('__'):
                        self._report_progress(f"Solving '{f.name}'")
                    f.builder.up_to_date()
            finally:
                self._progress_callback = None
        if dbg is not None:
            try:
                dbg.log("Solve Model: finished", log_level=0)
            except Exception:
                pass
        # Notify observers and include feature name for interested listeners
        if notify_observers:
            self._emit('all_features_updated')
            self._emit('model_update_finished')

    def features(self):
        """Return the list of features currently held by the internal model.

        Returns
        -------
        list
            List-like collection of feature objects contained in the wrapped
            LoopStructural `GeologicalModel`.
        """
        return self.model.features

    def get_stratigraphy_entry(self, unit_name: str) -> Optional[StratigraphyEntry]:
        """Return the raw contact/orientation data ingested for `unit_name`, if any.

        Accessor for `self.stratigraphy`, so callers outside this class (e.g.
        the data manager, syncing what's shown in the "Data Layers" table)
        don't need to know it's a plain dict keyed by unit name.
        """
        return self.stratigraphy.get(unit_name)

    def get_fault_entry(self, fault_name: str) -> Optional[FaultEntry]:
        """Return the raw trace data ingested for `fault_name`, if any.

        Accessor for `self.faults`, mirroring `get_stratigraphy_entry`.
        """
        return self.faults.get(fault_name)

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
        kwargs = {}
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
                kwargs['solver'] = 'admm'
            else:
                raise ValueError(f"Unknown layer type: {layer_data['type']}")
        self.model.create_and_add_foliation(name, data=pd.concat(dfs, ignore_index=True), **kwargs)
        # inform listeners that a new foliation/feature was added
        self._emit('model_updated')

    def add_unconformity(
        self, foliation_name: str, value: float, type: FeatureType = FeatureType.UNCONFORMITY
    ):
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
        # model geometry changed
        self._emit('model_updated')

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
        if isinstance(fold_frame, StructuralFrame):
            fold_frame = FoldFrame(fold_frame.name, fold_frame.features, None, fold_frame.model)
        if fold_frame is None:
            raise ValueError(f"Fold frame '{fold_frame_name}' not found in the model.")
        feature = self.model.get_feature_by_name(feature_name)
        if feature is None:
            raise ValueError(f"Feature '{feature_name}' not found in the model.")
        folded_feature = add_fold_to_feature(feature, fold_frame)
        self.model[feature_name] = folded_feature
        # feature replaced/modified
        self._emit('model_updated')

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
        # feature converted
        self._emit('model_updated')

    @property
    def fold_frames(self):
        """Return the fold frames in the model."""
        return [f for f in self.model.features if f.type == FeatureType.STRUCTURALFRAME]

    def evaluate_feature_on_points(
        self, feature_name: str, points: np.ndarray, scalar_type: str = 'scalar'
    ) -> np.ndarray:
        """Evaluate a model feature at the provided points.

        Parameters
        ----------
        feature_name : str
            Name of the feature to evaluate.
        points : array_like
            An (N, 3) array-like of points [x, y, z] at which to evaluate.
        scalar_type : {'scalar', 'gradient'}, optional
            Whether to evaluate scalar values or gradients. Default is 'scalar'.

        Returns
        -------
        numpy.ndarray
            Evaluated values. For 'scalar' an (N,) array is returned. For
            'gradient' an (N, 3) array is returned when supported by the model.
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
        crs: Optional[str] = None,
        value_field_name: Optional[str] = None,
    ) -> 'gpd.GeoDataFrame':
        """Evaluate a feature on points and return a GeoDataFrame with results.

        Parameters
        ----------
        feature_name : str
            Feature name to evaluate.
        points : array_like
            An (N, 3) array-like of points (x, y, z).
        scalar_type : {'scalar', 'gradient'}, optional
            Whether to compute scalar values or gradients.
        attributes : pandas.DataFrame or None, optional
            Optional attributes to attach (must have the same length as `points`).
        crs : str or None, optional
            Coordinate Reference System for the returned GeoDataFrame (e.g. 'EPSG:4326').
        value_field_name : str or None, optional
            Optional name for the value field; defaults to '<feature_name>_value' or '<feature_name>_gradient'.

        Returns
        -------
        geopandas.GeoDataFrame
            GeoDataFrame containing point geometries and computed value columns
            (and any provided attributes).
        """
        import geopandas as _gpd
        import pandas as _pd

        try:
            from shapely.geometry import Point as _Point
        except Exception:
            self._debug_manager.log(
                "Shapely not available; geometry column will be omitted.", log_level=2
            )
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
                df = _pd.concat(
                    [df.reset_index(drop=True), attributes.reset_index(drop=True)], axis=1
                )
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

    def export_feature_values_to_vtk_mesh(self, name, mesh, scalar_type='scalar'):
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
