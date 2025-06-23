from PyQt5.QtWidgets import (
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .loop_pyvistaqt_wrapper import LoopPyVistaQTPlotter
from .object_list_widget import ObjectListWidget


class VisualisationWidget(QWidget):
    def __init__(self, parent: QWidget = None, mapCanvas=None, logger=None):
        super().__init__(parent)
        # Load the UI file for Tab 1
        self.mapCanvas = mapCanvas
        self.logger = logger

        mainLayout = QVBoxLayout(self)
        self.setLayout(mainLayout)

        # Create a splitter to separate the viewer and the object list
        splitter = QSplitter(self)
        mainLayout.addWidget(splitter)

        # Create the object selection sidebar

        # Create the viewer
        self.plotter = LoopPyVistaQTPlotter(parent)
        # self.plotter.add_axes()
        
        self.objectList = ObjectListWidget(viewer=self.plotter)
        splitter.addWidget(self.objectList)
        splitter.addWidget(self.plotter)
