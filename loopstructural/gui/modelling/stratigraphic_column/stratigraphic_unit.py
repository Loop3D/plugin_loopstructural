import os
from typing import Optional

import numpy as np
from PyQt5 import uic
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QWidget


class StratigraphicUnitWidget(QWidget):
    deleteRequested = pyqtSignal(QWidget)  # Signal to request deletion
    thicknessChanged = pyqtSignal(float)  # Signal for thickness changes
    colourChanged = pyqtSignal(str)  # Signal for colour changes
    nameChanged = pyqtSignal(str)  # Signal for name changes

    def __init__(
        self,
        uuid,
        name: Optional[str] = None,
        colour: Optional[str] = None,
        thickness: float = 0.0,
        parent=None,
    ):
        super().__init__(parent)
        uic.loadUi(os.path.join(os.path.dirname(__file__), "stratigraphic_unit.ui"), self)
        self.uuid = uuid
        self._name = name if name is not None else ""
        # Convert colour using helper method
        self.colour = self._convert_colour(colour)
        self.thickness = thickness  # Optional thickness attribute
        # Connect buttons
        self.buttonDelete.clicked.connect(self.request_delete)
        self.buttonColour.clicked.connect(self.onColourSelectClicked)
        self.lineEditName.editingFinished.connect(self.onNameChanged)
        self.spinBoxThickness.valueChanged.connect(self.onThicknessChanged)
        # Initialize UI widgets with the provided values
        self.lineEditName.setText(self._name)
        self.spinBoxThickness.setValue(self.thickness)
        # Set color button style instead of widget background
        self._update_colour_button()

    def _convert_colour(self, colour):
        """Convert colour from various formats to Qt-compatible hex string.
        
        Parameters
        ----------
        colour : str, tuple, list, np.ndarray, or None
            Colour in various formats: hex string, RGB tuple/list/array
            
        Returns
        -------
        str
            Hex color string in format "#RRGGBB", or empty string if None
        """
        if colour is None:
            return ""
        
        # If it's already a string, return it
        if isinstance(colour, str):
            return colour
            
        # Handle tuple, list, or numpy array of RGB values
        if (isinstance(colour, (tuple, list)) or isinstance(colour, np.ndarray)) and len(colour) >= 3:
            # Convert (r, g, b) to "#RRGGBB"
            # Check if values are normalized floats (0.0-1.0) or integers (0-255)
            if all(isinstance(c, float) and 0.0 <= c <= 1.0 for c in colour[:3]):
                rgb = [int(c * 255) for c in colour[:3]]
            else:
                rgb = [int(c) for c in colour[:3]]
            return "#{:02x}{:02x}{:02x}".format(*rgb)
        
        # Fallback: try to convert to string
        return str(colour)

    @property
    def name(self):
        return str(self._name)

    @name.setter
    def name(self, value: str):
        self._name = str(value)

    def set_thickness(self, thickness: float):
        """Set the thickness of the stratigraphic unit.

        Parameters
        ----------
        thickness : float
            The thickness value to set.
        """
        self.thickness = thickness
        self.spinBoxThickness.setValue(thickness)
        self.validateFields()

    def _update_colour_button(self):
        """Update the color button's appearance to show the current color."""
        if self.colour:
            self.buttonColour.setStyleSheet(
                f"background-color: {self.colour}; border: 1px solid #999;"
            )
        else:
            self.buttonColour.setStyleSheet("background-color: #cccccc; border: 1px solid #999;")

    def onColourSelectClicked(self):
        """Open a color dialog to select a color for the stratigraphic unit."""
        from PyQt5.QtWidgets import QColorDialog

        color = QColorDialog.getColor()
        if color.isValid():
            self.colour = color.name()
            self._update_colour_button()
            self.colourChanged.emit(self.colour)

    def onThicknessChanged(self, thickness: float):
        """Handle changes to the thickness spinbox.

        Parameters
        ----------
        thickness : float
            The new thickness value.
        """
        self.thickness = thickness
        self.validateFields()
        self.thicknessChanged.emit(thickness)

    def onNameChanged(self):
        """Handle name edit completion and emit nameChanged if modified."""
        name = self.lineEditName.text().strip()
        if name != self.name:
            self.name = name
            self.validateFields()
            self.nameChanged.emit(name)

    def request_delete(self):

        self.deleteRequested.emit(self)

    def validateFields(self):
        """Validate the widget fields and update UI hints."""
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
        """Set the data for the stratigraphic unit widget.

        Parameters
        ----------
        data : dict or None
            Dictionary containing 'name' and 'colour' keys. If None, defaults are used.
        """
        # Safely update internal state first
        if data:
            self.name = str(data.get("name", ""))
            # Convert colour using helper method to handle various formats
            self.colour = self._convert_colour(data.get("colour"))
            # If a thickness value is provided, update the widget's thickness
            if 'thickness' in data and data.get('thickness') is not None:
                try:
                    th = float(data.get('thickness'))
                except Exception:
                    th = None
                if th is not None:
                    # Use set_thickness to update spinbox without emitting thicknessChanged
                    try:
                        self.set_thickness(th)
                    except Exception:
                        # ignore GUI update failures
                        pass
        else:
            self.name = ""
            self.colour = ""

        # Guard all direct Qt calls since the wrapped C++ objects may have been deleted
        try:
            if data:
                if hasattr(self, 'lineEditName') and self.lineEditName is not None:
                    try:
                        self.lineEditName.setText(self.name)
                    except RuntimeError:
                        # Widget has been deleted; abort GUI updates
                        return
                try:
                    self._update_colour_button()
                except RuntimeError:
                    return
            else:
                if hasattr(self, 'lineEditName') and self.lineEditName is not None:
                    try:
                        self.lineEditName.clear()
                    except RuntimeError:
                        return
                try:
                    self._update_colour_button()
                except RuntimeError:
                    return

            # Validate fields if widgets still exist
            try:
                self.validateFields()
            except RuntimeError:
                return
        except RuntimeError:
            # Catch any unexpected RuntimeError from underlying Qt objects
            return

    def getData(self) -> dict:
        """Return the widget data as a dictionary.

        Returns
        -------
        dict
            Dictionary containing 'uuid', 'name', 'colour', and 'thickness'.
        """
        return {
            "uuid": self.uuid,
            "name": self.name,
            "colour": self.colour,
            "thickness": self.thickness,
        }
