"""Widget for thickness calculator."""

import os

import pandas as pd
from PyQt5.QtWidgets import QMessageBox, QWidget
from qgis.core import QgsMapLayerProxyModel
from qgis.PyQt import uic

from loopstructural.toolbelt.preferences import PlgOptionsManager

from ...main.helpers import ColumnMatcher, get_layer_names
from ...main.vectorLayerWrapper import addGeoDataFrameToproject


class ThicknessCalculatorWidget(QWidget):
    """Widget for configuring and running the thickness calculator.

    This widget provides a GUI interface for the map2loop thickness
    calculation algorithms.
    """

    def __init__(self, parent=None, data_manager=None, debug_manager=None):
        """Initialize the thickness calculator widget.

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
        ui_path = os.path.join(os.path.dirname(__file__), "thickness_calculator_widget.ui")
        uic.loadUi(ui_path, self)

        # Configure layer filters programmatically (avoid enum values in .ui)

        self.dtmLayerComboBox.setFilters(QgsMapLayerProxyModel.RasterLayer)
        self.geologyLayerComboBox.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        self.basalContactsComboBox.setFilters(QgsMapLayerProxyModel.LineLayer)
        self.sampledContactsComboBox.setFilters(QgsMapLayerProxyModel.PointLayer)
        self.structureLayerComboBox.setFilters(QgsMapLayerProxyModel.PointLayer)
        self.crossSectionLayerComboBox.setFilters(QgsMapLayerProxyModel.LineLayer)

        # Initialize calculator types
        self.calculator_types = ["InterpolatedStructure", "StructuralPoint", "AlongSection"]
        self.calculatorTypeComboBox.addItems(self.calculator_types)

        # Initialize orientation types
        self.orientation_types = ['Dip Direction', 'Strike']
        self.orientationTypeComboBox.addItems(self.orientation_types)

        # Connect signals
        self.calculatorTypeComboBox.currentIndexChanged.connect(self._on_calculator_type_changed)
        self.geologyLayerComboBox.layerChanged.connect(self._on_geology_layer_changed)
        self.structureLayerComboBox.layerChanged.connect(self._on_structure_layer_changed)
        self.basalContactsComboBox.layerChanged.connect(self._on_basal_contacts_layer_changed)
        self.runButton.clicked.connect(self._run_calculator)
        self._guess_layers()
        # Set up field combo boxes
        self._setup_field_combo_boxes()
        self._restore_selection()

        # Initial state update
        self._on_calculator_type_changed()

    def set_debug_manager(self, debug_manager):
        """Attach a debug manager instance."""
        self._debug = debug_manager

    def _export_layer_for_debug(self, layer, name_prefix: str):
        # Prefer using DebugManager.export_layer if available
        try:
            if getattr(self, '_debug', None) and hasattr(self._debug, 'export_layer'):
                exported = self._debug.export_layer(layer, name_prefix)
                return exported

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

    def _log_params(self, context_label: str, params=None):
        if getattr(self, "_debug", None):
            payload = params if params is not None else self.get_parameters()
            payload = self._serialize_params_for_logging(payload, context_label)
            self._debug.log_params(context_label=context_label, params=payload)

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

        # Attempt to find basal contacts layer
        basal_contacts_names = get_layer_names(self.basalContactsComboBox)
        basal_matcher = ColumnMatcher(basal_contacts_names)
        basal_layer_match = basal_matcher.find_match('BASAL_CONTACTS')
        if basal_layer_match:
            basal_layer = self.data_manager.find_layer_by_name(basal_layer_match)
            self.basalContactsComboBox.setLayer(basal_layer)

        # Attempt to find sampled contacts layer
        sampled_contacts_names = get_layer_names(self.sampledContactsComboBox)
        sampled_matcher = ColumnMatcher(sampled_contacts_names)
        sampled_layer_match = sampled_matcher.find_match('SAMPLED_CONTACTS')
        if sampled_layer_match:
            sampled_layer = self.data_manager.find_layer_by_name(sampled_layer_match)
            self.sampledContactsComboBox.setLayer(sampled_layer)

        # Attempt to find structure layer
        structure_layer_names = get_layer_names(self.structureLayerComboBox)
        structure_matcher = ColumnMatcher(structure_layer_names)
        structure_layer_match = structure_matcher.find_match('STRUCTURE')
        if structure_layer_match:
            structure_layer = self.data_manager.find_layer_by_name(structure_layer_match)
            self.structureLayerComboBox.setLayer(structure_layer)

        # Attempt to find cross-sections layer
        cross_sections_layer_names = get_layer_names(self.crossSectionLayerComboBox)
        cross_sections_matcher = ColumnMatcher(cross_sections_layer_names)
        cross_sections_layer_match = cross_sections_matcher.find_match('CROSS_SECTIONS')
        if cross_sections_layer_match:
            cross_sections_layer = self.data_manager.find_layer_by_name(cross_sections_layer_match)
            self.crossSectionLayerComboBox.setLayer(cross_sections_layer)

    def _setup_field_combo_boxes(self):
        """Set up field combo boxes to link to their respective layers."""
        self.unitNameFieldComboBox.setLayer(self.geologyLayerComboBox.currentLayer())
        self.dipFieldComboBox.setLayer(self.structureLayerComboBox.currentLayer())
        self.dipDirFieldComboBox.setLayer(self.structureLayerComboBox.currentLayer())
        self.basalUnitNameFieldComboBox.setLayer(self.basalContactsComboBox.currentLayer())

    def _on_basal_contacts_layer_changed(self):
        """Update field combo box when basal contacts layer changes."""
        layer = self.basalContactsComboBox.currentLayer()
        self.basalUnitNameFieldComboBox.setLayer(layer)
        # Optionally auto-select a likely unit name field
        if layer:
            fields = [field.name() for field in layer.fields()]
            matcher = ColumnMatcher(fields)
            if unit_match := matcher.find_match('UNITNAME'):
                self.basalUnitNameFieldComboBox.setField(unit_match)

    def _on_geology_layer_changed(self):
        """Update field combo boxes when geology layer changes."""

        layer = self.geologyLayerComboBox.currentLayer()
        self.unitNameFieldComboBox.setLayer(layer)

        # Auto-detect appropriate fields
        if layer:
            fields = [field.name() for field in layer.fields()]
            matcher = ColumnMatcher(fields)

            # Auto-select UNITNAME field
            if unit_match := matcher.find_match('UNITNAME'):
                self.unitNameFieldComboBox.setField(unit_match)

    def _on_structure_layer_changed(self):
        """Update field combo boxes when structure layer changes."""

        layer = self.structureLayerComboBox.currentLayer()
        self.dipFieldComboBox.setLayer(layer)
        self.dipDirFieldComboBox.setLayer(layer)

        # Auto-detect appropriate fields
        if layer:
            fields = [field.name() for field in layer.fields()]
            matcher = ColumnMatcher(fields)

            # Auto-select DIP and DIPDIR fields
            if dip_match := matcher.find_match('DIP'):
                self.dipFieldComboBox.setField(dip_match)

            if dipdir_match := matcher.find_match('DIPDIR'):
                self.dipDirFieldComboBox.setField(dipdir_match)

    def _on_calculator_type_changed(self):
        """Update UI based on selected calculator type."""
        calculator_type = self.calculatorTypeComboBox.currentText()

        if calculator_type == "StructuralPoint":
            self.maxLineLengthLabel.setVisible(True)
            self.maxLineLengthSpinBox.setVisible(True)
            self.crossSectionLayerLabel.setVisible(False)
            self.crossSectionLayerComboBox.setVisible(False)

        elif calculator_type == "InterpolatedStructure":
            self.maxLineLengthLabel.setVisible(False)
            self.maxLineLengthSpinBox.setVisible(False)
            self.crossSectionLayerLabel.setVisible(False)
            self.crossSectionLayerComboBox.setVisible(False)

        elif calculator_type == "AlongSection":
            self.crossSectionLayerLabel.setVisible(True)
            self.crossSectionLayerComboBox.setVisible(True)
            self.maxLineLengthLabel.setVisible(False)
            self.maxLineLengthSpinBox.setVisible(False)

    def _restore_selection(self):
        """Restore persisted selections from data manager."""
        if not self.data_manager:
            return
        settings = self.data_manager.get_widget_settings('thickness_calculator_widget', {})
        if not settings:
            return
        for key, combo in (
            ('dtm_layer', self.dtmLayerComboBox),
            ('geology_layer', self.geologyLayerComboBox),
            ('basal_contacts_layer', self.basalContactsComboBox),
            ('sampled_contacts_layer', self.sampledContactsComboBox),
            ('structure_layer', self.structureLayerComboBox),
            ("cross_sections_layer", self.crossSectionLayerComboBox),
        ):
            if layer_name := settings.get(key):
                layer = self.data_manager.find_layer_by_name(layer_name)
                if layer:
                    combo.setLayer(layer)
        if 'calculator_type_index' in settings:
            self.calculatorTypeComboBox.setCurrentIndex(settings['calculator_type_index'])
        if 'orientation_type_index' in settings:
            self.orientationTypeComboBox.setCurrentIndex(settings['orientation_type_index'])
        if 'max_line_length' in settings:
            self.maxLineLengthSpinBox.setValue(settings['max_line_length'])
        if field := settings.get('unit_name_field'):
            self.unitNameFieldComboBox.setField(field)
        if field := settings.get('dip_field'):
            self.dipFieldComboBox.setField(field)
        if field := settings.get('dipdir_field'):
            self.dipDirFieldComboBox.setField(field)
        if field := settings.get('basal_unit_field'):
            self.basalUnitNameFieldComboBox.setField(field)

    def _persist_selection(self):
        """Persist current selections into data manager."""
        if not self.data_manager:
            return
        settings = {
            'dtm_layer': (
                self.dtmLayerComboBox.currentLayer().name()
                if self.dtmLayerComboBox.currentLayer()
                else None
            ),
            'geology_layer': (
                self.geologyLayerComboBox.currentLayer().name()
                if self.geologyLayerComboBox.currentLayer()
                else None
            ),
            'basal_contacts_layer': (
                self.basalContactsComboBox.currentLayer().name()
                if self.basalContactsComboBox.currentLayer()
                else None
            ),
            'sampled_contacts_layer': (
                self.sampledContactsComboBox.currentLayer().name()
                if self.sampledContactsComboBox.currentLayer()
                else None
            ),
            'structure_layer': (
                self.structureLayerComboBox.currentLayer().name()
                if self.structureLayerComboBox.currentLayer()
                else None
            ),
            'cross_sections_layer': (
                self.crossSectionLayerComboBox.currentLayer().name()
                if self.crossSectionLayerComboBox.currentLayer()
                else None
            ),
            'calculator_type_index': self.calculatorTypeComboBox.currentIndex(),
            'orientation_type_index': self.orientationTypeComboBox.currentIndex(),
            'max_line_length': self.maxLineLengthSpinBox.value(),
            'unit_name_field': self.unitNameFieldComboBox.currentField(),
            'dip_field': self.dipFieldComboBox.currentField(),
            'dipdir_field': self.dipDirFieldComboBox.currentField(),
            'basal_unit_field': self.basalUnitNameFieldComboBox.currentField(),
        }
        self.data_manager.set_widget_settings('thickness_calculator_widget', settings)

    def _run_calculator(self):
        """Run the thickness calculator algorithm using the map2loop API."""
        from ...main.m2l_api import calculate_thickness

        self._persist_selection()
        self._log_params("thickness_calculator_widget_run", self.get_parameters())

        # Validate inputs based on calculator type
        calculator_type = self.calculatorTypeComboBox.currentText()

        if calculator_type == "InterpolatedStructure":
            if not self.geologyLayerComboBox.currentLayer():
                QMessageBox.warning(self, "Missing Input", "Please select a geology layer.")
                return False
            if not self.basalContactsComboBox.currentLayer():
                QMessageBox.warning(self, "Missing Input", "Please select a basal contacts layer.")
                return False

        elif calculator_type == "StructuralPoint":
            if not self.structureLayerComboBox.currentLayer():
                QMessageBox.warning(self, "Missing Input", "Please select a structure layer.")
                return False

        elif calculator_type == "AlongSection":
            if not self.crossSectionLayerComboBox.currentLayer():
                QMessageBox.warning(self, "Missing Input", "Please select a cross-sections layer.")
                return False

        # Prepare parameters
        params = self.get_parameters()

        try:
            result = calculate_thickness(**params)
            if not result:
                QMessageBox.warning(
                    self, "No Results", "Thickness calculation returned no results."
                )
                return False

            # Expect result as dict with components; fall back to direct layer
            if isinstance(result, dict):
                thicknesses = result.get('thicknesses')
                lines = result.get('lines')
                location_tracking = result.get('location_tracking')
                # If thicknesses were calculated, update the stratigraphic column units
                try:
                    if thicknesses is not None and getattr(self, 'data_manager', None):
                        # Prefer median thickness if available, fallback to mean
                        thickness_col = (
                            'ThicknessMedian'
                            if 'ThicknessMedian' in getattr(thicknesses, 'columns', [])
                            else (
                                'ThicknessMean'
                                if 'ThicknessMean' in getattr(thicknesses, 'columns', [])
                                else None
                            )
                        )
                        if thickness_col is not None:
                            for _, row in thicknesses.iterrows():
                                unit_name = row.get('name') or row.get('UNITNAME')
                                if not unit_name:
                                    continue
                                try:
                                    value = row.get(thickness_col)
                                except Exception:
                                    value = None
                                # Skip invalid values (e.g. -1 means not calculated)
                                try:
                                    is_invalid = pd.isna(value) or float(value) == -1
                                except Exception:
                                    is_invalid = value is None
                                if is_invalid:
                                    continue
                                # Find unit in stratigraphic column and update thickness
                                try:
                                    strat_col = self.data_manager.get_stratigraphic_column()
                                    unit = strat_col.get_unit_by_name(unit_name)
                                    if unit is not None:
                                        unit.thickness = float(value)
                                except Exception as err:
                                    # Log but don't fail the widget
                                    try:
                                        if getattr(self, '_debug', None):
                                            self._debug.plugin.log(
                                                message=f"Failed to update stratigraphic unit thickness for {unit_name}: {err}",
                                                log_level=2,
                                            )
                                    except Exception:
                                        pass
                        # Notify any stratigraphic column callbacks
                        try:
                            if getattr(self.data_manager, 'stratigraphic_column_callback', None):
                                self.data_manager.stratigraphic_column_callback()
                        except Exception:
                            pass
                except Exception:
                    pass
                # if thicknesses is not None:
                #     addGeoDataFrameToproject(thicknesses, "Thickness Results")
                if lines is not None:
                    addGeoDataFrameToproject(lines, "Thickness Lines")
                if location_tracking is not None:
                    addGeoDataFrameToproject(location_tracking, "Thickness Locations")
                QMessageBox.information(
                    self,
                    "Success",
                    "Thickness calculation completed successfully and added to project.",
                )
                return True

            if hasattr(result, 'geometry'):
                addGeoDataFrameToproject(result, "Thickness Results")
                QMessageBox.information(
                    self,
                    "Success",
                    "Thickness calculation completed successfully and added to project.",
                )
                return True

            QMessageBox.information(self, "Success", f"Thickness calculation completed: {result}")
            return True

        except Exception as e:
            if self._debug:
                self._debug.plugin.log(
                    message=f"[map2loop] Thickness calculation failed: {e}",
                    log_level=2,
                )
            if PlgOptionsManager.get_debug_mode():
                raise e
            QMessageBox.critical(self, "Error", f"An error occurred: {str(e)}")
            return False

    def get_parameters(self):
        """Get current widget parameters.

        Returns
        -------
        dict
            Dictionary of current widget parameters.
        """
        params = {
            'calculator_type': self.calculatorTypeComboBox.currentText(),
            'dtm': self.dtmLayerComboBox.currentLayer(),
            'geology': self.geologyLayerComboBox.currentLayer(),
            'basal_contacts': self.basalContactsComboBox.currentLayer(),
            'sampled_contacts': self.sampledContactsComboBox.currentLayer(),
            'structure': self.structureLayerComboBox.currentLayer(),
            'cross_sections': self.crossSectionLayerComboBox.currentLayer(),
            'orientation_type': self.orientationTypeComboBox.currentText(),
            'unit_name_field': self.unitNameFieldComboBox.currentField(),
            'dip_field': self.dipFieldComboBox.currentField(),
            'dipdir_field': self.dipDirFieldComboBox.currentField(),
            'basal_contacts_unit_name': self.basalUnitNameFieldComboBox.currentField(),
            'max_line_length': self.maxLineLengthSpinBox.value(),
            'updater': (lambda msg: QMessageBox.information(self, "Progress", msg)),
            'stratigraphic_order': (
                self.data_manager.get_stratigraphic_unit_names()
                if self.data_manager and hasattr(self.data_manager, 'get_stratigraphic_unit_names')
                else None
            ),
            'debug_manager': self._debug,
        }
        return params
