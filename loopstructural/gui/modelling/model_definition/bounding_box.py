import os

from PyQt5.QtWidgets import QWidget
from qgis.PyQt import uic


class BoundingBoxWidget(QWidget):
    def __init__(self, parent=None, data_manager=None):
        self.data_manager = data_manager
        super().__init__(parent)
        ui_path = os.path.join(os.path.dirname(__file__), "bounding_box.ui")
        uic.loadUi(ui_path, self)
        self.originXSpinBox.valueChanged.connect(lambda x: self.onChangeExtent({'xmin': x}))
        self.maxXSpinBox.valueChanged.connect(lambda x: self.onChangeExtent({'xmax': x}))
        self.originYSpinBox.valueChanged.connect(lambda y: self.onChangeExtent({'ymin': y}))
        self.maxYSpinBox.valueChanged.connect(lambda y: self.onChangeExtent({'ymax': y}))
        self.originZSpinBox.valueChanged.connect(lambda z: self.onChangeExtent({'zmin': z}))
        self.maxZSpinBox.valueChanged.connect(lambda z: self.onChangeExtent({'zmax': z}))
        self.useCurrentViewExtentButton.clicked.connect(self.useCurrentViewExtent)
        self.selectFromCurrentLayerButton.clicked.connect(self.selectFromCurrentLayer)
        self.data_manager.set_bounding_box_update_callback(self.set_bounding_box)
    def set_bounding_box(self, bounding_box):
        """
        Set the bounding box values in the UI.
        :param bounding_box: BoundingBox object with xmin, xmax, ymin, ymax, zmin, zmax attributes.
        """
        self.originXSpinBox.setValue(bounding_box.origin[0])
        self.maxXSpinBox.setValue(bounding_box.maximum[0])
        self.originYSpinBox.setValue(bounding_box.origin[1])
        self.maxYSpinBox.setValue(bounding_box.maximum[1])
        self.originZSpinBox.setValue(bounding_box.origin[2])
        self.maxZSpinBox.setValue(bounding_box.maximum[2])

    def useCurrentViewExtent(self):
        """
        Use the current view extent from the map canvas.
        This method should be connected to a button or action in the UI.
        """
        if self.data_manager.map_canvas:
            extent = self.data_manager.map_canvas.extent()
            self.originXSpinBox.setValue(extent.xMinimum())
            self.originYSpinBox.setValue(extent.yMinimum())
            self.originZSpinBox.setValue(0)
            self.maxXSpinBox.setValue(extent.xMaximum())
            self.maxYSpinBox.setValue(extent.yMaximum())
            self.maxZSpinBox.setValue(1000)

    def selectFromCurrentLayer(self):
        """
        Select the bounding box from the current layer.
        This method should be connected to a button or action in the UI.
        """
        layer = self.data_manager.map_canvas.currentLayer()
        if layer:
            extent = layer.extent()
            self.originXSpinBox.setValue(extent.xMinimum())
            self.originYSpinBox.setValue(extent.yMinimum())
            self.originZSpinBox.setValue(0)
            self.maxXSpinBox.setValue(extent.xMaximum())
            self.maxYSpinBox.setValue(extent.yMaximum())
            self.maxZSpinBox.setValue(1000)

    def onChangeExtent(self, value):
        self.data_manager.set_bounding_box(**value)
