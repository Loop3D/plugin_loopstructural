import os

from PyQt5.QtWidgets import QWidget
from qgis.core import QgsMapLayerProxyModel, QgsWkbTypes
from qgis.PyQt import uic
from PyQt5.QtCore import Qt

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
        self.data_manager.set_basal_contacts_callback(self.set_basal_contacts)
        self.data_manager.set_structural_orientations_callback(self.set_orientations_layer)
        self.basal_contacts_use_z = False
        self.structural_points_use_z = False
        self.useBasalContactsZCoordinatesCheckBox.stateChanged.connect(lambda : self.enableBasalContactsZCheckBox(self.useBasalContactsZCoordinatesCheckBox.isChecked()))
        self.useBasalContactsZCoordinatesCheckBox.stateChanged.connect(self.onStructuralDataFieldChanged)
        self.useStructuralPointsZCoordinatesCheckBox.stateChanged.connect(lambda : self.enableStructuralPointsZCheckBox(self.useStructuralPointsZCoordinatesCheckBox.isChecked()))
        self.useStructuralPointsZCoordinatesCheckBox.stateChanged.connect(self.onStructuralDataFieldChanged)

    def enableBasalContactsZCheckBox(self, enable):
        self.useBasalContactsZCoordinatesCheckBox.setEnabled(enable)
        if enable:
            self.useBasalContactsZCoordinatesCheckBox.setChecked(self.basal_contacts_use_z)
        else:
            self.useBasalContactsZCoordinatesCheckBox.setChecked(False)
    def enableStructuralPointsZCheckBox(self, enable):
        self.useStructuralPointsZCoordinatesCheckBox.setEnabled(enable)
        if enable:
            self.useStructuralPointsZCoordinatesCheckBox.setChecked(self.structural_points_use_z)
        else:
            self.useStructuralPointsZCoordinatesCheckBox.setChecked(False)
    def set_basal_contacts(self, layer, unitname_field=None, use_z_coordinate=False):
        self.basalContactsLayer.setLayer(layer)
        if layer is not None and layer.isValid():
            if layer.wkbType() != QgsWkbTypes.Unknown:
                has_z = QgsWkbTypes.hasZ(layer.wkbType())
                self.data_manager.logger(message=f"Layer {layer.name()} has Z coordinate: {has_z}",log_level=2)
                self.enableBasalContactsZCheckBox(has_z)
            else:
                self.data_manager.logger(message="Unknown geometry type.",log_level=2)
        else:
            self.enableBasalContactsZCheckBox(False)
        if unitname_field:
            self.unitNameField.setField(unitname_field)
        self.basal_contacts_use_z = use_z_coordinate
        self.useBasalContactsZCoordinatesCheckBox.setChecked(use_z_coordinate)
    def set_orientations_layer(self, layer, strike_field=None, dip_field=None, unitname_field=None, orientation_type=None, use_z_coordinate=False):
        self.structuralDataLayer.setLayer(layer)
        if layer is not None and layer.isValid():
            if layer.wkbType() != QgsWkbTypes.Unknown:
                has_z = QgsWkbTypes.hasZ(layer.wkbType())
                self.data_manager.logger(message=f"Layer {layer.name()} has Z coordinate: {has_z}",level=2)
                self.enableStructuralPointsZCheckBox(has_z)
            else:
                self.data_manager.logger(message="Unknown geometry type.",level=2)
        else:
            self.enableStructuralPointsZCheckBox(False)
        if strike_field:
            self.orientationField.setField(strike_field)
        if dip_field:
            self.dipField.setField(dip_field)
        if unitname_field:
            self.structuralDataUnitName.setField(unitname_field)
        if orientation_type:
            index = self.orientationType.findText(orientation_type, Qt.MatchFixedString)
            if index >= 0:
                self.orientationType.setCurrentIndex(index)
        if use_z_coordinate:
            self.structural_points_use_z = use_z_coordinate
            self.useStructuralPointsZCoordinatesCheckBox.setChecked(use_z_coordinate)
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
            use_z_coordinate=self.structural_points_use_z,
        )
    def onStructuralDataFieldChanged(self, field):
        self.data_manager.set_structural_orientations(
            self.structuralDataLayer.currentLayer(),
            self.orientationField.currentField(),
            self.dipField.currentField(),
            self.structuralDataUnitName.currentField(),
            self.orientationType.currentText(),
            use_z_coordinate=self.structural_points_use_z
        )
        # self.updateDataManager()
    def onUnitFieldChanged(self, field):
        self.data_manager.set_basal_contacts(self.basalContactsLayer.currentLayer(), field, use_z_coordinate=self.basal_contacts_use_z)

        # self.updateDataManager()
