"""Widget for extracting basal contacts."""

import os

from qgis.core import QgsMapLayerProxyModel, QgsProject, QgsVectorFileWriter
from qgis.PyQt import uic
from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtWidgets import QMessageBox, QWidget

from ...main.helpers import ColumnMatcher, get_layer_names
from ...main.m2l_api import extract_basal_contacts
from ...main.vectorLayerWrapper import addGeoDataFrameToproject
from ..background_task import finish_background_task, start_background_task
from ..compatibility import configure_layer_combo


class BasalContactsWidget(QWidget):
    """Widget for configuring and running the basal contacts extractor.

    This widget provides a GUI interface for extracting basal contacts
    from geology layers.
    """

    # See sampler_widget.SamplerWidget for why these exist: _run_extractor
    # now starts a background task instead of returning True/False, so the
    # embedding dialog (map2loop_tools/dialogs.py) waits for these instead.
    task_succeeded = pyqtSignal()
    task_failed = pyqtSignal()

    def __init__(self, parent=None, data_manager=None, debug_manager=None):
        """Initialize the basal contacts widget.

        Parameters
        ----------
        parent : QWidget, optional
            Parent widget.
        data_manager : object, optional
            Data manager for accessing shared data.
        """
        super().__init__(parent)
        self.data_manager = data_manager
        self._debug = debug_manager

        # Load the UI file
        ui_path = os.path.join(os.path.dirname(__file__), "basal_contacts_widget.ui")
        uic.loadUi(ui_path, self)

        # Move layer filter setup out of the .ui (QgsMapLayerProxyModel values in .ui
        # can cause import errors outside QGIS). Set filters programmatically
        # and preserve the allowEmptyLayer setting for the faults combobox.
        # geology layer should only show polygon layers
        configure_layer_combo(self.geologyLayerComboBox, QgsMapLayerProxyModel.PolygonLayer)
        # faults should show line layers and allow empty selection (as set in .ui)
        configure_layer_combo(
            self.faultsLayerComboBox, QgsMapLayerProxyModel.LineLayer, allow_empty=True
        )

        # Connect signals
        self.geologyLayerComboBox.layerChanged.connect(self._on_geology_layer_changed)
        self.runButton.clicked.connect(self._run_extractor)
        self._guess_layers()
        # Set up field combo boxes
        self._setup_field_combo_boxes()
        self._restore_selection()

    def set_debug_manager(self, debug_manager):
        """Attach a debug manager instance."""
        self._debug = debug_manager

    def _export_layer_for_debug(self, layer, name_prefix: str):
        if not (self._debug and self._debug.is_debug()):
            return None
        try:
            debug_dir = self._debug.get_effective_debug_dir()
            out_path = debug_dir / f"{name_prefix}.gpkg"
            options = QgsVectorFileWriter.SaveVectorOptions()
            options.driverName = "GPKG"
            options.layerName = layer.name()
            res = QgsVectorFileWriter.writeAsVectorFormatV3(
                layer,
                str(out_path),
                QgsProject.instance().transformContext(),
                options,
            )
            if res[0] == QgsVectorFileWriter.NoError:
                return str(out_path)
        except Exception as err:
            self._debug.plugin.log(
                message=f"[map2loop] Failed to export layer '{name_prefix}': {err}",
                log_level=2,
            )
        return None

    def _serialize_layer(self, layer, name_prefix: str):
        try:
            export_path = self._export_layer_for_debug(layer, name_prefix)
            return {
                "name": layer.name(),
                "id": layer.id(),
                "provider": layer.providerType() if hasattr(layer, "providerType") else None,
                "source": layer.source() if hasattr(layer, "source") else None,
                "export_path": export_path,
            }
        except Exception:
            return str(layer)

    def _serialize_params_for_logging(self, params, context_label: str):
        serialized = {}
        for key, value in params.items():
            if hasattr(value, "source") or hasattr(value, "id"):
                serialized[key] = self._serialize_layer(value, f"{context_label}_{key}")
            else:
                serialized[key] = value
        return serialized

    def _log_params(self, context_label: str):
        if getattr(self, "_debug", None):
            try:
                self._debug.log_params(
                    context_label=context_label,
                    params=self._serialize_params_for_logging(self.get_parameters(), context_label),
                )
            except Exception:
                pass

    def _guess_layers(self):
        """Attempt to auto-select layers based on common naming conventions."""
        if not self.data_manager:
            return

        # Attempt to find geology layer
        geology_layer_names = get_layer_names(self.geologyLayerComboBox)
        geology_matcher = ColumnMatcher(geology_layer_names)
        geology_layer_match = geology_matcher.find_match('GEOLOGY')
        if geology_layer_match:
            geology_layer = self.data_manager.find_layer_by_name(geology_layer_match)
            self.geologyLayerComboBox.setLayer(geology_layer)

        # Attempt to find faults layer
        fault_layer_names = get_layer_names(self.faultsLayerComboBox)
        fault_layer_matcher = ColumnMatcher(fault_layer_names)
        fault_layer_match = fault_layer_matcher.find_match('FAULTS')
        if fault_layer_match:
            faults_layer = self.data_manager.find_layer_by_name(fault_layer_match)
            self.faultsLayerComboBox.setLayer(faults_layer)

    def _restore_selection(self):
        """Restore persisted selections from data manager."""
        if not self.data_manager:
            return
        settings = self.data_manager.get_widget_settings('basal_contacts_widget', {})
        if not settings:
            return
        if layer_name := settings.get('geology_layer'):
            layer = self.data_manager.find_layer_by_name(layer_name)
            if layer:
                self.geologyLayerComboBox.setLayer(layer)
        if layer_name := settings.get('faults_layer'):
            layer = self.data_manager.find_layer_by_name(layer_name)
            if layer:
                self.faultsLayerComboBox.setLayer(layer)
        if field := settings.get('unit_name_field'):
            self.unitNameFieldComboBox.setField(field)

    def _persist_selection(self):
        """Persist current selections into data manager."""
        if not self.data_manager:
            return
        settings = {
            'geology_layer': (
                self.geologyLayerComboBox.currentLayer().name()
                if self.geologyLayerComboBox.currentLayer()
                else None
            ),
            'faults_layer': (
                self.faultsLayerComboBox.currentLayer().name()
                if self.faultsLayerComboBox.currentLayer()
                else None
            ),
            'unit_name_field': self.unitNameFieldComboBox.currentField(),
        }
        self.data_manager.set_widget_settings('basal_contacts_widget', settings)

    def _setup_field_combo_boxes(self):
        """Set up field combo boxes to link to their respective layers."""
        geology = self.geologyLayerComboBox.currentLayer()
        if geology is not None:
            self.unitNameFieldComboBox.setLayer(geology)
        else:
            # Ensure combo boxes are cleared if no geology layer selected
            self.unitNameFieldComboBox.setLayer(None)

    def _on_geology_layer_changed(self):
        """Update field combo boxes when geology layer changes."""
        from ...main.helpers import ColumnMatcher

        layer = self.geologyLayerComboBox.currentLayer()
        self.unitNameFieldComboBox.setLayer(layer)

        # Auto-detect appropriate fields
        if layer:
            fields = [field.name() for field in layer.fields()]
            matcher = ColumnMatcher(fields)

            # Auto-select UNITNAME field
            if unit_match := matcher.find_match('UNITNAME'):
                self.unitNameFieldComboBox.setField(unit_match)

    def _run_extractor(self):
        """Validate inputs and start basal contacts extraction on a background thread.

        See SamplerWidget._run_sampler for the general shape of this
        pattern: returns False immediately on synchronous validation
        failure (dialog stays open); once validation passes, starts the
        actual map2loop call on a background QThread and returns None (the
        embedding dialog waits for task_succeeded/task_failed instead).
        """
        self._log_params("basal_contacts_widget_run")

        self._persist_selection()
        # Validate inputs
        if not self.geologyLayerComboBox.currentLayer():
            QMessageBox.warning(self, "Missing Input", "Please select a geology layer.")
            return False

        target = self._make_extract_contacts_target()

        self.setEnabled(False)
        self._extractor_thread, self._extractor_worker, self._extractor_progress = (
            start_background_task(
                self,
                target,
                title="Extracting",
                initial_label="Extracting basal contacts...",
                on_progress=self._on_extractor_progress,
                on_finished=self._on_extractor_finished,
                on_error=self._on_extractor_error,
            )
        )
        return None

    def _on_extractor_progress(self, message):
        try:
            self._extractor_progress.setLabelText(message)
        except Exception:
            pass

    def _on_extractor_finished(self, payload):
        result, all_contacts = payload
        finish_background_task(
            self._extractor_thread, self._extractor_worker, self._extractor_progress
        )
        self.setEnabled(True)

        self.data_manager.logger(f'All contacts extracted: {all_contacts}')
        contact_type = "basal contacts"
        if result:
            if all_contacts and result['all_contacts'].empty is False:
                addGeoDataFrameToproject(result['all_contacts'], "All contacts")
                contact_type = "all contacts and basal contacts"
            elif not all_contacts and result['basal_contacts'].empty is False:
                basal_layer = addGeoDataFrameToproject(result['basal_contacts'], "Basal contacts")
                if self.data_manager:
                    self.data_manager.apply_stratigraphic_colours_to_layer(
                        basal_layer, 'basal_unit'
                    )
            else:
                QMessageBox.information(
                    self,
                    "No Contacts Found",
                    "No contacts were found with the given parameters.",
                )
            QMessageBox.information(
                self,
                "Success",
                f"Successfully extracted {contact_type}!",
            )
            if self._debug and self._debug.is_debug():
                try:
                    self._debug.save_debug_file(
                        "basal_contacts_result.txt", str(result).encode("utf-8")
                    )
                except Exception as err:
                    self._debug.plugin.log(
                        message=f"[map2loop] Failed to save basal contacts debug output: {err}",
                        log_level=2,
                    )
            self.task_succeeded.emit()
        else:
            self.task_failed.emit()

    def _on_extractor_error(self, traceback_text):
        finish_background_task(
            self._extractor_thread, self._extractor_worker, self._extractor_progress
        )
        self.setEnabled(True)
        if self._debug:
            self._debug.plugin.log(
                message=f"[map2loop] Basal contacts extraction failed:\n{traceback_text}",
                log_level=2,
            )
            QMessageBox.critical(self, "Error", traceback_text)
        else:
            summary = (
                traceback_text.strip().splitlines()[-1]
                if traceback_text.strip()
                else str(traceback_text)
            )
            QMessageBox.critical(self, "Error", f"An error occurred: {summary}")
        self.task_failed.emit()

    def get_parameters(self):
        """Get current widget parameters.

        Returns
        -------
        dict
            Dictionary of current widget parameters.
        """
        ignore_units = []
        if self.ignoreUnitsLineEdit.text().strip():
            ignore_units = [
                unit.strip() for unit in self.ignoreUnitsLineEdit.text().split(',') if unit.strip()
            ]

        return {
            'geology_layer': self.geologyLayerComboBox.currentLayer(),
            'unit_name_field': self.unitNameFieldComboBox.currentField(),
            'faults_layer': self.faultsLayerComboBox.currentLayer(),
            'ignore_units': ignore_units,
            'all_contacts': self.allContactsCheckBox.isChecked(),
        }

    def set_parameters(self, params):
        """Set widget parameters.

        Parameters
        ----------
        params : dict
            Dictionary of parameters to set.
        """
        if params.get('geology_layer'):
            self.geologyLayerComboBox.setLayer(params['geology_layer'])
        if params.get('faults_layer'):
            self.faultsLayerComboBox.setLayer(params['faults_layer'])
        if params.get('ignore_units'):
            self.ignoreUnitsLineEdit.setText(', '.join(params['ignore_units']))
        if 'all_contacts' in params:
            self.allContactsCheckBox.setChecked(params['all_contacts'])

    def _make_extract_contacts_target(self):
        """Capture widget/data_manager state synchronously and return a
        `target(progress_callback)` closure suitable for a background thread.

        Everything read here comes from Qt widgets or shared manager state,
        so it has to happen on the GUI thread before the background run
        starts (the widget is then disabled for the duration, so nothing
        here can go stale underneath the running task). The closure itself
        only touches `geology.getFeatures()` (safe off the GUI thread --
        read-only provider access, same as any QgsTask) and
        `extract_basal_contacts()`; anything that touches the project or
        shows UI happens afterwards, in `_on_extractor_finished`.
        """
        ignore_units = []
        if self.ignoreUnitsLineEdit.text().strip():
            ignore_units = [
                unit.strip() for unit in self.ignoreUnitsLineEdit.text().split(',') if unit.strip()
            ]
        geology = self.geologyLayerComboBox.currentLayer()
        unit_name_field = self.unitNameFieldComboBox.currentField()
        faults = self.faultsLayerComboBox.currentLayer()
        stratigraphic_order = (
            self.data_manager.get_stratigraphic_unit_names() if self.data_manager else []
        )
        unit_colours = (
            self.data_manager.get_stratigraphic_unit_colours() if self.data_manager else {}
        )
        all_contacts = self.allContactsCheckBox.isChecked()
        target_crs = self.data_manager.get_model_crs() if self.data_manager else None
        if target_crs is None or not target_crs.isValid():
            target_crs = geology.crs() if geology else None

        def target(progress_callback):
            nonlocal stratigraphic_order

            if all_contacts:

                def _is_null_like(v):
                    # Python None
                    if v is None:
                        return True
                    # PyQGIS QVariant null check
                    if hasattr(v, "isNull") and callable(v.isNull) and v.isNull():
                        return True
                    # Empty strings or literal "NULL" (case-insensitive)
                    if isinstance(v, str):
                        s = v.strip()
                        if s == "" or s.upper() == "NULL":
                            return True
                    return False

                values = []
                for feat in geology.getFeatures():
                    try:
                        val = feat[unit_name_field]
                    except Exception:
                        val = None
                    if _is_null_like(val):
                        continue
                    if val not in values:
                        values.append(val)
                stratigraphic_order = values
                progress_callback(f"Extracting all contacts for units: {stratigraphic_order}")

            result = extract_basal_contacts(
                geology=geology,
                stratigraphic_order=stratigraphic_order,
                faults=faults,
                ignore_units=ignore_units,
                unit_name_field=unit_name_field,
                all_contacts=all_contacts,
                updater=progress_callback,
                debug_manager=self._debug,
                target_crs=target_crs,
                unit_colours=unit_colours,
            )
            return result, all_contacts

        return target
