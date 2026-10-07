import logging
from typing import Optional

import numpy as np
from qgis.core import QgsApplication, QgsMapLayerProxyModel
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
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from loopstructural.__about__ import DIR_PLUGIN_ROOT

from ..background_task import finish_background_task, start_background_task
from ..compatibility import configure_layer_combo
from .cross_section_utils import (
    build_block_model_mesh,
    build_line_extrusion_mesh,
    build_plane_mesh,
)
from .line_layer import line_xy_from_layer
from .mesh_builders import MeshBuilder, set_stratigraphy_arrays

logger = logging.getLogger(__name__)


class ViewerActionsWidget(QWidget):
    """The row of actions that add model-wide objects to the viewer: the
    bounding box, the fault and stratigraphic surfaces, the topography, cross
    sections and the block model.

    The long actions (topography, cross sections, block model) run on a
    background thread. The meshes come from `MeshBuilder`; this widget adds
    them to the viewer.
    """

    def __init__(self, parent=None, *, model_manager=None, viewer=None, data_manager=None):
        super().__init__(parent)
        self.model_manager = model_manager
        self.viewer = viewer
        self.data_manager = data_manager
        self.builder = MeshBuilder(model_manager)

        self.addBoundingBoxButton = self._make_tool_button("extents.svg", "Add Model Bounding Box")
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
        self._build_block_model_controls()

        # A single row of icon-only actions, in workflow order, replaces the
        # previous stack of full-width text buttons.
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        actionsRow = QHBoxLayout()
        actionsRow.addWidget(self.addBoundingBoxButton)
        actionsRow.addWidget(self.addFaultSurfacesButton)
        actionsRow.addWidget(self.addStratigraphicSurfacesButton)
        actionsRow.addWidget(self.addTopographyButton)
        actionsRow.addWidget(self.crossSectionButton)
        actionsRow.addWidget(self.blockModelButton)
        actionsRow.addStretch(1)
        layout.addLayout(actionsRow)
        layout.addWidget(self.colourTopographyByStratigraphyCheckBox)

        # background task handles shared by the plane and line cross-section
        # actions (only one can run at a time)
        self._cross_section_thread = None
        self._cross_section_worker = None
        self._cross_section_progress = None
        self._pending_cross_section_name = None

        # background task handles for the block model
        self._block_model_thread = None
        self._block_model_worker = None
        self._block_model_progress = None
        self._pending_block_model_name = None
        # Whether the user has hand-edited the plane's origin/normal/size --
        # while False, `on_model_updated` keeps re-syncing those fields to
        # the model's current bounding box (see
        # `_reset_plane_cross_section_defaults`). `model_manager.model` is
        # never None -- it starts out as a placeholder unit-cube model before
        # a real bounding box is set -- so this can't be a one-shot flag set
        # on first model sight; it has to keep tracking the *current* box
        # until the user opts out by typing a value in themselves.
        self._plane_defaults_dirty = False

    def on_model_updated(self):
        """Point the cross-section defaults at the current model."""
        if self.model_manager.model is not None and not self._plane_defaults_dirty:
            self._reset_plane_cross_section_defaults()

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
        configure_layer_combo(
            self.crossSectionLineLayerComboBox, QgsMapLayerProxyModel.Filter.LineLayer
        )
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

    def _build_block_model_controls(self):
        """Build the "Block Model" icon button (added to the shared actions
        row in __init__), which opens a dialog to set the number of blocks
        along each axis. The block model fills the model bounding box and is
        coloured by the stratigraphic column, like the cross sections.
        """
        self.blockModelButton = self._make_custom_icon_tool_button(
            "block_model.svg", "Block Model..."
        )
        self.blockModelButton.clicked.connect(self._show_block_model_dialog)
        self._block_model_resolution_initialised = False

        self.blockModelDialog = QDialog(self)
        self.blockModelDialog.setWindowTitle("Block Model")
        dialogLayout = QVBoxLayout(self.blockModelDialog)
        dialogLayout.addWidget(QLabel("Blocks fill the model bounding box"))
        form = QFormLayout()

        def make_cells_spinbox():
            box = QSpinBox(self)
            box.setRange(1, 1000)
            box.setValue(50)
            return box

        self.blockModelNxSpinBox = make_cells_spinbox()
        self.blockModelNySpinBox = make_cells_spinbox()
        self.blockModelNzSpinBox = make_cells_spinbox()
        form.addRow(
            "Blocks (x, y, z)",
            self._hbox(
                self.blockModelNxSpinBox, self.blockModelNySpinBox, self.blockModelNzSpinBox
            ),
        )
        self.blockModelUseModelResolutionButton = QPushButton("Use Model Resolution", self)
        self.blockModelUseModelResolutionButton.setToolTip(
            "Set the number of blocks to the model's interpolation grid"
        )
        self.blockModelUseModelResolutionButton.clicked.connect(self._reset_block_model_resolution)
        form.addRow("", self.blockModelUseModelResolutionButton)
        dialogLayout.addLayout(form)

        self.addBlockModelButton = QPushButton("Add Block Model", self)
        self.addBlockModelButton.clicked.connect(self.add_block_model)
        dialogLayout.addWidget(self.addBlockModelButton)

        closeButton = QPushButton("Close", self.blockModelDialog)
        closeButton.clicked.connect(self.blockModelDialog.close)
        dialogLayout.addWidget(closeButton)

    def _show_block_model_dialog(self):
        # Start from the model's own resolution the first time only, so the
        # user's block counts are kept between openings of the dialog.
        if not self._block_model_resolution_initialised:
            self._reset_block_model_resolution()
            self._block_model_resolution_initialised = True
        self.blockModelDialog.show()
        self.blockModelDialog.raise_()
        self.blockModelDialog.activateWindow()

    def _reset_block_model_resolution(self):
        if not self.model_manager or self.model_manager.model is None:
            return
        try:
            nsteps = np.asarray(self.model_manager.model.bounding_box.nsteps, dtype=int)
        except Exception:
            logger.info("Model bounding box has no resolution.")
            return
        for box, value in zip(
            (self.blockModelNxSpinBox, self.blockModelNySpinBox, self.blockModelNzSpinBox),
            nsteps,
        ):
            box.setValue(int(value))

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

    def add_model_bounding_box(self):
        if not self.model_manager:
            logger.info("Model manager is not set.")
            return
        self.viewer.add_mesh_object(
            self.builder.bounding_box(),
            name='model_bounding_box',
            source_feature='__model__',
            source_type='bounding_box',
        )
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
            mesh = surface.vtk()
            if mesh.n_points == 0:
                # A unit with no digitised data of its own (e.g. an
                # undigitised placeholder like "Top") can have no
                # constrained geometry anywhere in the model, so its
                # isovalue may not intersect the solved field at all --
                # pyvista refuses to plot an empty mesh, so skip it rather
                # than crashing every surface after it in this loop.
                logger.info(f"Skipping '{surface.name}': isosurface has no geometry.")
                continue
            self.viewer.add_mesh_object(
                mesh,
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

        mesh = self.builder.topography_from_grid(*result)
        self.viewer.add_mesh_object(
            mesh,
            name='topography_surface',
            scalars='Elevation',
            cmap='terrain',
            show_scalar_bar=True,
            source_type='topography_surface',
            metadata={'coloured': False},
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
            'topography_surface' in self.viewer.registry
        )
        logger.error(f"Failed to build topography surface: {traceback_text}")

    def _on_colour_topography_toggled(self, checked):
        if 'topography_surface' not in self.viewer.registry:
            return
        if checked:
            self._colour_topography_surface()
        else:
            mesh = self.viewer.registry.get('topography_surface').mesh
            self.viewer.add_mesh_object(
                mesh,
                name='topography_surface',
                scalars='Elevation',
                cmap='terrain',
                show_scalar_bar=True,
                source_type='topography_surface',
                metadata={'coloured': False},
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
        missing = self.model_manager.get_units_without_colour()
        if missing:
            QMessageBox.warning(
                self,
                "Missing unit colour",
                "Cannot colour the topography by stratigraphy. These units have no "
                "valid colour in the stratigraphic column:\n\n"
                + "\n".join(missing)
                + "\n\nSet a colour for each unit and try again.",
            )
            self.colourTopographyByStratigraphyCheckBox.blockSignals(True)
            self.colourTopographyByStratigraphyCheckBox.setChecked(False)
            self.colourTopographyByStratigraphyCheckBox.blockSignals(False)
            return
        mesh = self.viewer.registry.get('topography_surface').mesh

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
        mesh = self.viewer.registry.get('topography_surface').mesh
        set_stratigraphy_arrays(mesh.point_data, ids, colours)
        metadata = {'coloured': True, **self.builder.stratigraphy_metadata(colours)}
        self.viewer.add_mesh_object(
            mesh,
            name='topography_surface',
            scalars='colour',
            rgb=True,
            show_scalar_bar=False,
            # Directional lighting shades the same colour differently depending
            # on the DEM's local slope, which makes a unit's colour on the
            # topography look like it doesn't match that same unit's colour on
            # the (much flatter) stratigraphic surfaces. Flat/unlit shading
            # keeps it a true, direct colour-for-colour match.
            lighting=False,
            source_type='topography_surface',
            metadata=metadata,
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
        return self.viewer.registry.unique_name(base)

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
        target_crs = None
        if self.data_manager is not None:
            try:
                target_crs = self.data_manager.get_model_crs()
            except Exception:
                target_crs = None
        return line_xy_from_layer(layer, target_crs)

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
        set_stratigraphy_arrays(mesh.point_data, ids, colours)
        self.viewer.add_mesh_object(
            mesh,
            name=self._pending_cross_section_name,
            scalars='colour',
            rgb=True,
            show_scalar_bar=False,
            # see `_on_topography_colour_finished` for why cross sections use
            # flat/unlit shading: it keeps a unit's colour the same regardless
            # of how the section plane/line happens to be oriented.
            lighting=False,
            source_type=source_type,
            metadata=self.builder.stratigraphy_metadata(colours),
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

    def add_block_model(self):
        """Fill the model bounding box with blocks and colour each block by
        the stratigraphic unit at its centre.

        Evaluating the model at every block centre can be slow, so this runs
        on a background thread (see `add_topography_surface`).
        """
        if not self.model_manager:
            logger.info("Model manager is not set.")
            return
        if self.model_manager.model is None:
            logger.info("No model available to build a block model.")
            return
        missing = self.model_manager.get_units_without_colour()
        if missing:
            QMessageBox.warning(
                self,
                "Missing unit colour",
                "Cannot colour the block model by stratigraphy. These units have no "
                "valid colour in the stratigraphic column:\n\n"
                + "\n".join(missing)
                + "\n\nSet a colour for each unit and try again.",
            )
            return

        bb = self.model_manager.model.bounding_box
        origin = np.asarray(bb.origin, dtype=float)
        maximum = np.asarray(bb.maximum, dtype=float)
        ncells = (
            self.blockModelNxSpinBox.value(),
            self.blockModelNySpinBox.value(),
            self.blockModelNzSpinBox.value(),
        )

        def target(progress_callback):
            progress_callback("Building block model grid...")
            mesh = build_block_model_mesh(origin, maximum, ncells)
            progress_callback("Evaluating stratigraphy on block model...")
            ids = self.model_manager.evaluate_stratigraphy_on_points(mesh.cell_centers().points)
            colours = self.model_manager.get_stratigraphic_column_colours()
            return mesh, ids, colours

        self._pending_block_model_name = self._unique_cross_section_name('block_model')
        self.addBlockModelButton.setEnabled(False)
        self._block_model_thread, self._block_model_worker, self._block_model_progress = (
            start_background_task(
                self,
                target,
                title="Block Model",
                initial_label="Building block model grid...",
                on_progress=self._on_block_model_progress,
                on_finished=self._on_block_model_finished,
                on_error=self._on_block_model_error,
            )
        )

    def _on_block_model_progress(self, message):
        try:
            self._block_model_progress.setLabelText(message)
        except Exception:
            pass

    def _on_block_model_finished(self, result):
        finish_background_task(
            self._block_model_thread, self._block_model_worker, self._block_model_progress
        )
        self.addBlockModelButton.setEnabled(True)

        mesh, ids, colours = result
        set_stratigraphy_arrays(mesh.cell_data, ids, colours)
        self.viewer.add_mesh_object(
            mesh,
            name=self._pending_block_model_name,
            scalars='colour',
            rgb=True,
            show_scalar_bar=False,
            show_edges=False,
            source_type='block_model',
            metadata={
                'ncells': [int(n) for n in np.asarray(mesh.dimensions) - 1],
                **self.builder.stratigraphy_metadata(colours),
            },
        )
        logger.info(f"Added block model '{self._pending_block_model_name}'.")

    def _on_block_model_error(self, traceback_text):
        finish_background_task(
            self._block_model_thread, self._block_model_worker, self._block_model_progress
        )
        self.addBlockModelButton.setEnabled(True)
        logger.error(f"Failed to build block model: {traceback_text}")
