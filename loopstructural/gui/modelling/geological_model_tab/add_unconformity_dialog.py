from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QVBoxLayout,

)
from LoopStructural.modelling.features import FeatureType
class AddUnconformityDialog(QDialog):
    def __init__(self, parent=None, data_manager=None, model_manager=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.model_manager = model_manager
        self.setWindowTitle("Add Unconformity")
        self.setMinimumWidth(300)

        layout = QVBoxLayout()

        form_layout = QFormLayout()

        self.foliation_combo = QComboBox()
        foliations = [
            feature.name
            for feature in self.model_manager.features()
            if feature.type == FeatureType.INTERPOLATED
        ]
        self.foliation_combo.addItems(foliations)
        form_layout.addRow("Foliation:", self.foliation_combo)

        self.value_spinbox = QDoubleSpinBox()
        self.value_spinbox.setRange(-1e6, 1e6)
        self.value_spinbox.setDecimals(3)
        self.value_spinbox.setValue(0.0)
        form_layout.addRow("Value:", self.value_spinbox)

        self.type_combo = QComboBox()
        self.type_combo.addItems(["Unconformity", "Onlap Unconformity"])
        form_layout.addRow("Type:", self.type_combo)

        layout.addLayout(form_layout)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.setLayout(layout)

    def accept(self):
        foliation_name = self.foliation_combo.currentText()
        value = self.value_spinbox.value()
        type_text = self.type_combo.currentText()
        if type_text == "Unconformity":
            feature_type = FeatureType.UNCONFORMITY
        else:
            feature_type = FeatureType.ONLAPUNCONFORMITY

        try:
            self.model_manager.add_unconformity(foliation_name, value, feature_type)
            super().accept()
        except ValueError as e:
            from PyQt5.QtWidgets import QMessageBox

            QMessageBox.critical(self, "Error", str(e))
    def reject(self):
        super().reject()