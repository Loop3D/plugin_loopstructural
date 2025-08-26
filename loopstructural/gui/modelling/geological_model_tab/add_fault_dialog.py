import os

from PyQt5.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout
from PyQt5.uic import loadUi


class AddFaultDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        ui_path = os.path.join(os.path.dirname(__file__), 'add_fault_dialog.ui')
        loadUi(ui_path, self)
        self.setWindowTitle('Add Fault Feature')
        # You can access widgets by their objectName from the .ui file
        # Example: self.strike_input, self.dip_input, etc.

    def get_fault_data(self):
        return {
            'strike': self.strike_input.value(),
            'dip': self.dip_input.value(),
            'centre': (
                self.centre_x_input.value(),
                self.centre_y_input.value(),
                self.centre_z_input.value(),
            ),
            'ellipsoid_extents': (
                self.extent_x_input.value(),
                self.extent_y_input.value(),
                self.extent_z_input.value(),
            ),
            'displacement': self.displacement_input.value(),
            'pitch': self.pitch_input.value(),
            'name': self.name_input.text(),
        }
