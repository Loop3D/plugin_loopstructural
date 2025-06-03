import os
from typing import Optional

from PyQt5 import uic
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QWidget


class StratigraphicUnitWidget(QWidget):
    deleteRequested = pyqtSignal(QWidget)  # Signal to request deletion

    def __init__(self, uuid, name: Optional[str] = None, colour: Optional[str] = None, parent=None):
        super().__init__(parent)
        uic.loadUi(os.path.join(os.path.dirname(__file__), "stratigraphic_unit.ui"), self)
        self.uuid = uuid

        # Add delete button
        self.buttonDelete.clicked.connect(self.request_delete)

    def request_delete(self):

        self.deleteRequested.emit(self)

    def setData(self, data: Optional[dict] = None):
        """
        Set the data for the stratigraphic unit widget.
        :param data: A dictionary containing 'name' and 'colour' keys.
        """
        if data:
            self.name = data.get("name", "")
            self.colour = data.get("colour", "")
            self.lineEditName.setText(self.name)
            # self.lineEditColour.setText(self.colour)
        else:
            self.name = ""
            self.colour = ""
            self.lineEditName.clear()
            # self.lineEditColour.clear()
