import os

from PyQt5.QtWidgets import QWidget
from qgis.PyQt import uic

from loopstructural.gui.modelling.base_tab import BaseTab


class GeologialHistoryTab(BaseTab):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Load the UI file for Tab 1
        ui_widget = QWidget()
        uic.loadUi(os.path.join(os.path.dirname(__file__), "geological_history_tab.ui"), ui_widget)

        # Add the loaded UI widget to the container layout
        self.container_layout.addWidget(ui_widget)
