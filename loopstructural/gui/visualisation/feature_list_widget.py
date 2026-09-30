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
    QMessageBox,
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
from .cross_section_utils import (
    build_block_model_mesh,
    build_line_extrusion_mesh,
    build_plane_mesh,
)
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
        actionsRow = QHBoxLayout()
        actionsRow.addWidget(self.addBoundingBoxButton)
        actionsRow.addWidget(self.addFaultSurfacesButton)
        actionsRow.addWidget(self.addStratigraphicSurfacesButton)
        actionsRow.addWidget(self.addTopographyButton)
        actionsRow.addWidget(self.crossSectionButton)
        actionsRow.addWidget(self.blockModelButton)
        actionsRow.addStretch(1)
        self.mainLayout.addLayout(actionsRow)
        self.mainLayout.addWidget(self.colourTopographyByStratigraphyCheckBox)

        # Objects in the viewer are not rebuilt automatically when the model
        # changes (that can re-solve the whole model after each small edit).
        # They are marked out of date, and this button rebuilds them.
        self.updateObjectsButton = QPushButton(self)
        self.updateObjectsButton.setIcon(QgsApplication.getThemeIcon("mActionRefresh.svg"))
        self.updateObjectsButton.clicked.connect(self.update_out_of_date_objects)
        self.mainLayout.addWidget(self.updateObjectsButton)
        self._update_objects_thread = None
        self._update_objects_worker = None
        self._update_objects_progress = None
        if self.viewer is not None:
            self.viewer.outOfDateChanged.connect(self._refresh_update_objects_button)
        self._refresh_update_objects_button()

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
                # also listen for model and feature updates so the viewer
                # objects built from the model can be marked out of date
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

        selected_items = self.treeWidget.selectedItems()
        fold_actions = {}
        if selected_items and self._get_fold(selected_items[0].text(0)) is not None:
            fold_menu = menu.addMenu("Add Fold Constraints")
            for constraint, label in self.FOLD_CONSTRAINT_LABELS.items():
                fold_actions[fold_menu.addAction(label)] = constraint
            fold_menu.addSeparator()
            fold_actions[fold_menu.addAction("All")] = None

        action = menu.exec_(self.mapToGlobal(event.pos()))

        if not selected_items:
            return

        feature_name = selected_items[0].text(0)

        if action in fold_actions:
            constraint = fold_actions[action]
            constraints = [constraint] if constraint else list(self.FOLD_CONSTRAINT_LABELS)
            try:
                for c in constraints:
                    self.add_fold_constraint(feature_name, c)
            except Exception as e:
                logger.exception("Failed to add fold constraints")
                QMessageBox.warning(
                    self, "Fold Constraints", f"Cannot show the fold constraints:\n{e}"
                )
        elif action == add_scalar_action:
            self.add_scalar_field(feature_name)
        elif action == add_surface_action:
            self.add_surface(feature_name)
        elif action == add_vector_action:
            self.add_vector_field(feature_name)
        elif action == add_data_action:
            self.add_data(feature_name)

    def _build_scalar_field(self, feature_name):
        return self.model_manager.model[feature_name].scalar_field().vtk()

    def add_scalar_field(self, feature_name):
        self.viewer.add_mesh_object(
            self._build_scalar_field(feature_name),
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

    def _build_feature_surface(self, feature_name, isovalue):
        feature = self.model_manager.model[feature_name]
        surfaces = feature.surfaces(isovalue) if isovalue is not None else feature.surfaces()
        if not surfaces:
            raise ValueError(f"Feature '{feature_name}' has no surface at {isovalue}")
        return surfaces[0].vtk()

    def _build_vector_field(self, feature_name):
        vector_field = self.model_manager.model[feature_name].vector_field()
        return vector_field.vtk(scale=self._get_vector_scale())

    def add_vector_field(self, feature_name):
        self.viewer.add_mesh_object(
            self._build_vector_field(feature_name),
            name=f'{feature_name}_vector_field',
            source_feature=feature_name,
            source_type='feature_vector',
        )

    # Vectors used by the fold constraints in the DiscreteFoldInterpolator.
    # direction: gradient . direction = 0 (fold orientation constraint)
    # axis: gradient . axis = 0 (fold axis constraint)
    # norm: gradient . norm = fold_norm (fold normalisation constraint)
    FOLD_CONSTRAINT_LABELS = {
        'direction': "Fold Direction",
        'axis': "Fold Axis",
        'norm': "Fold Norm Direction",
    }
    FOLD_CONSTRAINT_COLOURS = {
        'direction': (0.2, 0.4, 1.0),
        'axis': (1.0, 0.2, 0.2),
        'norm': (0.1, 0.8, 0.2),
    }

    def _get_fold(self, feature_name):
        try:
            feature = self.model_manager.model[feature_name]
        except Exception:
            return None
        fold = getattr(feature, 'fold', None)
        if fold is None:
            fold = getattr(getattr(feature, 'builder', None), 'fold', None)
        return fold

    def _build_fold_constraint(self, feature_name, constraint):
        """Return the vectors of one fold constraint of a folded feature as
        a mesh, or None if the feature is not folded or the vectors are not
        defined.

        The vectors are evaluated on the model grid, in the same way as the
        interpolator evaluates them on the element barycentres.
        """
        fold = self._get_fold(feature_name)
        if fold is None:
            logger.info(f"Feature {feature_name} is not folded")
            return None
        feature = self.model_manager.model[feature_name]
        # make sure the fold rotation angles are fitted
        feature.builder.up_to_date()
        bounding_box = self.model_manager.model.bounding_box
        points = bounding_box.reproject(bounding_box.cell_centres())
        direction, axis, norm = fold.get_deformed_orientation(points)
        vectors = np.array({'direction': direction, 'axis': axis, 'norm': norm}[constraint])
        if vectors.shape != points.shape:
            # some fold settings (e.g. invert_norm) return a subset of the vectors
            logger.warning(
                f"Fold {constraint} vectors do not match the grid points ({vectors.shape} != {points.shape})"
            )
            return None
        length = np.linalg.norm(vectors, axis=1)
        mask = np.all(np.isfinite(vectors), axis=1) & (length > 0)
        if not np.any(mask):
            logger.warning(f"Fold {constraint} vectors for {feature_name} are not defined")
            return None
        vectors = vectors[mask] / length[mask, None]
        vector_points = VectorPoints(points[mask], vectors, f'{feature_name}_fold_{constraint}')
        return vector_points.vtk(scale=self._get_vector_scale())

    def add_fold_constraint(self, feature_name, constraint):
        """Add the vectors of one fold constraint of a folded feature to the viewer.

        Parameters
        ----------
        feature_name : str
            Name of the folded feature.
        constraint : str
            One of 'direction', 'axis' or 'norm'.
        """
        mesh = self._build_fold_constraint(feature_name, constraint)
        if mesh is None:
            return
        self.viewer.add_mesh_object(
            mesh,
            name=f'{feature_name}_fold_{constraint}',
            color=self.FOLD_CONSTRAINT_COLOURS[constraint],
            source_feature=feature_name,
            source_type=f'fold_constraint_{constraint}',
        )

    def _build_data_meshes(self, feature_name):
        """Return (name, mesh, source_type) for each data set of a feature."""
        meshes = []
        for d in self.model_manager.model[feature_name].get_data():
            d.locations = self.model_manager.model.rescale(d.locations)
            if issubclass(type(d), VectorPoints):
                # tolerance is None means all points are shown
                meshes.append(
                    (
                        f'{feature_name}_{d.name}_points',
                        d.vtk(scale=self._get_vector_scale(), tolerance=None),
                        'feature_points',
                    )
                )
            else:
                meshes.append((f'{feature_name}_{d.name}', d.vtk(), 'feature_data'))
        return meshes

    def add_data(self, feature_name):
        for name, mesh, source_type in self._build_data_meshes(feature_name):
            self.viewer.add_mesh_object(
                mesh, name=name, source_feature=feature_name, source_type=source_type
            )
        logger.info(f"Adding data to feature: {feature_name}")

    def _build_bounding_box(self):
        return self.model_manager.model.bounding_box.vtk().outline()

    def add_model_bounding_box(self):
        if not self.model_manager:
            logger.info("Model manager is not set.")
            return
        self.viewer.add_mesh_object(
            self._build_bounding_box(),
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

    def _find_fault_surface(self, name):
        for surface in self.model_manager.model.get_fault_surfaces():
            if str(surface.name) == str(name):
                return surface
        raise ValueError(f"Fault surface '{name}' is not in the model")

    def _find_stratigraphic_surface(self, name):
        for surface in self.model_manager.model.get_stratigraphic_surfaces():
            if str(surface.name) == str(name):
                return surface
        raise ValueError(f"Stratigraphic surface '{name}' is not in the model")

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
        self._set_stratigraphy_arrays(mesh.point_data, ids, colours)
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
            metadata={'coloured': True},
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
        if (
            target_crs is not None
            and target_crs.isValid()
            and source_crs.isValid()
            and source_crs != target_crs
        ):
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
        self._set_stratigraphy_arrays(mesh.point_data, ids, colours)
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
        self._set_stratigraphy_arrays(mesh.cell_data, ids, colours)
        self.viewer.add_mesh_object(
            mesh,
            name=self._pending_block_model_name,
            scalars='colour',
            rgb=True,
            show_scalar_bar=False,
            show_edges=False,
            source_type='block_model',
            metadata={'ncells': [int(n) for n in np.asarray(mesh.dimensions) - 1]},
        )
        logger.info(f"Added block model '{self._pending_block_model_name}'.")

    def _on_block_model_error(self, traceback_text):
        finish_background_task(
            self._block_model_thread, self._block_model_worker, self._block_model_progress
        )
        self.addBlockModelButton.setEnabled(True)
        logger.error(f"Failed to build block model: {traceback_text}")

    @staticmethod
    def _set_stratigraphy_arrays(data, ids, colours):
        """Store the unit ids and their colours as the 'stratigraphy' and
        'colour' arrays of `data` (a mesh's point_data or cell_data).

        Named arrays (not an RGB array passed straight to the viewer) let the
        object properties panel use the unit ids, and let
        `update_out_of_date_objects` add the object again with the same
        viewer settings.
        """
        data['stratigraphy'] = np.asarray(ids)
        data['colour'] = stratigraphic_ids_to_rgb(ids, colours)

    def _colour_by_stratigraphy(self, points, data):
        ids = self.model_manager.evaluate_stratigraphy_on_points(points)
        colours = self.model_manager.get_stratigraphic_column_colours()
        self._set_stratigraphy_arrays(data, ids, colours)

    # Viewer objects that `_rebuild_object` can build again from the model,
    # by `source_type` (fold constraints use the 'fold_constraint_' prefix).
    REBUILDABLE_SOURCE_TYPES = {
        'feature_scalar',
        'feature_surface',
        'feature_vector',
        'feature_vectors',
        'feature_points',
        'feature_data',
        'bounding_box',
        'fault_surface',
        'stratigraphic_surface',
        'cross_section_plane',
        'cross_section_line',
        'block_model',
        'topography_surface',
    }
    # Source types that are coloured by the stratigraphic column
    STRATIGRAPHY_COLOURED_SOURCE_TYPES = {
        'cross_section_plane',
        'cross_section_line',
        'block_model',
    }
    # Source types that are built from one feature of the model
    FEATURE_SOURCE_TYPES = {
        'feature_scalar',
        'feature_surface',
        'feature_vector',
        'feature_vectors',
        'feature_points',
        'feature_data',
    }

    def _is_rebuildable(self, meta) -> bool:
        source_type = meta.get('source_type') or ''
        return source_type in self.REBUILDABLE_SOURCE_TYPES or source_type.startswith(
            'fold_constraint_'
        )

    def _uses_stratigraphy_colours(self, spec) -> bool:
        if spec['source_type'] in self.STRATIGRAPHY_COLOURED_SOURCE_TYPES:
            return True
        return spec['source_type'] == 'topography_surface' and bool(
            spec['metadata'].get('coloured')
        )

    def _on_model_update(self, event: str, *args):
        """Mark the viewer objects built from the model as out of date.

        The objects are not rebuilt here: rebuilding can solve the model
        again, which is slow after each small edit. The user rebuilds them
        with the update button (see `update_out_of_date_objects`).
        """
        if not self.viewer:
            return
        if event not in ('model_updated', 'feature_updated'):
            return
        names = [
            name for name, meta in list(self.viewer.meshes.items()) if self._is_rebuildable(meta)
        ]
        self.viewer.set_out_of_date(names, True)

    def _refresh_update_objects_button(self):
        count = len(self.viewer.out_of_date_objects()) if self.viewer is not None else 0
        if self._update_objects_thread is not None:
            self.updateObjectsButton.setText("Updating Viewer Objects...")
            self.updateObjectsButton.setEnabled(False)
        elif count:
            noun = "Object" if count == 1 else "Objects"
            self.updateObjectsButton.setText(f"Update {count} Out-of-Date {noun}")
            self.updateObjectsButton.setToolTip(
                "The model changed after these objects were added to the viewer. "
                "Build them again from the current model."
            )
            self.updateObjectsButton.setEnabled(True)
        else:
            self.updateObjectsButton.setText("Viewer Objects Up to Date")
            self.updateObjectsButton.setToolTip("")
            self.updateObjectsButton.setEnabled(False)

    def update_out_of_date_objects(self):
        """Build all out-of-date viewer objects again from the current model.

        The objects are built on a background thread (this can solve the
        model), then added to the viewer again on the GUI thread with the
        same name and viewer settings (see `_on_update_objects_finished`).
        """
        if not self.model_manager or self.viewer is None:
            return
        if self.model_manager.model is None:
            logger.info("No model available to update the viewer objects.")
            return
        names = self.viewer.out_of_date_objects()
        if not names:
            return
        specs = []
        for name in names:
            meta = self.viewer.meshes[name]
            spec = {
                'name': name,
                'source_type': meta.get('source_type') or '',
                'source_feature': meta.get('source_feature'),
                'isovalue': meta.get('isovalue'),
                'metadata': dict(meta.get('metadata') or {}),
            }
            if spec['source_type'] in ('cross_section_plane', 'cross_section_line'):
                # the section geometry does not change; copy it so the
                # background thread does not change the mesh on screen
                spec['mesh'] = meta['mesh'].copy()
            specs.append(spec)

        if any(self._uses_stratigraphy_colours(spec) for spec in specs):
            missing = self.model_manager.get_units_without_colour()
            if missing:
                QMessageBox.warning(
                    self,
                    "Missing unit colour",
                    "Cannot update the objects coloured by stratigraphy. These units "
                    "have no valid colour in the stratigraphic column:\n\n"
                    + "\n".join(missing)
                    + "\n\nSet a colour for each unit and try again.",
                )
                return

        def target(progress_callback):
            results = []
            for i, spec in enumerate(specs):
                progress_callback(f"Updating {spec['name']} ({i + 1} of {len(specs)})...")
                try:
                    mesh, overrides = self._rebuild_object(spec)
                    results.append((spec['name'], mesh, overrides, None))
                except Exception as e:
                    results.append((spec['name'], None, {}, str(e)))
            return results

        self._update_objects_thread, self._update_objects_worker, self._update_objects_progress = (
            start_background_task(
                self,
                target,
                title="Update Viewer Objects",
                initial_label="Updating viewer objects...",
                on_progress=self._on_update_objects_progress,
                on_finished=self._on_update_objects_finished,
                on_error=self._on_update_objects_error,
            )
        )
        self._refresh_update_objects_button()

    def _rebuild_object(self, spec):
        """Build one viewer object again from the current model.

        Runs on a background thread, so it must not touch the viewer.
        Returns (mesh, overrides), where overrides are viewer settings that
        come from the model (e.g. a unit colour). Raises if the object cannot
        be built.
        """
        source_type = spec['source_type']
        feature_name = spec['source_feature']
        metadata = spec['metadata']
        model = self.model_manager.model

        if source_type in self.FEATURE_SOURCE_TYPES or source_type.startswith('fold_constraint_'):
            if feature_name is None or model.get_feature_by_name(feature_name) is None:
                raise ValueError(f"Feature '{feature_name}' is not in the model")

        overrides = {}
        if source_type == 'feature_scalar':
            mesh = self._build_scalar_field(feature_name)
        elif source_type == 'feature_surface':
            mesh = self._build_feature_surface(feature_name, spec['isovalue'])
        elif source_type in ('feature_vector', 'feature_vectors'):
            mesh = self._build_vector_field(feature_name)
        elif source_type.startswith('fold_constraint_'):
            constraint = source_type[len('fold_constraint_') :]
            mesh = self._build_fold_constraint(feature_name, constraint)
            if mesh is None:
                raise ValueError("The fold constraint vectors are not defined")
        elif source_type in ('feature_points', 'feature_data'):
            meshes = {name: m for name, m, _ in self._build_data_meshes(feature_name)}
            if spec['name'] not in meshes:
                raise ValueError(f"Feature '{feature_name}' has no data for this object")
            mesh = meshes[spec['name']]
        elif source_type == 'bounding_box':
            mesh = self._build_bounding_box()
        elif source_type == 'fault_surface':
            mesh = self._find_fault_surface(feature_name).vtk()
        elif source_type == 'stratigraphic_surface':
            surface = self._find_stratigraphic_surface(feature_name)
            mesh = surface.vtk()
            overrides['color'] = surface.colour
        elif source_type in ('cross_section_plane', 'cross_section_line'):
            mesh = spec['mesh']
            self._colour_by_stratigraphy(mesh.points, mesh.point_data)
        elif source_type == 'block_model':
            bb = model.bounding_box
            mesh = build_block_model_mesh(bb.origin, bb.maximum, metadata['ncells'])
            self._colour_by_stratigraphy(mesh.cell_centers().points, mesh.cell_data)
        elif source_type == 'topography_surface':
            xx, yy, zz = self.model_manager.sample_dem_grid()
            mesh = pv.StructuredGrid(xx, yy, zz)
            mesh['Elevation'] = mesh.points[:, 2]
            if metadata.get('coloured'):
                self._colour_by_stratigraphy(mesh.points, mesh.point_data)
        else:
            raise ValueError(f"Cannot update objects of type '{source_type}'")

        if getattr(mesh, 'n_points', 1) == 0:
            raise ValueError("The object has no geometry in the current model")
        return mesh, overrides

    def _on_update_objects_progress(self, message):
        try:
            self._update_objects_progress.setLabelText(message)
        except Exception:
            pass

    def _finish_update_objects_task(self):
        finish_background_task(
            self._update_objects_thread, self._update_objects_worker, self._update_objects_progress
        )
        self._update_objects_thread = None
        self._update_objects_worker = None
        self._update_objects_progress = None

    def _on_update_objects_finished(self, results):
        self._finish_update_objects_task()
        failed = []
        for name, mesh, overrides, error in results:
            entry = self.viewer.meshes.get(name)
            if entry is None:
                # removed from the viewer while the update ran
                continue
            if error is not None:
                failed.append(f"{name}: {error}")
                continue
            if not self._replace_viewer_object(name, entry, mesh, overrides):
                failed.append(f"{name}: cannot add the new object to the viewer")
        try:
            self.viewer.render()
        except Exception:
            pass
        self._refresh_update_objects_button()
        if failed:
            logger.warning("Cannot update viewer objects:\n" + "\n".join(failed))
            QMessageBox.warning(
                self,
                "Update Viewer Objects",
                "These objects were not updated and are still out of date:\n\n" + "\n".join(failed),
            )

    def _replace_viewer_object(self, name, entry, mesh, overrides) -> bool:
        """Put `mesh` in the viewer in place of the object `name`, with the
        same source values, viewer settings and visibility."""
        source = self.viewer.get_source_metadata(name)
        source['out_of_date'] = False
        kwargs = {
            key: value
            for key, value in (entry.get('kwargs') or {}).items()
            if key not in source and key != 'name'
        }
        kwargs.update(overrides)
        # a colour picked in the object properties panel has priority
        user_colour = entry.get('color')
        if user_colour is not None:
            kwargs['color'] = user_colour
        actor = entry.get('actor')
        visible = bool(getattr(actor, 'visibility', True))

        # pyvista replaces the actor with the same name, so the old object
        # stays in the viewer if the new one cannot be added
        try:
            self.viewer.add_mesh_object(mesh, name=name, **source, **kwargs)
        except Exception:
            # e.g. a scalar array selected in the properties panel that the
            # new mesh does not have; add it with the default colouring
            for key in ('scalars', 'cmap', 'clim', 'rgb'):
                kwargs.pop(key, None)
            try:
                self.viewer.add_mesh_object(mesh, name=name, **source, **kwargs)
            except Exception:
                logger.exception(f"Cannot add updated object '{name}' to the viewer")
                return False

        new_entry = self.viewer.meshes.get(name, {})
        if user_colour is not None:
            new_entry['color'] = user_colour
        if not visible and new_entry.get('actor') is not None:
            new_entry['actor'].visibility = False
        return True

    def _on_update_objects_error(self, traceback_text):
        self._finish_update_objects_task()
        self._refresh_update_objects_button()
        logger.error(f"Failed to update viewer objects: {traceback_text}")
        QMessageBox.warning(
            self,
            "Update Viewer Objects",
            "Cannot update the viewer objects. See the log for details.",
        )
