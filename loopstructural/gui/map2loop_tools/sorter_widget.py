"""Widget for running the automatic stratigraphic sorter."""

import os

from PyQt5.QtWidgets import QMessageBox, QWidget
from qgis.core import QgsProject, QgsRasterLayer, QgsVectorFileWriter
from qgis.PyQt import uic

from loopstructural.main.helpers import get_layer_names
from loopstructural.main.m2l_api import PARAMETERS_DICTIONARY, SORTER_LIST
from loopstructural.toolbelt.preferences import PlgOptionsManager


class SorterWidget(QWidget):
    """Widget for configuring and running the automatic stratigraphic sorter.

    This widget provides a GUI interface for the map2loop stratigraphic
    sorting algorithms.
    """

    def __init__(self, parent=None, data_manager=None, debug_manager=None):
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
        self._debug = debug_manager

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
        self.sorting_algorithms = list(SORTER_LIST.keys())
        self.sortingAlgorithmComboBox.addItems(self.sorting_algorithms)
        # Set default to 'Age based' if present, else fallback to first
        try:
            age_based_index = self.sorting_algorithms.index('Age based')
        except ValueError:
            age_based_index = 0
        self.sortingAlgorithmComboBox.setCurrentIndex(age_based_index)

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

    def set_debug_manager(self, debug_manager):
        """Attach a debug manager instance."""
        self._debug = debug_manager

    def _export_layer_for_debug(self, layer, name_prefix: str):
        # Prefer DebugManager.export_layer
        try:
            if getattr(self, '_debug', None) and hasattr(self._debug, 'export_layer'):
                return self._debug.export_layer(layer, name_prefix)

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
        dem_layer = self.data_manager.find_layer_by_name(dem_layer_match, layer_type=QgsRasterLayer)
        self.dtmLayerComboBox.setLayer(dem_layer)

    def _setup_field_combo_boxes(self):
        """Set up field combo boxes to link to their respective layers."""
        self.unitNameFieldComboBox.setLayer(self.geologyLayerComboBox.currentLayer())
        self.minAgeFieldComboBox.setLayer(self.geologyLayerComboBox.currentLayer())
        self.maxAgeFieldComboBox.setLayer(self.geologyLayerComboBox.currentLayer())
        self.dipFieldComboBox.setLayer(self.structureLayerComboBox.currentLayer())
        self.dipDirFieldComboBox.setLayer(self.structureLayerComboBox.currentLayer())

    def _on_geology_layer_changed(self):
        """Update field combo boxes when geology layer changes."""
        from ...main.helpers import ColumnMatcher

        layer = self.geologyLayerComboBox.currentLayer()
        self.unitNameFieldComboBox.setLayer(layer)
        self.minAgeFieldComboBox.setLayer(layer)
        self.maxAgeFieldComboBox.setLayer(layer)

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
        """Update UI based on selected sorting algorithm and map2loop requirements."""
        algorithm_index = self.sortingAlgorithmComboBox.currentIndex()
        algorithm_name = self.sorting_algorithms[algorithm_index]
        # Import map2loop's required arguments for sorters
        try:
            from map2loop.project import REQUIRED_ARGUMENTS as M2L_REQUIRED_ARGUMENTS
        except ImportError:
            M2L_REQUIRED_ARGUMENTS = {}
        # Fallback to PARAMETERS_DICTIONARY if not found
        required_fields = M2L_REQUIRED_ARGUMENTS.get(algorithm_name) or PARAMETERS_DICTIONARY.get(
            algorithm_name, []
        )

        # Hide all relevant widgets by default
        self.minAgeFieldLabel.setVisible(False)
        self.minAgeFieldComboBox.setVisible(False)
        self.maxAgeFieldLabel.setVisible(False)
        self.maxAgeFieldComboBox.setVisible(False)
        self.unitName1FieldLabel.setVisible(False)
        self.unitName1FieldComboBox.setVisible(False)
        self.unitName2FieldLabel.setVisible(False)
        self.unitName2FieldComboBox.setVisible(False)

        self.contactsLayerLabel.setVisible(False)
        self.contactsLayerComboBox.setVisible(False)
        self.structureLayerLabel.setVisible(False)
        self.structureLayerComboBox.setVisible(False)
        self.dipFieldLabel.setVisible(False)
        self.dipFieldComboBox.setVisible(False)
        self.dipDirFieldLabel.setVisible(False)
        self.dipDirFieldComboBox.setVisible(False)
        self.orientationTypeLabel.setVisible(False)
        self.orientationTypeComboBox.setVisible(False)
        self.dtmLayerLabel.setVisible(False)
        self.dtmLayerComboBox.setVisible(False)

        # Show widgets based on required fields
        geology_layer = self.geologyLayerComboBox.currentLayer()
        if 'min_age_column' in required_fields or 'min_age_field' in required_fields:
            self.minAgeFieldLabel.setVisible(True)
            self.minAgeFieldComboBox.setVisible(True)
            self.minAgeFieldComboBox.setLayer(geology_layer)
        if 'max_age_column' in required_fields or 'max_age_field' in required_fields:
            self.maxAgeFieldLabel.setVisible(True)
            self.maxAgeFieldComboBox.setVisible(True)
            self.maxAgeFieldComboBox.setLayer(geology_layer)
        if 'unitname1_column' in required_fields or 'unitname_1' in required_fields:
            self.unitName1FieldLabel.setVisible(True)
            self.unitName1FieldComboBox.setVisible(True)
            self.unitName1FieldComboBox.setLayer(self.contactsLayerComboBox.currentLayer())
        if 'unitname2_column' in required_fields or 'unitname_2' in required_fields:
            self.unitName2FieldLabel.setVisible(True)
            self.unitName2FieldComboBox.setVisible(True)
            self.unitName2FieldComboBox.setLayer(self.contactsLayerComboBox.currentLayer())

        if 'contacts' in required_fields or 'contacts_layer' in required_fields:
            self.contactsLayerLabel.setVisible(True)
            self.contactsLayerComboBox.setVisible(True)
        if 'structure' in required_fields or 'structure_layer' in required_fields:
            self.structureLayerLabel.setVisible(True)
            self.structureLayerComboBox.setVisible(True)
            self.dipFieldLabel.setVisible(True)
            self.dipFieldComboBox.setVisible(True)
            self.dipDirFieldLabel.setVisible(True)
            self.dipDirFieldComboBox.setVisible(True)
            self.orientationTypeLabel.setVisible(True)
            self.orientationTypeComboBox.setVisible(True)
            self.dtmLayerLabel.setVisible(True)
            self.dtmLayerComboBox.setVisible(True)

        # Optionally, handle any additional custom fields from map2loop
        # (Add more widget visibility logic here if new fields are added in map2loop)

    def _run_sorter(self):
        """Run the stratigraphic sorter algorithm."""
        from ...main.m2l_api import sort_stratigraphic_column

        self._log_params("sorter_widget_run")

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

            if is_observation_projections:
                kwargs['structure'] = self.structureLayerComboBox.currentLayer()
                kwargs['dip_field'] = self.dipFieldComboBox.currentField()
                kwargs['dipdir_field'] = self.dipDirFieldComboBox.currentField()
                kwargs['orientation_type'] = self.orientation_types[
                    self.orientationTypeComboBox.currentIndex()
                ]
                kwargs['dtm'] = self.dtmLayerComboBox.currentLayer()

            result = sort_stratigraphic_column(
                **kwargs,
                debug_manager=self._debug,
            )
            if self._debug and self._debug.is_debug():
                try:
                    payload = "\n".join(result) if result else ""
                    self._debug.save_debug_file("sorter_result.txt", payload.encode("utf-8"))
                except Exception as err:
                    self._debug.plugin.log(
                        message=f"[map2loop] Failed to save sorter debug output: {err}",
                        log_level=2,
                    )
            if result and len(result) > 0:
                # Clear and update stratigraphic column in data_manager
                self.data_manager.clear_stratigraphic_column()
                for unit in result:
                    self.data_manager.add_to_stratigraphic_column({'name': unit, 'type': 'unit'})
                self.data_manager.stratigraphic_column_callback()
                QMessageBox.information(
                    self,
                    "Success",
                    f"Stratigraphic column created successfully! ({len(result)} units)",
                )
            else:
                QMessageBox.warning(self, "Error", "Failed to create stratigraphic column.")

        except Exception as e:
            if self._debug:
                self._debug.plugin.log(
                    message=f"[map2loop] Sorter run failed: {e}",
                    log_level=2,
                )
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
        algorithm_index = self.sortingAlgorithmComboBox.currentIndex()
        is_observation_projections = algorithm_index == 5

        params = {
            'sorting_algorithm': algorithm_index,
            'geology_layer': self.geologyLayerComboBox.currentLayer(),
            'unit_name_field': self.unitNameFieldComboBox.currentField(),
            'min_age_field': self.minAgeFieldComboBox.currentField(),
            'max_age_field': self.maxAgeFieldComboBox.currentField(),
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
