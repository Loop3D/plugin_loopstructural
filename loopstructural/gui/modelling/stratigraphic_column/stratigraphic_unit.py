import os

from PyQt5 import uic
from PyQt5.QtWidgets import QWidget


class StratigraphicUnitWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        uic.loadUi(os.path.join(os.path.dirname(__file__), "stratigraphic_unit.ui"), self)
