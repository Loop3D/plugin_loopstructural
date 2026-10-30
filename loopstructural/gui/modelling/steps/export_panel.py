"""The export panel of step 5: surfaces, block model and cross-sections."""

from pathlib import Path

import numpy as np
from qgis.core import QgsMapLayerProxyModel
from qgis.gui import QgsCollapsibleGroupBox, QgsFileWidget, QgsMapLayerComboBox
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from loopstructural.main import model_export
from loopstructural.main.geoviewer import scene as geoviewer_scene
from loopstructural.main.geoviewer.link import DEFAULT_PORT, GeoViewerLink, LinkError
from loopstructural.toolbelt.preferences import PlgOptionsManager

from ...background_task import finish_background_task, start_background_task
from ...compatibility import configure_layer_combo
from ...messages import push_success
from ...visualisation.line_layer import line_xy_from_layer


def _format_combo(parent, formats):
    combo = QComboBox(parent)
    for extension, label in formats.items():
        combo.addItem(label, extension)
    return combo


def _spin(parent, value, minimum=1, maximum=2000):
    spin = QSpinBox(parent)
    spin.setRange(minimum, maximum)
    spin.setValue(value)
    return spin


def _double_spin(parent, value=0.0):
    spin = QDoubleSpinBox(parent)
    spin.setRange(-1e9, 1e9)
    spin.setDecimals(3)
    spin.setValue(value)
    return spin


