from qgis.PyQt.QtWidgets import QSizePolicy

from loopstructural.gui.modelling.base_tab import BaseTab
from loopstructural.gui.modelling.steps.section_stack import SectionStack

from .bounding_box import BoundingBoxWidget
from .dem import DEMWidget


class ModelDefinitionTab(BaseTab):
    """The area and the elevation (step 1 of the dock).

    The geology, contacts and structure layers are in step 2. The fault layers
    are in step 3. Save, Open and Reset are in the header of the dock.
    """

    def __init__(self, parent=None, data_manager=None):
        super().__init__(parent, data_manager)
        self.bounding_box = BoundingBoxWidget(self, data_manager)
        self.dem = DEMWidget(self, data_manager)

        # Set uniform size policy for all widgets
        for widget in [self.bounding_box, self.dem]:
            widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.sections = SectionStack(self, 'data', data_manager)
        self.sections.add_section(
            self.bounding_box,
            'bounding_box',
            'Bounding Box',
            summary=self._bounding_box_summary,
        )
        self.sections.add_section(self.dem, 'dem', 'DEM', summary=self._dem_summary)
        self.container_layout.addWidget(self.sections)
        self.container_layout.addStretch(1)

    def _bounding_box_summary(self):
        if self.data_manager is None or not self.data_manager.is_bounding_box_set():
            return "not set"
        return "set"

    def _dem_summary(self):
        if self.data_manager is None:
            return ""
        layer = getattr(self.data_manager, 'dem_layer', None)
        if getattr(self.data_manager, 'use_dem', False) and layer is not None:
            return layer.name()
        return "flat elevation"
