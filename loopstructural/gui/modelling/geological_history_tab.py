import os
from tokenize import group

from PyQt5.QtWidgets import QWidget
from qgis.PyQt import uic

from loopstructural.gui.modelling.base_tab import BaseTab
from loopstructural.gui.modelling.stratigraphic_column.stratigraphic_column import StratColumnWidget


class GeologialHistoryTab(BaseTab):
    def __init__(self, parent=None, data_manager=None):
        super().__init__(parent, data_manager, scrollable=True)

        # Load the UI file for Tab 1
        stratigraphic_column_widget = StratColumnWidget(self)

        # Add the loaded UI widget to the container layout
        self.add_widget(stratigraphic_column_widget, group_box=False)
