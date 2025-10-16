import os
from typing import Optional

from PyQt5 import uic
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QWidget


class UnconformityWidget(QWidget):
    deleteRequested = pyqtSignal(QWidget)  # Signal to request deletion

    def __init__(
        self,
        uuid,
        parent=None,
    ):
        super().__init__(parent)
        uic.loadUi(os.path.join(os.path.dirname(__file__), 'unconformity.ui'), self)
        # Add delete button
        self.buttonDelete.clicked.connect(self.request_delete)
        self.uuid = uuid
        self.unconformity_type = 'erode'
        self.comboBoxUnconformityType.currentIndexChanged.connect(
            lambda: setattr(self, 'unconformity_type', self.comboBoxUnconformityType.currentText())
        )

    def request_delete(self):

        self.deleteRequested.emit(self)

    def setData(self, data: Optional[dict] = None):
        """Set the data for the unconformity widget.

        Parameters
        ----------
        data : dict or None
            Dictionary containing 'unconformity_type' key. If None, defaults are used.
        """
        if data:
            self.unconformity_type = data.get("unconformity_type", "")
            self.unconformityTypeComboBox.setCurrentIndex(
                self.unconformityTypeComboBox.findText(self.unconformity_type)
            )
        else:
            self.unconformity_type = 'erode'
            self.unconformityTypeComboBox.setCurrentIndex(
                self.unconformityTypeComboBox.findText(self.unconformity_type)
            )