class ExportPanel(QgsCollapsibleGroupBox):
    """Write the results of a solved model to files.

    The exports run on a background task. The panel is enabled when the model
    is solved (see `set_model_solved`).
    """

    def __init__(self, parent=None, *, model_manager=None, data_manager=None):
        super().__init__("Export", parent)
        self.model_manager = model_manager
        self.data_manager = data_manager
        self._task = None  # (thread, worker, progress dialog) of the run
        self._model_solved = False
        self._plane_defaults = None  # the plane values set from the last bounding box

        layout = QVBoxLayout(self)
        self.hint = QLabel(self)
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)
        self.tabs = QTabWidget(self)
        self.tabs.addTab(self._surfaces_tab(), "Surfaces")
        self.tabs.addTab(self._block_model_tab(), "Block model")
        self.tabs.addTab(self._cross_section_tab(), "Cross-section")
        self.tabs.addTab(self._geoviewer_tab(), "GeoViewer")
        layout.addWidget(self.tabs)
        self.set_model_solved(False)
        self.setCollapsed(True)

    # -- tabs ---------------------------------------------------------------

    def _surfaces_tab(self):
        tab = QWidget(self)
        form = QFormLayout(tab)
        self.surface_format = _format_combo(tab, model_export.SURFACE_FORMATS)
        self.surface_strat = QCheckBox("Stratigraphic surfaces", tab)
        self.surface_strat.setChecked(True)
        self.surface_faults = QCheckBox("Fault surfaces", tab)
        self.surface_faults.setChecked(True)
        self.surface_folder = QgsFileWidget(tab)
        self.surface_folder.setStorageMode(QgsFileWidget.StorageMode.GetDirectory)
        self.surface_button = QPushButton("Export surfaces", tab)
        self.surface_button.clicked.connect(self.export_surfaces)
        form.addRow("Format", self.surface_format)
        form.addRow(self.surface_strat)
        form.addRow(self.surface_faults)
        form.addRow("Folder", self.surface_folder)
        form.addRow(self.surface_button)
        return tab

    def _block_model_tab(self):
        tab = QWidget(self)
        form = QFormLayout(tab)
        self.block_format = _format_combo(tab, model_export.BLOCK_MODEL_FORMATS)
        self.block_nx = _spin(tab, 50)
        self.block_ny = _spin(tab, 50)
        self.block_nz = _spin(tab, 25)
        self.block_file = QgsFileWidget(tab)
        self.block_file.setStorageMode(QgsFileWidget.StorageMode.SaveFile)
        self.block_button = QPushButton("Export block model", tab)
        self.block_button.clicked.connect(self.export_block_model)
        form.addRow("Format", self.block_format)
        form.addRow("Cells in X", self.block_nx)
        form.addRow("Cells in Y", self.block_ny)
        form.addRow("Cells in Z", self.block_nz)
        form.addRow("File", self.block_file)
        form.addRow(self.block_button)
        return tab

    def _cross_section_tab(self):
        tab = QWidget(self)
        form = QFormLayout(tab)
        self.section_format = _format_combo(tab, model_export.CROSS_SECTION_FORMATS)
        self.section_kind = QComboBox(tab)
        self.section_kind.addItem("Vertical section under a line layer", 'line')
        self.section_kind.addItem("Plane (origin and normal)", 'plane')
        self.section_kind.currentIndexChanged.connect(self._update_section_inputs)
        self.section_line = QgsMapLayerComboBox(tab)
        configure_layer_combo(self.section_line, QgsMapLayerProxyModel.Filter.LineLayer)
        self.section_origin = [_double_spin(tab) for _ in range(3)]
        self.section_normal = [_double_spin(tab, v) for v in (1.0, 0.0, 0.0)]
        self.section_size = _double_spin(tab, 1000.0)
        self.section_resolution = _spin(tab, 100)
        self.section_file = QgsFileWidget(tab)
        self.section_file.setStorageMode(QgsFileWidget.StorageMode.SaveFile)
        self.section_button = QPushButton("Export cross-section", tab)
        self.section_button.clicked.connect(self.export_cross_section)
        form.addRow("Format", self.section_format)
        form.addRow("Type", self.section_kind)
        form.addRow("Line layer", self.section_line)
        for label, widgets in (("Origin", self.section_origin), ("Normal", self.section_normal)):
            for axis, widget in zip("XYZ", widgets):
                form.addRow(f"{label} {axis}", widget)
        form.addRow("Plane size", self.section_size)
        form.addRow("Resolution", self.section_resolution)
        form.addRow("File", self.section_file)
        form.addRow(self.section_button)
        self._section_plane_rows = self.section_origin + self.section_normal + [self.section_size]
        self._section_form = form
        self._update_section_inputs()
        return tab

    def _geoviewer_tab(self):
        tab = QWidget(self)
        form = QFormLayout(tab)
        note = QLabel(
            "Send the surfaces of the model to GeoViewer, the advanced 3D viewer. "
            "Start GeoViewer first, and copy the port and the token from its link popup. "
            "A new push replaces the surfaces of the last push.",
            tab,
        )
        note.setWordWrap(True)
        self.geoviewer_port = _spin(tab, DEFAULT_PORT, minimum=1, maximum=65535)
        self.geoviewer_token = QLineEdit(tab)
        self.geoviewer_token.setEchoMode(QLineEdit.EchoMode.Password)
        self.geoviewer_stratigraphy = QCheckBox("Stratigraphic surfaces", tab)
        self.geoviewer_stratigraphy.setChecked(True)
        self.geoviewer_faults = QCheckBox("Fault surfaces", tab)
        self.geoviewer_faults.setChecked(True)
        self.geoviewer_button = QPushButton("Push model to GeoViewer", tab)
        self.geoviewer_button.clicked.connect(self.push_to_geoviewer)
        self._load_geoviewer_settings()
        form.addRow(note)
        form.addRow("Port", self.geoviewer_port)
        form.addRow("Token", self.geoviewer_token)
        form.addRow(self.geoviewer_stratigraphy)
        form.addRow(self.geoviewer_faults)
        form.addRow(self.geoviewer_button)
        return tab

    def _load_geoviewer_settings(self):
        port = PlgOptionsManager.get_value_from_key('geoviewer_port', DEFAULT_PORT, int)
        token = PlgOptionsManager.get_value_from_key('geoviewer_token', '', str)
        self.geoviewer_port.setValue(int(port or DEFAULT_PORT))
        self.geoviewer_token.setText(token or '')

    def _update_section_inputs(self, *_args):
        is_line = self.section_kind.currentData() == 'line'
        self.section_line.setVisible(is_line)
        self._section_form.labelForField(self.section_line).setVisible(is_line)
        for widget in self._section_plane_rows:
            widget.setVisible(not is_line)
            self._section_form.labelForField(widget).setVisible(not is_line)

    # -- state --------------------------------------------------------------

    def set_model_solved(self, solved):
        """Enable the exports when the model is solved."""
        self._model_solved = bool(solved)
        self.hint.setText(
            "Write the results of the model to files."
            if solved
            else "Build the model in step 4 to export its results."
        )
        for tab_index in range(self.tabs.count()):
            self.tabs.widget(tab_index).setEnabled(self._model_solved and self._task is None)
        # A model of faults only has no units: no stratigraphic surfaces, no block model
        has_units = not solved or self._has_stratigraphic_features()
        if has_units and not self.surface_strat.isEnabled():
            self.surface_strat.setChecked(True)
        self.surface_strat.setEnabled(has_units)
        if not has_units:
            self.surface_strat.setChecked(False)
        self.tabs.setTabEnabled(1, has_units)
        if not has_units:
            self.hint.setText("The model has faults only, so the block model is not offered.")
        if self._model_solved:
            self._set_plane_defaults()

    def _has_stratigraphic_features(self):
        """Return False if every feature of the model is a fault."""
        manager = self.model_manager
        if manager is None:
            return True
        faults = set(getattr(manager, 'faults', {}) or {}) | set(
            getattr(manager, 'parametric_faults', {}) or {}
        )
        names = [f.name for f in manager.features() if not f.name.startswith('__')]
        return any(name not in faults for name in names)

    def _plane_values(self):
        return tuple(w.value() for w in self.section_origin) + (self.section_size.value(),)

    def _set_plane_defaults(self):
        """Put the plane at the centre of the bounding box, with the size of its diagonal.

        The values change only if the user did not edit them since the last time.
        """
        model = getattr(self.model_manager, 'model', None)
        bounding_box = getattr(model, 'bounding_box', None)
        if bounding_box is None:
            return
        try:
            origin = np.asarray(bounding_box.origin, dtype=float)
            maximum = np.asarray(bounding_box.maximum, dtype=float)
        except (TypeError, ValueError):
            return
        current = self._plane_values()
        initial = (0.0, 0.0, 0.0, 1000.0)
        if current != initial and current != self._plane_defaults:
            return
        for widget, value in zip(self.section_origin, (origin + maximum) / 2.0):
            widget.setValue(float(value))
        self.section_size.setValue(float(np.linalg.norm(maximum - origin)))
        self._plane_defaults = self._plane_values()

    # -- actions ------------------------------------------------------------

    def _with_extension(self, file_widget, format_combo):
        """Return the output path with the extension of the format, or None.

        None means that the path is empty, or that the user does not want to
        overwrite the file. The file dialog asks about the name that the user
        selected, so ask again if the extension changes the name.
        """
        text = file_widget.filePath().strip()
        if not text:
            self._warn("Select a file.")
            return None
        path = Path(text).with_suffix(format_combo.currentData())
        if path != Path(text) and path.exists() and not self._confirm_overwrite([path]):
            return None
        return path

    def _confirm_overwrite(self, paths):
        names = "\n".join(p.name for p in paths[:10])
        if len(paths) > 10:
            names += f"\n... and {len(paths) - 10} more"
        answer = QMessageBox.question(
            self,
            "Export",
            f"These files exist and the export will overwrite them:\n\n{names}\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def _warn(self, text):
        QMessageBox.warning(self, "Export", text)

    def push_to_geoviewer(self):
        """Send the surfaces of the model to a running GeoViewer. The model does not change."""
        strat = self.geoviewer_stratigraphy.isChecked()
        faults = self.geoviewer_faults.isChecked()
        if not (strat or faults):
            return self._warn("Select the stratigraphic surfaces, the fault surfaces, or both.")
        port, token = self.geoviewer_port.value(), self.geoviewer_token.text().strip()
        PlgOptionsManager.set_value_from_key('geoviewer_port', port)
        PlgOptionsManager.set_value_from_key('geoviewer_token', token)
        manager = self.model_manager
        crs = self.data_manager.get_model_crs() if self.data_manager else None
        crs_text = crs.authid() if crs is not None and crs.isValid() else ''

        def target(progress):
            model = getattr(manager, 'model', None)
            if model is None:
                raise geoviewer_scene.PushError("Build the model in step 4 first.")
            try:
                result = GeoViewerLink(port, token).push(
                    crs_text,
                    geoviewer_scene.proposed_origin(model),
                    lambda origin: geoviewer_scene.model_messages(
                        manager, origin, stratigraphic=strat, faults=faults, progress=progress
                    ),
                    replace_prefix=geoviewer_scene.ID_PREFIX,
                    progress=progress,
                )
            except (LinkError, geoviewer_scene.PushError) as error:
                raise RuntimeError(str(error)) from error
            if result.refused or result.other_errors:
                details = "; ".join(text for _id, text in result.refused) or "; ".join(
                    result.other_errors
                )
                return f"{result.summary()} {details}"
            return result.summary()

        self._run(target, "Push model to GeoViewer")

    def export_surfaces(self):
        folder = self.surface_folder.filePath().strip()
        if not folder:
            return self._warn("Select a folder for the surfaces.")
        if not (self.surface_strat.isChecked() or self.surface_faults.isChecked()):
            return self._warn("Select the stratigraphic surfaces, the fault surfaces, or both.")
        extension = self.surface_format.currentData()
        existing = model_export.existing_surface_files(folder, extension)
        if existing and not self._confirm_overwrite(existing):
            return
        strat, faults = self.surface_strat.isChecked(), self.surface_faults.isChecked()

        def target(progress):
            files = model_export.export_surfaces(
                self.model_manager,
                folder,
                extension,
                stratigraphic=strat,
                faults=faults,
                progress=progress,
            )
            return f"{len(files)} surfaces written to {folder}"

        self._run(target, "Export surfaces")

    def export_block_model(self):
        path = self._with_extension(self.block_file, self.block_format)
        if path is None:
            return
        ncells = (self.block_nx.value(), self.block_ny.value(), self.block_nz.value())

        def target(progress):
            model_export.export_block_model(self.model_manager, path, ncells, progress=progress)
            return f"Block model written to {path}"

        self._run(target, "Export block model")

    def export_cross_section(self):
        path = self._with_extension(self.section_file, self.section_format)
        if path is None:
            return
        resolution = self.section_resolution.value()
        if self.section_kind.currentData() == 'line':
            layer = self.section_line.currentLayer()
            if layer is None:
                return self._warn("Select a line layer.")
            target_crs = self.data_manager.get_model_crs() if self.data_manager else None
            line_xy = line_xy_from_layer(layer, target_crs)
            if line_xy is None:
                return self._warn("The line layer has no usable line.")
            options = {'line_xy': line_xy, 'z_resolution': resolution}
        else:
            options = {
                'origin': [w.value() for w in self.section_origin],
                'normal': [w.value() for w in self.section_normal],
                'size': self.section_size.value(),
            }

        def target(progress):
            model_export.export_cross_section(
                self.model_manager, path, resolution=resolution, progress=progress, **options
            )
            return f"Cross-section written to {path}"

        self._run(target, "Export cross-section")

    # -- background task ----------------------------------------------------

    def _run(self, target, title):
        if not self._model_solved or self._task is not None:
            return
        self._task = start_background_task(
            self,
            target,
            title=title,
            initial_label=f"{title}...",
            on_progress=self._on_progress,
            on_finished=self._on_finished,
            on_error=self._on_error,
            # block the dock (and Build) while the export reads the model
            modal=True,
        )
        self.set_model_solved(self._model_solved)

    def _end_task(self):
        if self._task is not None:
            finish_background_task(*self._task)
            self._task = None
        self.set_model_solved(self._model_solved)

    def _on_progress(self, message):
        try:
            self._task[2].setLabelText(message)
        except Exception:
            pass

    def _on_finished(self, message):
        self._end_task()
        push_success("Export", message)

    def _on_error(self, traceback_text):
        self._end_task()
        reason = traceback_text.strip().splitlines()[-1] if traceback_text.strip() else "unknown"
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Critical)
        box.setWindowTitle("Export failed")
        box.setText(reason)
        box.setDetailedText(traceback_text)
        box.exec()
