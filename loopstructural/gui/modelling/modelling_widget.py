import os

from PyQt5.QtWidgets import QVBoxLayout, QWidget
from qgis.PyQt import uic

from loopstructural.gui.modelling.fault_graph.fault_graph import FaultGraph
from loopstructural.gui.modelling.geological_history_tab import GeologialHistoryTab
from loopstructural.gui.modelling.model_definition import ModelDefinitionTab
from loopstructural.gui.modelling.stratigraphic_column.stratigraphic_column import StratColumnWidget


class ModellingWidget(QWidget):
    def __init__(self, parent: QWidget = None, mapCanvas=None, logger=None):
        super().__init__(parent)
        # Load the UI file for Tab 1
        uic.loadUi(os.path.join(os.path.dirname(__file__), "modelling_widget.ui"), self)
        self.mapCanvas = mapCanvas
        self.logger = logger
        self.data_manager = None
        self.model_definition_tab_widget = None
        self.geological_history_tab_widget = None
        self.stratigraphic_column_tab_widget = None
        self.fault_graph_tab_widget = None

        # Ensure the tabs have layouts
        if not self.load_data_tab.layout():
            self.load_data_tab.setLayout(QVBoxLayout())
        if not self.geological_history_tab.layout():
            self.geological_history_tab.setLayout(QVBoxLayout())
        if not self.model_setup_tab.layout():
            self.model_setup_tab.setLayout(QVBoxLayout())
        if not self.topology_tab.layout():
            self.topology_tab.setLayout(QVBoxLayout())
        self.model_definition_tab_widget = ModelDefinitionTab(self)
        self.geological_history_tab_widget = GeologialHistoryTab(self)
        self.stratigraphic_column_tab_widget = StratColumnWidget(self)
        self.fault_graph_tab_widget = FaultGraph(self)
        self.load_data_tab.layout().addWidget(self.model_definition_tab_widget)
        self.geological_history_tab.layout().addWidget(self.geological_history_tab_widget)
        self.model_setup_tab.layout().addWidget(self.stratigraphic_column_tab_widget)
        self.topology_tab.layout().addWidget(self.fault_graph_tab_widget)
