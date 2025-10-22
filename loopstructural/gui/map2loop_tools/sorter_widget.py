"""Widget for running the automatic stratigraphic sorter."""

import os

from PyQt5.QtWidgets import QWidget, QMessageBox
from qgis.PyQt import uic


class SorterWidget(QWidget):
    """Widget for configuring and running the automatic stratigraphic sorter.

    This widget provides a GUI interface for the map2loop stratigraphic
    sorting algorithms.
    """

    def __init__(self, parent=None, data_manager=None):
        """Initialize the sorter widget.

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
        ui_path = os.path.join(os.path.dirname(__file__), "sorter_widget.ui")
        uic.loadUi(ui_path, self)

        # Initialize sorting algorithms
        self.sorting_algorithms = [
            "Age‐based",
            "NetworkX topological",
            "Hint (deprecated)",
            "Adjacency α",
            "Maximise contacts",
            "Observation projections",
        ]
        self.sortingAlgorithmComboBox.addItems(self.sorting_algorithms)
        self.sortingAlgorithmComboBox.setCurrentIndex(5)  # Default to Observation projections

        # Initialize orientation types
        self.orientation_types = ['', 'Dip Direction', 'Strike']
        self.orientationTypeComboBox.addItems(self.orientation_types)

        # Connect signals
        self.sortingAlgorithmComboBox.currentIndexChanged.connect(self._on_algorithm_changed)
        self.geologyLayerComboBox.layerChanged.connect(self._on_geology_layer_changed)
        self.structureLayerComboBox.layerChanged.connect(self._on_structure_layer_changed)
        self.runButton.clicked.connect(self._run_sorter)

        # Set up field combo boxes
        self._setup_field_combo_boxes()

        # Initial state update
        self._on_algorithm_changed()

    def _setup_field_combo_boxes(self):
        """Set up field combo boxes to link to their respective layers."""
        self.unitNameFieldComboBox.setLayer(self.geologyLayerComboBox.currentLayer())
        self.minAgeFieldComboBox.setLayer(self.geologyLayerComboBox.currentLayer())
        self.maxAgeFieldComboBox.setLayer(self.geologyLayerComboBox.currentLayer())
        self.groupFieldComboBox.setLayer(self.geologyLayerComboBox.currentLayer())
        self.dipFieldComboBox.setLayer(self.structureLayerComboBox.currentLayer())
        self.dipDirFieldComboBox.setLayer(self.structureLayerComboBox.currentLayer())

    def _on_geology_layer_changed(self):
        """Update field combo boxes when geology layer changes."""
        layer = self.geologyLayerComboBox.currentLayer()
        self.unitNameFieldComboBox.setLayer(layer)
        self.minAgeFieldComboBox.setLayer(layer)
        self.maxAgeFieldComboBox.setLayer(layer)
        self.groupFieldComboBox.setLayer(layer)

    def _on_structure_layer_changed(self):
        """Update field combo boxes when structure layer changes."""
        layer = self.structureLayerComboBox.currentLayer()
        self.dipFieldComboBox.setLayer(layer)
        self.dipDirFieldComboBox.setLayer(layer)

    def _on_algorithm_changed(self):
        """Update UI based on selected sorting algorithm."""
        algorithm_index = self.sortingAlgorithmComboBox.currentIndex()
        is_observation_projections = algorithm_index == 5

        # Show/hide structure-related fields for observation projections
        self.structureLayerLabel.setVisible(is_observation_projections)
        self.structureLayerComboBox.setVisible(is_observation_projections)
        self.dipFieldLabel.setVisible(is_observation_projections)
        self.dipFieldComboBox.setVisible(is_observation_projections)
        self.dipDirFieldLabel.setVisible(is_observation_projections)
        self.dipDirFieldComboBox.setVisible(is_observation_projections)
        self.orientationTypeLabel.setVisible(is_observation_projections)
        self.orientationTypeComboBox.setVisible(is_observation_projections)
        self.dtmLayerLabel.setVisible(is_observation_projections)
        self.dtmLayerComboBox.setVisible(is_observation_projections)

    def _run_sorter(self):
        """Run the stratigraphic sorter algorithm."""
        from qgis.core import QgsProcessingFeedback
        from qgis import processing

        # Validate inputs
        if not self.geologyLayerComboBox.currentLayer():
            QMessageBox.warning(self, "Missing Input", "Please select a geology layer.")
            return

        if not self.contactsLayerComboBox.currentLayer():
            QMessageBox.warning(self, "Missing Input", "Please select a contacts layer.")
            return

        algorithm_index = self.sortingAlgorithmComboBox.currentIndex()
        is_observation_projections = algorithm_index == 5

        if is_observation_projections:
            if not self.structureLayerComboBox.currentLayer():
                QMessageBox.warning(
                    self, "Missing Input", "Structure layer is required for observation projections."
                )
                return
            if not self.dtmLayerComboBox.currentLayer():
                QMessageBox.warning(
                    self, "Missing Input", "DTM layer is required for observation projections."
                )
                return

        # Prepare parameters
        params = {
            'SORTING_ALGORITHM': algorithm_index,
            'INPUT_GEOLOGY': self.geologyLayerComboBox.currentLayer(),
            'UNIT_NAME_FIELD': self.unitNameFieldComboBox.currentField(),
            'MIN_AGE_FIELD': self.minAgeFieldComboBox.currentField(),
            'MAX_AGE_FIELD': self.maxAgeFieldComboBox.currentField(),
            'GROUP_FIELD': self.groupFieldComboBox.currentField(),
            'CONTACTS_LAYER': self.contactsLayerComboBox.currentLayer(),
            'OUTPUT': 'TEMPORARY_OUTPUT',
            'JSON_OUTPUT': 'TEMPORARY_OUTPUT',
        }

        if is_observation_projections:
            params['INPUT_STRUCTURE'] = self.structureLayerComboBox.currentLayer()
            params['DIP_FIELD'] = self.dipFieldComboBox.currentField()
            params['DIPDIR_FIELD'] = self.dipDirFieldComboBox.currentField()
            params['ORIENTATION_TYPE'] = self.orientationTypeComboBox.currentIndex()
            params['INPUT_DTM'] = self.dtmLayerComboBox.currentLayer()

        # Run the algorithm
        try:
            feedback = QgsProcessingFeedback()
            result = processing.run("plugin_map2loop:loop_sorter", params, feedback=feedback)

            if result:
                QMessageBox.information(
                    self, "Success", "Stratigraphic column created successfully!"
                )
            else:
                QMessageBox.warning(self, "Error", "Failed to create stratigraphic column.")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred: {str(e)}")

    def get_parameters(self):
        """Get current widget parameters.

        Returns
        -------
        dict
            Dictionary of current widget parameters.
        """
        algorithm_index = self.sortingAlgorithmComboBox.currentIndex()
        is_observation_projections = algorithm_index == 5

        params = {
            'sorting_algorithm': algorithm_index,
            'geology_layer': self.geologyLayerComboBox.currentLayer(),
            'unit_name_field': self.unitNameFieldComboBox.currentField(),
            'min_age_field': self.minAgeFieldComboBox.currentField(),
            'max_age_field': self.maxAgeFieldComboBox.currentField(),
            'group_field': self.groupFieldComboBox.currentField(),
            'contacts_layer': self.contactsLayerComboBox.currentLayer(),
        }

        if is_observation_projections:
            params['structure_layer'] = self.structureLayerComboBox.currentLayer()
            params['dip_field'] = self.dipFieldComboBox.currentField()
            params['dipdir_field'] = self.dipDirFieldComboBox.currentField()
            params['orientation_type'] = self.orientationTypeComboBox.currentIndex()
            params['dtm_layer'] = self.dtmLayerComboBox.currentLayer()

        return params

    def set_parameters(self, params):
        """Set widget parameters.

        Parameters
        ----------
        params : dict
            Dictionary of parameters to set.
        """
        if 'sorting_algorithm' in params:
            self.sortingAlgorithmComboBox.setCurrentIndex(params['sorting_algorithm'])
        if 'geology_layer' in params and params['geology_layer']:
            self.geologyLayerComboBox.setLayer(params['geology_layer'])
        if 'contacts_layer' in params and params['contacts_layer']:
            self.contactsLayerComboBox.setLayer(params['contacts_layer'])
