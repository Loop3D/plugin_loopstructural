import os

from PyQt5.QtWidgets import QWidget
from qgis.core import QgsFieldProxyModel, QgsMapLayerProxyModel, QgsWkbTypes
from qgis.PyQt import uic

from ....main.helpers import ColumnMatcher, get_layer_names


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
        self._guess_layer_and_fields()
        self._restore_selection()

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

    def set_fault_trace_layer(
        self,
        layer,
        fault_name_field=None,
        fault_dip_field=None,
        fault_displacement_field=None,
        use_z_coordinate=False,
    ):
        self.faultTraceLayer.setLayer(layer)
        if fault_name_field:
            self.faultNameField.setField(fault_name_field)
        if fault_dip_field:
            self.faultDipField.setField(fault_dip_field)
        if fault_displacement_field:
            self.faultDisplacementField.setField(fault_displacement_field)
        if layer is not None and layer.isValid():
            if layer.wkbType() != QgsWkbTypes.Unknown:
                has_z = QgsWkbTypes.hasZ(layer.wkbType())
                self.enableZCheckbox(has_z)
                self.useZCoordinateCheckBox.setChecked(use_z_coordinate)
                self.useZCoordinate = use_z_coordinate
            else:
                self.data_manager.logger(message="Unknown geometry type.", log_level=2)

    def onFaultTraceLayerChanged(self, layer):
        self.faultNameField.setLayer(layer)
        self.faultDipField.setLayer(layer)
        self.faultDisplacementField.setLayer(layer)
        if layer is not None and layer.isValid():
            if layer.wkbType() != QgsWkbTypes.Unknown:

                has_z = QgsWkbTypes.hasZ(layer.wkbType())
                self.enableZCheckbox(has_z)
        if layer is None or not layer.isValid():
            self.data_manager.set_fault_trace_layer(
                None,
                fault_name_field=None,
                fault_dip_field=None,
                fault_displacement_field=None,
                use_z_coordinate=self.useZCoordinate,
            )
        self._persist_selection()

    def onFaultFieldChanged(self):
        self.data_manager.set_fault_trace_layer(
            self.faultTraceLayer.currentLayer(),
            fault_name_field=self.faultNameField.currentField(),
            fault_dip_field=self.faultDipField.currentField(),
            fault_displacement_field=self.faultDisplacementField.currentField(),
            use_z_coordinate=self.useZCoordinate,
        )
        self._persist_selection()

    def _guess_layer_and_fields(self):
        if not self.data_manager:
            return
        layer_names = get_layer_names(self.faultTraceLayer)
        matcher = ColumnMatcher(layer_names)
        match = matcher.find_match('FAULT')
        if match:
            layer = self.data_manager.find_layer_by_name(match)
            if layer:
                self.faultTraceLayer.setLayer(layer)
                fields = [field.name() for field in layer.fields()]
                field_matcher = ColumnMatcher(fields)
                if name_match := field_matcher.find_match('FAULT_NAME') or field_matcher.find_match(
                    'NAME'
                ):
                    self.faultNameField.setField(name_match)
                if dip_match := field_matcher.find_match('DIP'):
                    self.faultDipField.setField(dip_match)
                if disp_match := field_matcher.find_match(
                    'DISPLACEMENT'
                ) or field_matcher.find_match('SLIP'):
                    self.faultDisplacementField.setField(disp_match)

    def _persist_selection(self):
        if not self.data_manager:
            return
        settings = {
            'fault_layer': (
                self.faultTraceLayer.currentLayer().name()
                if self.faultTraceLayer.currentLayer()
                else None
            ),
            'fault_name_field': self.faultNameField.currentField(),
            'fault_dip_field': self.faultDipField.currentField(),
            'fault_displacement_field': self.faultDisplacementField.currentField(),
            'use_z': self.useZCoordinateCheckBox.isChecked(),
        }
        self.data_manager.set_widget_settings('fault_layers_widget', settings)

    def _restore_selection(self):
        if not self.data_manager:
            return
        settings = self.data_manager.get_widget_settings('fault_layers_widget', {})
        if not settings:
            return
        if layer_name := settings.get('fault_layer'):
            layer = self.data_manager.find_layer_by_name(layer_name)
            if layer:
                self.faultTraceLayer.setLayer(layer)
        if field := settings.get('fault_name_field'):
            self.faultNameField.setField(field)
        if field := settings.get('fault_dip_field'):
            self.faultDipField.setField(field)
        if field := settings.get('fault_displacement_field'):
            self.faultDisplacementField.setField(field)
        if 'use_z' in settings:
            self.useZCoordinateCheckBox.setChecked(settings['use_z'])
