"""Widget for extracting basal contacts."""

import os

from PyQt5.QtWidgets import QMessageBox, QWidget
from qgis.PyQt import uic


class BasalContactsWidget(QWidget):
    """Widget for configuring and running the basal contacts extractor.

    This widget provides a GUI interface for extracting basal contacts
    from geology layers.
    """

    def __init__(self, parent=None, data_manager=None):
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

        # Load the UI file
        ui_path = os.path.join(os.path.dirname(__file__), "basal_contacts_widget.ui")
        uic.loadUi(ui_path, self)

        # Move layer filter setup out of the .ui (QgsMapLayerProxyModel values in .ui
        # can cause import errors outside QGIS). Set filters programmatically
        # and preserve the allowEmptyLayer setting for the faults combobox.
        try:
            from qgis.core import QgsMapLayerProxyModel

            # geology layer should only show polygon layers
            self.geologyLayerComboBox.setFilters(QgsMapLayerProxyModel.PolygonLayer)

            # faults should show line layers and allow empty selection (as set in .ui)
            self.faultsLayerComboBox.setFilters(QgsMapLayerProxyModel.LineLayer)
            try:
                # QgsMapLayerComboBox has setAllowEmptyLayer method in newer QGIS versions
                self.faultsLayerComboBox.setAllowEmptyLayer(True)
            except Exception:
                # Older QGIS bindings may use allowEmptyLayer property; ignore if unavailable
                pass
        except Exception:
            # If QGIS isn't available (e.g. editing the UI outside QGIS), skip setting filters
            pass

        # Connect signals
        self.geologyLayerComboBox.layerChanged.connect(self._on_geology_layer_changed)
        self.runButton.clicked.connect(self._run_extractor)

        # Set up field combo boxes
        self._setup_field_combo_boxes()

    def _setup_field_combo_boxes(self):
        """Set up field combo boxes to link to their respective layers."""
        geology = self.geologyLayerComboBox.currentLayer()
        if geology is not None:
            self.unitNameFieldComboBox.setLayer(geology)
            self.formationFieldComboBox.setLayer(geology)
        else:
            # Ensure combo boxes are cleared if no geology layer selected
            try:
                self.unitNameFieldComboBox.setLayer(None)
                self.formationFieldComboBox.setLayer(None)
            except Exception:
                pass

    def _on_geology_layer_changed(self):
        """Update field combo boxes when geology layer changes."""
        layer = self.geologyLayerComboBox.currentLayer()
        self.unitNameFieldComboBox.setLayer(layer)
        self.formationFieldComboBox.setLayer(layer)

    def _run_extractor(self):
        """Run the basal contacts extraction algorithm."""
        from qgis import processing
        from qgis.core import QgsProcessingFeedback

        # Validate inputs
        if not self.geologyLayerComboBox.currentLayer():
            QMessageBox.warning(self, "Missing Input", "Please select a geology layer.")
            return

        if not self.stratiColumnComboBox.currentLayer():
            QMessageBox.warning(self, "Missing Input", "Please select a stratigraphic order layer.")
            return

        # Parse ignore units
        ignore_units = []
        if self.ignoreUnitsLineEdit.text().strip():
            ignore_units = [
                unit.strip() for unit in self.ignoreUnitsLineEdit.text().split(',') if unit.strip()
            ]

        # Prepare parameters
        params = {
            'GEOLOGY': self.geologyLayerComboBox.currentLayer(),
            'UNIT_NAME_FIELD': self.unitNameFieldComboBox.currentField(),
            'FORMATION_FIELD': self.formationFieldComboBox.currentField(),
            'FAULTS': self.faultsLayerComboBox.currentLayer(),
            'STRATIGRAPHIC_COLUMN': self.stratiColumnComboBox.currentLayer(),
            'IGNORE_UNITS': ignore_units,
            'OUTPUT': 'TEMPORARY_OUTPUT',
            'ALL_CONTACTS': 'TEMPORARY_OUTPUT',
        }

        # Run the algorithm
        try:
            feedback = QgsProcessingFeedback()
            result = processing.run("plugin_map2loop:basal_contacts", params, feedback=feedback)

            if result:
                QMessageBox.information(self, "Success", "Basal contacts extracted successfully!")
            else:
                QMessageBox.warning(self, "Error", "Failed to extract basal contacts.")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred: {str(e)}")

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
            'formation_field': self.formationFieldComboBox.currentField(),
            'faults_layer': self.faultsLayerComboBox.currentLayer(),
            'strati_column': self.stratiColumnComboBox.currentLayer(),
            'ignore_units': ignore_units,
        }

    def set_parameters(self, params):
        """Set widget parameters.

        Parameters
        ----------
        params : dict
            Dictionary of parameters to set.
        """
        if 'geology_layer' in params and params['geology_layer']:
            self.geologyLayerComboBox.setLayer(params['geology_layer'])
        if 'faults_layer' in params and params['faults_layer']:
            self.faultsLayerComboBox.setLayer(params['faults_layer'])
        if 'strati_column' in params and params['strati_column']:
            self.stratiColumnComboBox.setLayer(params['strati_column'])
        if 'ignore_units' in params and params['ignore_units']:
            self.ignoreUnitsLineEdit.setText(', '.join(params['ignore_units']))
