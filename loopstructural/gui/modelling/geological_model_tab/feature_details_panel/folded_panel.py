import numpy as np
from LoopStructural.utils import plungeazimuth2vector
from qgis.gui import QgsCollapsibleGroupBox
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QCheckBox, QDoubleSpinBox, QFormLayout

from ..splot import SPlotDialog
from ._base import BaseFeatureDetailsPanel

_INVALID_SPINBOX_STYLE = "QDoubleSpinBox { background-color: #f8d7da; border: 1px solid #c0392b; }"


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

        use_average = 'av_fold_axis' in self.feature.builder.build_arguments
        average_fold_axis_checkbox = QCheckBox("Average Fold Axis")
        average_fold_axis_checkbox.setChecked(use_average)
        average_fold_axis_checkbox.stateChanged.connect(self.on_average_fold_axis_changed)
        self.fold_plunge = QDoubleSpinBox()
        self.fold_plunge.setRange(0, 90)
        self.fold_plunge.setValue(0)
        self.fold_azimuth = QDoubleSpinBox()
        self.fold_azimuth.setRange(0, 360)
        self.fold_azimuth.setValue(0)
        fold_axis = self.feature.builder.build_arguments.get('fold_axis', None)
        if fold_axis is not None and len(np.shape(fold_axis)) == 1:
            # show the fold axis the builder already has (inverse of
            # plungeazimuth2vector)
            x, y, z = np.asarray(fold_axis, dtype=float) / np.linalg.norm(fold_axis)
            self.fold_plunge.setValue(np.degrees(np.arcsin(np.clip(-z, -1, 1))))
            self.fold_azimuth.setValue(np.degrees(np.arctan2(x, y)) % 360)
        # plunge/azimuth are only used when the fold axis is not averaged
        self.fold_azimuth.setEnabled(not use_average)
        self.fold_plunge.setEnabled(not use_average)
        self._update_fold_axis_highlight()
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

    def open_splot_dialog(self):
        dialog = SPlotDialog(
            self,
            data_manager=self.data_manager,
            model_manager=self.model_manager,
            feature_name=self.feature.name,
        )
        if dialog.exec() == dialog.Accepted:
            pass

    def remove_fold_frame(self):
        pass

    def on_average_fold_axis_changed(self, state):
        """Turn the average fold axis on or off.

        LoopStructural averages the fold axis when the 'av_fold_axis' key is
        present in the build arguments, whatever its value, so the key is
        removed (not set to False) when the box is unticked.
        """
        use_average = state == Qt.CheckState.Checked
        self.fold_plunge.setEnabled(not use_average)
        self.fold_azimuth.setEnabled(not use_average)
        builder = self.feature.builder
        if use_average:
            builder.update_build_arguments({'av_fold_axis': True})
        elif 'av_fold_axis' in builder.build_arguments:
            builder._build_arguments.pop('av_fold_axis', None)
            builder._up_to_date = False
        self._update_fold_axis_highlight()
        self.schedule_rebuild()

    def _update_fold_axis_highlight(self):
        """Highlight the plunge/azimuth boxes in red while they are enabled
        but no fold axis is set on the builder, i.e. the values shown are
        not used by the model."""
        not_set = (
            self.fold_plunge.isEnabled()
            and self.feature.builder.build_arguments.get('fold_axis', None) is None
        )
        style = _INVALID_SPINBOX_STYLE if not_set else ""
        tooltip = "Fold axis not set. Change the plunge or azimuth to set it." if not_set else ""
        for spinbox in (self.fold_plunge, self.fold_azimuth):
            spinbox.setStyleSheet(style)
            spinbox.setToolTip(tooltip)

    def foldAxisFromPlungeAzimuth(self):
        """Calculate the fold axis from plunge and azimuth."""
        if self.feature:
            plunge = self.fold_plunge.value()
            azimuth = self.fold_azimuth.value()
            vector = plungeazimuth2vector(plunge, azimuth)[0]
            if plunge is not None and azimuth is not None:
                self.feature.builder.update_build_arguments({'fold_axis': vector.tolist()})
                self._update_fold_axis_highlight()
                # schedule rebuild after updating builder arguments
                self.schedule_rebuild()
