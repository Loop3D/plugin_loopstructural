"""The dialog to choose the values of the isosurfaces of a model feature."""

from typing import List, Optional

from qgis.PyQt.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
)

from .isovalues import (
    default_range_values,
    values_from_list,
    values_from_range,
)


class IsosurfaceDialog(QDialog):
    """Enter the values as a list, or as a start, an end and a count.

    `low` and `high` are the range of the scalar field (None if not known).
    They set the default values.
    """

    def __init__(
        self,
        feature_name: str,
        low: Optional[float] = None,
        high: Optional[float] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(f"Add Isosurfaces: {feature_name}")
        layout = QVBoxLayout(self)
        if low is not None and high is not None:
            layout.addWidget(QLabel(f"The scalar field is from {low:.4g} to {high:.4g}."))
        else:
            layout.addWidget(QLabel("The range of the scalar field is not known."))

        defaults = [0.0, 1.0, 2.0]
        try:
            defaults = default_range_values(low, high, 5)
        except (TypeError, ValueError):
            pass

        self.listRadio = QRadioButton("List of values", self)
        self.listRadio.setChecked(True)
        layout.addWidget(self.listRadio)
        self.listEdit = QLineEdit(self)
        self.listEdit.setText(", ".join(f"{v:.4g}" for v in defaults))
        self.listEdit.setToolTip("Separate the values with commas")
        layout.addWidget(self.listEdit)

        self.rangeRadio = QRadioButton("Range of values", self)
        layout.addWidget(self.rangeRadio)
        form = QFormLayout()
        self.startSpinBox = QDoubleSpinBox(self)
        self.endSpinBox = QDoubleSpinBox(self)
        for box, value in ((self.startSpinBox, defaults[0]), (self.endSpinBox, defaults[-1])):
            box.setRange(-1e12, 1e12)
            box.setDecimals(4)
            box.setValue(value)
        self.countSpinBox = QSpinBox(self)
        self.countSpinBox.setRange(1, 100)
        self.countSpinBox.setValue(len(defaults))
        form.addRow("Start", self.startSpinBox)
        form.addRow("End", self.endSpinBox)
        form.addRow("Count", self.countSpinBox)
        layout.addLayout(form)

        self.errorLabel = QLabel("", self)
        self.errorLabel.setStyleSheet("color: red;")
        layout.addWidget(self.errorLabel)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.listRadio.toggled.connect(self._update_enabled)
        self._update_enabled()
        self._values: List[float] = []

    def _update_enabled(self, _checked=None):
        use_list = self.listRadio.isChecked()
        self.listEdit.setEnabled(use_list)
        for widget in (self.startSpinBox, self.endSpinBox, self.countSpinBox):
            widget.setEnabled(not use_list)

    def read_values(self) -> List[float]:
        """The values from the controls. Raises ValueError if they are not valid."""
        if self.listRadio.isChecked():
            return values_from_list(self.listEdit.text())
        return values_from_range(
            self.startSpinBox.value(), self.endSpinBox.value(), self.countSpinBox.value()
        )

    def _on_accept(self):
        try:
            self._values = self.read_values()
        except ValueError as e:
            self.errorLabel.setText(str(e))
            return
        self.accept()

    def values(self) -> List[float]:
        """The values that the user entered (after the dialog is accepted)."""
        return list(self._values)
