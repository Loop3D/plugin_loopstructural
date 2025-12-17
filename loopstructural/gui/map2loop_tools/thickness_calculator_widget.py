"""Widget for thickness calculator."""

import os

from PyQt5.QtWidgets import QLabel, QMessageBox, QWidget
from qgis.PyQt import uic

from loopstructural.toolbelt.preferences import PlgOptionsManager

from ...main.helpers import ColumnMatcher, get_layer_names
from ...main.vectorLayerWrapper import addGeoDataFrameToproject


class ThicknessCalculatorWidget(QWidget):
    """Widget for configuring and running the thickness calculator.

    This widget provides a GUI interface for the map2loop thickness
    calculation algorithms.
    """

    def __init__(self, parent=None, data_manager=None):
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

        # Load the UI file
        ui_path = os.path.join(os.path.dirname(__file__), "thickness_calculator_widget.ui")
        uic.loadUi(ui_path, self)

        # Configure layer filters programmatically (avoid enum values in .ui)
        try:
            from qgis.core import QgsMapLayerProxyModel

            self.dtmLayerComboBox.setFilters(QgsMapLayerProxyModel.RasterLayer)
            self.geologyLayerComboBox.setFilters(QgsMapLayerProxyModel.PolygonLayer)
            self.basalContactsComboBox.setFilters(QgsMapLayerProxyModel.LineLayer)
            self.sampledContactsComboBox.setFilters(QgsMapLayerProxyModel.PointLayer)
            self.structureLayerComboBox.setFilters(QgsMapLayerProxyModel.PointLayer)
        except Exception:
            pass

        # Initialize calculator types
        self.calculator_types = ["InterpolatedStructure", "StructuralPoint"]
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

        # Initial state update
        self._on_calculator_type_changed()

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
        else:  # InterpolatedStructure
            self.maxLineLengthLabel.setVisible(False)
            self.maxLineLengthSpinBox.setVisible(False)

    def _run_calculator(self):
        """Run the thickness calculator algorithm using the map2loop API."""
        from ...main.m2l_api import calculate_thickness

        # Validate inputs
        if not self.geologyLayerComboBox.currentLayer():
            QMessageBox.warning(self, "Missing Input", "Please select a geology layer.")
            return

        if not self.basalContactsComboBox.currentLayer():
            QMessageBox.warning(self, "Missing Input", "Please select a basal contacts layer.")
            return

        if not self.sampledContactsComboBox.currentLayer():
            QMessageBox.warning(self, "Missing Input", "Please select a sampled contacts layer.")
            return

        if not self.structureLayerComboBox.currentLayer():
            QMessageBox.warning(
                self, "Missing Input", "Please select a structure/orientation layer."
            )
            return

        calculator_type = self.calculatorTypeComboBox.currentText()

        # Prepare parameters
        try:
            kwargs = {
                'geology': self.geologyLayerComboBox.currentLayer(),
                'basal_contacts': self.basalContactsComboBox.currentLayer(),
                'sampled_contacts': self.sampledContactsComboBox.currentLayer(),
                'structure': self.structureLayerComboBox.currentLayer(),
                'calculator_type': calculator_type,
                'unit_name_field': self.unitNameFieldComboBox.currentField(),
                'basal_contacts_unit_name': self.basalUnitNameFieldComboBox.currentField(),
                'dip_field': self.dipFieldComboBox.currentField(),
                'dipdir_field': self.dipDirFieldComboBox.currentField(),
                'orientation_type': self.orientationTypeComboBox.currentText(),
                'updater': lambda msg: QMessageBox.information(self, "Progress", msg),
                'stratigraphic_order': (
                    self.data_manager.get_stratigraphic_unit_names() if self.data_manager else []
                ),
            }

            # Add optional parameters
            if self.dtmLayerComboBox.currentLayer():
                kwargs['dtm'] = self.dtmLayerComboBox.currentLayer()

            if calculator_type == "StructuralPoint":
                kwargs['max_line_length'] = self.maxLineLengthSpinBox.value()

            # Get stratigraphic order from data_manager
            if self.data_manager and hasattr(self.data_manager, 'stratigraphic_column'):
                strati_order = [unit['name'] for unit in self.data_manager._stratigraphic_column]
                if strati_order:
                    kwargs['stratigraphic_order'] = strati_order

            result = calculate_thickness(**kwargs)

            for idx in result['thicknesses'].index:
                u = result['thicknesses'].loc[idx, 'name']
                thick = result['thicknesses'].loc[idx, 'ThicknessStdDev']
                if thick > 0:
                    unit = self.data_manager._stratigraphic_column.get_unit_by_name(u)
                    if unit:
                        unit.thickness = thick
                    else:
                        self.data_manager.logger(
                            f"Warning: Unit '{u}' not found in stratigraphic column.",
                            level=QLabel.Warning,
                        )
            # Save debugging files if checkbox is checked
            if self.saveDebugCheckBox.isChecked():
                if 'lines' in result:
                    if result['lines'] is not None and not result['lines'].empty:
                        addGeoDataFrameToproject(result['lines'], "Lines")
                if 'location_tracking' in result:
                    if (
                        result['location_tracking'] is not None
                        and not result['location_tracking'].empty
                    ):
                        addGeoDataFrameToproject(
                            result['location_tracking'], "Thickness Location Tracking"
                        )
            if result is not None and not result['thicknesses'].empty:
                QMessageBox.information(
                    self,
                    "Success",
                    f"Thickness calculation completed successfully! ({len(result)} records)",
                )
            else:
                QMessageBox.warning(self, "Error", "No thickness data was calculated.")

        except Exception as e:
            if PlgOptionsManager.get_debug_mode():
                raise e
            QMessageBox.critical(self, "Error", f"An error occurred: {str(e)}")

    def get_parameters(self):
        """Get current widget parameters.

        Returns
        -------
        dict
            Dictionary of current widget parameters.
        """
        return {
            'calculator_type': self.calculatorTypeComboBox.currentIndex(),
            'dtm_layer': self.dtmLayerComboBox.currentLayer(),
            'geology_layer': self.geologyLayerComboBox.currentLayer(),
            'unit_name_field': self.unitNameFieldComboBox.currentField(),
            'basal_contacts': self.basalContactsComboBox.currentLayer(),
            'sampled_contacts': self.sampledContactsComboBox.currentLayer(),
            'structure_layer': self.structureLayerComboBox.currentLayer(),
            'dip_field': self.dipFieldComboBox.currentField(),
            'dipdir_field': self.dipDirFieldComboBox.currentField(),
            'orientation_type': self.orientationTypeComboBox.currentIndex(),
            'max_line_length': self.maxLineLengthSpinBox.value(),
        }

    def set_parameters(self, params):
        """Set widget parameters.

        Parameters
        ----------
        params : dict
            Dictionary of parameters to set.
        """
        if 'calculator_type' in params:
            self.calculatorTypeComboBox.setCurrentIndex(params['calculator_type'])
        if 'dtm_layer' in params and params['dtm_layer']:
            self.dtmLayerComboBox.setLayer(params['dtm_layer'])
        if 'geology_layer' in params and params['geology_layer']:
            self.geologyLayerComboBox.setLayer(params['geology_layer'])
        if 'basal_contacts' in params and params['basal_contacts']:
            self.basalContactsComboBox.setLayer(params['basal_contacts'])
        if 'sampled_contacts' in params and params['sampled_contacts']:
            self.sampledContactsComboBox.setLayer(params['sampled_contacts'])
        if 'structure_layer' in params and params['structure_layer']:
            self.structureLayerComboBox.setLayer(params['structure_layer'])
        if 'orientation_type' in params:
            self.orientationTypeComboBox.setCurrentIndex(params['orientation_type'])
        if 'max_line_length' in params:
            self.maxLineLengthSpinBox.setValue(params['max_line_length'])
