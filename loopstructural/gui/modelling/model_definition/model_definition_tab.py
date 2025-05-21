import os

from PyQt5.QtWidgets import QSizePolicy, QToolBox
from qgis.PyQt import uic

from loopstructural.gui.modelling.base_tab import BaseTab

from .bounding_box import BoundingBoxWidget
from .fault_layers import FaultLayersWidget
from .stratigraphic_layers import StratigraphicLayersWidget


class ModelDefinitionTab(BaseTab):
    def __init__(self, parent=None):
        super().__init__(parent, scrollable=True)
        # Load the UI file for Tab 1

        # Create a QToolBox for collapsible sections
        # self.toolBox = QToolBox(self)
        # self.add_widget(self.toolBox)

        # Add widgets to the QToolBox
        bounding_box = BoundingBoxWidget(self)
        fault_layers = FaultLayersWidget(self)
        stratigraphy_layers = StratigraphicLayersWidget(self)

        # Set uniform size policy for all widgets
        for widget in [bounding_box, fault_layers, stratigraphy_layers]:
            widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.add_widget(bounding_box, 'Bounding Box')  # , "Bounding Box")
        self.add_widget(fault_layers, 'Fault Layers')  # , "Fault Layers")
        self.add_widget(stratigraphy_layers, 'Stratigraphic Layers')  # , "Stratigraphic Layers")
