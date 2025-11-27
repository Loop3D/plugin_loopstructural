"""Widget for running the automatic stratigraphic sorter."""

import os

from PyQt5.QtWidgets import QMessageBox, QWidget
from qgis.core import QgsRasterLayer
from qgis.PyQt import uic

from loopstructural.main.helpers import get_layer_names


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
        if data_manager is None:
            raise ValueError("data_manager must be provided")
        self.data_manager = data_manager

        # Load the UI file
        ui_path = os.path.join(os.path.dirname(__file__), "sorter_widget.ui")
        uic.loadUi(ui_path, self)

        # Configure layer filters programmatically (avoid QGIS enums in UI)
        try:
            from qgis.core import QgsMapLayerProxyModel

            self.geologyLayerComboBox.setFilters(QgsMapLayerProxyModel.PolygonLayer)
            self.contactsLayerComboBox.setFilters(QgsMapLayerProxyModel.LineLayer)
            self.structureLayerComboBox.setFilters(QgsMapLayerProxyModel.PointLayer)
            self.dtmLayerComboBox.setFilters(QgsMapLayerProxyModel.RasterLayer)
            # preserve allowEmptyLayer where UI set it
        except Exception:
            pass

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
        self.orientationTypeComboBox.setCurrentIndex(1)  # Default to Dip Direction
        self._guess_layers()

        # Set up field combo boxes
        self._setup_field_combo_boxes()

        # Initial state update
        self._on_algorithm_changed()

    def _guess_layers(self):
        """Automatically detect and set appropriate field names using ColumnMatcher."""
        from ...main.helpers import ColumnMatcher

        # Auto-detect geology fields
        geology_layer_names = get_layer_names(self.geologyLayerComboBox)

        geology_layer_matcher = ColumnMatcher(geology_layer_names)
        geology_layer_match = geology_layer_matcher.find_match('GEOLOGY')
        geology_layer = self.data_manager.find_layer_by_name(geology_layer_match)
        self.geologyLayerComboBox.setLayer(geology_layer)

        # Auto-detect structure fields
        structure_layer_names = get_layer_names(self.structureLayerComboBox)
        structure_layer_matcher = ColumnMatcher(structure_layer_names)
        structure_layer_match = structure_layer_matcher.find_match('STRUCTURE')
        structure_layer = self.data_manager.find_layer_by_name(structure_layer_match)
        self.structureLayerComboBox.setLayer(structure_layer)

        contact_layer_names = get_layer_names(self.contactsLayerComboBox)
        contact_layer_matcher = ColumnMatcher(contact_layer_names)
        contact_layer_match = contact_layer_matcher.find_match('CONTACTS')
        contact_layer = self.data_manager.find_layer_by_name(contact_layer_match)
        self.contactsLayerComboBox.setLayer(contact_layer)

        dem_layer_names = get_layer_names(self.dtmLayerComboBox)
        dem_layer_matcher = ColumnMatcher(dem_layer_names)
        dem_layer_match = dem_layer_matcher.find_match('DTM')
        if not dem_layer_match:
            dem_layer_match = dem_layer_matcher.find_match('DEM')
        print(dem_layer_match)
        dem_layer = self.data_manager.find_layer_by_name(dem_layer_match, layer_type=QgsRasterLayer)
        self.dtmLayerComboBox.setLayer(dem_layer)

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
        from ...main.helpers import ColumnMatcher

        layer = self.geologyLayerComboBox.currentLayer()
        self.unitNameFieldComboBox.setLayer(layer)
        self.minAgeFieldComboBox.setLayer(layer)
        self.maxAgeFieldComboBox.setLayer(layer)
        self.groupFieldComboBox.setLayer(layer)

        # Auto-detect appropriate fields
        if layer:
            fields = [field.name() for field in layer.fields()]
            matcher = ColumnMatcher(fields)

            # Auto-select best matches
            if unit_match := matcher.find_match('UNITNAME'):
                self.unitNameFieldComboBox.setField(unit_match)

            if min_age_match := matcher.find_match('MIN_AGE'):
                self.minAgeFieldComboBox.setField(min_age_match)

            if max_age_match := matcher.find_match('MAX_AGE'):
                self.maxAgeFieldComboBox.setField(max_age_match)

            if group_match := matcher.find_match('GROUP'):
                self.groupFieldComboBox.setField(group_match)

    def _on_structure_layer_changed(self):
        """Update field combo boxes when structure layer changes."""
        from ...main.helpers import ColumnMatcher

        layer = self.structureLayerComboBox.currentLayer()
        self.dipFieldComboBox.setLayer(layer)
        self.dipDirFieldComboBox.setLayer(layer)

        # Auto-detect appropriate fields
        if layer:
            fields = [field.name() for field in layer.fields()]
            matcher = ColumnMatcher(fields)

            # Auto-select best matches
            if dip_match := matcher.find_match('DIP'):
                self.dipFieldComboBox.setField(dip_match)

            if dipdir_match := matcher.find_match('DIPDIR'):
                self.dipDirFieldComboBox.setField(dipdir_match)

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
        from ...main.m2l_api import sort_stratigraphic_column

        # Validate inputs
        if not self.geologyLayerComboBox.currentLayer():
            QMessageBox.warning(self, "Missing Input", "Please select a geology layer.")
            return

        if not self.contactsLayerComboBox.currentLayer():
            QMessageBox.warning(self, "Missing Input", "Please select a contacts layer.")
            return

        algorithm_index = self.sortingAlgorithmComboBox.currentIndex()
        algorithm_name = self.sorting_algorithms[algorithm_index]
        is_observation_projections = algorithm_index == 5

        if is_observation_projections:
            if not self.structureLayerComboBox.currentLayer():
                QMessageBox.warning(
                    self,
                    "Missing Input",
                    "Structure layer is required for observation projections.",
                )
                return
            if not self.dtmLayerComboBox.currentLayer():
                QMessageBox.warning(
                    self, "Missing Input", "DTM layer is required for observation projections."
                )
                return

        # Run the sorter API
        try:
            kwargs = {
                'geology': self.geologyLayerComboBox.currentLayer(),
                'contacts': self.contactsLayerComboBox.currentLayer(),
                'sorting_algorithm': algorithm_name,
                'unit_name_field': self.unitNameFieldComboBox.currentField(),
                'updater': lambda msg: QMessageBox.information(self, "Progress", msg),
            }

            # Add optional fields
            min_age_field = self.minAgeFieldComboBox.currentField()
            if min_age_field:
                kwargs['min_age_field'] = min_age_field

            max_age_field = self.maxAgeFieldComboBox.currentField()
            if max_age_field:
                kwargs['max_age_field'] = max_age_field

            group_field = self.groupFieldComboBox.currentField()
            if group_field:
                kwargs['group_field'] = group_field

            if is_observation_projections:
                kwargs['structure'] = self.structureLayerComboBox.currentLayer()
                kwargs['dip_field'] = self.dipFieldComboBox.currentField()
                kwargs['dipdir_field'] = self.dipDirFieldComboBox.currentField()
                kwargs['orientation_type'] = self.orientation_types[
                    self.orientationTypeComboBox.currentIndex()
                ]
                kwargs['dtm'] = self.dtmLayerComboBox.currentLayer()

            result = sort_stratigraphic_column(**kwargs)

            if result and len(result) > 0:
                QMessageBox.information(
                    self,
                    "Success",
                    f"Stratigraphic column created successfully! ({len(result)} units)",
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
