import numpy as np
from LoopStructural.modelling.features import StructuralFrame
from LoopStructural.utils import normal_vector_to_strike_and_dip
from qgis.gui import QgsCollapsibleGroupBox, QgsMapLayerComboBox
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from qgis.utils import plugins

from LoopStructural import getLogger
from loopstructural.main import preview

from ....background_task import finish_background_task, start_background_task
from ....messages import push_info, push_warning
from ...steps.section_stack import SectionStack
from ..bounding_box_widget import BoundingBoxWidget
from ..layer_selection_table import LayerSelectionTable

logger = getLogger(__name__)


# Helper functions for retrieving fault dip and pitch from stored data or calculations
def retrieve_dip_value(fault, model_manager):
    """
    Retrieve dip value from stored fault data or calculate from normal vector.

    Args:
        fault: The fault object with a name and fault_normal_vector attribute
        model_manager: The model manager with faults dictionary

    Returns:
        float: The dip angle in degrees
    """
    dip = None
    if model_manager is not None and fault.name in model_manager.faults:
        fault_data = model_manager.faults[fault.name].get('data')
        if fault_data is not None and 'dip' in fault_data.columns and not fault_data.empty:
            dip = fault_data['dip'].mean()

    # Fallback: calculate from normal vector if not found in stored data
    if dip is None:
        try:
            dip = normal_vector_to_strike_and_dip(fault.fault_normal_vector)[0, 1]
        except Exception:
            dip = 90  # Default value if calculation fails

    return dip


def retrieve_pitch_value(fault, model_manager):
    """
    Retrieve pitch value from stored fault data.

    Args:
        fault: The fault object with a name attribute
        model_manager: The model manager with faults dictionary

    Returns:
        float: The pitch angle in degrees (default 0)
    """
    pitch = 0
    if model_manager is not None and fault.name in model_manager.faults:
        fault_data = model_manager.faults[fault.name].get('data')
        if fault_data is not None and 'pitch' in fault_data.columns and not fault_data.empty:
            pitch = fault_data['pitch'].mean()

    return pitch


