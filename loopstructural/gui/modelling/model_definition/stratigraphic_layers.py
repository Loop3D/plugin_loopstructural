import os

from PyQt5.QtWidgets import QWidget
from qgis.PyQt import uic


class StratigraphicLayersWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        ui_path = os.path.join(os.path.dirname(__file__), "stratigraphic_layers.ui")
        uic.loadUi(ui_path, self)
