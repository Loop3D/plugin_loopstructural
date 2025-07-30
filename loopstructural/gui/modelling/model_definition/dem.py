import os

from PyQt5.QtWidgets import QWidget
from qgis.core import QgsMapLayerProxyModel
from qgis.PyQt import uic
from qgis.PyQt.QtWidgets import QSizePolicy


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

    def set_dem_layer(self, layer):
        """Set the DEM layer in the combo box."""
        # if layer:
        #     self.demLayerQgsMapLayerComboBox.setLayer(layer)
        pass

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

    def onElevationChanged(self):
        """Handle changes to the elevation value."""
        elevation = self.elevationQgsDoubleSpinBox.value()
        self.data_manager.set_elevation(elevation)
        self.data_manager.set_use_dem(False)
