
from PyQt5.QtWidgets import QSizePolicy

from loopstructural.gui.modelling.base_tab import BaseTab

from .bounding_box import BoundingBoxWidget
from .fault_layers import FaultLayersWidget
from .stratigraphic_layers import StratigraphicLayersWidget
from .dem import DEMWidget

class ModelDefinitionTab(BaseTab):
    def __init__(self, parent=None, data_manager=None):
        super().__init__(parent, data_manager, scrollable=True)      
        # Add widgets to the QToolBox
        self.bounding_box = BoundingBoxWidget(self, data_manager)
        self.dem = DEMWidget(self, data_manager)
        self.fault_layers = FaultLayersWidget(self, data_manager)
        self.stratigraphy_layers = StratigraphicLayersWidget(self, data_manager)

        # Set uniform size policy for all widgets
        for widget in [self.bounding_box, self.fault_layers, self.dem,self.stratigraphy_layers]:
            widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.add_widget(self.bounding_box, 'Bounding Box')  # , "Bounding Box")
        self.add_widget(self.dem, 'DEM')
        self.add_widget(self.fault_layers, 'Fault Layers')  # , "Fault Layers")
        self.add_widget(self.stratigraphy_layers, 'Stratigraphic Layers')  # , "Stratigraphic Layers")
