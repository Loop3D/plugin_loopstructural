from PyQt5.QtWidgets import QTabWidget, QVBoxLayout, QWidget
from .modelling.modelling_widget import ModellingWidget
from .visualisation.visualisation_widget import VisualisationWidget
class LoopWidget(QWidget):
    def __init__(self, parent=None, *, mapCanvas=None, logger=None, data_manager=None, model_manager=None):
        super().__init__(parent)
        self.mapCanvas = mapCanvas
        self.logger = logger
        self.data_manager = data_manager
        self.model_manager = model_manager

        mainLayout = QVBoxLayout(self)
        self.setLayout(mainLayout)
        tabWidget = QTabWidget(self)
        tabWidget.setTabPosition(QTabWidget.South)
        mainLayout.addWidget(tabWidget)
        self.modelling_widget = ModellingWidget(
            self, mapCanvas=self.mapCanvas, logger=self.logger, data_manager=self.data_manager, model_manager=self.model_manager
        )

        self.visualisation_widget = VisualisationWidget(
            self, mapCanvas=self.mapCanvas, logger=self.logger, model_manager=self.model_manager
        )
        tabWidget.addTab(self.modelling_widget, "Modelling")
        tabWidget.addTab(self.visualisation_widget, "Visualisation")
        