from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QSlider, QLabel, QDoubleSpinBox, QCheckBox, QFormLayout, QComboBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QScrollArea
from LoopStructural.utils import normal_vector_to_strike_and_dip
class BaseFeatureDetailsPanel(QWidget):
    def __init__(self, parent=None,*, feature=None):
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

        ## define interpolator parameters
        # Regularisation slider
        self.regularisation_slider = QSlider(Qt.Horizontal)
        self.regularisation_slider.setRange(0, 100)
        self.regularisation_slider.setValue(1)
        self.regularisation_label = QLabel("Regularisation: 1")
        self.regularisation_slider.valueChanged.connect(
            lambda value: self.regularisation_label.setText(f"Regularisation: {value}")
        )
        # self.regularisation_slider.valueChanged.connect(
        #     lambda value: feature.builder.foliation_parameters.__setitem__('regularisation', value)
        # )
        self.regularisation_slider.valueChanged.connect(
            lambda value: feature.builder.update_build_arguments({'regularisation': value})
        )
        self.cpw_slider = QSlider(Qt.Horizontal)
        self.cpw_slider.setRange(0, 100)
        self.cpw_slider.setValue(1)
        self.cpw_label = QLabel("Value point weight: 1")
        self.cpw_slider.valueChanged.connect(
            lambda value: self.cpw_label.setText(f"Value point weight: {value}")
        )
        self.cpw_slider.valueChanged.connect(
            lambda value: feature.builder.update_build_arguments({'cpw':value})
        )
        self.npw_slider = QSlider(Qt.Horizontal)
        self.npw_slider.setRange(0, 100)
        self.npw_slider.setValue(1)
        self.npw_label = QLabel("Normal vector weight: 1")
        self.npw_slider.valueChanged.connect(
            lambda value: self.npw_label.setText(f"Normal vector weight: {value}")
        )
        self.npw_slider.valueChanged.connect(
            lambda value: feature.builder.update_build_arguments({'npw':value})
        )
        self.interpolator_type_label = QLabel("Interpolator Type:")
        self.interpolator_type_combo = QComboBox()
        self.interpolator_type_combo.addItems(["FDI", "PLI", "surfe"])

        self.n_elements_spinbox = QDoubleSpinBox()
        self.n_elements_spinbox.setRange(100, 1000000)
        self.n_elements_spinbox.setValue(5000)
        self.n_elements_spinbox.setPrefix("Number of Elements: ")
        
        self.n_elements_spinbox.valueChanged.connect(lambda value: feature.builder.update_build_arguments({'nelements  ': value}))

        # Form layout for better organization
        form_layout = QFormLayout()
        form_layout.addRow(self.interpolator_type_label, self.interpolator_type_combo)
        form_layout.addRow("Number of Elements:", self.n_elements_spinbox)
        form_layout.addRow(self.regularisation_label, self.regularisation_slider)
        form_layout.addRow(self.cpw_label, self.cpw_slider)
        form_layout.addRow(self.npw_label, self.npw_slider)

        

        self.layout.addLayout(form_layout)

class FaultFeatureDetailsPanel(BaseFeatureDetailsPanel):
    def __init__(self, parent=None,*, fault=None):
        super().__init__(parent,feature=fault)
        if fault is None:
            raise ValueError("Fault must be provided.")
        self.fault = fault
        dip = normal_vector_to_strike_and_dip(fault.fault_normal_vector)[0, 0]

        self.fault_parameters = {'displacement': fault.displacement,
                                 'major_axis_length': fault.fault_major_axis,
                                'minor_axis_length': fault.fault_minor_axis,
                                'intermediate_axis_length': fault.fault_intermediate_axis,
                                'dip': dip,
                                # 'pitch'
                                # 'enabled': fault.fault_enabled
                                }

        # Fault displacement slider
        self.displacement_spinbox = QDoubleSpinBox()
        self.displacement_spinbox.setRange(0, 1000000)  # Example range
        self.displacement_spinbox.setValue(self.fault.displacement)
        self.displacement_label = QLabel(f"Fault Displacement:")
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
        # self.dip_spinbox.valueChanged.connect(
            
        # Enabled field
        # self.enabled_checkbox = QCheckBox("Enabled")
        # self.enabled_checkbox.setChecked(False)

        # Form layout for better organization
        form_layout = QFormLayout()
        form_layout.addRow(self.displacement_label, self.displacement_spinbox)
        form_layout.addRow("Major Axis Length:", self.major_axis_spinbox)
        form_layout.addRow("Minor Axis Length:", self.minor_axis_spinbox)
        form_layout.addRow("Intermediate Axis Length:", self.intermediate_axis_spinbox)
        form_layout.addRow("Fault Dip:", self.dip_spinbox)
        # form_layout.addRow("Enabled:", self.enabled_checkbox)

        self.layout.addLayout(form_layout)
        # self.setLayout(self.layout)

class FoliationFeatureDetailsPanel(BaseFeatureDetailsPanel):
    def __init__(self, parent=None,*, feature=None):
        super().__init__(parent, feature=feature)

        
        # Remove redundant layout setting
        # self.setLayout(self.layout)
