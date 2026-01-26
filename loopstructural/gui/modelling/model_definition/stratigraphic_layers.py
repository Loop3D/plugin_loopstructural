import os

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget
from qgis.core import QgsMapLayerProxyModel, QgsWkbTypes
from qgis.PyQt import uic

from ...main.helpers import ColumnMatcher, get_layer_names


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
        self.structuralDataUnitName.fieldChanged.connect(self.onStructuralDataFieldChanged)
        self.orientationType.currentIndexChanged.connect(self.onOrientationTypeChanged)
        self.data_manager.set_basal_contacts_callback(self.set_basal_contacts)
        self.data_manager.set_structural_orientations_callback(self.set_orientations_layer)
        self.basal_contacts_use_z = False
        self.structural_points_use_z = False
        self.useBasalContactsZCoordinatesCheckBox.stateChanged.connect(
            lambda: self.enableBasalContactsZCheckBox(
                self.useBasalContactsZCoordinatesCheckBox.isChecked()
            )
        )
        self.useBasalContactsZCoordinatesCheckBox.stateChanged.connect(
            self.onStructuralDataFieldChanged
        )
        self.useStructuralPointsZCoordinatesCheckBox.stateChanged.connect(
            lambda: self.enableStructuralPointsZCheckBox(
                self.useStructuralPointsZCoordinatesCheckBox.isChecked()
            )
        )
        self.useStructuralPointsZCoordinatesCheckBox.stateChanged.connect(
            self.onStructuralDataFieldChanged
        )
        self._guess_layers_and_fields()
        self._restore_selection()

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

                self.enableBasalContactsZCheckBox(has_z)
            else:
                self.data_manager.logger(message="Unknown geometry type.", log_level=2)
        else:
            self.enableBasalContactsZCheckBox(False)
        if unitname_field:
            self.unitNameField.setField(unitname_field)
        self.basal_contacts_use_z = use_z_coordinate
        self.useBasalContactsZCoordinatesCheckBox.setChecked(use_z_coordinate)

    def set_orientations_layer(
        self,
        layer,
        strike_field=None,
        dip_field=None,
        unitname_field=None,
        orientation_type=None,
        use_z_coordinate=False,
    ):
        self.structuralDataLayer.setLayer(layer)
        if layer is not None and layer.isValid():
            if layer.wkbType() != QgsWkbTypes.Unknown:
                has_z = QgsWkbTypes.hasZ(layer.wkbType())
                self.enableStructuralPointsZCheckBox(has_z)
            else:
                self.data_manager.logger(message="Unknown geometry type.", level=2)
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
        self._persist_selection()

    def onOrientationTypeChanged(self, index):
        if index == 0:
            self.orientationLabel.setText("Strike")
        else:
            self.orientationLabel.setText("Dip Direction")

    def onStructuralDataLayerChanged(self, layer):
        self.orientationField.setLayer(layer)
        self.dipField.setLayer(layer)
        self.structuralDataUnitName.setLayer(layer)
        if self.dipField.currentField() is None or self.orientationField.currentField() is None:
            return
        self.data_manager.set_structural_orientations(
            layer,
            self.orientationField.currentField(),
            self.dipField.currentField(),
            self.structuralDataUnitName.currentField(),
            use_z_coordinate=self.structural_points_use_z,
        )

    def onStructuralDataFieldChanged(self, field):
        if self.structuralDataLayer.currentLayer() is None:
            return
        if self.orientationField.currentField() is None or self.dipField.currentField() is None:
            return
        if self.structuralDataUnitName.currentField() is None:
            return

        self.data_manager.set_structural_orientations(
            self.structuralDataLayer.currentLayer(),
            self.orientationField.currentField(),
            self.dipField.currentField(),
            self.structuralDataUnitName.currentField(),
            self.orientationType.currentText(),
            use_z_coordinate=self.structural_points_use_z,
        )
        self._persist_selection()
        # self.updateDataManager()

    def onUnitFieldChanged(self, field):
        self.data_manager.set_basal_contacts(
            self.basalContactsLayer.currentLayer(),
            field,
            use_z_coordinate=self.basal_contacts_use_z,
        )
        self._persist_selection()

        # self.updateDataManager()

    def _guess_layers_and_fields(self):
        if not self.data_manager:
            return
        # Basal contacts
        basal_names = get_layer_names(self.basalContactsLayer)
        basal_matcher = ColumnMatcher(basal_names)
        basal_match = basal_matcher.find_match('BASAL_CONTACTS')
        if basal_match:
            layer = self.data_manager.find_layer_by_name(basal_match)
            if layer:
                self.basalContactsLayer.setLayer(layer)
                fields = [f.name() for f in layer.fields()]
                fmatcher = ColumnMatcher(fields)
                if unit_match := fmatcher.find_match('UNITNAME'):
                    self.unitNameField.setField(unit_match)
        # Structural data
        structural_names = get_layer_names(self.structuralDataLayer)
        structural_matcher = ColumnMatcher(structural_names)
        structural_match = structural_matcher.find_match('STRUCTURE') or structural_matcher.find_match(
            'ORIENTATION'
        )
        if structural_match:
            layer = self.data_manager.find_layer_by_name(structural_match)
            if layer:
                self.structuralDataLayer.setLayer(layer)
                fields = [f.name() for f in layer.fields()]
                fmatcher = ColumnMatcher(fields)
                if strike_match := fmatcher.find_match('STRIKE') or fmatcher.find_match('DIPDIR'):
                    self.orientationField.setField(strike_match)
                if dip_match := fmatcher.find_match('DIP'):
                    self.dipField.setField(dip_match)
                if unit_match := fmatcher.find_match('UNITNAME'):
                    self.structuralDataUnitName.setField(unit_match)

    def _persist_selection(self):
        if not self.data_manager:
            return
        settings = {
            'basal_layer': self.basalContactsLayer.currentLayer().name()
            if self.basalContactsLayer.currentLayer()
            else None,
            'structural_layer': self.structuralDataLayer.currentLayer().name()
            if self.structuralDataLayer.currentLayer()
            else None,
            'unit_name_field': self.unitNameField.currentField(),
            'orientation_field': self.orientationField.currentField(),
            'dip_field': self.dipField.currentField(),
            'structural_unit_field': self.structuralDataUnitName.currentField(),
            'orientation_type': self.orientationType.currentText(),
            'use_basal_z': self.useBasalContactsZCoordinatesCheckBox.isChecked(),
            'use_structural_z': self.useStructuralPointsZCoordinatesCheckBox.isChecked(),
        }
        self.data_manager.set_widget_settings('stratigraphic_layers_widget', settings)

    def _restore_selection(self):
        if not self.data_manager:
            return
        settings = self.data_manager.get_widget_settings('stratigraphic_layers_widget', {})
        if not settings:
            return
        if layer_name := settings.get('basal_layer'):
            layer = self.data_manager.find_layer_by_name(layer_name)
            if layer:
                self.basalContactsLayer.setLayer(layer)
        if layer_name := settings.get('structural_layer'):
            layer = self.data_manager.find_layer_by_name(layer_name)
            if layer:
                self.structuralDataLayer.setLayer(layer)
        if field := settings.get('unit_name_field'):
            self.unitNameField.setField(field)
        if field := settings.get('orientation_field'):
            self.orientationField.setField(field)
        if field := settings.get('dip_field'):
            self.dipField.setField(field)
        if field := settings.get('structural_unit_field'):
            self.structuralDataUnitName.setField(field)
        if 'orientation_type' in settings:
            idx = self.orientationType.findText(settings['orientation_type'], Qt.MatchFixedString)
            if idx >= 0:
                self.orientationType.setCurrentIndex(idx)
        if 'use_basal_z' in settings:
            self.useBasalContactsZCoordinatesCheckBox.setChecked(settings['use_basal_z'])
        if 'use_structural_z' in settings:
            self.useStructuralPointsZCoordinatesCheckBox.setChecked(settings['use_structural_z'])
