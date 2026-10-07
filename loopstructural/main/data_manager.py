import json
from collections import defaultdict
from functools import partial
from pathlib import Path
from typing import Optional

import numpy as np
from LoopStructural.datatypes import BoundingBox
from LoopStructural.modelling.core.stratigraphic_column import StratigraphicColumnElementType
from qgis.core import (
    QgsCategorizedSymbolRenderer,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsGraduatedSymbolRenderer,
    QgsMapLayer,
    QgsPointXY,
    QgsProject,
    QgsRectangle,
    QgsRendererCategory,
    QgsRendererRange,
    QgsStyle,
    QgsSymbol,
    QgsVectorLayer,
    QgsWkbTypes,
)
from qgis.PyQt.QtGui import QColor

from LoopStructural import FaultTopology, StratigraphicColumn

from . import derived_data, layer_roles
from .data_types import BasalContactsConfig, FaultTracesConfig, StructuralOrientationsConfig
from .derived_data import DerivedData, ThicknessSources
from .layer_roles import LayerRoles
from .m2l_api import paint_stratigraphic_order
from .vectorLayerWrapper import qgsLayerToGeoDataFrame


def _lookup_colour_ramp(ramp_name):
    """Return the named QGIS colour ramp, or the first available ramp if it is not found."""
    style = QgsStyle().defaultStyle()
    ramp = style.colorRamp(ramp_name) if ramp_name else None
    if ramp is None:
        ramp_names = style.colorRampNames()
        if ramp_names:
            ramp = style.colorRamp(ramp_names[0])
    return ramp


def _colour_to_qcolor(colour):
    """Convert a stratigraphic unit colour (hex string, colour name, or RGB tuple/array) to a QColor."""
    if colour is None:
        return None
    if isinstance(colour, str):
        qcolour = QColor(colour)
        return qcolour if qcolour.isValid() else None
    if isinstance(colour, (tuple, list, np.ndarray)) and len(colour) >= 3:
        rgb = list(colour[:3])
        if all(isinstance(c, float) and 0.0 <= c <= 1.0 for c in rgb):
            rgb = [int(c * 255) for c in rgb]
        else:
            rgb = [int(c) for c in rgb]
        return QColor(*rgb)
    return None


__title__ = "LoopStructural"
# Marks an argument that the caller did not give, because None is a value
# for some of them (for example, no faults layer).
_UNSET = object()


def _layer_name(layer):
    """Return the name of a layer, the same string, or None."""
    if layer is None or isinstance(layer, str):
        return layer
    try:
        return layer.name()
    except RuntimeError:
        # the C++ layer was deleted
        return None


