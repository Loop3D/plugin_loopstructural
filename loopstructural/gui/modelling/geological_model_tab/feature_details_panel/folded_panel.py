from LoopStructural.utils import plungeazimuth2vector
from qgis.gui import QgsCollapsibleGroupBox
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QCheckBox, QDoubleSpinBox, QFormLayout

from ..splot import SPlotDialog
from ._base import BaseFeatureDetailsPanel


class FoldedFeatureDetailsPanel(BaseFeatureDetailsPanel):
    def __init__(self, parent=None, *, feature=None, model_manager=None, data_manager=None):
        super().__init__(
            parent, feature=feature, model_manager=model_manager, data_manager=data_manager
        )

    def addMidBlock(self):
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
            lambda value: self.feature.builder.update_build_arguments(
                {
                    'fold_weights': {
                        **self.feature.builder.build_arguments.get('fold_weights', {}),
                        'fold_norm': value,
                    }
                }
            )
        )
        norm_length.valueChanged.connect(lambda value: self.schedule_rebuild())
        form_layout.addRow("Normal Length", norm_length)

        norm_weight = QDoubleSpinBox()
        norm_weight.setRange(0, 100000)
        norm_weight.setValue(1)
        norm_weight.valueChanged.connect(
            lambda value: self.feature.builder.update_build_arguments(
                {
                    'fold_weights': {
                        **self.feature.builder.build_arguments.get('fold_weights', {}),
                        'fold_normalisation': value,
                    }
                }
            )
        )
        norm_weight.valueChanged.connect(lambda value: self.schedule_rebuild())
        form_layout.addRow("Normal Weight", norm_weight)

        fold_axis_weight = QDoubleSpinBox()
        fold_axis_weight.setRange(0, 100000)
        fold_axis_weight.setValue(1)
        fold_axis_weight.valueChanged.connect(
            lambda value: self.feature.builder.update_build_arguments(
                {
                    'fold_weights': {
                        **self.feature.builder.build_arguments.get('fold_weights', {}),
                        'fold_axis_w': value,
                    }
                }
            )
        )
        fold_axis_weight.valueChanged.connect(lambda value: self.schedule_rebuild())
        form_layout.addRow("Fold Axis Weight", fold_axis_weight)

        fold_orientation_weight = QDoubleSpinBox()
        fold_orientation_weight.setRange(0, 100000)
        fold_orientation_weight.setValue(1)
        fold_orientation_weight.valueChanged.connect(
            lambda value: self.feature.builder.update_build_arguments(
                {
                    'fold_weights': {
                        **self.feature.builder.build_arguments.get('fold_weights', {}),
                        'fold_orientation': value,
                    }
                }
            )
        )
        fold_orientation_weight.valueChanged.connect(lambda value: self.schedule_rebuild())
        form_layout.addRow("Fold Orientation Weight", fold_orientation_weight)

        average_fold_axis_checkbox = QCheckBox("Average Fold Axis")
        average_fold_axis_checkbox.setChecked(False)
        average_fold_axis_checkbox.stateChanged.connect(
            lambda state: self.feature.builder.update_build_arguments(
                {'av_fold_axis': state != Qt.Checked}
            )
        )
        average_fold_axis_checkbox.stateChanged.connect(
            lambda state: self.fold_azimuth.setEnabled(state != Qt.Checked)
        )
        average_fold_axis_checkbox.stateChanged.connect(
            lambda state: self.fold_plunge.setEnabled(state != Qt.Checked)
        )
        self.fold_plunge = QDoubleSpinBox()
        self.fold_plunge.setRange(0, 90)
        self.fold_plunge.setValue(0)
        self.fold_azimuth = QDoubleSpinBox()
        self.fold_azimuth.setRange(0, 360)
        self.fold_azimuth.setValue(0)
        self.fold_azimuth.setEnabled(False)
        self.fold_plunge.setEnabled(False)
        self.fold_plunge.valueChanged.connect(self.foldAxisFromPlungeAzimuth)
        self.fold_azimuth.valueChanged.connect(self.foldAxisFromPlungeAzimuth)
        form_layout.addRow(average_fold_axis_checkbox)
        form_layout.addRow("Fold Plunge", self.fold_plunge)
        form_layout.addRow("Fold Azimuth", self.fold_azimuth)
        # splot_button = QPushButton("S-Plot")
        # splot_button.clicked.connect(
        #     lambda: self.open_splot_dialog()
        # )
        # form_layout.addRow(splot_button)
        group_box = QgsCollapsibleGroupBox()
        group_box.setLayout(form_layout)
        self.layout.addWidget(group_box)
        # Remove redundant layout setting
        self.setLayout(self.layout)

    def open_splot_dialog(self):
        dialog = SPlotDialog(
            self,
            data_manager=self.data_manager,
            model_manager=self.model_manager,
            feature_name=self.feature.name,
        )
        if dialog.exec_() == dialog.Accepted:
            pass

    def remove_fold_frame(self):
        pass

    def foldAxisFromPlungeAzimuth(self):
        """Calculate the fold axis from plunge and azimuth."""
        if self.feature:
            plunge = self.fold_plunge.value()
            azimuth = self.fold_azimuth.value()
            vector = plungeazimuth2vector(plunge, azimuth)[0]
            if plunge is not None and azimuth is not None:
                self.feature.builder.update_build_arguments({'fold_axis': vector.tolist()})
                # schedule rebuild after updating builder arguments
                self.schedule_rebuild()
