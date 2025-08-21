from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from LoopStructural.modelling.features import StructuralFrame
from LoopStructural.utils import normal_vector_to_strike_and_dip, plungeazimuth2vector


class BaseFeatureDetailsPanel(QWidget):
    def __init__(self, parent=None, *, feature=None, model_manager=None):
        super().__init__(parent)
        self.feature = feature
        self.model_manager = model_manager
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
        # Regularisation spin box
        self.regularisation_spin_box = QDoubleSpinBox()
        self.regularisation_spin_box.setRange(0, 100)
        self.regularisation_spin_box.setValue(
            feature.builder.build_arguments.get('regularisation', 1.0)
        )
        self.regularisation_spin_box.valueChanged.connect(
            lambda value: feature.builder.update_build_arguments({'regularisation': value})
        )
        self.cpw_spin_box = QDoubleSpinBox()
        self.cpw_spin_box.setRange(0, 100)
        self.cpw_spin_box.setValue(feature.builder.build_arguments.get('cpw', 1.0))
        self.cpw_spin_box.valueChanged.connect(
            lambda value: feature.builder.update_build_arguments({'cpw': value})
        )

        self.npw_spin_box = QDoubleSpinBox()
        self.npw_spin_box.setRange(0, 100)
        self.npw_spin_box.setValue(feature.builder.build_arguments.get('npw', 1.0))
        self.npw_spin_box.valueChanged.connect(
            lambda value: feature.builder.update_build_arguments({'npw': value})
        )
        self.interpolator_type_label = QLabel("Interpolator Type:")
        self.interpolator_type_combo = QComboBox()
        self.interpolator_type_combo.addItems(["FDI", "PLI", "surfe"])

        self.n_elements_spinbox = QDoubleSpinBox()
        self.n_elements_spinbox.setRange(100, 1000000)
        self.n_elements_spinbox.setValue(self.getNelements(feature))
        self.n_elements_spinbox.setPrefix("Number of Elements: ")

        self.n_elements_spinbox.valueChanged.connect(self.updateNelements)

        # Form layout for better organization
        form_layout = QFormLayout()
        form_layout.addRow(self.interpolator_type_label, self.interpolator_type_combo)
        form_layout.addRow("Number of Elements:", self.n_elements_spinbox)
        form_layout.addRow('Regularisation', self.regularisation_spin_box)
        form_layout.addRow('Contact points weight', self.cpw_spin_box)
        form_layout.addRow('Orientation point weight', self.npw_spin_box)

        QgsCollapsibleGroupBox = QWidget()
        QgsCollapsibleGroupBox.setLayout(form_layout)
        self.layout.addWidget(QgsCollapsibleGroupBox)

        # self.layout.addLayout(form_layout)

    def updateNelements(self, value):
        """Update the number of elements in the feature's interpolator."""
        if self.feature:
            if issubclass(type(self.feature), StructuralFrame):
                for i in range(3):
                    if self.feature[i].interpolator is not None:
                        self.feature[i].interpolator.nelements = value
                        self.feature[i].builder.update_build_arguments({'nelements': value})
                        self.feature[i].builder.build()
            elif self.feature.interpolator is not None:

                self.feature.interpolator.nelements = value
                self.feature.builder.update_build_arguments({'nelements': value})
                self.feature.builder.build()
        else:
            print("Error: Feature is not initialized.")

    def getNelements(self, feature):
        """Get the number of elements from the feature's interpolator."""
        if feature:
            if issubclass(type(feature), StructuralFrame):
                return feature[0].interpolator.n_elements
            elif feature.interpolator is not None:
                return feature.interpolator.n_elements
        return 1000