# number of cells in the bounding box grid (used for isosurfaces and
# evaluation, not for the interpolation)
DEFAULT_BOUNDING_BOX_NELEMENTS = 100_000
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
        self._bounding_box_set = False

        self._basal_contacts: Optional[BasalContactsConfig] = None
        self._fault_traces: Optional[FaultTracesConfig] = None
        self._structural_orientations: Optional[StructuralOrientationsConfig] = None
        self._unique_basal_units = []
        self.map_canvas = mapCanvas
        self.logger = logger
        self._stratigraphic_column = StratigraphicColumn()
        self._fault_topology = FaultTopology(self._stratigraphic_column)
        # Maps a stratigraphic-column unconformity's uuid to the name of an
        # existing fault that should realise that boundary, instead of a
        # flat isovalue surface -- see `set_fault_boundary`. Kept as a plain
        # dict (not part of `StratigraphicColumn` itself) so this stays a
        # plugin-side concept for now; passed by reference to the model
        # manager the same way `_stratigraphic_column`/`_fault_topology` are.
        self._fault_boundaries: dict[str, str] = {}
        # uuids of the fault-linked unconformities whose polarity is flipped,
        # i.e. the other side of the fault is kept. Shared by reference with
        # the model manager, same as `_fault_boundaries`.
        self._flipped_fault_boundaries: set[str] = set()
        self._model_manager = None
        self.bounding_box_callback = None
        self.basal_contacts_callback = None
        self.fault_traces_callback = None
        self.structural_orientations_callback = None
        self._stratigraphic_column_callbacks = []
        self.fault_adjacency = None
        self.fault_stratigraphy_adjacency = None
        self.elevation = np.nan
        self.dem_layer = None
        self.use_dem = True
        self.dem_callback = None
        self.widget_settings = {}
        self.feature_data = defaultdict(dict)
        self._model_crs = None
        self._use_project_crs = True
        self.model_crs_callback = None
        # layer id -> (layer, slots) for each input layer whose data this
        # manager listens to; see `refresh_layer_watchers`.
        self._watched_layers = {}
        # ids of the watched layers whose data changed after the model
        # data was last read from them
        self._changed_layer_ids = set()
        self._layer_data_changed_callbacks = []
        # The layer that each role has (geology, fault traces, ...). The
        # tools read these as their default layers.
        self.layer_roles = LayerRoles(layer_resolver=self._find_any_layer)
        self.layer_roles.attach(self._on_layer_role_changed)
        # For each derived result, the inputs of the last run. See
        # `derived_data` for how an out-of-date result is found.
        self.derived = DerivedData()
        self.derived.register(derived_data.BASAL_CONTACTS, self.basal_contacts_inputs)
        self.derived.register(derived_data.THICKNESS, self.thickness_inputs)
        self.derived.register(derived_data.STYLED_FIELDS, self.styled_fields_inputs)
        # Records if the thickness of each unit was typed or calculated
        self.thickness_sources = ThicknessSources()
        self.debug_manager = None

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
        self.widget_settings = {}

    def set_model_manager(self, model_manager):
        """Set the model manager for the data manager."""
        if model_manager is None:
            raise ValueError("model_manager cannot be None")
        self._model_manager = model_manager
        self._model_manager.set_stratigraphic_column(self._stratigraphic_column)
        self._model_manager.set_fault_topology(self._fault_topology)
        self._model_manager.set_fault_boundaries(self._fault_boundaries)
        self._model_manager.set_flipped_fault_boundaries(self._flipped_fault_boundaries)
        self._model_manager.update_bounding_box(self._bounding_box)

    def set_bounding_box(
        self, xmin=None, xmax=None, ymin=None, ymax=None, zmin=None, zmax=None, *, mark_set=True
    ):
        """Set the bounding box for the model."""
        origin = self._bounding_box.origin
        maximum = self._bounding_box.maximum
        # nsteps can be a list (see BoundingBoxWidget._on_nsteps_changed), and
        # BoundingBox.nelements calls nsteps.prod()
        current = float(np.prod(np.asarray(self._bounding_box.nsteps, dtype=float)))
        # Keep the requested element count. The nelements setter rounds each
        # axis up, so the product grows a little on each call. Use the product
        # only when nsteps was changed somewhere else (for example the widget).
        nelements = getattr(self, '_grid_nelements', None)
        if nelements is None or current != getattr(self, '_grid_nsteps_product', None):
            nelements = current

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
        # nsteps does not change when origin/maximum change, so the old
        # nsteps gives very long cells in the new box and small features (for
        # example a synform core) do not show in the isosurfaces. Keep the
        # element count and make the cells cubic again for the new extent.
        # While the sides are set one at a time the box can have no volume
        # (for example xmin > xmax); the nelements setter then gives nsteps of
        # 0, and 0 elements stays 0 on every later call, so skip it until the
        # box is valid, and use the default count if the count is not valid.
        if np.all(np.asarray(maximum) - np.asarray(origin) > 0):
            if not np.isfinite(nelements) or nelements < 1:
                nelements = DEFAULT_BOUNDING_BOX_NELEMENTS
            self._bounding_box.nelements = nelements
            self._grid_nelements = nelements
            self._grid_nsteps_product = float(
                np.prod(np.asarray(self._bounding_box.nsteps, dtype=float))
            )
        if mark_set:
            self._bounding_box_set = True
        self._model_manager.update_bounding_box(self._bounding_box)
        if self.bounding_box_callback:
            self.bounding_box_callback(self._bounding_box)

    def set_bounding_box_update_callback(self, callback):
        self.bounding_box_callback = callback
        self.bounding_box_callback(self._bounding_box)

    def is_bounding_box_set(self):
        """Return True if the bounding box has been explicitly set by the user."""
        return bool(self._bounding_box_set)

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
        self._stratigraphic_column_callbacks.append(callback)

    @property
    def stratigraphic_column_callback(self):
        def call_all():
            # Find the derived results that the change made out of date
            # first, so that the widgets show the new status.
            self.derived.refresh()
            for cb in self._stratigraphic_column_callbacks:
                cb()

        return call_all

    def set_debug_manager(self, debug_manager):
        """Set the debug manager for the tools that the data manager can start."""
        self.debug_manager = debug_manager

    def _on_layer_role_changed(self, role, value):
        """A layer role changed: the derived results can be out of date."""
        self.derived.refresh()

    def get_layer_role(self, role):
        """Get the layer (or the field name) that a role has, or None."""
        return self.layer_roles.get(role)

    def adopt_layer_roles(self, **roles):
        """Set the roles that have no value. A role with a value does not change.

        A tool calls this when it runs, so that the layer that the user
        selected in the tool becomes the default of the other tools.
        """
        for role, value in roles.items():
            if value is not None and self.layer_roles.get(role) is None:
                self.layer_roles.set(role, value)

    # -- derived data --------------------------------------------------

    def _settings_layer_name(self, settings, key, role):
        """Return the layer name that a tool used last, or the role value."""
        if key in settings:
            return settings[key]
        return _layer_name(self.layer_roles.get(role))

    def basal_contacts_inputs(
        self,
        *,
        geology=_UNSET,
        unit_field=_UNSET,
        faults=_UNSET,
        ignore_units=_UNSET,
        override_units=_UNSET,
    ):
        """Return the inputs of the basal contacts calculation.

        A value that is not given comes from the layer roles and from the
        last settings of the Basal Contacts tool. A tool that runs gives its
        own values, so the record is the inputs of the run.
        """
        settings = self.get_widget_settings('basal_contacts_widget', {}) or {}
        if geology is _UNSET:
            geology = self.layer_roles.get(layer_roles.GEOLOGY)
        if unit_field is _UNSET:
            unit_field = self.layer_roles.get(layer_roles.GEOLOGY_UNIT_FIELD)
        if faults is _UNSET:
            faults = self._settings_layer_name(settings, 'faults_layer', layer_roles.FAULT_TRACES)
        if ignore_units is _UNSET:
            ignore_units = settings.get('ignore_units', [])
        if override_units is _UNSET:
            override_units = settings.get('basal_override_units', [])
        return {
            'unit_order': self.get_stratigraphic_unit_names(),
            'geology': _layer_name(geology),
            'unit_field': unit_field,
            'faults': _layer_name(faults),
            'ignore_units': sorted(ignore_units or []),
            'override_units': sorted(override_units or []),
        }

    def thickness_inputs(
        self,
        *,
        geology=_UNSET,
        unit_field=_UNSET,
        contacts_layer=_UNSET,
        calculator_type=_UNSET,
        structure=_UNSET,
        cross_sections=_UNSET,
    ):
        """Return the inputs of the thickness calculation.

        Without a contacts layer, the calculation makes the contacts from
        the geology layer, so the inputs of the contacts are inputs of the
        thickness.
        """
        settings = self.get_widget_settings('thickness_calculator_widget', {}) or {}
        if geology is _UNSET:
            geology = self.layer_roles.get(layer_roles.GEOLOGY)
        if unit_field is _UNSET:
            unit_field = self.layer_roles.get(layer_roles.GEOLOGY_UNIT_FIELD)
        if contacts_layer is _UNSET:
            if self.layer_roles.contacts_source == layer_roles.CONTACTS_FROM_LAYER:
                contacts_layer = self.layer_roles.get(layer_roles.BASAL_CONTACTS)
            else:
                contacts_layer = settings.get('basal_contacts_layer')
        if calculator_type is _UNSET:
            calculator_type = settings.get('calculator_type')
        if structure is _UNSET:
            structure = self._settings_layer_name(
                settings, 'structure_layer', layer_roles.STRUCTURE
            )
        if cross_sections is _UNSET:
            cross_sections = settings.get('cross_sections_layer')
        contacts_layer = _layer_name(contacts_layer)
        if contacts_layer is not None:
            contacts = {'layer': contacts_layer}
        else:
            contacts = {
                'calculated': self.basal_contacts_inputs(geology=geology, unit_field=unit_field)
            }
        return {
            'unit_order': self.get_stratigraphic_unit_names(),
            'geology': _layer_name(geology),
            'unit_field': unit_field,
            'contacts': contacts,
            'calculator_type': calculator_type,
            'structure': _layer_name(structure),
            'cross_sections': _layer_name(cross_sections),
        }

    def styled_fields_inputs(self):
        """Return the inputs of the `strat_order` / `strat_thickness` fields."""
        thicknesses = {}
        for unit in self._stratigraphic_column.order:
            if unit.element_type == StratigraphicColumnElementType.UNIT:
                thickness = unit.thickness
                thicknesses[unit.name] = (
                    round(float(thickness), 6) if derived_data.thickness_is_set(thickness) else None
                )
        return {'unit_order': self.get_stratigraphic_unit_names(), 'thicknesses': thicknesses}

    def refresh_stratigraphic_order_field(self, layer, field_name):
        """Write the order of the column to the `strat_order` field of a layer again.

        The style of the layer does not change.

        Returns
        -------
        bool
            True if the field was written.
        """
        unit_names = self.get_stratigraphic_unit_names()
        if layer is None or not field_name or not unit_names:
            return False
        try:
            paint_stratigraphic_order(layer, unit_names, field_name)
        except Exception as err:
            self.logger(message=f"Failed to write stratigraphic order onto layer: {err}")
            return False
        self.derived.record(
            derived_data.STYLED_FIELDS,
            inputs=self.styled_fields_inputs(),
            detail={'layer': layer.name(), 'field': field_name},
        )
        return True

    def get_derived_status(self, name):
        """Return `current`, `out_of_date` or `not_run` for a derived result."""
        return self.derived.status(name)

    # -- thickness -----------------------------------------------------

    def get_thickness_source(self, unit_uuid):
        """Return `typed`, `calculated` or None for the thickness of a unit."""
        return self.thickness_sources.get(unit_uuid)

    def note_thickness_edit(self, unit_data):
        """Record that the user typed the thickness of a unit.

        The unit rows also send their value back when the data manager
        sets it, so only a value that is not the same as the value in the
        column is a user edit. The row shows two decimals.
        """
        element = self._stratigraphic_column.get_element_by_uuid(unit_data.get('uuid'))
        if element is None or element.element_type != StratigraphicColumnElementType.UNIT:
            return
        new = unit_data.get('thickness')
        if not derived_data.thickness_is_set(new):
            # the user cleared the value
            self.thickness_sources.discard(element.uuid)
            return
        old = element.thickness
        if derived_data.thickness_is_set(old) and abs(float(old) - float(new)) <= 0.005 + 1e-9:
            return
        self.thickness_sources.set(element.uuid, derived_data.TYPED)

    def apply_calculated_thicknesses(self, thicknesses):
        """Set the thickness of units from a calculation.

        A thickness that the user typed does not change.

        Parameters
        ----------
        thicknesses : dict
            Unit name -> thickness. A value that is not a number above zero
            (map2loop uses -1 for a unit with no result) is ignored.

        Returns
        -------
        tuple of list
            The names of the units that changed, and the names of the units
            that kept their typed thickness.
        """
        applied, skipped = [], []
        for name, value in thicknesses.items():
            if not derived_data.thickness_is_set(value):
                continue
            unit = self._stratigraphic_column.get_unit_by_name(name=name)
            if unit is None:
                continue
            if not self.thickness_sources.can_overwrite(unit.uuid, unit.thickness):
                skipped.append(name)
                continue
            unit.thickness = float(value)
            self.thickness_sources.set(unit.uuid, derived_data.CALCULATED)
            applied.append(name)
        if applied:
            self.stratigraphic_column_callback()
        return applied, skipped

    def set_dem_callback(self, callback):
        """Set the callback for when the DEM layer is updated."""
        self.dem_callback = callback
        if self.dem_layer:
            self.dem_callback(self.dem_layer)

    def get_bounding_box(self):
        """Get the current bounding box."""
        return self._bounding_box

    def set_model_crs(self, crs, use_project_crs=False):
        """Set the model CRS.

        Parameters
        ----------
        crs : QgsCoordinateReferenceSystem or None
            The CRS to use for the model. If None and use_project_crs is True,
            will use the project CRS.
        use_project_crs : bool
            If True, use the project CRS instead of a custom CRS.

        Returns
        -------
        tuple
            (success: bool, message: str)
        """
        self._use_project_crs = use_project_crs

        if use_project_crs:
            crs = self.project.crs()

        # Validate CRS
        if crs is None or not crs.isValid():
            self._model_crs = None
            msg = "Model CRS is not valid."
            self.logger(message=msg, log_level=2)
            if self.model_crs_callback:
                self.model_crs_callback(self._model_crs, self._use_project_crs)
            return False, msg

        # Check if CRS is projected (not geographic)
        if crs.isGeographic():
            self._model_crs = None
            # Safely get CRS description
            try:
                crs_desc = crs.description() or crs.authid() or "Unknown"
            except Exception:
                crs_desc = crs.authid() if hasattr(crs, 'authid') else "Unknown"
            msg = (
                f"Model CRS must be projected (in meters), not geographic. Selected CRS: {crs_desc}"
            )
            self.logger(message=msg, log_level=2)
            if self.model_crs_callback:
                self.model_crs_callback(self._model_crs, self._use_project_crs)
            return False, msg

        self._model_crs = crs
        # Safely get CRS description
        try:
            crs_desc = crs.description() or "Unknown"
            crs_id = crs.authid() or "Unknown"
        except Exception:
            crs_desc = "Unknown"
            crs_id = crs.authid() if hasattr(crs, 'authid') else "Unknown"
        msg = f"Model CRS set to: {crs_desc} ({crs_id})"
        self.logger(message=msg, log_level=3)

        if self.model_crs_callback:
            self.model_crs_callback(self._model_crs, self._use_project_crs)

        return True, msg

    def get_model_crs(self):
        """Get the model CRS.

        Returns
        -------
        QgsCoordinateReferenceSystem or None
            The model CRS, or None if not set.
        """
        if self._use_project_crs:
            return self.project.crs()
        return self._model_crs

    def is_model_crs_valid(self):
        """Check if the model CRS is valid and projected.

        Returns
        -------
        bool
            True if the model CRS is valid and projected, False otherwise.
        """
        crs = self.get_model_crs()
        if crs is None or not crs.isValid():
            return False
        if crs.isGeographic():
            return False
        return True

    def set_model_crs_callback(self, callback):
        """Set the callback for when the model CRS is updated."""
        self.model_crs_callback = callback
        # Trigger callback with current values
        if self.model_crs_callback:
            self.model_crs_callback(self.get_model_crs(), self._use_project_crs)

    def _refresh_dem_function(self):
        """Recompute `dem_function` from the current `use_dem`/`dem_layer`/
        `elevation` state and push it to the model manager.

        `dem_function` must be derived from all three together, not just
        whichever of `set_use_dem`/`set_dem_layer`/`set_elevation` happened to
        run last -- that "last call wins" approach previously let a
        just-restored, valid DEM layer get silently overwritten back to a
        flat constant (e.g. project load always restores `elevation` after
        `dem_layer`, even when `use_dem` is True).
        """
        if self.use_dem and self.dem_layer is not None:
            # Callers pass (x, y) in the model CRS, but `sample()` expects the
            # DEM's own CRS. Cache the transform and rebuild it only when the
            # model or DEM CRS changes, because this is called once per point.
            cache = {'model_crs': None, 'dem_crs': None, 'transform': None}

            def to_dem_crs(x, y):
                model_crs = self.get_model_crs()
                dem_crs = self.dem_layer.crs()
                if (
                    model_crs is None
                    or not model_crs.isValid()
                    or not dem_crs.isValid()
                    or model_crs == dem_crs
                ):
                    return QgsPointXY(x, y)
                if cache['model_crs'] != model_crs or cache['dem_crs'] != dem_crs:
                    cache['model_crs'] = model_crs
                    cache['dem_crs'] = dem_crs
                    cache['transform'] = QgsCoordinateTransform(model_crs, dem_crs, self.project)
                return cache['transform'].transform(QgsPointXY(x, y))

            def dem_function(x, y):
                if not self.dem_layer.isValid():
                    self.logger(
                        message="DEM layer is not valid, using 0.0 for elevation.",
                        log_level=2,
                    )
                    return 0.0
                value = self.dem_layer.dataProvider().sample(to_dem_crs(x, y), 1)[0]
                # `sample()` returns NaN (not None) for points outside the
                # raster's extent or on nodata cells, depending on provider.
                if value is None or np.isnan(value):
                    return 0.0
                return value

            self.dem_function = dem_function
        else:
            elevation = self.elevation if not np.isnan(self.elevation) else 0.0
            self.dem_function = lambda x, y: elevation
        self._model_manager.set_dem_function(self.dem_function)

    def set_elevation(self, elevation):
        """Set the constant elevation used when no DEM layer is active."""
        self.elevation = elevation
        self._refresh_dem_function()

    def set_dem_layer(self, dem_layer):
        """Set the DEM layer to sample elevation from when `use_dem` is True."""
        self.dem_layer = dem_layer
        self.layer_roles.set(layer_roles.DEM, dem_layer)
        if dem_layer is None:
            self.logger(
                message="DEM layer is None, using 0.0 for elevation. Choose a valid layer or specify a constant value",
                log_level=2,
            )
        self._refresh_dem_function()
        if self.dem_callback:
            self.dem_callback(self.dem_layer)

    def set_use_dem(self, use_dem):
        """Switch the active elevation source between the DEM layer and the
        constant elevation."""
        self.use_dem = use_dem
        self._refresh_dem_function()

    def set_basal_contacts(self, basal_contacts, unitname_field=None, use_z_coordinate=False):
        """Set the basal contacts for the model."""
        self._basal_contacts = {
            'layer': basal_contacts,
            'unitname_field': unitname_field,
            'use_z_coordinate': use_z_coordinate,
        }
        self.layer_roles.set(layer_roles.BASAL_CONTACTS, basal_contacts)
        # self._unitname_field = unitname_field
        self.calculate_unique_basal_units()
        # if stratigraphic column is not empty, update contacts
        if len(self._stratigraphic_column.order) > 0:
            self.update_stratigraphy()
        if self.basal_contacts_callback:
            self.basal_contacts_callback(**self._basal_contacts)
        self.refresh_layer_watchers()

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
        if self.stratigraphic_column_callback:
            self.stratigraphic_column_callback()

    def init_stratigraphic_column_from_layer_field(self, layer, field_name):
        """Initialise the stratigraphic column from the unique values of a
        field on a polygon layer.

        Parameters
        ----------
        layer : QgsVectorLayer
            The layer to read unit names from.
        field_name : str
            Name of the field on ``layer`` holding the stratigraphic unit name.

        Returns
        -------
        bool
            True if any units were found and added, False otherwise.
        """
        if layer is None or not field_name:
            self.logger(message="No layer/field set, cannot initialise stratigraphic column.")
            return False

        unique_names = []
        for feature in layer.getFeatures():
            value = feature[field_name]
            if value is None or (hasattr(value, 'isNull') and value.isNull()):
                continue
            text = str(value).strip()
            if text and text not in unique_names:
                unique_names.append(text)

        if not unique_names:
            self.logger(
                message=f"No values found in field '{field_name}' on layer '{layer.name()}'."
            )
            return False

        for unit_name in unique_names:
            if not self._stratigraphic_column.get_unit_by_name(name=unit_name):
                self._stratigraphic_column.add_unit(name=unit_name, colour=None)
        self.update_stratigraphy()
        if self.stratigraphic_column_callback:
            self.stratigraphic_column_callback()
        return True

    def apply_stratigraphic_colours_to_layer(self, layer, field_name):
        """Push the stratigraphic column's unit colours onto a map layer.

        Builds a categorized renderer on the given layer, keyed by
        ``field_name``, using the colour assigned to each unit in the
        stratigraphic column.

        Parameters
        ----------
        layer : QgsVectorLayer
            The layer to style (e.g. the geological units/geology layer).
        field_name : str
            Name of the field on ``layer`` holding the stratigraphic unit name.

        Returns
        -------
        bool
            True if the renderer was applied, False otherwise (e.g. no layer
            or field given, or no units in the stratigraphic column).
        """
        if layer is None or not field_name:
            self.logger(message="No layer/unit name field set, cannot apply stratigraphic colours.")
            return False

        categories = []
        for unit in self._stratigraphic_column.order:
            if unit.element_type != StratigraphicColumnElementType.UNIT:
                continue
            symbol = QgsSymbol.defaultSymbol(layer.geometryType())
            if layer.geometryType() == QgsWkbTypes.GeometryType.LineGeometry:
                # default line symbols are thin (~0.26mm) and hard to tell
                # apart by colour at a glance -- widen so per-unit basal
                # contact colours are easy to distinguish on the map canvas.
                symbol.setWidth(0.8)
            qcolour = _colour_to_qcolor(unit.colour)
            if qcolour is not None:
                symbol.setColor(qcolour)
            categories.append(QgsRendererCategory(unit.name, symbol, unit.name))

        if not categories:
            self.logger(message="Stratigraphic column has no units, cannot apply colours.")
            return False

        layer.setRenderer(QgsCategorizedSymbolRenderer(field_name, categories))
        layer.triggerRepaint()
        self.logger(message=f"Applied stratigraphic column colours to layer '{layer.name()}'.")
        return True

    def apply_stratigraphic_age_to_layer(self, layer, field_name, ramp_name=None):
        """Write the stratigraphic order onto a layer and style it with a graduated colour ramp.

        Writes an integer 'strat_order' field to ``layer`` (0 = first unit in
        the stratigraphic column) matched via ``field_name``, then applies a
        graduated renderer over that field.

        Parameters
        ----------
        layer : QgsVectorLayer
            The layer to update (e.g. the geological units/geology layer).
        field_name : str
            Name of the field on ``layer`` holding the stratigraphic unit name.
        ramp_name : str, optional
            Name of a QGIS colour ramp (from QgsStyle) to use for the
            graduated renderer. Falls back to any available ramp if not found.

        Returns
        -------
        bool
            True if the field was written and the renderer applied, False otherwise.
        """
        if layer is None or not field_name:
            self.logger(message="No layer/unit name field set, cannot apply stratigraphic age.")
            return False

        unit_names = self.get_stratigraphic_unit_names()
        if not unit_names:
            self.logger(
                message="Stratigraphic column has no units, cannot apply stratigraphic age."
            )
            return False

        age_field_name = "strat_order"
        try:
            paint_stratigraphic_order(layer, unit_names, field_name)
        except Exception as err:
            self.logger(message=f"Failed to write stratigraphic order onto layer: {err}")
            return False

        unique_values = set()
        for feature in layer.getFeatures():
            value = feature[age_field_name]
            if value is None or (hasattr(value, 'isNull') and value.isNull()):
                continue
            unique_values.add(int(value))
        unique_values = sorted(unique_values)

        if not unique_values:
            self.logger(
                message="No features matched a stratigraphic unit, cannot style layer by age."
            )
            return False

        ramp = _lookup_colour_ramp(ramp_name)

        n = len(unique_values)
        ranges = []
        for i, value in enumerate(unique_values):
            symbol = QgsSymbol.defaultSymbol(layer.geometryType())
            if ramp is not None:
                symbol.setColor(ramp.color(i / (n - 1) if n > 1 else 0))
            ranges.append(QgsRendererRange(value - 0.5, value + 0.5, symbol, str(value)))

        layer.setRenderer(QgsGraduatedSymbolRenderer(age_field_name, ranges))
        layer.triggerRepaint()
        self.logger(
            message=f"Applied stratigraphic age field '{age_field_name}' and graduated "
            f"styling to layer '{layer.name()}'."
        )
        self.derived.record(
            derived_data.STYLED_FIELDS,
            inputs=self.styled_fields_inputs(),
            detail={'layer': layer.name(), 'field': field_name},
        )
        return True

    def apply_stratigraphic_thickness_to_layer(self, layer, field_name, ramp_name=None):
        """Write each unit's thickness onto a layer and style it with a graduated colour ramp.

        Writes a 'strat_thickness' field to ``layer`` holding the thickness
        set for the matching unit in the stratigraphic column (matched via
        ``field_name``), then applies a graduated renderer over that field.
        Features that do not match a unit are left empty.

        Parameters
        ----------
        layer : QgsVectorLayer
            The layer to update (e.g. the geological units/geology layer).
        field_name : str
            Name of the field on ``layer`` holding the stratigraphic unit name.
        ramp_name : str, optional
            Name of a QGIS colour ramp (from QgsStyle) to use for the
            graduated renderer. Falls back to any available ramp if not found.

        Returns
        -------
        bool
            True if the field was written and the renderer applied, False otherwise.
        """
        if layer is None or not field_name:
            self.logger(
                message="No layer/unit name field set, cannot apply stratigraphic thickness."
            )
            return False
        if layer.fields().indexFromName(field_name) < 0:
            self.logger(message=f"Field '{field_name}' not found on layer '{layer.name()}'.")
            return False

        thicknesses = {}
        for unit in self._stratigraphic_column.order:
            if unit.element_type != StratigraphicColumnElementType.UNIT:
                continue
            if unit.thickness is None:
                continue
            thicknesses[unit.name] = float(unit.thickness)
        if not thicknesses:
            self.logger(
                message="Stratigraphic column has no units, cannot apply stratigraphic thickness."
            )
            return False

        thickness_field_name = "strat_thickness"
        try:
            from qgis.core import QgsField

            from loopstructural.gui.compatibility import QVariantCompat

            layer.startEditing()
            if layer.fields().indexFromName(thickness_field_name) < 0:
                layer.dataProvider().addAttributes(
                    [QgsField(thickness_field_name, QVariantCompat.Double)]
                )
                layer.updateFields()
            thickness_index = layer.fields().indexFromName(thickness_field_name)
            for feature in layer.getFeatures():
                value = feature[field_name]
                unit_name = None if value is None else str(value).strip()
                layer.changeAttributeValue(
                    feature.id(), thickness_index, thicknesses.get(unit_name)
                )
            if not layer.commitChanges():
                raise RuntimeError("; ".join(layer.commitErrors()))
        except Exception as err:
            layer.rollBack()
            self.logger(message=f"Failed to write stratigraphic thickness onto layer: {err}")
            return False

        unique_values = set()
        for feature in layer.getFeatures():
            value = feature[thickness_field_name]
            if value is None or (hasattr(value, 'isNull') and value.isNull()):
                continue
            unique_values.add(float(value))
        unique_values = sorted(unique_values)

        if not unique_values:
            self.logger(
                message="No features matched a stratigraphic unit, cannot style layer by thickness."
            )
            return False

        ramp = _lookup_colour_ramp(ramp_name)

        # One class per thickness value, with the class limits half-way
        # between adjacent values so that each value is in only one class.
        minimum = unique_values[0]
        span = unique_values[-1] - minimum
        ranges = []
        for i, value in enumerate(unique_values):
            lower = value if i == 0 else (unique_values[i - 1] + value) / 2
            upper = value if i == len(unique_values) - 1 else (value + unique_values[i + 1]) / 2
            symbol = QgsSymbol.defaultSymbol(layer.geometryType())
            if ramp is not None:
                symbol.setColor(ramp.color((value - minimum) / span if span > 0 else 0))
            ranges.append(QgsRendererRange(lower, upper, symbol, f"{value:g}"))

        layer.setRenderer(QgsGraduatedSymbolRenderer(thickness_field_name, ranges))
        layer.triggerRepaint()
        self.logger(
            message=f"Applied stratigraphic thickness field '{thickness_field_name}' and "
            f"graduated styling to layer '{layer.name()}'."
        )
        return True

    def get_stratigraphic_unit_names(self):
        """Get the names of the stratigraphic units in the column, youngest first.

        `StratigraphicColumn.order` is oldest first (the base is index 0).
        map2loop expects the youngest unit first: `extract_basal_contacts`
        gives each contact the unit with the lower index as its basal unit.
        If the order is oldest first, each contact gets the name of the unit
        below it, and the model folds are inverted.
        """
        units = []
        for u in reversed(self._stratigraphic_column.order):
            if u.element_type == StratigraphicColumnElementType.UNIT:
                units.append(u.name)
        return units

    def get_stratigraphic_unit_colours(self):
        """Get a mapping of stratigraphic unit name to its assigned colour.

        Colours are normalised to hex strings (e.g. '#89cebc'). The
        stratigraphic column stores unit colours in whatever form
        LoopStructural gives them (often an RGB float triple in [0, 1]
        rather than a hex string); writing that raw value into a layer
        attribute breaks QGIS's memory provider, which rejects the whole
        addFeatures() batch when a list is stored in a string field.
        """
        colours = {}
        for u in self._stratigraphic_column.order:
            if u.element_type == StratigraphicColumnElementType.UNIT:
                qcolour = _colour_to_qcolor(u.colour)
                colours[u.name] = qcolour.name() if qcolour is not None else None
        return colours

    def add_to_stratigraphic_column(self, unit_data):
        """Add a unit or unconformity to the stratigraphic column."""
        stratigraphic_element = None
        if isinstance(unit_data, dict):
            if unit_data.get('type') == 'unit':
                stratigraphic_element = self._stratigraphic_column.add_unit(
                    name=unit_data.get('name'), colour=unit_data.get('colour', None)
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
            if self.stratigraphic_column_callback:
                self.stratigraphic_column_callback()
            return stratigraphic_element

    def remove_from_stratigraphic_column(self, unit_uuid):
        """Remove a unit or unconformity from the stratigraphic column."""
        self._stratigraphic_column.remove_unit(uuid=unit_uuid)
        self._fault_boundaries.pop(unit_uuid, None)
        self._flipped_fault_boundaries.discard(unit_uuid)
        self.update_stratigraphy()
        if self.stratigraphic_column_callback:
            self.stratigraphic_column_callback()

    def set_fault_boundary(self, unconformity_uuid, fault_name, *, flipped=False):
        """Mark a stratigraphic-column unconformity as realised by an
        existing fault instead of a flat isovalue surface.

        Parameters
        ----------
        unconformity_uuid : str
            uuid of the `StratigraphicUnconformity` element in the column.
        fault_name : str
            Name of an existing fault (as known to `_fault_topology`) whose
            surface should be used as the domain boundary at this point in
            the column.
        flipped : bool, optional
            If True, reverse the polarity of the fault surface so that the
            other side of the fault is kept, by default False.
        """
        changed = self._fault_boundaries.get(unconformity_uuid) != fault_name or (
            self.is_fault_boundary_flipped(unconformity_uuid) != bool(flipped)
        )
        self._fault_boundaries[unconformity_uuid] = fault_name
        if flipped:
            self._flipped_fault_boundaries.add(unconformity_uuid)
        else:
            self._flipped_fault_boundaries.discard(unconformity_uuid)
        if changed:
            self._mark_column_changed()
        if self.stratigraphic_column_callback:
            self.stratigraphic_column_callback()

    def clear_fault_boundary(self, unconformity_uuid):
        """Undo `set_fault_boundary`, reverting the unconformity to a plain isovalue boundary."""
        self._flipped_fault_boundaries.discard(unconformity_uuid)
        if self._fault_boundaries.pop(unconformity_uuid, None) is not None:
            self._mark_column_changed()
            if self.stratigraphic_column_callback:
                self.stratigraphic_column_callback()

    def _mark_column_changed(self):
        """Tell the model manager that Initialize Model must run again to
        apply a change to the boundaries of the stratigraphic column.
        """
        if self._model_manager is not None:
            self._model_manager.mark_column_changed()

    def get_fault_boundary(self, unconformity_uuid):
        """Return the fault name linked to this unconformity, or None."""
        return self._fault_boundaries.get(unconformity_uuid)

    def is_fault_boundary_flipped(self, unconformity_uuid):
        """Return True if the polarity of this fault-linked unconformity is flipped."""
        return unconformity_uuid in self._flipped_fault_boundaries

    def get_fault_boundaries(self):
        """Return the uuid -> fault_name mapping of all fault-linked boundaries."""
        return dict(self._fault_boundaries)

    def get_fault_boundary_fault_names(self):
        """Return the set of fault names currently used as domain boundaries.

        These faults are built as non-displacing domain splits (see
        `GeologicalModelManager.update_foliation_features`), so they should
        not also be offered in fault-fault (FAULTED/ABUTTING) or
        fault-stratigraphy relationship editors, which assume a
        displacement-modelled fault.
        """
        return set(self._fault_boundaries.values())

    def fault_spans_model_domain(self, fault_name, *, tolerance=0.0):
        """Check whether a fault's trace data reaches every edge of the
        model's XY bounding box.

        A fault used as a domain boundary crops the *entire* model on
        either side of its interpolated surface (see
        `LoopStructural.modelling.core._model_relationships`), so unlike an
        ordinary local fault trace it needs to be constrained across the
        whole domain -- otherwise the interpolator extrapolates the crop
        surface into areas with no supporting data. Returns True if no
        fault trace data is available yet (nothing to check against).

        Parameters
        ----------
        fault_name : str
            Name of the fault to check, as found in `get_fault_traces()`'s layer.
        tolerance : float, optional
            Allowed gap, in model units, between the trace's extent and the
            bounding box edge before it is considered "not spanning".
        """
        if self._fault_traces is None or self._fault_traces['layer'] is None:
            return True
        layer = self._fault_traces['layer']
        name_field = self._fault_traces['fault_name_field']
        trace_extent = None
        for feature in layer.getFeatures():
            if name_field is not None and str(feature[name_field]) != str(fault_name):
                continue
            geom = feature.geometry()
            if geom is None or geom.isEmpty():
                continue
            bbox = geom.boundingBox()
            trace_extent = bbox if trace_extent is None else trace_extent.combineExtentWith(bbox)
        if trace_extent is None:
            return True
        xmin, ymin = self._bounding_box.origin[0], self._bounding_box.origin[1]
        xmax, ymax = self._bounding_box.maximum[0], self._bounding_box.maximum[1]
        # A boundary only needs to fully cross the domain along one axis (an
        # east-west or north-south cut) to split the whole model -- it does
        # not need to cover the full bounding box in both directions.
        spans_x = (
            trace_extent.xMinimum() <= xmin + tolerance
            and trace_extent.xMaximum() >= xmax - tolerance
        )
        spans_y = (
            trace_extent.yMinimum() <= ymin + tolerance
            and trace_extent.yMaximum() >= ymax - tolerance
        )
        return spans_x or spans_y

    def get_input_layers(self):
        """Return a dict of {role: layer} for every input layer currently
        configured (basal contacts, fault traces, structural orientations)."""
        layers = {}
        for role, config in (
            ('Basal contacts', self._basal_contacts),
            ('Fault traces', self._fault_traces),
            ('Structural orientations', self._structural_orientations),
        ):
            if not config:
                continue
            layer = config.get('layer')
            try:
                if layer is None or not layer.isValid():
                    continue
            except RuntimeError:
                # underlying C++ layer was deleted
                continue
            layers[role] = layer
        return layers

    def _manual_foliation_layer_rows(self):
        """Yield `(layer, layer_data)` for each input layer of the foliations
        the user added (`GeologicalModelManager.manual_foliations`).

        A foliation loaded from a state file has no QGIS layer object, so
        its layer is found again by name.
        """
        if self._model_manager is None:
            return
        for spec in self._model_manager.manual_foliations.values():
            for key, layer_data in spec['data'].items():
                if layer_data.get('processed'):
                    continue
                layer = layer_data.get('layer')
                if layer is None:
                    layer = self.find_layer_by_name(layer_data.get('layer_name', key))
                if layer is not None:
                    yield layer, layer_data

    def _layers_to_watch(self):
        """Return {layer id: layer} for every layer the model reads data from."""
        layers = list(self.get_input_layers().values())
        for entries in self.feature_data.values():
            for entry in entries.values():
                if not entry.get('processed') and entry.get('layer') is not None:
                    layers.append(entry['layer'])
        layers.extend(layer for layer, _ in self._manual_foliation_layer_rows())
        watched = {}
        for layer in layers:
            try:
                if isinstance(layer, QgsVectorLayer) and layer.isValid():
                    watched[layer.id()] = layer
            except RuntimeError:
                # underlying C++ layer was deleted
                continue
        return watched

    def refresh_layer_watchers(self):
        """Listen for data changes on each layer the model reads data from,
        and stop listening to the layers it no longer uses.

        An edit in the edit buffer, a commit, a new data source or a reload
        flags the layer as changed, see `get_changed_layers`. A change
        written straight to the data provider (not through the layer) emits
        none of these signals.
        """
        wanted = self._layers_to_watch()
        for layer_id in list(self._watched_layers):
            if layer_id not in wanted:
                self._unwatch_layer(layer_id)
        for layer_id, layer in wanted.items():
            if layer_id in self._watched_layers:
                continue
            on_changed = partial(self._on_layer_data_changed, layer_id)
            on_deleted = partial(self._unwatch_layer, layer_id)
            for signal in self._layer_change_signals(layer):
                signal.connect(on_changed)
            layer.willBeDeleted.connect(on_deleted)
            self._watched_layers[layer_id] = (layer, on_changed, on_deleted)

    @staticmethod
    def _layer_change_signals(layer):
        return (
            layer.layerModified,
            layer.afterCommitChanges,
            layer.dataSourceChanged,
            layer.dataChanged,
        )

    def _unwatch_layer(self, layer_id):
        layer, on_changed, on_deleted = self._watched_layers.pop(layer_id)
        if layer_id in self._changed_layer_ids:
            self._changed_layer_ids.discard(layer_id)
            self._notify_layer_data_changed()
        try:
            for signal in self._layer_change_signals(layer):
                signal.disconnect(on_changed)
            layer.willBeDeleted.disconnect(on_deleted)
        except (RuntimeError, TypeError):
            # the layer was deleted, or the slot was not connected
            pass

    def _on_layer_data_changed(self, layer_id):
        self._changed_layer_ids.add(layer_id)
        self._notify_layer_data_changed()

    def _notify_layer_data_changed(self):
        for callback in self._layer_data_changed_callbacks:
            try:
                callback()
            except Exception as e:
                self.logger(message=f"Error in layer data changed callback: {e}", log_level=2)

    def add_layer_data_changed_callback(self, callback):
        """Call `callback()` when a watched layer changes, and when the
        changed layers are read again."""
        self._layer_data_changed_callbacks.append(callback)

    def get_changed_layers(self):
        """Return the names of the input layers whose data changed after the
        model data was last read from them."""
        return sorted(self._watched_layers[i][0].name() for i in self._changed_layer_ids)

    def reload_changed_layers(self):
        """Read the model data again from the input layers that changed.

        This only updates the data that the model manager holds (the
        stratigraphy, the faults and the data of the foliations the user
        added). Initialize Model uses this data, and
        `GeologicalModelManager.refresh_feature_data` puts it into the
        existing features.
        """
        changed = set(self._changed_layer_ids)
        if not changed:
            return

        def is_changed(config):
            layer = config.get('layer') if config else None
            try:
                return layer is not None and layer.id() in changed
            except RuntimeError:
                return False

        if is_changed(self._basal_contacts):
            self.calculate_unique_basal_units()
        if is_changed(self._basal_contacts) or is_changed(self._structural_orientations):
            self.update_stratigraphy()
        if is_changed(self._fault_traces):
            self.update_faults()
        model_crs = self.get_model_crs()
        for layer, layer_data in self._manual_foliation_layer_rows():
            if layer.id() in changed:
                layer_data['df'] = qgsLayerToGeoDataFrame(layer, target_crs=model_crs)
        self._changed_layer_ids.clear()
        self._notify_layer_data_changed()

    def refresh_model_data(self):
        """Read the changed input layers again and put their data into the
        features already in the model, without Initialize Model.

        Returns
        -------
        dict
            See `GeologicalModelManager.refresh_feature_data`.
        """
        if self._model_manager is None:
            raise RuntimeError("Model manager is not set.")
        self.reload_changed_layers()
        return self._model_manager.refresh_feature_data()

    def get_layers_outside_bounding_box(self):
        """Check which input layers do not overlap the bounding box in XY.

        Layer extents are reprojected into the model CRS before comparing.

        Returns
        -------
        tuple(list, list)
            (names of layers that overlap the bounding box,
             names of layers that do not overlap it)
        """
        model_crs = self.get_model_crs()
        bbox = QgsRectangle(
            self._bounding_box.origin[0],
            self._bounding_box.origin[1],
            self._bounding_box.maximum[0],
            self._bounding_box.maximum[1],
        )
        inside = []
        outside = []
        for role, layer in self.get_input_layers().items():
            name = f"{role} ({layer.name()})"
            try:
                extent = layer.extent()
                layer_crs = layer.crs()
                if (
                    model_crs is not None
                    and model_crs.isValid()
                    and layer_crs.isValid()
                    and layer_crs != model_crs
                ):
                    transform = QgsCoordinateTransform(layer_crs, model_crs, self.project)
                    extent = transform.transformBoundingBox(extent)
            except Exception:
                # can't determine the extent, so don't report it either way
                continue
            if extent.isNull():
                continue
            if bbox.intersects(extent) or bbox.contains(extent):
                inside.append(name)
            else:
                outside.append(name)
        return inside, outside

    def update_stratigraphic_column_order(self, new_order):
        """Update the order of units in the stratigraphic column."""
        if not isinstance(new_order, list):
            raise ValueError("new_order must be a list of unit uuids.")
        self._stratigraphic_column.update_order(new_order)
        self.update_stratigraphy()
        if self.stratigraphic_column_callback:
            self.stratigraphic_column_callback()

    def get_basal_contacts(self) -> Optional[BasalContactsConfig]:
        """Get the basal contacts."""
        return self._basal_contacts

    def get_unique_faults(self):
        """Get the unique faults from the fault traces."""
        if self._fault_traces is None or self._fault_traces['layer'] is None:
            return []
        if self._fault_traces['fault_name_field'] is None:
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
        self.layer_roles.set(layer_roles.FAULT_TRACES, fault_trace_layer)
        self.update_faults()
        if self.fault_traces_callback:
            self.fault_traces_callback(**self._fault_traces)
        self.refresh_layer_watchers()

    def get_fault_traces(self) -> Optional[FaultTracesConfig]:
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
        self.layer_roles.set(layer_roles.STRUCTURE, structural_orientations)
        if self.structural_orientations_callback:
            self.structural_orientations_callback(**self._structural_orientations)
        self.update_stratigraphy()
        self.refresh_layer_watchers()

    def get_structural_orientations(self) -> Optional[StructuralOrientationsConfig]:
        """Get the structural orientations."""
        return self._structural_orientations

    def get_stratigraphic_column(self):
        """Get the stratigraphic column."""
        return self._stratigraphic_column

    def clear_stratigraphic_column(self):
        self._stratigraphic_column.clear()

    def update_stratigraphy(self):
        """Update the foliation features in the model manager."""
        self.logger(message="Updating stratigraphy...", log_level=4)
        if self._model_manager is not None:
            model_crs = self.get_model_crs()
            if self._basal_contacts is not None:
                self._model_manager.update_contact_traces(
                    qgsLayerToGeoDataFrame(self._basal_contacts['layer'], target_crs=model_crs),
                    unit_name_field=self._basal_contacts['unitname_field'],
                    use_z_coordinate=self._basal_contacts.get('use_z_coordinate', False),
                )
            if self._structural_orientations is not None:
                self.logger(message="Updating structural orientations...", log_level=4)
                self._model_manager.update_structural_data(
                    qgsLayerToGeoDataFrame(
                        self._structural_orientations['layer'], target_crs=model_crs
                    ),
                    strike_field=self._structural_orientations['strike_field'],
                    dip_field=self._structural_orientations['dip_field'],
                    unit_name_field=self._structural_orientations['unitname_field'],
                    dip_direction=(
                        True
                        if self._structural_orientations['orientation_type'] == "Dip Direction/Dip"
                        else False
                    ),
                    use_z_coordinate=self._structural_orientations.get('use_z_coordinate', False),
                )
            self._sync_processed_feature_data()
        else:
            self.logger(message="Model manager is not set, cannot update foliation features.")

    def update_faults(self):
        """Update the faults in the model manager."""
        unique_faults = self.get_unique_faults()
        for f in unique_faults:
            self.logger(message=f"Adding fault {f} to fault topology", log_level=4)
            if f not in self._fault_topology.faults:
                self._fault_topology.add_fault(f)
        faults_to_remove = list(set(self._fault_topology.faults) - set(unique_faults))
        for fault in faults_to_remove:
            self.logger(message=f"Removing fault {fault} from fault topology", log_level=4)
            self._fault_topology.remove_fault(fault)
        self.fault_adjacency = np.zeros((len(unique_faults), len(unique_faults)), dtype=int)
        if self._model_manager is not None:
            model_crs = self.get_model_crs()
            self._model_manager.update_fault_points(
                qgsLayerToGeoDataFrame(self._fault_traces['layer'], target_crs=model_crs),
                fault_name_field=self._fault_traces['fault_name_field'],
                fault_dip_field=self._fault_traces['fault_dip_field'],
                fault_pitch_field=self._fault_traces.get('fault_pitch_field', None),
                fault_displacement_field=self._fault_traces['fault_displacement_field'],
                use_z_coordinate=self._fault_traces['use_z_coordinate'],
            )
            self._sync_processed_feature_data()
        else:
            self.logger(message="Model manager is not set, cannot update faults.")

    def update_stratigraphic_column(self):
        """Update the stratigraphic column in the model manager."""
        if self._model_manager is not None:
            self._model_manager.groups = self._stratigraphic_column.get_groups()
            self._sync_processed_feature_data()
        else:
            self.logger(message="Model manager is not set, cannot update stratigraphic column.")

    def _sync_processed_feature_data(self):
        """Mirror data ingested by the automated data-processing workflow
        (basal contacts / structural orientations / fault traces) into
        `feature_data` as read-only rows.

        That workflow writes straight into the model manager (`stratigraphy`
        / `faults`) and never goes through `update_feature_data`, so the
        per-feature "Data Layers" table stayed empty even when the
        interpolator had plenty of data -- there was no way to see, from the
        table, that a feature's constraints came from an automatically
        processed basal-contacts/orientations/fault-trace layer rather than
        one picked via "Add Data". Rows created here are flagged
        `processed=True` so the table can render them read-only and so this
        sync can safely drop and rebuild them each time without touching
        manually added rows.
        """
        for entries in self.feature_data.values():
            for key in [k for k, v in entries.items() if v.get('processed')]:
                del entries[key]

        if self._model_manager is None:
            return

        if self._stratigraphic_column is not None:
            for group in self._stratigraphic_column.get_groups():
                for unit in group.units:
                    unit_data = self._model_manager.get_stratigraphy_entry(unit.name)
                    if not unit_data:
                        continue
                    contact = unit_data.get('contact')
                    if (
                        contact is not None
                        and not contact.empty
                        and self._basal_contacts is not None
                    ):
                        self._add_processed_feature_row(
                            group.name,
                            self._basal_contacts.get('layer'),
                            'Contact (auto)',
                            unit.name,
                        )
                    orientations = unit_data.get('orientations')
                    if (
                        orientations is not None
                        and not orientations.empty
                        and self._structural_orientations is not None
                    ):
                        self._add_processed_feature_row(
                            group.name,
                            self._structural_orientations.get('layer'),
                            'Orientation (auto)',
                            unit.name,
                        )

        if self._fault_traces is not None:
            for fault_name, fault_data in self._model_manager.faults.items():
                data = fault_data.get('data')
                if data is not None and not data.empty:
                    self._add_processed_feature_row(
                        fault_name,
                        self._fault_traces.get('layer'),
                        'Fault trace (auto)',
                        fault_name,
                    )

    def _add_processed_feature_row(self, feature_name, layer, type_label, source_name):
        """Add a single read-only, workflow-derived row to `feature_data`.

        Keyed on a string distinct from a plain layer name so a processed row
        never collides with (or is silently overwritten by, or overwrites) a
        manually added row that happens to reference the same physical layer.
        """
        if layer is None:
            return
        display_name = f"{source_name} ({layer.name()}, auto)"
        self.feature_data[feature_name][display_name] = {
            'layer': layer,
            'layer_name': display_name,
            'type': type_label,
            'processed': True,
        }

    def clear_data(self):
        """Clear all data in the manager."""
        self._bounding_box = BoundingBox()
        self._basal_contacts = None
        self._fault_traces = None
        self._structural_orientations = None

    def reset(self):
        """Reset the entire application state.

        Clears all loaded layers/fields, the stratigraphic column, the fault
        topology, the DEM/elevation and CRS settings, and the geological
        model itself, restoring the plugin to its initial empty state. All
        connected UI widgets are notified via their existing callbacks so
        they refresh to reflect the cleared state.
        """
        self.logger(message="Resetting application state...", log_level=3)

        # Clear the stratigraphic column and fault topology in place (rather
        # than replacing them) since other widgets hold direct observer
        # attachments to these specific objects.
        self.clear_stratigraphic_column()
        if self.stratigraphic_column_callback:
            self.stratigraphic_column_callback()

        self._fault_topology.faults = []
        self._fault_topology.adjacency = {}
        self._fault_topology.stratigraphy_fault_relationships = {}
        self._fault_topology.notify('fault_topology_reset')

        # Clear loaded layer/field selections and notify listening widgets.
        self.set_basal_contacts(None, unitname_field=None, use_z_coordinate=False)
        self._unique_basal_units = []
        self.set_fault_trace_layer(
            None,
            fault_name_field=None,
            fault_dip_field=None,
            fault_displacement_field=None,
            use_z_coordinate=False,
        )
        self.set_structural_orientations(None)

        self.fault_adjacency = None
        self.fault_stratigraphy_adjacency = None
        self.feature_data = defaultdict(dict)
        self.widget_settings = {}
        self.layer_roles.clear()
        self.thickness_sources.clear()
        self.derived.clear()

        self.set_dem_layer(None)
        self.use_dem = True
        self.elevation = np.nan

        self.set_bounding_box(**default_bounding_box, mark_set=False)
        self.set_model_crs(None, use_project_crs=True)

        if self._model_manager is not None:
            self._model_manager.reset()
            self._model_manager.update_bounding_box(self._bounding_box)
            self._model_manager.set_dem_function(self.dem_function)

        self._changed_layer_ids.clear()
        self.refresh_layer_watchers()

        self.logger(message="Application state reset.", log_level=3)

    def save_state(self, filepath):
        """Save the full application state to disk.

        Writes the data manager's configuration (bounding box, layer/field
        selections, stratigraphic column, DEM/CRS settings, ...) as JSON to
        `filepath`, and the built geological model to a sibling
        ``<filepath>.model`` file (pickled via dill, see
        ``LoopStructural.GeologicalModel.to_file``).

        Parameters
        ----------
        filepath : str or Path
            Destination path for the JSON state file.
        """
        path = Path(filepath)
        state = {'data_manager': self.to_dict()}

        if self._model_manager is not None:
            model_path = path.parent / f"{path.name}.model"
            self._model_manager.save_model(str(model_path))
            state['model_file'] = model_path.name
            state['manual_foliations'] = self._model_manager.manual_foliations_to_dict()

        with open(path, 'w') as f:
            json.dump(state, f, indent=2)
        self.logger(message=f"Saved application state to '{path}'.", log_level=3)

    def load_state(self, filepath):
        """Load a previously saved application state from disk.

        Restores the data manager's configuration and, if present, the
        sibling ``<filepath>.model`` file saved alongside it by
        `save_state`.

        Parameters
        ----------
        filepath : str or Path
            Path to the JSON state file previously written by `save_state`.
        """
        path = Path(filepath)
        with open(path, 'r') as f:
            state = json.load(f)

        if 'data_manager' in state:
            self.update_from_dict(state['data_manager'])

        model_filename = state.get('model_file')
        if model_filename and self._model_manager is not None:
            model_path = path.parent / model_filename
            self._model_manager.load_model(str(model_path))
        if self._model_manager is not None:
            # the pickled model already has these features; this lets
            # Initialize Model build them again
            self._model_manager.manual_foliations_from_dict(state.get('manual_foliations', {}))
        # the data was just read from the layers
        self._changed_layer_ids.clear()
        self.refresh_layer_watchers()

        self.logger(message=f"Loaded application state from '{path}'.", log_level=3)

    def _get_model_crs_authid(self):
        """Get the model CRS authid string for serialization.

        Returns
        -------
        str or None
            CRS authid string (e.g., 'EPSG:32633') or None if CRS is not valid.
        """
        if not self._model_crs:
            return None
        if not isinstance(self._model_crs, QgsCoordinateReferenceSystem):
            return None
        if not self._model_crs.isValid():
            return None
        return self._model_crs.authid()

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
            try:
                basal_contacts['layer'] = basal_contacts['layer'].name()
            except RuntimeError as e:
                self.logger(message=f"Error getting basal contacts layer name: {e}", log_level=2)
                basal_contacts['layer'] = None
        if fault_traces and 'layer' in fault_traces and fault_traces['layer'] is not None:
            try:
                fault_traces['layer'] = fault_traces['layer'].name()
            except RuntimeError as e:
                self.logger(message=f"Error getting fault traces layer name: {e}", log_level=2)
                fault_traces['layer'] = None
        if (
            structural_orientations
            and 'layer' in structural_orientations
            and structural_orientations['layer'] is not None
        ):
            try:
                structural_orientations['layer'] = structural_orientations['layer'].name()
            except RuntimeError as e:
                self.logger(
                    message=f"Error getting structural orientations layer name: {e}",
                    log_level=2,
                )
                structural_orientations['layer'] = None
        dem_layer_name = None
        if self.dem_layer is not None:
            try:
                dem_layer_name = self.dem_layer.name()
            except RuntimeError as e:
                self.logger(message=f"Error getting DEM layer name: {e}", log_level=2)

        return {
            'bounding_box': self._bounding_box.to_dict(),
            'bounding_box_set': self._bounding_box_set,
            'basal_contacts': basal_contacts,
            'fault_traces': fault_traces,
            'structural_orientations': structural_orientations,
            'stratigraphic_column': (
                self._stratigraphic_column.to_dict() if self._stratigraphic_column else None
            ),
            'fault_boundaries': dict(self._fault_boundaries),
            'flipped_fault_boundaries': sorted(self._flipped_fault_boundaries),
            'dem_layer': dem_layer_name if self.dem_layer else None,
            'use_dem': self.use_dem,
            'elevation': self.elevation,
            'widget_settings': self.widget_settings,
            'model_crs': self._get_model_crs_authid(),
            'use_project_crs': self._use_project_crs,
            'layer_roles': self.layer_roles.to_dict(),
            'derived_data': self.derived.to_dict(),
            'thickness_sources': self.thickness_sources.to_dict(),
        }

    def _restore_derived_state(self, data):
        """Restore the layer roles, derived-data records and thickness sources.

        A state file from an older version has none of these keys. The roles
        for the layers that the data manager already restored are the same
        as the layers of these settings. The other roles and the records
        get their default values.
        """
        roles = data.get('layer_roles')
        if roles:
            self.layer_roles.from_dict(roles)
        else:
            self.layer_roles.set(layer_roles.GEOLOGY, None)
            self.layer_roles.set(layer_roles.GEOLOGY_UNIT_FIELD, None)
            self.layer_roles.contacts_source = layer_roles.CONTACTS_FROM_GEOLOGY
        self.thickness_sources.from_dict(data.get('thickness_sources'))
        self.derived.from_dict(data.get('derived_data'))

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
                mark_set=data.get('bounding_box_set', True),
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
            # See the matching call in update_from_dict for why this is needed.
            self._stratigraphic_column.update_unit_values()
            self.stratigraphic_column_callback()
        self._fault_boundaries.clear()
        if data.get('fault_boundaries'):
            self._fault_boundaries.update(data['fault_boundaries'])
        self._flipped_fault_boundaries.clear()
        if data.get('flipped_fault_boundaries'):
            self._flipped_fault_boundaries.update(data['flipped_fault_boundaries'])
        if 'widget_settings' in data:
            self.widget_settings = data['widget_settings']
        self._restore_derived_state(data)

        # Load model CRS settings
        if 'use_project_crs' in data:
            self._use_project_crs = data['use_project_crs']
        if 'model_crs' in data and data['model_crs'] is not None:
            crs = QgsCoordinateReferenceSystem(data['model_crs'])
            if crs.isValid():
                self.set_model_crs(crs, use_project_crs=self._use_project_crs)

    def update_from_dict(self, data):
        """Update the data manager from a dictionary."""
        # Model CRS must be restored before anything below that reprojects
        # a layer against it (basal_contacts/fault_traces/
        # structural_orientations, all via get_model_crs()) -- restoring it
        # last meant every reprojection during project load ran against
        # whatever `_use_project_crs`/`_model_crs` still held from __init__
        # (use_project_crs=True, i.e. the *project's* CRS) instead of the
        # saved model CRS, silently skipping reprojection whenever a layer
        # happened to already be in the project's CRS but not the model's.
        if 'use_project_crs' in data:
            self._use_project_crs = data['use_project_crs']
        else:
            self._use_project_crs = True
        if 'model_crs' in data and data['model_crs'] is not None:
            crs = QgsCoordinateReferenceSystem(data['model_crs'])
            if crs.isValid():
                self.set_model_crs(crs, use_project_crs=self._use_project_crs)

        if 'bounding_box' in data:
            self.set_bounding_box(
                xmin=data['bounding_box']['origin'][0],
                xmax=data['bounding_box']['maximum'][0],
                ymin=data['bounding_box']['origin'][1],
                ymax=data['bounding_box']['maximum'][1],
                zmin=data['bounding_box']['origin'][2],
                zmax=data['bounding_box']['maximum'][2],
                mark_set=data.get('bounding_box_set', True),
            )
        else:
            self.set_bounding_box(**default_bounding_box, mark_set=False)
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
            # update_from_dict restores elements via add_element, not
            # add_unit -- only add_unit computes each unit's min/max
            # scalar-field range as a side effect. Without this, every
            # restored unit keeps the default (0, inf) range, so
            # evaluate_model can't tell any unit in a group apart from any
            # other and just labels every point with whichever unit was
            # last in the group (see GeologicalModelManager.
            # set_stratigraphic_column, which already does this for the
            # very first load -- this covers every reload afterwards).
            self._stratigraphic_column.update_unit_values()
        else:
            self._stratigraphic_column.clear()

        # Mutate in place rather than reassign: `_fault_boundaries` is
        # shared by reference with the model manager (see set_model_manager).
        self._fault_boundaries.clear()
        if data.get('fault_boundaries'):
            self._fault_boundaries.update(data['fault_boundaries'])
        self._flipped_fault_boundaries.clear()
        if data.get('flipped_fault_boundaries'):
            self._flipped_fault_boundaries.update(data['flipped_fault_boundaries'])

        if 'widget_settings' in data:
            self.widget_settings = data['widget_settings']
        else:
            self.widget_settings = {}

        self._restore_derived_state(data)

        if self.stratigraphic_column_callback:
            self.stratigraphic_column_callback()

    def find_layer_by_name(self, layer_name, layer_type=QgsVectorLayer):
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

            while i < len(layers) and not issubclass(type(layers[i]), layer_type):

                i += 1
            if i >= len(layers):
                self.logger(message=f"Layer '{layer_name}' is not a vector layer.", log_level=2)
                return None
            if issubclass(type(layers[i]), layer_type):
                return layers[i]
            else:
                self.logger(message=f"Layer '{layer_name}' is not a vector layer.", log_level=2)
                return None

    def _find_any_layer(self, layer_name):
        """Find a layer of any type (vector or raster) by name."""
        return self.find_layer_by_name(layer_name, layer_type=QgsMapLayer)

    def update_feature_data(self, feature_name: str, feature_data: dict):
        """Update the feature data in the data manager."""
        if not isinstance(feature_data, dict):
            raise ValueError("feature_data must be a dictionary.")
        self.feature_data[feature_name][feature_data['layer_name']] = feature_data
        self.logger(message=f"Updated feature data for '{feature_name}'.")
        self.refresh_layer_watchers()

    def set_widget_settings(self, widget_name: str, settings: dict):
        """Store widget settings for persistence.

        The settings of a tool are inputs of the derived results, so the
        status of these results can change.
        """
        self.widget_settings[widget_name] = settings
        self.derived.refresh()

    def get_widget_settings(self, widget_name: str, default=None):
        """Retrieve persisted widget settings."""
        if widget_name in self.widget_settings:
            return self.widget_settings[widget_name]
        return default

    def add_foliation_to_model(
        self,
        foliation_name: str,
        *,
        folded_feature_name=None,
        restrict_to_stratigraphic_domain=True,
    ):
        """Add a foliation to the model.

        See `ModelManager.add_foliation` for `restrict_to_stratigraphic_domain`.
        """
        if foliation_name not in self.feature_data:
            raise ValueError(f"Foliation '{foliation_name}' does not exist in the data manager.")
        foliation_data = self.feature_data[foliation_name]
        model_crs = self.get_model_crs()
        for layer in foliation_data.values():
            layer['df'] = qgsLayerToGeoDataFrame(
                layer['layer'], target_crs=model_crs
            )  # Convert QgsVectorLayer to GeoDataFrame
        if self._model_manager:
            self._model_manager.add_foliation(
                foliation_name,
                foliation_data,
                folded_feature_name=folded_feature_name,
                use_z_coordinate=True,
                restrict_to_stratigraphic_domain=restrict_to_stratigraphic_domain,
            )
            self.logger(message=f"Added foliation '{foliation_name}' to the model.")
            self.refresh_layer_watchers()
        else:
            raise RuntimeError("Model manager is not set.")
