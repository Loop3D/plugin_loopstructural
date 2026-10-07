from qgis.PyQt.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from ....main import parametric_fault


def _spin(low, high, decimals=2, step=1.0):
    spin = QDoubleSpinBox()
    spin.setRange(low, high)
    spin.setDecimals(decimals)
    spin.setSingleStep(step)
    return spin


class AddFaultDialog(QDialog):
    """Ask for a fault that is given by numbers: a centre, a strike, a dip and a size.

    Faults that have a trace on the map come from the fault layer in step 3.
    The start values come from the bounding box of the model.
    """

    def __init__(self, parent=None, *, model_manager=None):
        super().__init__(parent)
        self.model_manager = model_manager
        self.setWindowTitle('Add Fault')

        layout = QVBoxLayout(self)
        name_form = QFormLayout()
        self.name_input = QLineEdit()
        name_form.addRow("Name:", self.name_input)
        layout.addLayout(name_form)

        orientation = QGroupBox("Orientation")
        form = QFormLayout(orientation)
        self.strike_input = _spin(0, 360)
        self.strike_input.setToolTip("Degrees clockwise from north. The fault dips to the right.")
        self.dip_input = _spin(0.01, 90)
        self.pitch_input = _spin(-180, 180)
        self.pitch_input.setToolTip(
            "The angle of the slip in the fault plane, from the strike direction towards "
            "the down-dip direction. 0 is strike-slip. 90 is dip-slip."
        )
        self.displacement_input = _spin(-1e9, 1e9)
        self.displacement_input.setToolTip("The size of the slip, in model units.")
        form.addRow("Strike (°):", self.strike_input)
        form.addRow("Dip (°):", self.dip_input)
        form.addRow("Pitch (°):", self.pitch_input)
        form.addRow("Displacement:", self.displacement_input)
        layout.addWidget(orientation)

        position = QGroupBox("Position")
        form = QFormLayout(position)
        centre_row = QHBoxLayout()
        self.centre_inputs = [_spin(-1e9, 1e9) for _ in range(3)]
        for label, spin in zip("XYZ", self.centre_inputs):
            centre_row.addWidget(QLabel(label))
            centre_row.addWidget(spin)
        form.addRow("Centre:", centre_row)
        layout.addWidget(position)

        size = QGroupBox("Size")
        form = QFormLayout(size)
        self.major_input = _spin(0.01, 1e9)
        self.major_input.setToolTip("How far the fault extends along its strike.")
        self.intermediate_input = _spin(0.01, 1e9)
        self.intermediate_input.setToolTip("How far the fault extends down its dip.")
        self.minor_input = _spin(0.01, 1e9)
        self.minor_input.setToolTip("How far the fault changes the field, across the fault.")
        form.addRow("Length along strike:", self.major_input)
        form.addRow("Extent down dip:", self.intermediate_input)
        form.addRow("Influence distance:", self.minor_input)
        layout.addWidget(size)

        self.problem_label = QLabel()
        self.problem_label.setWordWrap(True)
        layout.addWidget(self.problem_label)
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        self._set_start_values()
        for spin in (
            self.strike_input,
            self.dip_input,
            self.pitch_input,
            self.displacement_input,
            self.major_input,
            self.intermediate_input,
            self.minor_input,
            *self.centre_inputs,
        ):
            spin.valueChanged.connect(self._validate)
        self.name_input.textChanged.connect(self._validate)
        self._validate()

    def _set_start_values(self):
        model = getattr(self.model_manager, 'model', None)
        box = getattr(model, 'bounding_box', None)
        if box is None:
            spec = parametric_fault.default_spec([0, 0, 0], [1000, 1000, 1000])
        else:
            spec = parametric_fault.default_spec(box.origin, box.maximum)
        self.strike_input.setValue(spec['strike'])
        self.dip_input.setValue(spec['dip'])
        self.pitch_input.setValue(spec['pitch'])
        self.displacement_input.setValue(spec['displacement'])
        for spin, value in zip(self.centre_inputs, spec['centre']):
            spin.setValue(value)
        self.major_input.setValue(spec['major_axis'])
        self.intermediate_input.setValue(spec['intermediate_axis'])
        self.minor_input.setValue(spec['minor_axis'])

    def _taken_names(self):
        return self.model_manager.used_names() if self.model_manager is not None else set()

    def _validate(self, *args):
        found = parametric_fault.problems(self.get_fault_data(), self._taken_names())
        self.problem_label.setText("\n".join(found))
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(not found)

    def get_fault_data(self):
        return {
            'name': self.name_input.text().strip(),
            'strike': self.strike_input.value(),
            'dip': self.dip_input.value(),
            'pitch': self.pitch_input.value(),
            'displacement': self.displacement_input.value(),
            'centre': tuple(spin.value() for spin in self.centre_inputs),
            'major_axis': self.major_input.value(),
            'intermediate_axis': self.intermediate_input.value(),
            'minor_axis': self.minor_input.value(),
        }
