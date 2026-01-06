from PyQt5.QtWidgets import QSizePolicy

from loopstructural.gui.modelling.base_tab import BaseTab

from .fault_graph import FaultGraph


class ModelGraphTab(BaseTab):
    def __init__(self, parent=None, data_manager=None):
        super().__init__(parent, data_manager, scrollable=True)
        # Add widgets to the QToolBox
        self.graph = FaultGraph(self)

        # Set uniform size policy for all widgets
        for widget in [self.graph]:
            widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.add_widget(self.graph, 'Fault Graph')
