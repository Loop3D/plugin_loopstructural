import os

from PyQt5.QtWidgets import QWidget
from qgis.core import QgsFieldProxyModel, QgsMapLayerProxyModel
from qgis.PyQt import uic

from ....main.geometry.calculateLineAzimuth import calculateAverageAzimuth


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

    def onFaultTraceLayerChanged(self, layer):
        self.faultNameField.setLayer(layer)
        self.faultDipField.setLayer(layer)
        self.faultDisplacementField.setLayer(layer)

    def onFaultFieldChanged(self):
        self.data_manager.set_fault_trace_layer(
            self.faultTraceLayer.currentLayer(),
            fault_name_field = self.faultNameField.currentField(),
            fault_dip_field = self.faultDipField.currentField(),
            fault_displacement_field = self.faultDisplacementField.currentField(),
        )