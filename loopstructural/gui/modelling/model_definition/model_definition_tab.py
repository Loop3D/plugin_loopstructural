from qgis.PyQt.QtWidgets import QSizePolicy

from loopstructural.gui.modelling.base_tab import BaseTab

from .bounding_box import BoundingBoxWidget
from .dem import DEMWidget


class ModelDefinitionTab(BaseTab):
    """The area and the elevation (step 1 of the dock).

    The geology, contacts and structure layers are in step 2. The fault layers
    are in step 3. Save, Open and Reset are in the header of the dock.
    """

    def __init__(self, parent=None, data_manager=None):
        super().__init__(parent, data_manager, scrollable=True)
        # Add widgets to the QToolBox
        self.bounding_box = BoundingBoxWidget(self, data_manager)
        self.dem = DEMWidget(self, data_manager)

        # Set uniform size policy for all widgets
        for widget in [self.bounding_box, self.dem]:
            widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.add_widget(self.bounding_box, 'Bounding Box')
        self.add_widget(self.dem, 'DEM')
