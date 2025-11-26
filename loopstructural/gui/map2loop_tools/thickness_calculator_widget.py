"""Widget for thickness calculator."""

import os

from PyQt5.QtWidgets import QMessageBox, QWidget
from qgis.PyQt import uic


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
        self.runButton.clicked.connect(self._run_calculator)

        # Set up field combo boxes
        self._setup_field_combo_boxes()

        # Initial state update
        self._on_calculator_type_changed()

    def _setup_field_combo_boxes(self):
        """Set up field combo boxes to link to their respective layers."""
        self.unitNameFieldComboBox.setLayer(self.geologyLayerComboBox.currentLayer())
        self.dipFieldComboBox.setLayer(self.structureLayerComboBox.currentLayer())
        self.dipDirFieldComboBox.setLayer(self.structureLayerComboBox.currentLayer())

    def _on_geology_layer_changed(self):
        """Update field combo boxes when geology layer changes."""
        layer = self.geologyLayerComboBox.currentLayer()
        self.unitNameFieldComboBox.setLayer(layer)

    def _on_structure_layer_changed(self):
        """Update field combo boxes when structure layer changes."""
        layer = self.structureLayerComboBox.currentLayer()
        self.dipFieldComboBox.setLayer(layer)
        self.dipDirFieldComboBox.setLayer(layer)

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
                'dip_field': self.dipFieldComboBox.currentField(),
                'dipdir_field': self.dipDirFieldComboBox.currentField(),
                'orientation_type': self.orientationTypeComboBox.currentText(),
                'updater': lambda msg: QMessageBox.information(self, "Progress", msg),
            }

            # Add optional parameters
            if self.dtmLayerComboBox.currentLayer():
                kwargs['dtm'] = self.dtmLayerComboBox.currentLayer()

            if calculator_type == "StructuralPoint":
                kwargs['max_line_length'] = self.maxLineLengthSpinBox.value()

            if self.stratiColumnComboBox.currentLayer():
                # Extract unit names from stratigraphic column layer
                strati_layer = self.stratiColumnComboBox.currentLayer()
                strati_order = [
                    f['unit_name']
                    for f in strati_layer.getFeatures()
                    if 'unit_name' in f.fields().names()
                ]
                if strati_order:
                    kwargs['stratigraphic_order'] = strati_order

            result = calculate_thickness(**kwargs)

            if result is not None and not result.empty:
                QMessageBox.information(
                    self,
                    "Success",
                    f"Thickness calculation completed successfully! ({len(result)} records)",
                )
            else:
                QMessageBox.warning(self, "Error", "No thickness data was calculated.")

        except Exception as e:
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
            'strati_column': self.stratiColumnComboBox.currentLayer(),
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
        if 'strati_column' in params and params['strati_column']:
            self.stratiColumnComboBox.setLayer(params['strati_column'])
        if 'orientation_type' in params:
            self.orientationTypeComboBox.setCurrentIndex(params['orientation_type'])
        if 'max_line_length' in params:
            self.maxLineLengthSpinBox.setValue(params['max_line_length'])
