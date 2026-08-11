from LoopStructural.utils import normal_vector_to_strike_and_dip, strikedip2vector
from qgis.PyQt.QtWidgets import QDoubleSpinBox, QFormLayout

from ._base import BaseFeatureDetailsPanel, retrieve_dip_value, retrieve_pitch_value


class FaultFeatureDetailsPanel(BaseFeatureDetailsPanel):

    def __init__(self, parent=None, *, fault=None, model_manager=None, data_manager=None):
        super().__init__(
            parent, feature=fault, model_manager=model_manager, data_manager=data_manager
        )
        if fault is None:
            raise ValueError("Fault must be provided.")
        self.fault = fault

        # Retrieve dip and pitch using helper functions
        dip = retrieve_dip_value(fault, model_manager)
        pitch = retrieve_pitch_value(fault, model_manager)

        self.fault_parameters = {
            'displacement': fault.displacement,
            'major_axis_length': fault.fault_major_axis,
            'minor_axis_length': fault.fault_minor_axis,
            'intermediate_axis_length': fault.fault_intermediate_axis,
            'dip': dip,
            'pitch': pitch,
            # 'enabled': fault.fault_enabled
        }

        def update_displacement(value):
            self.fault.displacement = value

        def update_major_axis(value):
            self.fault.fault_major_axis = value
            # these mutate the fault/builder directly rather than going through
            # update_build_arguments (which self-flags dirty), so we have to
            # mark it stale by hand or the debounced rebuild below is a no-op:
            # builder.update() checks _up_to_date first and skips rebuilding
            # entirely if nothing told it the fault changed.
            self.fault.builder.set_not_up_to_date(self)
            self.schedule_rebuild()

        def update_minor_axis(value):
            self.fault.fault_minor_axis = value
            self.fault.builder.set_not_up_to_date(self)
            self.schedule_rebuild()

        def update_intermediate_axis(value):
            self.fault.fault_intermediate_axis = value
            self.fault.builder.set_not_up_to_date(self)
            self.schedule_rebuild()

        def update_dip(value):
            strike = normal_vector_to_strike_and_dip(self.fault.fault_normal_vector)[0, 0]
            self.fault.builder.fault_normal_vector = strikedip2vector([strike], [value])[0]
            self.fault.builder.set_not_up_to_date(self)
            self.schedule_rebuild()

        # Fault displacement slider
        self.displacement_spinbox = QDoubleSpinBox()
        self.displacement_spinbox.setRange(0, 1000000)  # Example range
        self.displacement_spinbox.setValue(self.fault.displacement)
        self.displacement_spinbox.valueChanged.connect(update_displacement)

        # Fault axis lengths
        self.major_axis_spinbox = QDoubleSpinBox()
        self.major_axis_spinbox.setRange(0, float('inf'))
        self.major_axis_spinbox.setValue(self.fault.fault_major_axis)
        # self.major_axis_spinbox.setPrefix("Major Axis Length: ")
        self.major_axis_spinbox.valueChanged.connect(update_major_axis)
        self.minor_axis_spinbox = QDoubleSpinBox()
        self.minor_axis_spinbox.setRange(0, float('inf'))
        self.minor_axis_spinbox.setValue(self.fault.fault_minor_axis)
        # self.minor_axis_spinbox.setPrefix("Minor Axis Length: ")
        self.minor_axis_spinbox.valueChanged.connect(update_minor_axis)
        self.intermediate_axis_spinbox = QDoubleSpinBox()
        self.intermediate_axis_spinbox.setRange(0, float('inf'))
        self.intermediate_axis_spinbox.setValue(fault.fault_intermediate_axis)
        self.intermediate_axis_spinbox.valueChanged.connect(update_intermediate_axis)
        # self.intermediate_axis_spinbox.setPrefix("Intermediate Axis Length: ")

        # Fault dip field
        self.dip_spinbox = QDoubleSpinBox()
        self.dip_spinbox.setRange(0, 90)  # Dip angle range
        self.dip_spinbox.setValue(dip)
        # self.dip_spinbox.setPrefix("Fault Dip: ")
        self.dip_spinbox.valueChanged.connect(update_dip)
        self.pitch_spinbox = QDoubleSpinBox()
        self.pitch_spinbox.setRange(0, 180)
        self.pitch_spinbox.setValue(self.fault_parameters['pitch'])
        self.pitch_spinbox.valueChanged.connect(
            lambda value: self.fault_parameters.__setitem__('pitch', value)
        )
        # self.dip_spinbox.valueChanged.connect(

        # Enabled field
        # self.enabled_checkbox = QCheckBox("Enabled")
        # self.enabled_checkbox.setChecked(False)

        # Form layout for better organization
        form_layout = QFormLayout()
        form_layout.addRow("Fault displacement", self.displacement_spinbox)
        form_layout.addRow("Major Axis Length", self.major_axis_spinbox)
        form_layout.addRow("Minor Axis Length", self.minor_axis_spinbox)
        form_layout.addRow("Intermediate Axis Length", self.intermediate_axis_spinbox)
        form_layout.addRow("Fault Dip", self.dip_spinbox)
        # form_layout.addRow("Enabled:", self.enabled_checkbox)

        self.layout.addLayout(form_layout)
        self.setLayout(self.layout)
