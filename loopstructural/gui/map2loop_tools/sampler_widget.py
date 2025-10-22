"""Widget for running the sampler."""

import os

from PyQt5.QtWidgets import QWidget, QMessageBox
from qgis.PyQt import uic


class SamplerWidget(QWidget):
    """Widget for configuring and running the sampler.

    This widget provides a GUI interface for the map2loop sampler algorithms
    (Decimator and Spacing).
    """

    def __init__(self, parent=None, data_manager=None):
        """Initialize the sampler widget.

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
        ui_path = os.path.join(os.path.dirname(__file__), "sampler_widget.ui")
        uic.loadUi(ui_path, self)

        # Initialize sampler types
        self.sampler_types = ["Decimator", "Spacing"]
        self.samplerTypeComboBox.addItems(self.sampler_types)

        # Connect signals
        self.samplerTypeComboBox.currentIndexChanged.connect(self._on_sampler_type_changed)
        self.runButton.clicked.connect(self._run_sampler)

        # Initial state update
        self._on_sampler_type_changed()

    def _on_sampler_type_changed(self):
        """Update UI based on selected sampler type."""
        sampler_type = self.samplerTypeComboBox.currentText()

        if sampler_type == "Decimator":
            self.decimationLabel.setVisible(True)
            self.decimationSpinBox.setVisible(True)
            self.spacingLabel.setVisible(False)
            self.spacingSpinBox.setVisible(False)
            # Decimator requires DTM and geology
            self.dtmLayerComboBox.setAllowEmptyLayer(False)
            self.geologyLayerComboBox.setAllowEmptyLayer(False)
        else:  # Spacing
            self.decimationLabel.setVisible(False)
            self.decimationSpinBox.setVisible(False)
            self.spacingLabel.setVisible(True)
            self.spacingSpinBox.setVisible(True)
            # Spacing can work with optional DTM and geology
            self.dtmLayerComboBox.setAllowEmptyLayer(True)
            self.geologyLayerComboBox.setAllowEmptyLayer(True)

    def _run_sampler(self):
        """Run the sampler algorithm."""
        from qgis.core import QgsProcessingFeedback
        from qgis import processing

        # Validate inputs
        if not self.spatialDataLayerComboBox.currentLayer():
            QMessageBox.warning(self, "Missing Input", "Please select a spatial data layer.")
            return

        sampler_type = self.samplerTypeComboBox.currentText()

        if sampler_type == "Decimator":
            if not self.geologyLayerComboBox.currentLayer():
                QMessageBox.warning(
                    self, "Missing Input", "Geology layer is required for Decimator."
                )
                return
            if not self.dtmLayerComboBox.currentLayer():
                QMessageBox.warning(self, "Missing Input", "DTM layer is required for Decimator.")
                return

        # Prepare parameters
        params = {
            'SAMPLER_TYPE': self.samplerTypeComboBox.currentIndex(),
            'SPATIAL_DATA': self.spatialDataLayerComboBox.currentLayer(),
            'DTM': self.dtmLayerComboBox.currentLayer(),
            'GEOLOGY': self.geologyLayerComboBox.currentLayer(),
            'DECIMATION': self.decimationSpinBox.value(),
            'SPACING': self.spacingSpinBox.value(),
            'OUTPUT': 'TEMPORARY_OUTPUT',
        }

        # Run the algorithm
        try:
            feedback = QgsProcessingFeedback()
            result = processing.run("plugin_map2loop:sampler", params, feedback=feedback)

            if result:
                QMessageBox.information(self, "Success", "Sampling completed successfully!")
            else:
                QMessageBox.warning(self, "Error", "Failed to complete sampling.")

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
            'sampler_type': self.samplerTypeComboBox.currentIndex(),
            'dtm_layer': self.dtmLayerComboBox.currentLayer(),
            'geology_layer': self.geologyLayerComboBox.currentLayer(),
            'spatial_data_layer': self.spatialDataLayerComboBox.currentLayer(),
            'decimation': self.decimationSpinBox.value(),
            'spacing': self.spacingSpinBox.value(),
        }

    def set_parameters(self, params):
        """Set widget parameters.

        Parameters
        ----------
        params : dict
            Dictionary of parameters to set.
        """
        if 'sampler_type' in params:
            self.samplerTypeComboBox.setCurrentIndex(params['sampler_type'])
        if 'dtm_layer' in params and params['dtm_layer']:
            self.dtmLayerComboBox.setLayer(params['dtm_layer'])
        if 'geology_layer' in params and params['geology_layer']:
            self.geologyLayerComboBox.setLayer(params['geology_layer'])
        if 'spatial_data_layer' in params and params['spatial_data_layer']:
            self.spatialDataLayerComboBox.setLayer(params['spatial_data_layer'])
        if 'decimation' in params:
            self.decimationSpinBox.setValue(params['decimation'])
        if 'spacing' in params:
            self.spacingSpinBox.setValue(params['spacing'])
