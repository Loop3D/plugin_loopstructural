from xmlrpc.client import Fault

from PyQt5.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from loopstructural.gui.modelling.fault_adjacency_tab import FaultAdjacencyTab
from loopstructural.gui.modelling.geological_history_tab import GeologialHistoryTab
from loopstructural.gui.modelling.geological_model_tab import GeologicalModelTab
from loopstructural.gui.modelling.model_definition import ModelDefinitionTab


class ModellingWidget(QWidget):
    def __init__(
        self,
        parent: QWidget = None,
        *,
        mapCanvas=None,
        logger=None,
        data_manager=None,
        model_manager=None,
    ):

        super().__init__(parent)
        self.mapCanvas = mapCanvas
        self.logger = logger
        self.data_manager = data_manager  # ModellingDataManager(mapCanvas=mapCanvas, logger=logger)
        self.model_manager = model_manager
        self.geological_history_tab_widget = None
        self.stratigraphic_column_tab_widget = None
        self.fault_graph_tab_widget = None
        self.model_definition_tab_widget = ModelDefinitionTab(self, data_manager=self.data_manager)
        self.geological_history_tab_widget = GeologialHistoryTab(
            self, data_manager=self.data_manager
        )
        self.fault_adjacency_tab_widget = FaultAdjacencyTab(self, data_manager=self.data_manager)
        self.geological_model_tab_widget = GeologicalModelTab(self, model_manager=self.model_manager)

        mainLayout = QVBoxLayout(self)
        self.setLayout(mainLayout)
        tabWidget = QTabWidget(self)
        mainLayout.addWidget(tabWidget)
        tabWidget.addTab(self.model_definition_tab_widget, "Load Data")
        tabWidget.addTab(self.geological_history_tab_widget, "Stratigraphic Column")
        tabWidget.addTab(self.fault_adjacency_tab_widget, "Fault Adjacency")
        tabWidget.addTab(self.geological_model_tab_widget, "Geological Model")
