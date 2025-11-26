"""Widget for extracting basal contacts."""

import os

from PyQt5.QtWidgets import QMessageBox, QWidget
from qgis.PyQt import uic

from loopstructural.gui.modelling.model_definition import fault_layers

from ...main.m2l_api import extract_basal_contacts


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
        else:
            # Ensure combo boxes are cleared if no geology layer selected
            try:
                self.unitNameFieldComboBox.setLayer(None)
            except Exception:
                pass

    def _on_geology_layer_changed(self):
        """Update field combo boxes when geology layer changes."""
        layer = self.geologyLayerComboBox.currentLayer()
        self.unitNameFieldComboBox.setLayer(layer)

    def _run_extractor(self):
        """Run the basal contacts extraction algorithm."""
        # Validate inputs
        if not self.geologyLayerComboBox.currentLayer():
            QMessageBox.warning(self, "Missing Input", "Please select a geology layer.")
            return

        # Parse ignore units
        ignore_units = []
        if self.ignoreUnitsLineEdit.text().strip():
            ignore_units = [
                unit.strip() for unit in self.ignoreUnitsLineEdit.text().split(',') if unit.strip()
            ]
        geology = self.geologyLayerComboBox.currentLayer()
        unit_name_field = self.unitNameFieldComboBox.currentField()
        faults = self.faultsLayerComboBox.currentLayer()
        stratigraphic_order = (
            self.data_manager._stratigraphic_column.get_unit_names() if self.data_manager else []
        )
        extract_basal_contacts(
            geology=geology,
            stratigraphic_order=stratigraphic_order,
            faults=faults,
            ignore_units=ignore_units,
            unit_name_field=unit_name_field,
            all_contacts=False,
            updater=lambda message: QMessageBox.information(self, "Extraction Progress", message),
        )

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
        
        if 'ignore_units' in params and params['ignore_units']:
            self.ignoreUnitsLineEdit.setText(', '.join(params['ignore_units']))
