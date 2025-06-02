import os
from typing import Optional

from PyQt5 import uic
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QWidget


class UnconformityWidget(QWidget):
    deleteRequested = pyqtSignal(QWidget)  # Signal to request deletion

    def __init__(self, parent=None):
        super().__init__(parent)
        uic.loadUi(os.path.join(os.path.dirname(__file__), 'unconformity.ui'), self)
        # Add delete button
        self.buttonDelete.clicked.connect(self.request_delete)

    def request_delete(self):

        self.deleteRequested.emit(self)
