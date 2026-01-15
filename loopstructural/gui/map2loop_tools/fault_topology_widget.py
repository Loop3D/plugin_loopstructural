"""Widget for calculating fault topology from a fault layer."""

import os

import geopandas as gpd
from PyQt5.QtWidgets import QDialog, QMessageBox
from qgis.PyQt import uic


class FaultTopologyWidget(QDialog):
    def _guess_fault_layer_and_field(self):
        """Attempt to auto-select the fault layer and ID field based on common names."""
        try:
            from ...main.helpers import ColumnMatcher, get_layer_names
        except ImportError:
            return
        # Guess fault layer
        fault_layer_names = get_layer_names(self.faultLayerComboBox)
        fault_matcher = ColumnMatcher(fault_layer_names)
        fault_layer_match = fault_matcher.find_match('FAULTS')
        if fault_layer_match and hasattr(self, 'data_manager') and self.data_manager:
            fault_layer = self.data_manager.find_layer_by_name(fault_layer_match)
            self.faultLayerComboBox.setLayer(fault_layer)
        # Guess ID field
        layer = self.faultLayerComboBox.currentLayer()
        if layer:
            fields = [field.name() for field in layer.fields()]
            matcher = ColumnMatcher(fields)
            for key in ["ID", "NAME", "FNAME", "id", "name", "fname"]:
                match = matcher.find_match(key)
                if match:
                    self.faultIdFieldComboBox.setField(match)
                    break

    """Widget for calculating fault topology from a fault layer."""

    def __init__(self, parent=None, data_manager=None):
        super().__init__(parent)
        self.data_manager = data_manager
        # Load the UI file
        ui_path = os.path.join(os.path.dirname(__file__), "fault_topology_widget.ui")
        uic.loadUi(ui_path, self)
        # Set filter for fault layer selection
        try:
            from qgis.core import QgsMapLayerProxyModel

            self.faultLayerComboBox.setFilters(QgsMapLayerProxyModel.LineLayer)
            self.faultLayerComboBox.layerChanged.connect(self._on_fault_layer_changed)
        except Exception:
            pass
        self.runButton.clicked.connect(self._run_topology)
        self._guess_fault_layer_and_field()

    def _on_fault_layer_changed(self):
        layer = self.faultLayerComboBox.currentLayer()
        self.faultIdFieldComboBox.setLayer(layer)
        # Optionally auto-select a likely ID field
        if layer:
            fields = [field.name() for field in layer.fields()]
            for name in ["id", "ID", "fault_id", "FaultID", "FaultId"]:
                if name in fields:
                    self.faultIdFieldComboBox.setField(name)
                    break

    def _run_topology(self):
        layer = self.faultLayerComboBox.currentLayer()
        if not layer:
            QMessageBox.warning(self, "Missing Input", "Please select a fault layer.")
            return
        id_field = self.faultIdFieldComboBox.currentField()
        if not id_field:
            QMessageBox.warning(self, "Missing Input", "Please select a fault ID field.")
            return
        # Convert to GeoDataFrame
        gdf = gpd.GeoDataFrame.from_features(layer.getFeatures())
        if gdf.empty:
            QMessageBox.warning(self, "No Data", "The selected layer has no features.")
            return
        # Rename the selected ID field to 'ID' for Topology class compatibility
        if id_field != "ID":
            gdf = gdf.rename(columns={id_field: "ID"})
        # Use map2loop Topology class
        try:
            from map2loop.topology import Topology
        except ImportError:
            QMessageBox.critical(self, "Error", "Could not import map2loop Topology class.")
            return
        topology = Topology(geology_data=None, fault_data=gdf)
        df = topology.fault_fault_relationships
        # if self.data_manager is not None:
        #     self.data_manager.
        # Show or add to project
        # addGeoDataFrameToproject(gdf, "Input Faults")
        # addGeoDataFrameToproject(df, "Fault Topology Table")
        QMessageBox.information(self, "Success", f"Calculated fault topology for {len(df)} pairs.")