class FaultFeatureDetailsPanel(BaseFeatureDetailsPanel):

    def __init__(self, parent=None, *, fault=None, model_manager=None):
        super().__init__(parent, feature=fault, model_manager=model_manager)
        if fault is None:
            raise ValueError("Fault must be provided.")
        self.fault = fault
        dip = normal_vector_to_strike_and_dip(fault.fault_normal_vector)[0, 0]
        pitch = 0
        self.fault_parameters = {
            'displacement': fault.displacement,
            'major_axis_length': fault.fault_major_axis,
            'minor_axis_length': fault.fault_minor_axis,
            'intermediate_axis_length': fault.fault_intermediate_axis,
            'dip': dip,
            'pitch': pitch,
            # 'enabled': fault.fault_enabled
        }

        # # Fault displacement slider
        # self.displacement_spinbox = QDoubleSpinBox()
        # self.displacement_spinbox.setRange(0, 1000000)  # Example range
        # self.displacement_spinbox.setValue(self.fault.displacement)
        # self.displacement_spinbox.valueChanged.connect(
        #     lambda value: self.fault_parameters.__setitem__('displacement', value)
        # )

        # # Fault axis lengths
        # self.major_axis_spinbox = QDoubleSpinBox()
        # self.major_axis_spinbox.setRange(0, float('inf'))
        # self.major_axis_spinbox.setValue(self.fault_parameters['major_axis_length'])
        # # self.major_axis_spinbox.setPrefix("Major Axis Length: ")
        # self.major_axis_spinbox.valueChanged.connect(
        #     lambda value: self.fault_parameters.__setitem__('major_axis_length', value)
        # )
        # self.minor_axis_spinbox = QDoubleSpinBox()
        # self.minor_axis_spinbox.setRange(0, float('inf'))
        # self.minor_axis_spinbox.setValue(self.fault_parameters['minor_axis_length'])
        # # self.minor_axis_spinbox.setPrefix("Minor Axis Length: ")
        # self.minor_axis_spinbox.valueChanged.connect(
        #     lambda value: self.fault_parameters.__setitem__('minor_axis_length', value)
        # )
        # self.intermediate_axis_spinbox = QDoubleSpinBox()
        # self.intermediate_axis_spinbox.setRange(0, float('inf'))
        # self.intermediate_axis_spinbox.setValue(self.fault_parameters['intermediate_axis_length'])
        # self.intermediate_axis_spinbox.valueChanged.connect(
        #     lambda value: self.fault_parameters.__setitem__('intermediate_axis_length', value)
        # )
        # # self.intermediate_axis_spinbox.setPrefix("Intermediate Axis Length: ")

        # # Fault dip field
        # self.dip_spinbox = QDoubleSpinBox()
        # self.dip_spinbox.setRange(0, 90)  # Dip angle range
        # self.dip_spinbox.setValue(self.fault_parameters['dip'])
        # # self.dip_spinbox.setPrefix("Fault Dip: ")
        # self.dip_spinbox.valueChanged.connect(
        #     lambda value: self.fault_parameters.__setitem__('dip', value)
        # )
        # self.pitch_spinbox = QDoubleSpinBox()
        # self.pitch_spinbox.setRange(0, 180)
        # self.pitch_spinbox.setValue(self.fault_parameters['pitch'])
        # self.pitch_spinbox.valueChanged.connect(
        #     lambda value: self.fault_parameters.__setitem__('pitch', value)
        # )
        # # self.dip_spinbox.valueChanged.connect(

        # # Enabled field
        # # self.enabled_checkbox = QCheckBox("Enabled")
        # # self.enabled_checkbox.setChecked(False)

        # # Form layout for better organization
        # form_layout = QFormLayout()
        # form_layout.addRow("Fault displacement", self.displacement_spinbox)
        # form_layout.addRow("Major Axis Length", self.major_axis_spinbox)
        # form_layout.addRow("Minor Axis Length", self.minor_axis_spinbox)
        # form_layout.addRow("Intermediate Axis Length", self.intermediate_axis_spinbox)
        # form_layout.addRow("Fault Dip", self.dip_spinbox)
        # # form_layout.addRow("Enabled:", self.enabled_checkbox)

        # self.layout.addLayout(form_layout)
        # self.setLayout(self.layout)


class FoliationFeatureDetailsPanel(BaseFeatureDetailsPanel):
    def __init__(self, parent=None, *, feature=None, model_manager=None):
        super().__init__(parent, feature=feature, model_manager=model_manager)
        if feature is None:
            raise ValueError("Feature must be provided.")
        self.feature = feature
        form_layout = QFormLayout()
        fold_frame_combobox = QComboBox()
        fold_frame_combobox.addItems([""] + [f.name for f in self.model_manager.fold_frames])
        fold_frame_combobox.currentTextChanged.connect(self.on_fold_frame_changed)
        form_layout.addRow("Attach fold frame", fold_frame_combobox)

        QgsCollapsibleGroupBox = QWidget()
        QgsCollapsibleGroupBox.setLayout(form_layout)
        self.layout.addWidget(QgsCollapsibleGroupBox)

        # Remove redundant layout setting
        self.setLayout(self.layout)

    def on_fold_frame_changed(self, text):
        self.model_manager.add_fold_to_feature(self.feature.name, fold_frame_name=text)


class StructuralFrameFeatureDetailsPanel(BaseFeatureDetailsPanel):
    def __init__(self, parent=None, *, feature=None, model_manager=None):
        super().__init__(parent, feature=feature, model_manager=model_manager)


