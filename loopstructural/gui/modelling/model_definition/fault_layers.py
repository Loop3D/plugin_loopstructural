import os

from PyQt5.QtWidgets import QWidget
from qgis.core import QgsFieldProxyModel, QgsMapLayerProxyModel, QgsWkbTypes
from qgis.PyQt import uic



class FaultLayersWidget(QWidget):
    def __init__(self, parent=None, data_manager=None):
        self.data_manager = data_manager
        super().__init__(parent)
        ui_path = os.path.join(os.path.dirname(__file__), "fault_layers.ui")
        uic.loadUi(ui_path, self)
        self.faultTraceLayer.setFilters(
            QgsMapLayerProxyModel.LineLayer | QgsMapLayerProxyModel.PointLayer
        )
        self.faultTraceLayer.setAllowEmptyLayer(True)
        self.faultDipField.setFilters(QgsFieldProxyModel.Numeric)
        # fault displacement field can only be double or int
        self.faultDisplacementField.setFilters(QgsFieldProxyModel.Numeric)
        self.faultTraceLayer.layerChanged.connect(self.onFaultTraceLayerChanged)
        self.faultNameField.fieldChanged.connect(self.onFaultFieldChanged)
        self.faultDipField.fieldChanged.connect(self.onFaultFieldChanged)
        self.faultDisplacementField.fieldChanged.connect(self.onFaultFieldChanged)
        self.data_manager.set_fault_trace_layer_callback(self.set_fault_trace_layer)
        self.useZCoordinateCheckBox.stateChanged.connect(self.onUseZCoordinateClicked)
        self.useZCoordinateCheckBox.stateChanged.connect(self.onFaultFieldChanged)
        self.useZCoordinate = False
    def enableZCheckbox(self, enable):
        """Enable or disable the Z coordinate checkbox."""
        self.useZCoordinateCheckBox.setEnabled(enable)
        if enable:
            self.useZCoordinateCheckBox.setChecked(self.useZCoordinate)
        else:
            self.useZCoordinateCheckBox.setChecked(False)
    def onUseZCoordinateClicked(self):
        """Handle changes to the Z coordinate checkbox."""
        self.useZCoordinate = self.useZCoordinateCheckBox.isChecked()
    def set_fault_trace_layer(self, layer, fault_name_field=None, fault_dip_field=None, fault_displacement_field=None):
        self.faultTraceLayer.setLayer(layer)
        if fault_name_field:
            self.faultNameField.setField(fault_name_field)
        if fault_dip_field:
            self.faultDipField.setField(fault_dip_field)
        if fault_displacement_field:
            self.faultDisplacementField.setField(fault_displacement_field)
    def onFaultTraceLayerChanged(self, layer):
        self.faultNameField.setLayer(layer)
        self.faultDipField.setLayer(layer)
        self.faultDisplacementField.setLayer(layer)
        if layer is not None and layer.isValid():
            if layer.wkbType() != QgsWkbTypes.Unknown:
                
                has_z = QgsWkbTypes.hasZ(layer.wkbType())
                print(f"Layer {layer.name()} has Z coordinate: {has_z}")
                self.enableZCheckbox(has_z)
    def onFaultFieldChanged(self):
        self.data_manager.set_fault_trace_layer(
            self.faultTraceLayer.currentLayer(),
            fault_name_field = self.faultNameField.currentField(),
            fault_dip_field = self.faultDipField.currentField(),
            fault_displacement_field = self.faultDisplacementField.currentField(),
            use_z_coordinate=self.useZCoordinate
        )
