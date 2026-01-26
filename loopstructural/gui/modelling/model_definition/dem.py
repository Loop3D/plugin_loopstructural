import os

from PyQt5.QtWidgets import QWidget
from qgis.core import QgsMapLayerProxyModel
from qgis.PyQt import uic

from ...main.helpers import ColumnMatcher, get_layer_names


class DEMWidget(QWidget):
    def __init__(self, parent=None, data_manager=None):
        self.data_manager = data_manager
        super().__init__(parent)
        ui_path = os.path.join(os.path.dirname(__file__), "dem.ui")
        uic.loadUi(ui_path, self)
        self.demLayerQgsMapLayerComboBox.setFilters(QgsMapLayerProxyModel.RasterLayer)
        self.useDEMCheckBox.stateChanged.connect(self.onUseDEMClicked)
        self.elevationQgsDoubleSpinBox.valueChanged.connect(self.onElevationChanged)
        self.onElevationChanged()
        self.data_manager.set_dem_callback(self.set_dem_layer)
        self._guess_layer()
        self._restore_selection()

    def set_dem_layer(self, layer):
        """Set the DEM layer in the combo box."""
        if layer:
            self.demLayerQgsMapLayerComboBox.setLayer(layer)
            self.useDEMCheckBox.setChecked(True)
        else:
            self.demLayerQgsMapLayerComboBox.setCurrentIndex(-1)
            self.useDEMCheckBox.setChecked(False)
        self._persist_selection()


    def onUseDEMClicked(self):
        if self.useDEMCheckBox.isChecked():
            self.demLayerQgsMapLayerComboBox.setEnabled(True)
            self.elevationQgsDoubleSpinBox.setEnabled(False)
            self.data_manager.set_use_dem(True)
            self.onDEMLayerChanged()
        else:
            self.demLayerQgsMapLayerComboBox.setEnabled(False)
            self.elevationQgsDoubleSpinBox.setEnabled(True)
            self.data_manager.set_dem_layer(None)
            self.data_manager.set_elevation(self.elevationQgsDoubleSpinBox.value())
            self.data_manager.set_use_dem(False)

    def onDEMLayerChanged(self):
        """Handle changes to the DEM layer selection."""
        selected_layer = self.demLayerQgsMapLayerComboBox.currentLayer()
        if selected_layer:
            self.data_manager.set_dem_layer(selected_layer)
        else:
            self.data_manager.set_dem_layer(None)
        self.data_manager.set_use_dem(True)
        self._persist_selection()

    def onElevationChanged(self):
        """Handle changes to the elevation value."""
        elevation = self.elevationQgsDoubleSpinBox.value()
        self.data_manager.set_elevation(elevation)
        self.data_manager.set_use_dem(False)

    def _guess_layer(self):
        if not self.data_manager:
            return
        layer_names = get_layer_names(self.demLayerQgsMapLayerComboBox)
        matcher = ColumnMatcher(layer_names)
        match = matcher.find_match('DEM') or matcher.find_match('DTM')
        if match:
            layer = self.data_manager.find_layer_by_name(match)
            if layer:
                self.demLayerQgsMapLayerComboBox.setLayer(layer)

    def _persist_selection(self):
        if not self.data_manager:
            return
        settings = {
            'dem_layer': (
                self.demLayerQgsMapLayerComboBox.currentLayer().name()
                if self.demLayerQgsMapLayerComboBox.currentLayer()
                else None
            ),
            'use_dem': self.useDEMCheckBox.isChecked(),
            'elevation': self.elevationQgsDoubleSpinBox.value(),
        }
        self.data_manager.set_widget_settings('dem_widget', settings)

    def _restore_selection(self):
        if not self.data_manager:
            return
        settings = self.data_manager.get_widget_settings('dem_widget', {})
        if not settings:
            return
        if layer_name := settings.get('dem_layer'):
            layer = self.data_manager.find_layer_by_name(layer_name)
            if layer:
                self.demLayerQgsMapLayerComboBox.setLayer(layer)
        if 'use_dem' in settings:
            self.useDEMCheckBox.setChecked(settings['use_dem'])
        if 'elevation' in settings:
            self.elevationQgsDoubleSpinBox.setValue(settings['elevation'])
