from qgis.gui import QgsCollapsibleGroupBox
from qgis.PyQt.QtWidgets import QComboBox, QFormLayout, QPushButton

from ._base import BaseFeatureDetailsPanel


class FoliationFeatureDetailsPanel(BaseFeatureDetailsPanel):
    def __init__(self, parent=None, *, feature=None, model_manager=None, data_manager=None):
        super().__init__(
            parent, feature=feature, model_manager=model_manager, data_manager=data_manager
        )
        if feature is None:
            raise ValueError("Feature must be provided.")
        self.feature = feature

    def addMidBlock(self):
        form_layout = QFormLayout()
        fold_frame_combobox = QComboBox()
        fold_frame_combobox.addItems([""] + [f.name for f in self.model_manager.fold_frames])
        fold_frame_combobox.currentTextChanged.connect(self.on_fold_frame_changed)
        form_layout.addRow("Attach fold frame", fold_frame_combobox)

        convert_to_frame_button = QPushButton("Convert to Structural Frame")
        convert_to_frame_button.clicked.connect(
            lambda: self.model_manager.convert_feature_to_structural_frame(self.feature.name)
        )
        form_layout.addRow(convert_to_frame_button)
        group_box = QgsCollapsibleGroupBox('Fold Settings')
        group_box.setLayout(form_layout)
        self.layout.addWidget(group_box)

        # Remove redundant layout setting
        self.setLayout(self.layout)

    def on_fold_frame_changed(self, text):
        self.model_manager.add_fold_to_feature(self.feature.name, fold_frame_name=text)
