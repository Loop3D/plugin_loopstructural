import os
from typing import Optional

from PyQt5 import uic
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QHBoxLayout, QWidget


class StratigraphicUnitWidget(QWidget):
    deleteRequested = pyqtSignal(QWidget)  # Signal to request deletion

    def __init__(self, name: Optional[str] = None, colour: Optional[str] = None, parent=None):
        super().__init__(parent)
        uic.loadUi(os.path.join(os.path.dirname(__file__), "stratigraphic_unit.ui"), self)

        # Add delete button
        layout = QHBoxLayout(self)
        self.buttonDelete.clicked.connect(self.request_delete)
        self.setLayout(layout)

    def request_delete(self):
        print("Delete button clicked in StratigraphicUnitWidget")  # Debug print
        print("Emitting deleteRequested signal")  # Debug print
        self.deleteRequested.emit(self)
