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

    def onFaultFieldChanged(self, field):
        name_field = self.faultNameField.currentField()
        dip_field = self.faultDipField.currentField()
        displacement_field = self.faultDisplacementField.currentField()
        layer = self.faultNameField.layer()

        if name_field and layer:
            self._faults = {}
            for feature in layer.getFeatures():
                self._faults[str(feature[name_field])] = {
                    'fault_dip': feature.attributeMap().get(dip_field, 90),
                    'displacement': feature.attributeMap().get(
                        displacement_field, 0.1 * feature.geometry().length()
                    ),
                    'fault_centre': {
                        'x': feature.geometry().centroid().asPoint().x(),
                        'y': feature.geometry().centroid().asPoint().y(),
                    },
                    'major_axis': feature.geometry().length(),
                    'intermediate_axis': feature.geometry().length(),
                    'minor_axis': feature.geometry().length() / 3,
                    'active': True,
                    "azimuth": calculateAverageAzimuth(feature.geometry()),
                    "fault_pitch": feature.attributeMap().get('pitch', 90),
                    "crs": layer.crs().authid(),
                }
