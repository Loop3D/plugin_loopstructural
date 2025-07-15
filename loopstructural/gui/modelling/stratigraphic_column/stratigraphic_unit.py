import os
from typing import Optional

from PyQt5 import uic
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QWidget


class StratigraphicUnitWidget(QWidget):
    deleteRequested = pyqtSignal(QWidget)  # Signal to request deletion
    thicknessChanged = pyqtSignal(float)  # Signal for thickness changes
    colourChanged = pyqtSignal(str)  # Signal for colour changes
    nameChanged = pyqtSignal(str)  # Signal for name changes
    def __init__(self, uuid, name: Optional[str] = None, colour: Optional[str] = None, parent=None):
        super().__init__(parent)
        uic.loadUi(os.path.join(os.path.dirname(__file__), "stratigraphic_unit.ui"), self)
        self.uuid = uuid
        self.name = name if name is not None else ""
        self.colour = colour if colour is not None else ""
        self.thickness = 0.0  # Optional thickness attribute
        # Add delete button
        self.buttonDelete.clicked.connect(self.request_delete)
        self.lineEditName.editingFinished.connect(self.onNameChanged)
        self.spinBoxThickness.valueChanged.connect(self.onThicknessChanged)

    def set_thickness(self, thickness: float):
        """
        Set the thickness of the stratigraphic unit.
        :param thickness: The thickness value to set.
        """
        self.thickness = thickness
        self.spinBoxThickness.setValue(thickness)
        self.validateFields()
    
    def onColourSelectClicked(self):
        """
        Open a color dialog to select a color for the stratigraphic unit.
        """
        from PyQt5.QtWidgets import QColorDialog

        color = QColorDialog.getColor()
        if color.isValid():
            self.colour = color.name()
        self.buttonColor.setStyleSheet(f"background-color: {self.colour};")

    def onThicknessChanged(self, thickness: float):
        """
        Update the thickness of the stratigraphic unit.
        :param thickness: The new thickness value.
        """
        self.thickness = thickness
        self.validateFields()
        self.thicknessChanged.emit(thickness)
    def onNameChanged(self):
        """
        Update the name of the stratigraphic unit.
        :param name: The new name value.
        """
        name = self.lineEditName.text().strip()
        if name != self.name:
            self.name = name
            self.validateFields()
            self.nameChanged.emit(name)
    def request_delete(self):

        self.deleteRequested.emit(self)



    def validateFields(self):
        """
        Validate the fields and update the widget's appearance.
        """
        # Reset all styles first
        self.lineEditName.setStyleSheet("")
        self.spinBoxThickness.setStyleSheet("")
        self.lineEditName.setToolTip("")
        self.spinBoxThickness.setToolTip("")

        if not self.name or self.name.strip() == "":
            self.lineEditName.setStyleSheet("border: 2px solid red;")
            self.lineEditName.setToolTip("Name cannot be empty.")
        elif hasattr(self, 'thickness') and not self.thickness > 0:
            self.spinBoxThickness.setStyleSheet("border: 2px solid red;")
            self.spinBoxThickness.setToolTip("Thickness must be greater than zero.")

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

        self.validateFields()

    def getData(self) -> dict:
        """
        Get the data from the stratigraphic unit widget.
        :return: A dictionary containing 'name', 'colour', and 'thickness'.
        """
        return {
            "uuid": self.uuid,
            "name": self.name,
            "colour": self.colour,
            "thickness": self.thickness
        }
