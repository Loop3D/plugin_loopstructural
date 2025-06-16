from LoopStructural import GeologicalModel
from PyQt5.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from loopstructural.gui.modelling.fault_graph.fault_graph import FaultGraph
from loopstructural.gui.modelling.geological_history_tab import GeologialHistoryTab
from loopstructural.gui.modelling.geological_model_tab import GeologicalModelTab
from loopstructural.gui.modelling.model_definition import ModelDefinitionTab
from loopstructural.gui.modelling.stratigraphic_column.stratigraphic_column import StratColumnWidget
from loopstructural.main.data_manager import ModellingDataManager
from loopstructural.main.model_manager import GeologicalModelManager


class ModellingWidget(QWidget):
    def __init__(self, parent: QWidget = None, mapCanvas=None, logger=None):
        super().__init__(parent)
        # Load the UI file for Tab 1
        # uic.loadUi(os.path.join(os.path.dirname(__file__), "modelling_widget.ui"), self)
        self.mapCanvas = mapCanvas
        self.logger = logger
        self.data_manager = ModellingDataManager(mapCanvas=mapCanvas, logger=logger)
        self.model_manager = GeologicalModelManager()
        self.geological_history_tab_widget = None
        self.stratigraphic_column_tab_widget = None
        self.fault_graph_tab_widget = None
        self.model_definition_tab_widget = ModelDefinitionTab(self, data_manager=self.data_manager)
        self.geological_history_tab_widget = GeologialHistoryTab(
            self, data_manager=self.data_manager
        )
        self.geological_model_tab_widget = GeologicalModelTab(self)
        mainLayout = QVBoxLayout(self)
        self.setLayout(mainLayout)
        tabWidget = QTabWidget(self)
        mainLayout.addWidget(tabWidget)
        tabWidget.addTab(self.model_definition_tab_widget, "Load Data")
        tabWidget.addTab(self.geological_history_tab_widget, "Stratigraphic Column")
        tabWidget.addTab(self.geological_model_tab_widget, "Geological Model")