class FoldedFeatureDetailsPanel(BaseFeatureDetailsPanel):
    def __init__(self, parent=None, *, feature=None, model_manager=None):
        super().__init__(parent, feature=feature, model_manager=model_manager)
        # Remove redundant layout setting
        # self.setLayout(self.layout)
        form_layout = QFormLayout()
        # remove_fold_frame_button = QPushButton("Remove Fold Frame")
        # remove_fold_frame_button.clicked.connect(self.remove_fold_frame)
        # form_layout.addRow(remove_fold_frame_button)

        norm_length = QDoubleSpinBox()
        norm_length.setRange(0, 100000)
        norm_length.setValue(1)  # Set a default value
        norm_length.valueChanged.connect(
            lambda value: feature.builder.update_build_arguments(
                {
                    'fold_weights': {
                        **feature.builder.build_arguments.get('fold_weights', {}),
                        'fold_norm': value,
                    }
                }
            )
        )
        form_layout.addRow("Normal Length", norm_length)

        norm_weight = QDoubleSpinBox()
        norm_weight.setRange(0, 100000)
        norm_weight.setValue(1)
        norm_weight.valueChanged.connect(
            lambda value: feature.builder.update_build_arguments(
                {
                    'fold_weights': {
                        **feature.builder.build_arguments.get('fold_weights', {}),
                        'fold_normalisation': value,
                    }
                }
            )
        )
        form_layout.addRow("Normal Weight", norm_weight)

        fold_axis_weight = QDoubleSpinBox()
        fold_axis_weight.setRange(0, 100000)
        fold_axis_weight.setValue(1)
        fold_axis_weight.valueChanged.connect(
            lambda value: feature.builder.update_build_arguments(
                {
                    'fold_weights': {
                        **feature.builder.build_arguments.get('fold_weights', {}),
                        'fold_axis_w': value,
                    }
                }
            )
        )
        form_layout.addRow("Fold Axis Weight", fold_axis_weight)

        fold_orientation_weight = QDoubleSpinBox()
        fold_orientation_weight.setRange(0, 100000)
        fold_orientation_weight.setValue(1)
        fold_orientation_weight.valueChanged.connect(
            lambda value: feature.builder.update_build_arguments(
                {
                    'fold_weights': {
                        **feature.builder.build_arguments.get('fold_weights', {}),
                        'fold_orientation': value,
                    }
                }
            )
        )
        form_layout.addRow("Fold Orientation Weight", fold_orientation_weight)

        average_fold_axis_checkbox = QCheckBox("Average Fold Axis")
        average_fold_axis_checkbox.setChecked(True)
        average_fold_axis_checkbox.stateChanged.connect(
            lambda state: feature.builder.update_build_arguments(
                {'av_fold_axis': state != Qt.Checked}
            )
        )
        average_fold_axis_checkbox.stateChanged.connect(
            lambda state: fold_azimuth.setEnabled(state == Qt.Checked)
        )
        average_fold_axis_checkbox.stateChanged.connect(
            lambda state: fold_plunge.setEnabled(state == Qt.Checked)
        )
        fold_plunge = QDoubleSpinBox()
        fold_plunge.setRange(0, 90)
        fold_plunge.setValue(0)
        fold_azimuth = QDoubleSpinBox()
        fold_azimuth.setRange(0, 360)
        fold_azimuth.setValue(0)
        fold_azimuth.setEnabled(False)
        fold_plunge.setEnabled(False)
        fold_plunge.valueChanged.connect(self.foldAxisFromPlungeAzimuth)
        fold_azimuth.valueChanged.connect(self.foldAxisFromPlungeAzimuth)
        form_layout.addRow(average_fold_axis_checkbox)
        form_layout.addRow("Fold Plunge", fold_plunge)
        form_layout.addRow("Fold Azimuth", fold_azimuth)
        QgsCollapsibleGroupBox = QWidget()
        QgsCollapsibleGroupBox.setLayout(form_layout)
        self.layout.addWidget(QgsCollapsibleGroupBox)
        # Remove redundant layout setting
        self.setLayout(self.layout)

    def remove_fold_frame(self):
        pass

    def foldAxisFromPlungeAzimuth(self):
        """Calculate the fold axis from plunge and azimuth."""
        if self.feature:
            plunge = (
                self.layout().itemAt(0).widget().findChild(QDoubleSpinBox, "fold_plunge").value()
            )
            azimuth = (
                self.layout().itemAt(0).widget().findChild(QDoubleSpinBox, "fold_azimuth").value()
            )
            vector = plungeazimuth2vector(plunge, azimuth)[0]
            if plunge is not None and azimuth is not None:
                self.feature.builder.update_build_arguments({'fold_axis': vector})
