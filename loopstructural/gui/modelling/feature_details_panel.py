from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QSlider, QLabel, QDoubleSpinBox, QCheckBox, QFormLayout
)
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QScrollArea
from LoopStructural.utils import normal_vector_to_strike_and_dip
class BaseFeatureDetailsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Create a scroll area for horizontal scrolling
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # Create content widget to hold the form layout
        content = QWidget()
        self.layout = QVBoxLayout(content)
        # Set the content widget as the scroll area's widget
        scroll.setWidget(content)

        # Add scroll area to main layout
        mainLayout = QVBoxLayout(self)
        mainLayout.addWidget(scroll)

        # Set the main layout
        self.setLayout(mainLayout)

class FaultFeatureDetailsPanel(BaseFeatureDetailsPanel):
    def __init__(self, parent=None,*, fault=None):
        super().__init__(parent)
        if fault is None:
            raise ValueError("Fault must be provided.")
        self.fault = fault
        dip = normal_vector_to_strike_and_dip(fault.fault_normal_vector)[0, 0]

        self.fault_parameters = {'displacement': fault.displacement,
                                 'major_axis_length': fault.fault_major_axis,
                                'minor_axis_length': fault.fault_minor_axis,
                                'intermediate_axis_length': fault.fault_intermediate_axis,
                                'dip': dip,
                                # 'enabled': fault.fault_enabled
                                }

        # Fault displacement slider
        self.displacement_slider = QSlider(Qt.Horizontal)
        self.displacement_slider.setRange(0, 1000)  # Example range
        self.displacement_slider.setValue(self.fault.displacement)
        self.displacement_label = QLabel(f"Fault Displacement: {self.fault.displacement}")
        self.displacement_slider.valueChanged.connect(
            lambda value: self.displacement_label.setText(f"Fault Displacement: {value}")
        )
        self.displacement_slider.valueChanged.connect(
            lambda value: self.fault_parameters.__setitem__('displacement', value)
        )

        # Fault axis lengths
        self.major_axis_spinbox = QDoubleSpinBox()
        self.major_axis_spinbox.setRange(0, float('inf'))
        self.major_axis_spinbox.setValue(self.fault_parameters['major_axis_length'])
        # self.major_axis_spinbox.setPrefix("Major Axis Length: ")
        self.major_axis_spinbox.valueChanged.connect(
            lambda value: self.fault_parameters.__setitem__('major_axis_length', value)
        )
        self.minor_axis_spinbox = QDoubleSpinBox()
        self.minor_axis_spinbox.setRange(0, float('inf'))
        self.minor_axis_spinbox.setValue(self.fault_parameters['minor_axis_length'])
        # self.minor_axis_spinbox.setPrefix("Minor Axis Length: ")
        self.minor_axis_spinbox.valueChanged.connect(
            lambda value: self.fault_parameters.__setitem__('minor_axis_length', value)
        )
        self.intermediate_axis_spinbox = QDoubleSpinBox()
        self.intermediate_axis_spinbox.setRange(0, float('inf'))
        self.intermediate_axis_spinbox.setValue(self.fault_parameters['intermediate_axis_length'])
        self.intermediate_axis_spinbox.valueChanged.connect(
            lambda value: self.fault_parameters.__setitem__('intermediate_axis_length', value)
        )
        # self.intermediate_axis_spinbox.setPrefix("Intermediate Axis Length: ")

        # Fault dip field
        self.dip_spinbox = QDoubleSpinBox()
        self.dip_spinbox.setRange(0, 90)  # Dip angle range
        self.dip_spinbox.setValue(self.fault_parameters['dip'])
        # self.dip_spinbox.setPrefix("Fault Dip: ")
        self.dip_spinbox.valueChanged.connect(
            lambda value: self.fault_parameters.__setitem__('dip', value)
        )
        # Enabled field
        # self.enabled_checkbox = QCheckBox("Enabled")
        # self.enabled_checkbox.setChecked(False)

        # Form layout for better organization
        form_layout = QFormLayout()
        form_layout.addRow(self.displacement_label, self.displacement_slider)
        form_layout.addRow("Major Axis Length:", self.major_axis_spinbox)
        form_layout.addRow("Minor Axis Length:", self.minor_axis_spinbox)
        form_layout.addRow("Intermediate Axis Length:", self.intermediate_axis_spinbox)
        form_layout.addRow("Fault Dip:", self.dip_spinbox)
        # form_layout.addRow("Enabled:", self.enabled_checkbox)

        self.layout.addLayout(form_layout)
        # self.setLayout(self.layout)

class FoliationFeatureDetailsPanel(BaseFeatureDetailsPanel):
    def __init__(self, parent=None,*, feature=None):
        super().__init__(parent)

        # Foliation thickness slider
        self.thickness_slider = QSlider(Qt.Horizontal)
        self.thickness_slider.setRange(0, 100)  # Example range
        self.thickness_slider.setValue(0)
        self.thickness_label = QLabel("Foliation Thickness: 0")
        self.thickness_slider.valueChanged.connect(
            lambda value: self.thickness_label.setText(f"Foliation Thickness: {value}")
        )

        # Foliation orientation
        self.orientation_spinbox = QDoubleSpinBox()
        self.orientation_spinbox.setRange(0, 360)  # Orientation angle range
        self.orientation_spinbox.setValue(0)
        self.orientation_spinbox.setPrefix("Orientation: ")

        # Enabled field
        self.enabled_checkbox = QCheckBox("Enabled")
        self.enabled_checkbox.setChecked(False)

        # Form layout for better organization
        form_layout = QFormLayout()
        form_layout.addRow(self.thickness_label, self.thickness_slider)
        form_layout.addRow("Orientation:", self.orientation_spinbox)
        form_layout.addRow("Enabled:", self.enabled_checkbox)

        self.layout.addLayout(form_layout)
        # Remove redundant layout setting
        # self.setLayout(self.layout)
