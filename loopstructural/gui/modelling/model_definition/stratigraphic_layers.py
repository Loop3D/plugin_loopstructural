import os

from PyQt5.QtWidgets import QWidget
from qgis.core import QgsMapLayerProxyModel
from qgis.PyQt import uic


class StratigraphicLayersWidget(QWidget):
    def __init__(self, parent=None, data_manager=None):
        if data_manager is None:
            raise ValueError("data_manager must be provided")
        self.data_manager = data_manager
        super().__init__(parent)
        ui_path = os.path.join(os.path.dirname(__file__), "stratigraphic_layers.ui")
        uic.loadUi(ui_path, self)
        self.basalContactsLayer.setFilters(
            QgsMapLayerProxyModel.LineLayer | QgsMapLayerProxyModel.PointLayer
        )
        self.basalContactsLayer.setAllowEmptyLayer(True)
        # Structural data can only be points
        self.structuralDataLayer.setFilters(QgsMapLayerProxyModel.PointLayer)
        self.basalContactsLayer.setAllowEmptyLayer(True)
        self.basalContactsLayer.layerChanged.connect(self.onBasalContactsChanged)
        self.structuralDataLayer.layerChanged.connect(self.onStructuralDataLayerChanged)
        self.unitNameField.fieldChanged.connect(self.onUnitFieldChanged)
        self.orientationField.setLayer(self.structuralDataLayer.currentLayer())
        self.dipField.fieldChanged.connect(self.onStructuralDataFieldChanged)
        self.orientationField.fieldChanged.connect(self.onStructuralDataFieldChanged)
        self.structuralDataUnitName.setLayer(self.structuralDataLayer.currentLayer())
        self.orientationType.currentIndexChanged.connect(self.onOrientationTypeChanged)

    def onBasalContactsChanged(self, layer):
        self.unitNameField.setLayer(layer)
        self.data_manager.set_basal_contacts(layer, self.unitNameField.currentField())
    def onOrientationTypeChanged(self, index):
        if index == 0:
            self.orientationLabel.setText("Strike")
        else:
            self.orientationLabel.setText("Dip Direction")

    def onStructuralDataLayerChanged(self, layer):
        self.orientationField.setLayer(layer)
        self.dipField.setLayer(layer)
        self.structuralDataUnitName.setLayer(layer)
        self.data_manager.set_structural_orientations(
            layer,
            self.orientationField.currentField(),
            self.dipField.currentField(),
            self.structuralDataUnitName.currentField(),
        )
    def onStructuralDataFieldChanged(self, field):
        self.data_manager.set_structural_orientations(
            self.structuralDataLayer.currentLayer(),
            self.orientationField.currentField(),
            self.dipField.currentField(),
            self.structuralDataUnitName.currentField(),
            self.orientationType.currentText()
        )
        # self.updateDataManager()
    def onUnitFieldChanged(self, field):
        self.data_manager.set_basal_contacts(self.basalContactsLayer.currentLayer(), field)

        # self.updateDataManager()
