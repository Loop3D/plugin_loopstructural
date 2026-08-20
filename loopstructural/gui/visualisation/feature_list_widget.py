import logging
from typing import Optional, Union

import numpy as np
import pyvista as pv
from LoopStructural.datatypes import VectorPoints
from qgis.core import (
    QgsApplication,
    QgsCoordinateTransform,
    QgsGeometry,
    QgsMapLayerProxyModel,
    QgsProject,
    QgsWkbTypes,
)
from qgis.gui import QgsMapLayerComboBox
from qgis.PyQt.QtCore import QSize
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from loopstructural.__about__ import DIR_PLUGIN_ROOT

from ..background_task import finish_background_task, start_background_task
from ..compatibility import configure_layer_combo
from .cross_section_utils import build_line_extrusion_mesh, build_plane_mesh
from .mesh_scalar_utils import stratigraphic_ids_to_rgb

logger = logging.getLogger(__name__)


class FeatureListWidget(QWidget):
    def __init__(self, parent=None, *, model_manager=None, viewer=None, data_manager=None):
        super().__init__(parent)
        self.mainLayout = QVBoxLayout(self)
        self.treeWidget = QTreeWidget(self)
        self.treeWidget.setHeaderHidden(True)  # Hide the header
        self.mainLayout.addWidget(self.treeWidget)
        self.setLayout(self.mainLayout)
        self.model_manager = model_manager
        self.viewer = viewer
        self.data_manager = data_manager

        # Add buttons
        self.addBoundingBoxButton = self._make_tool_button(
            "extents.svg", "Add Model Bounding Box"
        )
        self.addFaultSurfacesButton = self._make_custom_icon_tool_button(
            "fault.svg", "Add Fault Surfaces"
        )
        self.addStratigraphicSurfacesButton = self._make_custom_icon_tool_button(
            "stratigraphic_column_icon.svg", "Add Stratigraphic Surfaces"
        )
        self.addTopographyButton = self._make_tool_button(
            "mActionAddRasterLayer.svg", "Add Topography Surface"
        )
        self.colourTopographyByStratigraphyCheckBox = QCheckBox(
            "Colour Topography by Stratigraphic Column", self
        )
        self.colourTopographyByStratigraphyCheckBox.setEnabled(False)

        # Connect buttons to their respective methods
        self.addBoundingBoxButton.clicked.connect(self.add_model_bounding_box)
        self.addFaultSurfacesButton.clicked.connect(self.add_fault_surfaces)
        self.addStratigraphicSurfacesButton.clicked.connect(self.add_stratigraphic_surfaces)
        self.addTopographyButton.clicked.connect(self.add_topography_surface)
        self.colourTopographyByStratigraphyCheckBox.toggled.connect(
            self._on_colour_topography_toggled
        )

        # background task handles for the topography surface (grid sampling and
        # stratigraphy evaluation both run off the GUI thread; see background_task.py)
        self._topography_thread = None
        self._topography_worker = None
        self._topography_progress = None

        self._build_cross_section_controls()

        # A single row of icon-only actions, in workflow order, replaces the
        # previous stack of full-width text buttons.
        actionsRow = QHBoxLayout()
        actionsRow.addWidget(self.addBoundingBoxButton)
        actionsRow.addWidget(self.addFaultSurfacesButton)
        actionsRow.addWidget(self.addStratigraphicSurfacesButton)
        actionsRow.addWidget(self.addTopographyButton)
        actionsRow.addWidget(self.crossSectionButton)
        actionsRow.addStretch(1)
        self.mainLayout.addLayout(actionsRow)
        self.mainLayout.addWidget(self.colourTopographyByStratigraphyCheckBox)

        # background task handles shared by the plane and line cross-section
        # actions (only one can run at a time)
        self._cross_section_thread = None
        self._cross_section_worker = None
        self._cross_section_progress = None
        self._pending_cross_section_name = None
        # Whether the user has hand-edited the plane's origin/normal/size --
        # while False, `update_feature_list` keeps re-syncing those fields to
        # the model's current bounding box (see
        # `_reset_plane_cross_section_defaults`). `model_manager.model` is
        # never None -- it starts out as a placeholder unit-cube model before
        # a real bounding box is set -- so this can't be a one-shot flag set
        # on first model sight; it has to keep tracking the *current* box
        # until the user opts out by typing a value in themselves.
        self._plane_defaults_dirty = False

        # Populate the feature list
        self.update_feature_list()
        # register observer to refresh list and viewer when model changes
        if self.model_manager is not None:
            # Attach to specific model events using the Observable framework
            try:
                # listeners will receive (observable, event, *args)
                # attach wrappers that match the Observable callback signature
                self._disp_update = self.model_manager.attach(
                    lambda _obs, _event, *a, **k: self.update_feature_list(), 'model_updated'
                )
                # also listen for model and feature updates so visualisation can refresh
                # forward event and args into the handler so it can act on specific surfaces
                self._disp_feature = self.model_manager.attach(
                    lambda _obs, _event, *a, **k: self._on_model_update(_event, *a), 'model_updated'
                )
                self._disp_feature2 = self.model_manager.attach(
                    lambda _obs, _event, *a, **k: self._on_model_update(_event, *a),
                    'feature_updated',
                )
            except Exception:
                # Fall back to legacy observers list if available
                try:
                    self.model_manager.observers.append(self.update_feature_list)
                    self.model_manager.observers.append(self._on_model_update)
                except Exception:
                    pass

    def _make_tool_button(self, theme_icon_name: str, tooltip: str) -> QToolButton:
        """Build a small icon-only tool button using a QGIS theme icon, with
        the given tooltip standing in for the label text it no longer shows.
        """
        return self._build_tool_button(QgsApplication.getThemeIcon(theme_icon_name), tooltip)

    def _make_custom_icon_tool_button(self, icon_filename: str, tooltip: str) -> QToolButton:
        """Build a small icon-only tool button using one of this plugin's own
        icons (see resources/images), for geological concepts QGIS's own
        theme has no dedicated icon for.
        """
        icon_path = str(DIR_PLUGIN_ROOT / "resources" / "images" / icon_filename)
        return self._build_tool_button(QIcon(icon_path), tooltip)

    def _build_tool_button(self, icon: QIcon, tooltip: str) -> QToolButton:
        button = QToolButton(self)
        button.setIcon(icon)
        button.setIconSize(QSize(22, 22))
        button.setToolTip(tooltip)
        button.setAutoRaise(True)
        return button

    def _build_cross_section_controls(self):
        """Build the "Cross Section" icon button (added to the shared actions
        row in __init__), which opens a dialog with a plane (origin + normal)
        mode and a line-extrusion (pick a QGIS line layer) mode as separate
        tabs. Both are added to the viewer coloured by the stratigraphic
        column, reusing the same evaluate-points -> ids -> rgb pipeline as
        topography colouring.
        """
        self.crossSectionButton = self._make_custom_icon_tool_button(
            "cross_section.svg", "Cross Section..."
        )
        self.crossSectionButton.clicked.connect(self._show_cross_section_dialog)

        self.crossSectionDialog = QDialog(self)
        self.crossSectionDialog.setWindowTitle("Cross Section")
        dialogLayout = QVBoxLayout(self.crossSectionDialog)
        tabs = QTabWidget(self.crossSectionDialog)
        dialogLayout.addWidget(tabs)

        planeTab = QWidget(self.crossSectionDialog)
        groupLayout = QVBoxLayout(planeTab)

        groupLayout.addWidget(QLabel("Plane (origin + normal)"))
        planeForm = QFormLayout()

        def make_coord_spinbox(default=0.0):
            box = QDoubleSpinBox(self)
            box.setRange(-1e9, 1e9)
            box.setDecimals(2)
            box.setValue(default)
            return box

        self.crossSectionOriginXSpinBox = make_coord_spinbox()
        self.crossSectionOriginYSpinBox = make_coord_spinbox()
        self.crossSectionOriginZSpinBox = make_coord_spinbox()
        self.crossSectionNormalXSpinBox = make_coord_spinbox(1.0)
        self.crossSectionNormalYSpinBox = make_coord_spinbox(0.0)
        self.crossSectionNormalZSpinBox = make_coord_spinbox(0.0)
        self.crossSectionSizeSpinBox = make_coord_spinbox(1000.0)
        self.crossSectionSizeSpinBox.setRange(0.01, 1e9)
        self.crossSectionResolutionSpinBox = QSpinBox(self)
        self.crossSectionResolutionSpinBox.setRange(2, 500)
        self.crossSectionResolutionSpinBox.setValue(50)

        # Track whether the user has hand-edited the plane's geometry so we
        # know when to stop re-syncing it to the model's bounding box (see
        # `_reset_plane_cross_section_defaults`).
        for box in (
            self.crossSectionOriginXSpinBox,
            self.crossSectionOriginYSpinBox,
            self.crossSectionOriginZSpinBox,
            self.crossSectionNormalXSpinBox,
            self.crossSectionNormalYSpinBox,
            self.crossSectionNormalZSpinBox,
            self.crossSectionSizeSpinBox,
        ):
            box.valueChanged.connect(self._mark_plane_defaults_dirty)

        planeForm.addRow(
            "Origin (x, y, z)",
            self._hbox(
                self.crossSectionOriginXSpinBox,
                self.crossSectionOriginYSpinBox,
                self.crossSectionOriginZSpinBox,
            ),
        )
        planeForm.addRow(
            "Normal (x, y, z)",
            self._hbox(
                self.crossSectionNormalXSpinBox,
                self.crossSectionNormalYSpinBox,
                self.crossSectionNormalZSpinBox,
            ),
        )
        planeForm.addRow("Size", self.crossSectionSizeSpinBox)
        planeForm.addRow("Resolution", self.crossSectionResolutionSpinBox)
        groupLayout.addLayout(planeForm)

        self.addPlaneCrossSectionButton = QPushButton("Add Plane Cross Section", self)
        self.addPlaneCrossSectionButton.clicked.connect(self.add_plane_cross_section)
        groupLayout.addWidget(self.addPlaneCrossSectionButton)
        groupLayout.addStretch(1)
        tabs.addTab(planeTab, "Plane")

        lineTab = QWidget(self.crossSectionDialog)
        lineTabLayout = QVBoxLayout(lineTab)
        lineTabLayout.addWidget(QLabel("Extrude a QGIS line layer vertically"))
        lineForm = QFormLayout()

        self.crossSectionLineLayerComboBox = QgsMapLayerComboBox(self)
        configure_layer_combo(self.crossSectionLineLayerComboBox, QgsMapLayerProxyModel.LineLayer)
        lineForm.addRow("Line layer", self.crossSectionLineLayerComboBox)

        self.crossSectionLineResolutionSpinBox = QSpinBox(self)
        self.crossSectionLineResolutionSpinBox.setRange(2, 500)
        self.crossSectionLineResolutionSpinBox.setValue(50)
        lineForm.addRow("Resolution along line", self.crossSectionLineResolutionSpinBox)

        self.crossSectionLineVerticalResolutionSpinBox = QSpinBox(self)
        self.crossSectionLineVerticalResolutionSpinBox.setRange(2, 500)
        self.crossSectionLineVerticalResolutionSpinBox.setValue(50)
        lineForm.addRow("Vertical resolution", self.crossSectionLineVerticalResolutionSpinBox)
        lineTabLayout.addLayout(lineForm)

        self.addLineCrossSectionButton = QPushButton("Add Cross Section from Line", self)
        self.addLineCrossSectionButton.clicked.connect(self.add_line_cross_section)
        lineTabLayout.addWidget(self.addLineCrossSectionButton)
        lineTabLayout.addStretch(1)
        tabs.addTab(lineTab, "Line")

        closeButton = QPushButton("Close", self.crossSectionDialog)
        closeButton.clicked.connect(self.crossSectionDialog.close)
        dialogLayout.addWidget(closeButton)

    def _show_cross_section_dialog(self):
        self.crossSectionDialog.show()
        self.crossSectionDialog.raise_()
        self.crossSectionDialog.activateWindow()

    @staticmethod
    def _hbox(*widgets):
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        for w in widgets:
            layout.addWidget(w)
        return container

    def update_feature_list(self):
        if not self.model_manager:
            return

        self.treeWidget.clear()
        for feature in self.model_manager.features():
            if not feature.name.startswith('__'):
                self.add_feature(feature)
        if self.model_manager.model is not None and not self._plane_defaults_dirty:
            self._reset_plane_cross_section_defaults()

    def _get_vector_scale(self, scale: Optional[Union[float, int]] = None) -> float:
        autoscale = 1.0
        if self.model_manager.model is not None:
            # automatically scale vector data to be 5% of the bounding box length
            autoscale = self.model_manager.model.bounding_box.length.max() * 0.05
        if scale is None:
            scale = autoscale
        else:
            scale = scale * autoscale

        return scale

    def add_feature(self, feature):
        """Add a feature to the feature list widget.

        Parameters
        ----------
        feature : Feature
            The feature object to add to the list.
        """
        featureItem = QTreeWidgetItem(self.treeWidget)
        featureItem.setText(0, feature.name)

    def contextMenuEvent(self, event):
        menu = QMenu(self)

        add_scalar_action = menu.addAction("Add Scalar Field")
        add_surface_action = menu.addAction("Add Surface")
        add_vector_action = menu.addAction("Add Vector Field")
        add_data_action = menu.addAction("Add Data")

        action = menu.exec_(self.mapToGlobal(event.pos()))

        selected_items = self.treeWidget.selectedItems()
        if not selected_items:
            return

        feature_name = selected_items[0].text(0)

        if action == add_scalar_action:
            self.add_scalar_field(feature_name)
        elif action == add_surface_action:
            self.add_surface(feature_name)
        elif action == add_vector_action:
            self.add_vector_field(feature_name)
        elif action == add_data_action:
            self.add_data(feature_name)

    def add_scalar_field(self, feature_name):
        scalar_field = self.model_manager.model[feature_name].scalar_field()
        self.viewer.add_mesh_object(
            scalar_field.vtk(),
            name=f'{feature_name}_scalar_field',
            source_feature=feature_name,
            source_type='feature_scalar',
        )

    def add_surface(self, feature_name):
        surfaces = self.model_manager.model[feature_name].surfaces()
        for i, surface in enumerate(surfaces):
            # ensure unique names for multiple surfaces per feature
            mesh_name = f'{feature_name}_surface' if i == 0 else f'{feature_name}_surface_{i+1}'
            # try to determine an isovalue for this surface (may be an attribute or encoded in name)
            isovalue = None
            try:
                isovalue = getattr(surface, 'isovalue', None)
            except Exception:
                isovalue = None
            if isovalue is None:
                # attempt to parse trailing numeric suffix in the surface name
                try:
                    parts = str(surface.name).rsplit('_', 1)
                    if len(parts) == 2:
                        isovalue = float(parts[1])
                except Exception:
                    isovalue = None

            self.viewer.add_mesh_object(
                surface.vtk(),
                name=mesh_name,
                source_feature=feature_name,
                source_type='feature_surface',
                isovalue=isovalue,
            )

    def add_vector_field(self, feature_name):
        vector_field = self.model_manager.model[feature_name].vector_field()
        scale = self._get_vector_scale()
        self.viewer.add_mesh_object(
            vector_field.vtk(scale=scale),
            name=f'{feature_name}_vector_field',
            source_feature=feature_name,
            source_type='feature_vector',
        )

    def add_data(self, feature_name):
        data = self.model_manager.model[feature_name].get_data()
        for d in data:
            d.locations = self.model_manager.model.rescale(d.locations)
            if issubclass(type(d), VectorPoints):
                scale = self._get_vector_scale()
                # tolerance is None means all points are shown
                self.viewer.add_mesh_object(
                    d.vtk(scale=scale, tolerance=None),
                    name=f'{feature_name}_{d.name}_points',
                    source_feature=feature_name,
                    source_type='feature_points',
                )
            else:
                self.viewer.add_mesh_object(
                    d.vtk(),
                    name=f'{feature_name}_{d.name}',
                    source_feature=feature_name,
                    source_type='feature_data',
                )
        logger.info(f"Adding data to feature: {feature_name}")

    def add_model_bounding_box(self):
        if not self.model_manager:
            logger.info("Model manager is not set.")
            return
        bb = self.model_manager.model.bounding_box.vtk().outline()
        self.viewer.add_mesh_object(
            bb, name='model_bounding_box', source_feature='__model__', source_type='bounding_box'
        )
        # Logic for adding model bounding box
        logger.info("Adding model bounding box...")

    def add_fault_surfaces(self):
        if not self.model_manager:
            logger.info("Model manager is not set.")
            return
        self.model_manager.update_all_features(subset='faults')
        fault_surfaces = self.model_manager.model.get_fault_surfaces()
        for surface in fault_surfaces:
            self.viewer.add_mesh_object(
                surface.vtk(),
                name=f'fault_surface_{surface.name}',
                source_feature=surface.name,
                source_type='fault_surface',
                isovalue=0.0,
            )
        logger.info("Adding fault surfaces...")

    def add_stratigraphic_surfaces(self):
        if not self.model_manager:
            logger.info("Model manager is not set.")
            return
        stratigraphic_surfaces = self.model_manager.model.get_stratigraphic_surfaces()

        for surface in stratigraphic_surfaces:
            self.viewer.add_mesh_object(
                surface.vtk(),
                name=surface.name,
                color=surface.colour,
                source_feature=surface.name,
                isovalue=np.mean(surface.values),
                source_type='stratigraphic_surface',
            )

    def add_topography_surface(self):
        """Sample the current DEM across the model extent and add it to the
        viewer as a surface, shaded by elevation.

        DEM sampling runs on a background thread (it calls into the QGIS
        raster provider once per grid point) so the UI doesn't freeze; see
        `_on_topography_grid_finished` for where the mesh is actually added.
        """
        if not self.model_manager:
            logger.info("Model manager is not set.")
            return
        if self.model_manager.model is None:
            logger.info("No model available to build a topography surface.")
            return

        def target(progress_callback):
            progress_callback("Sampling DEM...")
            return self.model_manager.sample_dem_grid()

        self.addTopographyButton.setEnabled(False)
        self._topography_thread, self._topography_worker, self._topography_progress = (
            start_background_task(
                self,
                target,
                title="Topography",
                initial_label="Sampling DEM...",
                on_progress=self._on_topography_progress,
                on_finished=self._on_topography_grid_finished,
                on_error=self._on_topography_error,
            )
        )

    def _on_topography_progress(self, message):
        try:
            self._topography_progress.setLabelText(message)
        except Exception:
            pass

    def _on_topography_grid_finished(self, result):
        finish_background_task(
            self._topography_thread, self._topography_worker, self._topography_progress
        )
        self.addTopographyButton.setEnabled(True)

        xx, yy, zz = result
        mesh = pv.StructuredGrid(xx, yy, zz)
        mesh['Elevation'] = mesh.points[:, 2]
        self.viewer.add_mesh_object(
            mesh,
            name='topography_surface',
            scalars='Elevation',
            cmap='terrain',
            show_scalar_bar=True,
            source_type='topography_surface',
        )
        self.colourTopographyByStratigraphyCheckBox.setEnabled(True)
        if self.colourTopographyByStratigraphyCheckBox.isChecked():
            self._colour_topography_surface()
        logger.info("Adding topography surface...")

    def _on_topography_error(self, traceback_text):
        finish_background_task(
            self._topography_thread, self._topography_worker, self._topography_progress
        )
        self.addTopographyButton.setEnabled(True)
        self.colourTopographyByStratigraphyCheckBox.setEnabled(
            'topography_surface' in getattr(self.viewer, 'meshes', {})
        )
        logger.error(f"Failed to build topography surface: {traceback_text}")

    def _on_colour_topography_toggled(self, checked):
        if 'topography_surface' not in getattr(self.viewer, 'meshes', {}):
            return
        if checked:
            self._colour_topography_surface()
        else:
            mesh = self.viewer.meshes['topography_surface']['mesh']
            self.viewer.add_mesh_object(
                mesh,
                name='topography_surface',
                scalars='Elevation',
                cmap='terrain',
                show_scalar_bar=True,
                source_type='topography_surface',
            )

    def _colour_topography_surface(self):
        """Evaluate the stratigraphic unit at each topography point and
        recolour the surface using the stratigraphic column's unit colours.

        Evaluating the full model at every grid point can be slow, so this
        also runs on a background thread (see `add_topography_surface`).
        """
        if not self.model_manager:
            logger.info("Model manager is not set.")
            return
        mesh = self.viewer.meshes['topography_surface']['mesh']

        def target(progress_callback):
            progress_callback("Evaluating stratigraphy on topography...")
            ids = self.model_manager.evaluate_stratigraphy_on_points(mesh.points)
            colours = self.model_manager.get_stratigraphic_column_colours()
            return ids, colours

        self.colourTopographyByStratigraphyCheckBox.setEnabled(False)
        self._topography_thread, self._topography_worker, self._topography_progress = (
            start_background_task(
                self,
                target,
                title="Topography",
                initial_label="Evaluating stratigraphy on topography...",
                on_progress=self._on_topography_progress,
                on_finished=self._on_topography_colour_finished,
                on_error=self._on_topography_error,
            )
        )

    def _on_topography_colour_finished(self, result):
        finish_background_task(
            self._topography_thread, self._topography_worker, self._topography_progress
        )
        self.colourTopographyByStratigraphyCheckBox.setEnabled(True)

        ids, colours = result
        mesh = self.viewer.meshes['topography_surface']['mesh']
        rgb = stratigraphic_ids_to_rgb(ids, colours)
        self.viewer.add_mesh_object(
            mesh,
            name='topography_surface',
            scalars=rgb,
            rgb=True,
            show_scalar_bar=False,
            # Directional lighting shades the same colour differently depending
            # on the DEM's local slope, which makes a unit's colour on the
            # topography look like it doesn't match that same unit's colour on
            # the (much flatter) stratigraphic surfaces. Flat/unlit shading
            # keeps it a true, direct colour-for-colour match.
            lighting=False,
            source_type='topography_surface',
        )
        logger.info("Coloured topography surface by stratigraphic column.")

    def _mark_plane_defaults_dirty(self, _value=None):
        self._plane_defaults_dirty = True

    def _reset_plane_cross_section_defaults(self):
        """Point the plane cross-section controls at the model: origin at the
        bounding box centre, normal along X, size the bounding box diagonal.

        Called on every model update (see `update_feature_list`), not just
        once, since `model_manager.model` -- and so its bounding box -- exists
        (as a unit-cube placeholder) before the user has set a real one.
        Values are set with signals blocked so this doesn't itself trip
        `_mark_plane_defaults_dirty` and disable future re-syncing.
        """
        bb = self.model_manager.model.bounding_box
        origin = np.asarray(bb.origin, dtype=float)
        maximum = np.asarray(bb.maximum, dtype=float)
        centre = (origin + maximum) / 2.0
        diagonal = float(np.linalg.norm(maximum - origin))
        for box, value in (
            (self.crossSectionOriginXSpinBox, float(centre[0])),
            (self.crossSectionOriginYSpinBox, float(centre[1])),
            (self.crossSectionOriginZSpinBox, float(centre[2])),
            (self.crossSectionNormalXSpinBox, 1.0),
            (self.crossSectionNormalYSpinBox, 0.0),
            (self.crossSectionNormalZSpinBox, 0.0),
            (self.crossSectionSizeSpinBox, diagonal if diagonal > 0 else 1000.0),
        ):
            box.blockSignals(True)
            box.setValue(value)
            box.blockSignals(False)

    def _unique_cross_section_name(self, base: str) -> str:
        if base not in self.viewer.meshes:
            return base
        i = 2
        while f'{base}_{i}' in self.viewer.meshes:
            i += 1
        return f'{base}_{i}'

    def add_plane_cross_section(self):
        """Build a plane (origin + normal) cross section and colour it by the
        stratigraphic column.

        Building the plane is cheap; evaluating the stratigraphic column at
        every plane point is not, so both run on a background thread (see
        `add_topography_surface` for the same pattern).
        """
        if not self.model_manager:
            logger.info("Model manager is not set.")
            return
        if self.model_manager.model is None:
            logger.info("No model available to build a cross section.")
            return

        origin = (
            self.crossSectionOriginXSpinBox.value(),
            self.crossSectionOriginYSpinBox.value(),
            self.crossSectionOriginZSpinBox.value(),
        )
        normal = (
            self.crossSectionNormalXSpinBox.value(),
            self.crossSectionNormalYSpinBox.value(),
            self.crossSectionNormalZSpinBox.value(),
        )
        if np.allclose(normal, 0.0):
            logger.info("Cross section normal cannot be the zero vector.")
            return
        size = self.crossSectionSizeSpinBox.value()
        resolution = self.crossSectionResolutionSpinBox.value()

        def target(progress_callback):
            progress_callback("Building cross section plane...")
            mesh = build_plane_mesh(origin, normal, size, resolution)
            progress_callback("Evaluating stratigraphy on cross section...")
            ids = self.model_manager.evaluate_stratigraphy_on_points(mesh.points)
            colours = self.model_manager.get_stratigraphic_column_colours()
            return mesh, ids, colours

        self._pending_cross_section_name = self._unique_cross_section_name('cross_section_plane')
        self.addPlaneCrossSectionButton.setEnabled(False)
        self._cross_section_thread, self._cross_section_worker, self._cross_section_progress = (
            start_background_task(
                self,
                target,
                title="Cross Section",
                initial_label="Building cross section plane...",
                on_progress=self._on_cross_section_progress,
                on_finished=self._on_plane_cross_section_finished,
                on_error=self._on_cross_section_error,
            )
        )

    def _extract_line_xy(self, layer) -> Optional[np.ndarray]:
        """Return an (M, 2) array of ordered vertices for `layer`'s first
        selected feature (or first feature, if nothing is selected),
        reprojected into the model's CRS if one is available.
        """
        features = (
            list(layer.getSelectedFeatures())
            if layer.selectedFeatureCount() > 0
            else list(layer.getFeatures())
        )
        if not features:
            return None
        geom = features[0].geometry()
        if geom is None or geom.isEmpty():
            return None

        target_crs = None
        if self.data_manager is not None:
            try:
                target_crs = self.data_manager.get_model_crs()
            except Exception:
                target_crs = None
        source_crs = layer.sourceCrs()
        if target_crs is not None and target_crs.isValid() and source_crs.isValid() and source_crs != target_crs:
            geom = QgsGeometry(geom)
            geom.transform(QgsCoordinateTransform(source_crs, target_crs, QgsProject.instance()))

        if QgsWkbTypes.isMultiType(geom.wkbType()):
            parts = geom.asMultiPolyline()
            polyline = parts[0] if parts else []
        else:
            polyline = geom.asPolyline()
        if len(polyline) < 2:
            return None
        return np.array([[pt.x(), pt.y()] for pt in polyline])

    def add_line_cross_section(self):
        """Extrude the selected QGIS line layer vertically across the model's
        Z range, colouring the resulting cross section by the stratigraphic
        column. See `add_plane_cross_section` for the plane-based equivalent.
        """
        if not self.model_manager:
            logger.info("Model manager is not set.")
            return
        if self.model_manager.model is None:
            logger.info("No model available to build a cross section.")
            return
        layer = self.crossSectionLineLayerComboBox.currentLayer()
        if layer is None:
            logger.info("No line layer selected for cross section.")
            return
        coords_xy = self._extract_line_xy(layer)
        if coords_xy is None:
            logger.info("Selected layer has no usable line geometry for a cross section.")
            return

        bb = self.model_manager.model.bounding_box
        z_min, z_max = float(bb.origin[2]), float(bb.maximum[2])
        resolution = self.crossSectionLineResolutionSpinBox.value()
        z_resolution = self.crossSectionLineVerticalResolutionSpinBox.value()

        def target(progress_callback):
            progress_callback("Building cross section from line...")
            mesh = build_line_extrusion_mesh(
                coords_xy, z_min, z_max, resolution=resolution, z_resolution=z_resolution
            )
            progress_callback("Evaluating stratigraphy on cross section...")
            ids = self.model_manager.evaluate_stratigraphy_on_points(mesh.points)
            colours = self.model_manager.get_stratigraphic_column_colours()
            return mesh, ids, colours

        self._pending_cross_section_name = self._unique_cross_section_name(
            f'cross_section_line_{layer.name()}'
        )
        self.addLineCrossSectionButton.setEnabled(False)
        self._cross_section_thread, self._cross_section_worker, self._cross_section_progress = (
            start_background_task(
                self,
                target,
                title="Cross Section",
                initial_label="Building cross section from line...",
                on_progress=self._on_cross_section_progress,
                on_finished=self._on_line_cross_section_finished,
                on_error=self._on_cross_section_error,
            )
        )

    def _on_cross_section_progress(self, message):
        try:
            self._cross_section_progress.setLabelText(message)
        except Exception:
            pass

    def _add_cross_section_mesh(self, result, source_type):
        mesh, ids, colours = result
        rgb = stratigraphic_ids_to_rgb(ids, colours)
        self.viewer.add_mesh_object(
            mesh,
            name=self._pending_cross_section_name,
            scalars=rgb,
            rgb=True,
            show_scalar_bar=False,
            # see `_on_topography_colour_finished` for why cross sections use
            # flat/unlit shading: it keeps a unit's colour the same regardless
            # of how the section plane/line happens to be oriented.
            lighting=False,
            source_type=source_type,
        )
        logger.info(f"Added cross section '{self._pending_cross_section_name}'.")

    def _on_plane_cross_section_finished(self, result):
        finish_background_task(
            self._cross_section_thread, self._cross_section_worker, self._cross_section_progress
        )
        self.addPlaneCrossSectionButton.setEnabled(True)
        self._add_cross_section_mesh(result, 'cross_section_plane')

    def _on_line_cross_section_finished(self, result):
        finish_background_task(
            self._cross_section_thread, self._cross_section_worker, self._cross_section_progress
        )
        self.addLineCrossSectionButton.setEnabled(True)
        self._add_cross_section_mesh(result, 'cross_section_line')

    def _on_cross_section_error(self, traceback_text):
        finish_background_task(
            self._cross_section_thread, self._cross_section_worker, self._cross_section_progress
        )
        self.addPlaneCrossSectionButton.setEnabled(True)
        self.addLineCrossSectionButton.setEnabled(True)
        logger.error(f"Failed to build cross section: {traceback_text}")

    def _on_model_update(self, event: str, *args):
        """Called when the underlying model_manager notifies observers.

        We remove any meshes that were created from model features and re-add
        them from the current model so visualisation follows model changes.

        If the notification is for a specific feature (event == 'feature_updated')
        and an isovalue is provided (either as second arg or stored in viewer
        metadata), only the matching surface will be re-added. For generic
        'model_updated' notifications the previous behaviour (re-add all
        affected feature representations) is preserved.
        """

        # Prefer the DebugManager for logging when available (it forwards to
        # the plugin/toolbelt logger and handles debug mode). Fall back to the
        # module logger if no debug manager is present.
        def _log(msg, level=0):
            try:
                dbg = None
                if getattr(self, 'model_manager', None) is not None:
                    dbg = getattr(self.model_manager, '_debug_manager', None)
                if dbg is not None and hasattr(dbg, 'log'):
                    # DebugManager.log expects message and log_level keyword
                    dbg.log(str(msg), log_level=level)
                else:
                    logger.info(str(msg))
            except Exception:
                try:
                    logger.info(str(msg))
                except Exception:
                    pass

        _log(f"Model update event received: {event} with args: {args}")
        try:
            _log([f"Mesh: {name}, Meta: {meta}" for name, meta in self.viewer.meshes.items()])
        except Exception:
            _log("Model update: failed to enumerate viewer meshes")

        if not self.model_manager or not self.viewer:
            return
        if event not in ('model_updated', 'feature_updated'):
            return
        feature_name = None
        if event == 'feature_updated' and len(args) >= 1:
            feature_name = args[0]

        # If the model was reset (None) or features referenced by viewer meshes
        # no longer exist in the current model, remove the linkage from those
        # meshes so they are not treated as feature-driven on subsequent updates.
        try:
            try:
                current_features = {f.name for f in self.model_manager.features()}
            except Exception:
                current_features = set()

            # If the model is None or a feature referenced by a mesh is missing,
            # decouple that mesh from the feature so it remains visible but won't
            # be auto-updated or re-added when the model changes.
            for mesh_name, meta in list(self.viewer.meshes.items()):
                sf = meta.get('source_feature', None)
                if sf is None:
                    continue
                if self.model_manager.model is None or sf not in current_features:
                    _log(f"Decoupling mesh '{mesh_name}' from missing feature '{sf}'")
                    meta.pop('source_feature', None)
                    meta.pop('source_type', None)
                    meta.pop('isovalue', None)
                    # mark as decoupled so other logic can detect it if needed
                    meta['decoupled_from_feature'] = True
        except Exception:
            _log('Failed while decoupling meshes from features')

        # Build a set of features that currently have viewer meshes
        affected_features = set()
        for _, meta in list(self.viewer.meshes.items()):
            if feature_name is not None:
                if meta.get('source_feature', None) == feature_name:
                    affected_features.add(feature_name)
                    _log(f"Updating visualisation for feature: {feature_name}")
                    continue

            sf = meta.get('source_feature', None)

            if sf is not None:
                affected_features.add(sf)
        _log(f"Affected features to update: {affected_features}")
        # For each affected feature, only update existing meshes tied to that feature
        for feature_name in affected_features:
            # collect mesh names that belong to this feature (snapshot to avoid mutation while iterating)
            meshes_for_feature = [
                name
                for name, meta in list(self.viewer.meshes.items())
                if meta.get('source_feature') == feature_name
            ]
            _log(f"Re-adding meshes for feature: {feature_name}: {meshes_for_feature}")

            for mesh_name in meshes_for_feature:
                meta = self.viewer.meshes.get(mesh_name, {})
                source_type = meta.get('source_type')
                kwargs = meta.get('kwargs', {}) or {}
                isovalue = meta.get('isovalue', None)

                # remove existing actor/entry so add_mesh_object can recreate with same name
                try:
                    self.viewer.remove_object(mesh_name)
                    _log(f"Removed existing mesh: {mesh_name}")
                except Exception:
                    _log(f"Failed to remove existing mesh: {mesh_name}")

                try:
                    # Surfaces associated with individual features
                    if source_type == 'feature_surface':
                        surfaces = []
                        try:
                            if isovalue is not None:
                                surfaces = self.model_manager.model[feature_name].surfaces(isovalue)
                            else:
                                surfaces = self.model_manager.model[feature_name].surfaces()

                            if surfaces:
                                add_name = mesh_name
                                _log(
                                    f"Re-adding surface for feature: {feature_name} with isovalue: {isovalue} and {kwargs}"
                                )
                                kwargs['isovalue'] = isovalue

                                self.viewer.add_mesh_object(
                                    surfaces[0].vtk(),
                                    name=add_name,
                                    source_feature=feature_name,
                                    source_type='feature_surface',
                                    isovalue=isovalue,
                                    **kwargs,
                                )
                                continue
                        except Exception as e:
                            _log(
                                f"Failed to find matching surface for feature: {feature_name} with isovalue: {isovalue}, trying all surfaces. Error: {e}"
                            )

                    # Fault surfaces (added via add_fault_surfaces)
                    if source_type == 'fault_surface':
                        try:
                            fault_surfaces = self.model_manager.model.get_fault_surfaces()
                            match = next(
                                (s for s in fault_surfaces if str(s.name) == str(feature_name)),
                                None,
                            )
                            if match is not None:
                                _log(f"Re-adding fault surface for: {feature_name}")
                                self.viewer.add_mesh_object(
                                    match.vtk(),
                                    name=mesh_name,
                                    source_feature=feature_name,
                                    source_type='fault_surface',
                                    isovalue=meta.get('isovalue', 0.0),
                                    **kwargs,
                                )
                                continue
                        except Exception as e:
                            _log(f"Failed to re-add fault surface for {feature_name}: {e}")

                    # Stratigraphic surfaces (added via add_stratigraphic_surfaces)
                    if source_type == 'stratigraphic_surface':
                        try:
                            strat_surfaces = self.model_manager.model.get_stratigraphic_surfaces()
                            match = next(
                                (s for s in strat_surfaces if str(s.name) == str(feature_name)),
                                None,
                            )
                            if match is not None:
                                _log(f"Re-adding stratigraphic surface for: {feature_name}")
                                kwargs['color'] = getattr(match, 'colour', None)

                                self.viewer.add_mesh_object(
                                    match.vtk(),
                                    name=mesh_name,
                                    source_feature=feature_name,
                                    source_type='stratigraphic_surface',
                                    **kwargs,
                                )
                                continue
                        except Exception as e:
                            _log(f"Failed to re-add stratigraphic surface for {feature_name}: {e}")

                    # Vectors, points, scalar fields and other feature related objects
                    if source_type == 'feature_vector' or source_type == 'feature_vectors':
                        try:
                            self.add_vector_field(feature_name)
                            continue
                        except Exception as e:
                            _log(f"Failed to re-add vector field for {feature_name}: {e}")

                    if source_type in ('feature_points', 'feature_data'):
                        try:
                            self.add_data(feature_name)
                            continue
                        except Exception as e:
                            _log(f"Failed to re-add data for {feature_name}: {e}")

                    if source_type == 'feature_scalar':
                        try:
                            self.add_scalar_field(feature_name)
                            continue
                        except Exception as e:
                            _log(f"Failed to re-add scalar field for {feature_name}: {e}")

                    if source_type == 'bounding_box' or mesh_name == 'model_bounding_box':
                        try:
                            self.add_model_bounding_box()
                            continue
                        except Exception as e:
                            _log(f"Failed to re-add bounding box: {e}")

                    # Fallback: if nothing matched, attempt to re-add by using viewer metadata
                    # Many viewer entries store the vtk source under meta['vtk'] or similar; try best-effort
                    try:
                        vtk_src = meta.get('vtk')
                        if vtk_src is not None:
                            _log(f"Fallback re-add for mesh {mesh_name}")
                            self.viewer.add_mesh_object(vtk_src, name=mesh_name, **kwargs)
                    except Exception:
                        pass

                except Exception as e:
                    _log(f"Failed to update visualisation for feature: {feature_name}. Error: {e}")

        # Refresh the viewer
        try:
            self.viewer.update()
        except Exception:
            pass
