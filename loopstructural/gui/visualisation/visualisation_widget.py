from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .loop_pyvistaqt_wrapper import LoopPyVistaQTPlotter
from .object_list_widget import ObjectListWidget
from .feature_list_widget import FeatureListWidget


class VisualisationWidget(QWidget):
    def __init__(self, parent: QWidget = None, mapCanvas=None, logger=None, model_manager=None):

        super().__init__(parent)
        # Load the UI file for Tab 1
        self.mapCanvas = mapCanvas
        self.logger = logger
        self.model_manager = model_manager

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

        # Modify layout to stack object list and feature list vertically
        sidebarSplitter = QSplitter(Qt.Vertical, self)
        sidebarSplitter.addWidget(self.objectList)

        # Create the feature list widget
        self.featureList = FeatureListWidget(model_manager=self.model_manager, viewer=self.plotter)
        sidebarSplitter.addWidget(self.featureList)
        splitter.addWidget(sidebarSplitter)
        splitter.addWidget(self.plotter)