class BaseFeatureDetailsPanel(QWidget):
    def __init__(self, parent=None, *, feature=None, model_manager=None, data_manager=None):
        super().__init__(parent)
        self.plugin = plugins.get('loopstructural')

        self.feature = feature
        self.model_manager = model_manager
        self.data_manager = data_manager
        # The sections of the panel. At most two are open. The page that holds
        # the panel has the scroll area.
        mainLayout = QVBoxLayout(self)
        mainLayout.setContentsMargins(0, 0, 0, 0)
        self.layout = SectionStack(self, 'feature_details', data_manager)
        mainLayout.addWidget(self.layout)
        mainLayout.addStretch(1)

        ## define interpolator parameters
        # Regularisation spin box
        self.regularisation_spin_box = QDoubleSpinBox()
        self.regularisation_spin_box.setRange(0, 100)
        self.regularisation_spin_box.setValue(
            feature.builder.build_arguments.get('regularisation', 1.0)
        )
        # Update build arguments and schedule a debounced rebuild
        self.regularisation_spin_box.valueChanged.connect(
            lambda value: (
                self.feature.builder.update_build_arguments({'regularisation': value}),
                self.schedule_rebuild(),
            )
        )
        self.cpw_spin_box = QDoubleSpinBox()
        self.cpw_spin_box.setRange(0, 100)
        self.cpw_spin_box.setValue(feature.builder.build_arguments.get('cpw', 1.0))
        self.cpw_spin_box.valueChanged.connect(
            lambda value: (
                self.feature.builder.update_build_arguments({'cpw': value}),
                self.schedule_rebuild(),
            )
        )

        self.npw_spin_box = QDoubleSpinBox()
        self.npw_spin_box.setRange(0, 100)
        self.npw_spin_box.setValue(feature.builder.build_arguments.get('npw', 1.0))
        self.npw_spin_box.valueChanged.connect(
            lambda value: (
                self.feature.builder.update_build_arguments({'npw': value}),
                self.schedule_rebuild(),
            )
        )
        self.interpolator_type_label = QLabel("Interpolator Type:")
        self.interpolator_type_combo = QComboBox()
        self.interpolator_type_combo.addItems(["FDI", "PLI", "surfe"])

        self.n_elements_spinbox = QDoubleSpinBox()
        self.n_elements_spinbox.setRange(100, 1000000)
        self.n_elements_spinbox.setValue(self.getNelements(feature))
        self.n_elements_spinbox.setPrefix("Number of Elements: ")
        self.n_elements_auto_check = QCheckBox("Automatic")
        self.n_elements_auto_check.setToolTip(
            "Choose the number of elements from the data of the feature. "
            "Clear the check box to keep the number that you enter."
        )
        self.n_elements_auto_check.setChecked(not self._has_nelements_override())
        self.n_elements_spinbox.setEnabled(not self.n_elements_auto_check.isChecked())

        self.n_elements_spinbox.valueChanged.connect(self.updateNelements)
        self.n_elements_auto_check.toggled.connect(self._on_nelements_auto_toggled)

        table_group_box = QgsCollapsibleGroupBox('Data Layers')
        self.layer_table = LayerSelectionTable(
            data_manager=self.data_manager,
            feature_name_provider=lambda: self.feature.name,
            name_validator=lambda: (True, ''),  # Always valid in this context
        )
        table_layout = QVBoxLayout()
        table_layout.addWidget(self._build_detach_widget())
        table_layout.addWidget(self.layer_table)
        self.view_constraint_data_button = QPushButton("View Data Used by Interpolator")
        self.view_constraint_data_button.setToolTip(
            "Add the raw point/orientation data currently used by this feature's "
            "interpolator as a temporary QGIS layer. Useful when the data came "
            "from the automated data-processing workflow, which populates the "
            "interpolator directly and never appears in the table above."
        )
        self.view_constraint_data_button.clicked.connect(self._show_constraint_data_on_map)
        table_layout.addWidget(self.view_constraint_data_button)
        table_group_box.setLayout(table_layout)
        # Form layout for better organization
        form_layout = QFormLayout()
        form_layout.addRow(self.interpolator_type_label, self.interpolator_type_combo)
        form_layout.addRow("Number of Elements:", self.n_elements_spinbox)
        form_layout.addRow("", self.n_elements_auto_check)
        form_layout.addRow('Regularisation', self.regularisation_spin_box)
        form_layout.addRow('Contact points weight', self.cpw_spin_box)
        form_layout.addRow('Orientation point weight', self.npw_spin_box)
        group_box = QgsCollapsibleGroupBox('Interpolator Settings')
        group_box.setLayout(form_layout)
        self.layout.add_section(
            group_box,
            'interpolator',
            'Interpolator Settings',
            summary=lambda: (
                f"{self.interpolator_type_combo.currentText()}, "
                f"{int(self.n_elements_spinbox.value())} elements"
                f"{' (automatic)' if self.n_elements_auto_check.isChecked() else ''}"
            ),
        )
        self.layout.add_section(self._build_preview_widget(), 'preview', 'Preview', collapsed=True)
        self.layout.add_section(table_group_box, 'data_layers', 'Data Layers')
        # this will call the addMidBlock and addExportBlock methods
        self.addMidBlock()
        self.addExportBlock()

    def _build_preview_widget(self):
        """Return the group with the button that shows the isolines of this feature on the map."""
        group = QgsCollapsibleGroupBox('Preview')
        row = QHBoxLayout(group)
        self.preview_levels_spin = QSpinBox()
        self.preview_levels_spin.setRange(1, 100)
        self.preview_levels_spin.setValue(preview.DEFAULT_LEVEL_COUNT)
        self.preview_levels_spin.setPrefix("Lines: ")
        self.preview_levels_spin.setToolTip("The number of isolines.")
        self.preview_button = QPushButton("Preview on map")
        self.preview_button.setToolTip(
            "Solve this feature only, and add its isolines on the ground (the DEM) to the "
            "project as a temporary layer. The other features are not solved."
        )
        self.preview_button.clicked.connect(self.preview_on_map)
        row.addWidget(self.preview_levels_spin)
        row.addWidget(self.preview_button, 1)
        self._preview_layer_id = None
        return group

    def preview_on_map(self):
        """Solve this feature and show its isolines on the map canvas.

        The grid is read on the GUI thread (the DEM can be a raster layer). The
        solve and the lines are made on a background thread.
        """
        manager = self.model_manager
        name = self.feature.name
        model = getattr(manager, 'model', None)
        if model is None or model.bounding_box is None:
            QMessageBox.warning(self, "Preview", "Build the model first.")
            return
        bounding_box = model.bounding_box
        x, y, points = preview.grid_points(
            bounding_box.origin,
            bounding_box.maximum,
            preview.DEFAULT_RESOLUTION,
            getattr(manager, 'dem_function', None),
        )
        count = self.preview_levels_spin.value()

        def target(progress_callback):
            progress_callback("Solving the feature...")
            values = np.asarray(manager.evaluate_feature_on_points(name, points), dtype=float)
            if values.ndim != 1:
                raise ValueError("The feature has no scalar field to draw.")
            values = values.reshape(len(y), len(x))
            progress_callback("Making the lines...")
            levels = preview.default_levels(values, count)
            return preview.isolines(x, y, values, levels), levels

        self.preview_button.setEnabled(False)
        self._preview_task = start_background_task(
            self,
            target,
            title="Preview",
            initial_label="Solving the feature...",
            on_progress=self._on_preview_progress,
            on_finished=self._on_preview_finished,
            on_error=self._on_preview_error,
        )

    def _on_preview_progress(self, message):
        try:
            self._preview_task[2].setLabelText(message)
        except Exception:
            pass

    def _end_preview_task(self):
        finish_background_task(*self._preview_task)
        self.preview_button.setEnabled(True)

    def _on_preview_error(self, traceback_text):
        self._end_preview_task()
        lines = traceback_text.strip().splitlines()
        QMessageBox.critical(
            self, "Preview failed", lines[-1] if lines else "The preview stopped with an error."
        )

    def _on_preview_finished(self, result):
        self._end_preview_task()
        lines, levels = result
        if not lines:
            push_warning(
                "Preview",
                f"'{self.feature.name}' has no isolines on the map. The field has no range "
                "or no values in the model area.",
            )
            return
        self._show_preview_lines(lines)
        # the feature is solved now, so the ticks of the feature list change
        self.model_manager.notify('model_updated')
        push_info(
            "Preview",
            f"{len(lines)} lines for '{self.feature.name}', from {levels.min():g} to {levels.max():g}.",
        )

    def _show_preview_lines(self, lines):
        """Add the isolines as a temporary layer. An earlier preview of this feature is replaced."""
        from qgis.core import (
            QgsFeature,
            QgsField,
            QgsGeometry,
            QgsPointXY,
            QgsProject,
            QgsVectorLayer,
        )

        from loopstructural.gui.compatibility import QVariantCompat

        project = QgsProject.instance()
        previous = getattr(self, '_preview_layer_id', None)
        if previous and project.mapLayer(previous) is not None:
            project.removeMapLayer(previous)
        crs = self.data_manager.get_model_crs() if self.data_manager is not None else None
        crs_text = crs.authid() if crs is not None and crs.isValid() else project.crs().authid()
        layer = QgsVectorLayer(
            f"LineString?crs={crs_text}", f"Preview: {self.feature.name}", "memory"
        )
        provider = layer.dataProvider()
        provider.addAttributes([QgsField("value", QVariantCompat.Double)])
        layer.updateFields()
        features = []
        for level, coordinates in lines:
            feature = QgsFeature(layer.fields())
            feature.setGeometry(
                QgsGeometry.fromPolylineXY([QgsPointXY(px, py) for px, py in coordinates])
            )
            feature.setAttribute("value", level)
            features.append(feature)
        provider.addFeatures(features)
        layer.updateExtents()
        project.addMapLayer(layer)
        self._preview_layer_id = layer.id()

    def _build_detach_widget(self):
        """Return the row that tells where the data of a generated feature comes from.

        A generated feature is one that the stratigraphic column makes. Its
        contact and orientation rows are read-only. The user can add rows to
        them, or detach the feature to keep a fixed copy of the data.
        """
        self.detach_widget = QWidget()
        row = QHBoxLayout(self.detach_widget)
        row.setContentsMargins(0, 0, 0, 0)
        self.detach_label = QLabel()
        self.detach_label.setWordWrap(True)
        self.detach_button = QPushButton()
        self.detach_button.clicked.connect(self._toggle_detached)
        row.addWidget(self.detach_label, 1)
        row.addWidget(self.detach_button)
        self._refresh_detach_widget()
        return self.detach_widget

    def _refresh_detach_widget(self):
        manager = self.model_manager
        name = self.feature.name
        if manager is None or not manager.is_generated(name):
            self.detach_widget.hide()
            return
        self.detach_widget.show()
        if manager.is_detached(name):
            self.detach_label.setText(
                "Detached. The rows from the column are a fixed copy. They do not change "
                "when the column or the contacts change."
            )
            self.detach_button.setText("Follow the column again")
            self.detach_button.setToolTip(
                "Use the data of the stratigraphic column again. The model needs a rebuild."
            )
        else:
            self.detach_label.setText(
                "The read-only rows come from the stratigraphic column. Rows that you "
                "add are used together with them."
            )
            self.detach_button.setText("Detach")
            self.detach_button.setToolTip(
                "Keep a fixed copy of the data of this feature, so that it does not "
                "follow the column."
            )

    def _toggle_detached(self):
        manager = self.model_manager
        name = self.feature.name
        if manager.is_detached(name):
            reply = QMessageBox.question(
                self,
                "Follow the column again",
                f"'{name}' will use the data of the stratigraphic column again. "
                "The fixed copy is removed. Continue?",
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            manager.attach_feature(name)
            push_info("Feature", f"'{name}' follows the stratigraphic column again. Rebuild the model.")
        elif manager.detach_feature(name):
            push_info("Feature", f"'{name}' is detached. Its data is a fixed copy.")
        else:
            QMessageBox.warning(
                self, "Cannot detach", f"'{name}' has no data from the column to keep."
            )
            return
        self.data_manager._sync_processed_feature_data()
        self.layer_table.restore_table_state()
        self._refresh_detach_widget()

    def addMidBlock(self):
        """Base mid block is intentionally empty now — bounding-box controls
        were moved into the export/evaluation section so they appear alongside
        export controls. Subclasses should override this to add feature-specific
        mid-panel controls.
        """
        return

    def addExportBlock(self):
        # Export/Evaluation blocks container
        self.export_eval_container = QWidget()
        self.export_eval_layout = QVBoxLayout(self.export_eval_container)
        self.export_eval_layout.setContentsMargins(0, 0, 0, 0)
        self.export_eval_layout.setSpacing(6)

        # --- Bounding box controls (moved here into dedicated widget) ---
        bb_widget = BoundingBoxWidget(
            parent=self, model_manager=self.model_manager, data_manager=self.data_manager
        )
        # keep reference so export handlers can use it
        self.bounding_box_widget = bb_widget
        self.export_eval_layout.addWidget(bb_widget)

        # --- Per-feature export controls (for this panel's feature) ---
        try:
            from qgis.PyQt.QtWidgets import QFormLayout
        except Exception:
            # imports may fail outside QGIS environment; we'll handle at runtime
            pass

        export_widget = QgsCollapsibleGroupBox('Export Feature')
        export_layout = QFormLayout(export_widget)

        # Scalar selector (support scalar and gradient)
        self.scalar_field_combo = QComboBox()
        self.scalar_field_combo.addItems(["scalar", "gradient"])
        export_layout.addRow("Scalar:", self.scalar_field_combo)

        # Evaluate target: bounding-box centres or project point layer
        self.evaluate_target_combo = QComboBox()
        self.evaluate_target_combo.addItems(
            ["Bounding box cell centres", "Project point layer", "Viewer Object"]
        )
        export_layout.addRow("Evaluate on:", self.evaluate_target_combo)

        # Project layer selector (populated with point vector layers from project)
        self.project_layer_combo = QgsMapLayerComboBox()
        self.project_layer_combo.setEnabled(False)
        # self.project_layer_combo.setFilters(QgsMapLayerComboBox.PointLayer)
        self.project_layer_combo.setVisible(False)  # initially hidden
        self.meshObjectCombo = QComboBox()
        export_layout.addRow("Project point layer:", self.project_layer_combo)
        export_layout.addRow("Viewer object:", self.meshObjectCombo)
        # hide the labels for these rows initially (keep layout spacing until used)
        lbl = export_layout.labelForField(self.project_layer_combo)
        if lbl is not None:
            lbl.setVisible(False)
        lbl = export_layout.labelForField(self.meshObjectCombo)
        if lbl is not None:
            lbl.setVisible(False)

        # Connect evaluate target change to enable/disable project layer combo
        def _on_evaluate_target_changed(index):
            use_project = index == 1
            use_vtk = index == 2
            self.project_layer_combo.setVisible(use_project)
            self.project_layer_combo.setEnabled(use_project)
            self.meshObjectCombo.setVisible(use_vtk)
            self.meshObjectCombo.setEnabled(use_vtk)
            # also hide/show the labels associated with those fields
            lbl = export_layout.labelForField(self.project_layer_combo)
            if lbl is not None:
                lbl.setVisible(use_project)
            lbl = export_layout.labelForField(self.meshObjectCombo)
            if lbl is not None:
                lbl.setVisible(use_vtk)
            if use_vtk:
                # populate with pyvista objects from viewer
                self.meshObjectCombo.clear()
                if self.plugin.loop_widget.visualisation_widget.plotter is not None:
                    viewer = self.plugin.loop_widget.visualisation_widget.plotter
                    mesh_names = list(viewer.meshes.keys())
                    self.meshObjectCombo.addItems(mesh_names)

        self.evaluate_target_combo.currentIndexChanged.connect(_on_evaluate_target_changed)

        # Export button
        self.export_points_button = QPushButton("Export to QGIS points")
        export_layout.addRow(self.export_points_button)
        self.export_points_button.clicked.connect(self._export_scalar_points)

        self.export_eval_layout.addWidget(export_widget)

        # Dictionary to hold per-feature export/eval blocks for later population
        self.export_blocks = {}

        # Create a placeholder block for each feature known to the model_manager.
        # These blocks are intentionally minimal now (only a disabled label) and
        # will be populated with export/evaluate controls later.
        if self.model_manager is not None:
            for feat in self.model_manager.features():
                block = QWidget()
                block.setObjectName(f"export_block_{getattr(feat, 'name', 'feature')}")
                block_layout = QVBoxLayout(block)
                block_layout.setContentsMargins(0, 0, 0, 0)
                self.export_eval_layout.addWidget(block)
                self.export_blocks[getattr(feat, 'name', f"feature_{len(self.export_blocks)}")] = (
                    block
                )

        self.layout.addWidget(self.export_eval_container)

    def _on_bounding_box_updated(self, bounding_box):
        """Callback to update UI widgets when bounding box object changes externally.

        Blocks spinbox signals to avoid feedback loops, updates nelements, nsteps,
        and then restores signals.
        """
        # Collect spinboxes if they exist on this instance
        spinboxes = []
        for name in ('bb_nelements_spinbox', 'bb_nsteps_x', 'bb_nsteps_y', 'bb_nsteps_z'):
            sb = getattr(self, name, None)
            if sb is not None:
                spinboxes.append(sb)

        # Block signals
        for sb in spinboxes:
            try:
                sb.blockSignals(True)
            except Exception:
                pass

        try:
            if getattr(bounding_box, 'nelements', None) is not None and hasattr(
                self, 'bb_nelements_spinbox'
            ):
                try:
                    self.bb_nelements_spinbox.setValue(int(bounding_box.nelements))
                except Exception:
                    try:
                        self.bb_nelements_spinbox.setValue(bounding_box.nelements)
                    except Exception:
                        logger.debug(
                            'Could not set nelements spinbox from bounding_box', exc_info=True
                        )

            if getattr(bounding_box, 'nsteps', None) is not None:
                try:
                    nsteps = list(bounding_box.nsteps)
                except Exception:
                    try:
                        nsteps = [
                            int(bounding_box.nsteps[0]),
                            int(bounding_box.nsteps[1]),
                            int(bounding_box.nsteps[2]),
                        ]
                    except Exception:
                        nsteps = None
                if nsteps is not None:
                    try:
                        if hasattr(self, 'bb_nsteps_x'):
                            self.bb_nsteps_x.setValue(int(nsteps[0]))
                        if hasattr(self, 'bb_nsteps_y'):
                            self.bb_nsteps_y.setValue(int(nsteps[1]))
                        if hasattr(self, 'bb_nsteps_z'):
                            self.bb_nsteps_z.setValue(int(nsteps[2]))
                    except Exception:
                        logger.debug(
                            'Could not set nsteps spinboxes from bounding_box', exc_info=True
                        )

        finally:
            # Unblock signals
            for sb in spinboxes:
                try:
                    sb.blockSignals(False)
                except Exception:
                    pass

    def _has_nelements_override(self):
        """Return True if the user set the number of elements of this feature."""
        manager = self.model_manager
        name = getattr(self.feature, 'name', None)
        return manager is not None and name in getattr(manager, 'nelements_overrides', {})

    def _on_nelements_auto_toggled(self, automatic):
        """Use the automatic number again, or keep the number that is shown."""
        manager = self.model_manager
        name = getattr(self.feature, 'name', None)
        self.n_elements_spinbox.setEnabled(not automatic)
        if manager is None or name is None:
            return
        if automatic:
            manager.set_nelements_override(name, None)
            used = manager.nelements_used.get(name)
            if used is not None:
                self.n_elements_spinbox.blockSignals(True)
                self.n_elements_spinbox.setValue(used[0])
                self.n_elements_spinbox.blockSignals(False)
                self.updateNelements(used[0], keep=False)
        else:
            manager.set_nelements_override(name, int(self.n_elements_spinbox.value()))

    def updateNelements(self, value, keep=True):
        """Update the number of elements in the feature's interpolator.

        With `keep`, the feature keeps this number in the next builds, until
        the user selects "Automatic".
        """
        if keep and self.model_manager is not None and self.feature is not None:
            self.model_manager.set_nelements_override(self.feature.name, int(value))
        if self.feature:
            if issubclass(type(self.feature), StructuralFrame):
                for i in range(3):
                    if self.feature[i].interpolator is not None:
                        self.feature[i].interpolator.nelements = value
                        self.feature[i].builder.update_build_arguments({'nelements': value})
                # schedule a single debounced rebuild after user stops changing value
                self.schedule_rebuild()
            elif self.feature.interpolator is not None:

                self.feature.interpolator.nelements = value
                self.feature.builder.update_build_arguments({'nelements': value})
                # schedule a debounced rebuild instead of building immediately
                self.schedule_rebuild()
        else:
            print("Error: Feature is not initialized.")

    def getNelements(self, feature):
        """Get the number of elements from the feature's interpolator."""
        if feature:
            used = getattr(self.model_manager, 'nelements_used', {}).get(
                getattr(feature, 'name', None)
            )
            if used is not None:
                return used[0]
            if issubclass(type(feature), StructuralFrame):
                return feature[0].interpolator.n_elements
            elif feature.interpolator is not None:
                return feature.interpolator.n_elements
        return 1000

    def _export_scalar_points(self):
        """Gather points (bounding-box centres or project point layer), evaluate feature values
        using the model_manager and add the resulting GeoDataFrame as a memory layer to the
        QGIS project. Imports and QGIS calls are guarded so the module can be imported
        outside of QGIS.
        """
        # determine scalar type
        logger.info('Exporting scalar points')
        scalar_type = (
            self.scalar_field_combo.currentText()
            if hasattr(self, 'scalar_field_combo')
            else 'scalar'
        )

        # gather points
        pts = None
        attributes_df = None
        crs = self.data_manager.project.crs().authid()
        try:
            # QGIS imports (guarded)
            from qgis.core import QgsFeature, QgsField, QgsPoint, QgsProject, QgsVectorLayer

            from loopstructural.gui.compatibility import QVariantCompat
        except Exception as e:
            # Not running inside QGIS — nothing to do
            logger.info('Not running inside QGIS, cannot export points')
            print(e)
            return

        # Evaluate on bounding box grid
        if self.evaluate_target_combo.currentIndex() == 0:
            # use bounding-box resolution or custom nsteps
            logger.info('Using bounding box cell centres for evaluation')

            pts = self.model_manager.model.bounding_box.cell_centres()
            # no extra attributes for grid
            attributes_df = None
            logger.info(f'Got {len(pts)} points from bounding box cell centres')
        elif self.evaluate_target_combo.currentIndex() == 1:
            # Evaluate on an existing project point layer
            layer_id = None
            try:
                layer_id = self.project_layer_combo.currentData()
            except Exception:
                layer_id = None
            if layer_id is None:
                return
            layer = QgsProject.instance().mapLayer(layer_id)
            if layer is None:
                return
            # build points array and attributes
            pts_list = []
            attrs = []
            fields = [f.name() for f in layer.fields()]
            for feat in layer.getFeatures():
                try:
                    geom = feat.geometry()
                    if geom is None or geom.isEmpty():
                        continue
                    # handle point geometries
                    if geom.type() == 0:  # QgsWkbTypes.PointGeometry -> numeric value 0
                        try:
                            p = geom.asPoint()
                            x, y = p.x(), p.y()
                            # some QgsPoint has z attribute
                            try:
                                z = p.z()
                            except Exception:
                                z = (
                                    self.model_manager.dem_function(x, y)
                                    if hasattr(self.model_manager, 'dem_function')
                                    else 0
                                )
                        except Exception:
                            # fallback to centroid
                            try:
                                c = geom.centroid().asPoint()
                                x, y = c.x(), c.y()
                                z = (
                                    self.model_manager.dem_function(x, y)
                                    if hasattr(self.model_manager, 'dem_function')
                                    else 0
                                )
                            except Exception:
                                continue
                        pts_list.append((x, y, z))
                        # collect attributes
                        row = {k: feat[k] for k in fields}
                        attrs.append(row)
                    else:
                        # skip non-point geometries
                        continue
                except Exception:
                    continue
            if len(pts_list) == 0:
                return
            import pandas as _pd

            pts = _pd.DataFrame(pts_list).values
            try:
                attributes_df = _pd.DataFrame(attrs)
            except Exception:
                attributes_df = None
            try:
                crs = layer.crs().authid()
            except Exception:
                crs = None
        elif self.evaluate_target_combo.currentIndex() == 2:
            # Evaluate on an object from the viewer
            # These are all pyvista objects and we want to add
            # the scalar as a new field to the objects

            viewer = self.plugin.loop_widget.visualisation_widget.plotter
            if viewer is None:
                return
            mesh = self.meshObjectCombo.currentText()
            if not mesh:
                return
            vtk_mesh = viewer.meshes[mesh]['mesh']
            self.model_manager.export_feature_values_to_vtk_mesh(
                self.feature.name, vtk_mesh, scalar_type=scalar_type
            )
        # call model_manager to produce GeoDataFrame
        try:
            logger.info('Exporting feature values to GeoDataFrame')
            gdf = self.model_manager.export_feature_values_to_geodataframe(
                self.feature.name,
                pts,
                scalar_type=scalar_type,
                attributes=attributes_df,
                crs=crs,
            )
        except Exception:
            logger.debug('Failed to export feature values', exc_info=True)
            return

        # convert returned GeoDataFrame to a QGIS memory layer and add to project
        if gdf is None or len(gdf) == 0:
            return

        # create memory layer
        # derive CRS string if available
        layer_uri = 'Point'
        if hasattr(gdf, 'crs') and gdf.crs is not None:
            try:
                crs_str = gdf.crs.to_string()
                if crs_str:
                    layer_uri = f"Point?crs={crs_str}"
            except Exception:
                pass
        mem_layer = QgsVectorLayer(layer_uri, f"model_{self.feature.name}", 'memory')
        prov = mem_layer.dataProvider()

        # add fields
        cols = [c for c in gdf.columns if c != 'geometry']
        qfields = []
        for c in cols:
            sample = gdf[c].dropna()
            qtype = QVariantCompat.String
            if not sample.empty:
                v = sample.iloc[0]
                if isinstance(v, (int,)):
                    qtype = QVariantCompat.Int
                elif isinstance(v, (float,)):
                    qtype = QVariantCompat.Double
                else:
                    qtype = QVariantCompat.String
            prov.addAttributes([QgsField(c, qtype)])
            qfields.append(c)
        mem_layer.updateFields()

        # add features
        feats = []
        for _, row in gdf.reset_index(drop=True).iterrows():
            f = QgsFeature()
            # set attributes in provider order
            attr_vals = [row.get(c) for c in qfields]
            try:
                f.setAttributes(attr_vals)
            except Exception:
                pass
            # geometry
            try:
                geom = row.get('geometry')
                if geom is not None:
                    # try to extract x,y,z from shapely Point
                    try:
                        x, y = geom.x, geom.y
                        z = geom.z if hasattr(geom, 'z') else None
                        if z is None:
                            qgsp = QgsPoint(x, y, 0)
                        else:
                            qgsp = QgsPoint(x, y, z)
                        f.setGeometry(qgsp)
                    except Exception:
                        # fallback: skip geometry
                        pass
            except Exception:
                pass
            feats.append(f)
        if feats:
            prov.addFeatures(feats)
            mem_layer.updateExtents()
            QgsProject.instance().addMapLayer(mem_layer)

    def _collect_builder_dataframes(self):
        """Collect the raw constraint dataframe(s) actually being used by this
        feature's interpolator.

        This reads straight from `feature.builder.data`, so it reflects the
        data regardless of how it got there -- either picked layer-by-layer
        through the "Data Layers" table above (backed by
        `data_manager.feature_data`), or ingested in bulk by the automated
        data-processing workflow (map2loop tools), which writes directly into
        the builder and never touches `data_manager.feature_data`, leaving
        that table empty even though the interpolator has data.
        """
        builder = getattr(self.feature, 'builder', None)
        if builder is None:
            return []
        # Structural frames (faults, folded frames) wrap three per-coordinate
        # builders, each with its own `.data`; the frame builder's own
        # `.data` attribute is just a `[[], [], []]` placeholder.
        sub_builders = getattr(builder, 'builders', None)
        if sub_builders:
            frames = []
            for i, sub in enumerate(sub_builders):
                data = getattr(sub, 'data', None)
                if data is not None and hasattr(data, 'empty') and not data.empty:
                    data = data.copy()
                    if 'coord' not in data.columns:
                        data['coord'] = i
                    frames.append(data)
            return frames
        data = getattr(builder, 'data', None)
        if data is not None and hasattr(data, 'empty') and not data.empty:
            return [data.copy()]
        return []

    def _show_constraint_data_on_map(self):
        """Add the interpolator's raw constraint data as a temporary (memory)
        QGIS point layer, so the user can visually check what's actually
        being fitted -- particularly useful when the data came from the
        automated data-processing workflow and so isn't listed in the "Data
        Layers" table above. The layer is a plain memory layer, not linked
        back to any source layer or object.
        """
        try:
            from qgis.core import QgsFeature, QgsField, QgsPoint, QgsProject, QgsVectorLayer

            from loopstructural.gui.compatibility import QVariantCompat
        except Exception:
            logger.info('Not running inside QGIS, cannot show constraint data')
            return

        frames = self._collect_builder_dataframes()
        if not frames:
            QMessageBox.information(
                self, "No data", "No interpolator constraint data found for this feature."
            )
            return

        import numpy as np
        import pandas as pd

        combined = pd.concat(frames, ignore_index=True)
        combined = combined.dropna(axis=1, how='all')
        if combined.empty or not {'X', 'Y'}.issubset(combined.columns):
            QMessageBox.information(
                self, "No data", "No interpolator constraint data found for this feature."
            )
            return

        # derive strike/dip from normal vectors where available, for readability
        if {'nx', 'ny', 'nz'}.issubset(combined.columns):
            try:
                mask = combined[['nx', 'ny', 'nz']].notna().all(axis=1)
                if mask.any():
                    sd = normal_vector_to_strike_and_dip(
                        combined.loc[mask, ['nx', 'ny', 'nz']].to_numpy(float)
                    )
                    combined.loc[mask, 'strike'] = sd[:, 0]
                    combined.loc[mask, 'dip'] = sd[:, 1]
            except Exception:
                logger.debug('Could not derive strike/dip from normal vectors', exc_info=True)

        crs = self.data_manager.get_model_crs() if self.data_manager else None
        layer_uri = 'PointZ'
        if crs is not None and crs.isValid():
            layer_uri = f"PointZ?crs={crs.authid()}"
        mem_layer = QgsVectorLayer(layer_uri, f"{self.feature.name} constraint data", 'memory')
        prov = mem_layer.dataProvider()

        attr_cols = [c for c in combined.columns if c not in ('X', 'Y', 'Z')]
        qfields = []
        for c in attr_cols:
            sample = combined[c].dropna()
            qtype = QVariantCompat.String
            if not sample.empty:
                v = sample.iloc[0]
                if isinstance(v, (bool, np.bool_)):
                    qtype = QVariantCompat.Bool
                elif isinstance(v, (int, np.integer)):
                    qtype = QVariantCompat.Int
                elif isinstance(v, (float, np.floating)):
                    qtype = QVariantCompat.Double
            prov.addAttributes([QgsField(str(c), qtype)])
            qfields.append(c)
        mem_layer.updateFields()

        feats = []
        for _, row in combined.iterrows():
            x_val, y_val = row.get('X'), row.get('Y')
            if x_val is None or y_val is None or pd.isna(x_val) or pd.isna(y_val):
                continue
            try:
                x, y = float(x_val), float(y_val)
                z_val = row.get('Z')
                z = 0.0 if z_val is None or pd.isna(z_val) else float(z_val)
            except (TypeError, ValueError):
                continue
            f = QgsFeature()
            try:
                f.setAttributes([row.get(c) for c in qfields])
            except Exception:
                pass
            f.setGeometry(QgsPoint(x, y, z))
            feats.append(f)

        if not feats:
            QMessageBox.information(
                self, "No data", "No interpolator constraint data found for this feature."
            )
            return
        prov.addFeatures(feats)
        mem_layer.updateExtents()
        QgsProject.instance().addMapLayer(mem_layer)

    def schedule_rebuild(self):
        """Flag the current feature as not up to date, without solving it.

        Callers are expected to have already flagged the feature's builder as
        not up to date (either via `update_build_arguments`, which does this
        itself, or by calling `builder.set_not_up_to_date(...)` directly).
        This just notifies observers -- on the GUI thread, since this is only
        ever called from a widget's valueChanged handler -- so the feature
        list's tick flips to "not built" right away. It deliberately does not
        trigger an actual rebuild/solve: that stays a user-initiated action
        (e.g. the "Solve Model" button), since re-solving can be expensive and
        the user may still be adjusting other parameters.
        """
        if self.model_manager is not None:
            try:
                self.model_manager.notify('model_updated')
            except Exception:
                for obs in getattr(self.model_manager, 'observers', []):
                    try:
                        obs()
                    except Exception:
                        pass
