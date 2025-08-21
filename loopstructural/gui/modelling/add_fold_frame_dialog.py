import os

from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)
from PyQt5.uic import loadUi
from qgis.core import QgsMapLayerProxyModel
from qgis.gui import QgsFieldComboBox, QgsMapLayerComboBox


class AddFoldFrameDialog(QDialog):
    def __init__(self, parent=None, *, data_manager=None, model_manager=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.model_manager = model_manager
        ui_path = os.path.join(os.path.dirname(__file__), 'add_fold_frame_dialog.ui')
        loadUi(ui_path, self)
        self.setWindowTitle('Add Fold Frame')
        # Setup table columns
        self.items_table.setColumnCount(3)
        self.items_table.setHorizontalHeaderLabels(["Type", "Select Layer", "Delete"])
        # Connect add button
        self.add_item_button.clicked.connect(self.add_item_row)
        self.buttonBox.accepted.connect(self.add_fold_frame)
        self.buttonBox.rejected.connect(self.reject)

        self.modelFeatureComboBox.addItems(
            [f.name for f in self.model_manager.features() if not f.name.startswith("__")]
        )
        self.name_valid = False
        self.name_error = ""

        def validate_name_field(text):
            """Validate the feature name field."""
            valid = True
            if not text.strip():
                valid = False
                self.name_error = "Feature name cannot be empty."
            if text.strip() in [f.name for f in self.model_manager.features()]:
                valid = False
                self.name_error = "Feature name must be unique."

            if not valid:
                self.name_valid = False
                self.feature_name_input.setStyleSheet("border: 1px solid red;")
            else:
                self.feature_name_input.setStyleSheet("")
                self.name_valid = True

        self.feature_name_input.textChanged.connect(validate_name_field)

    @property
    def name(self):
        return self.feature_name_input.text().strip()

    def add_item_row(self):
        row = self.items_table.rowCount()
        self.items_table.insertRow(row)
        # Type dropdown
        type_combo = self._create_type_combo()
        self.items_table.setCellWidget(row, 0, type_combo)
        # Select Layer button
        select_layer_btn = self._create_select_layer_button(row, type_combo)
        self.items_table.setCellWidget(row, 1, select_layer_btn)
        # Delete button
        del_btn = self._create_delete_button(row)
        self.items_table.setCellWidget(row, 2, del_btn)

    def add_layer_to_data_manager(self, layer_data: dict):
        """Add selected layer data to the data manager."""
        if not isinstance(layer_data, dict):
            raise ValueError("layer_data must be a dictionary.")
        if self.data_manager:
            self.data_manager.update_fold_frame_data(self.name, layer_data)
        else:
            raise RuntimeError("Data manager is not set.")

    def _create_select_layer_button(self, row, type_combo):
        btn = QPushButton("Select Layer")

        def open_layer_dialog():
            if not self.name_valid:
                self.data_manager.logger(f'Name is invalid: {self.name_error}', log_level=2)
                return
            dialog = QDialog(self)
            dialog.setWindowTitle("Select Layer")
            layout = QVBoxLayout(dialog)
            # Layer combo box (replace with QgsLayerComboBox in QGIS environment)
            layer_label = QLabel("Layer:")
            layout.addWidget(layer_label)
            layer_combo = QgsMapLayerComboBox()
            layer_combo.setFilters(
                QgsMapLayerProxyModel.LineLayer | QgsMapLayerProxyModel.PointLayer
            )
            layout.addWidget(layer_combo)
            strike_field_combo = None
            dip_field_combo = None
            if type_combo.currentText() == "Orientation":
                field_layout = QHBoxLayout()
                strike_field_label = QLabel("Strike:")
                dip_field_label = QLabel("Dip:")

                strike_field_combo = QgsFieldComboBox()
                dip_field_combo = QgsFieldComboBox()
                field_layout.addWidget(strike_field_label)
                field_layout.addWidget(strike_field_combo)
                field_layout.addWidget(dip_field_label)
                field_layout.addWidget(dip_field_combo)
                layer_combo.layerChanged.connect(strike_field_combo.setLayer)

                layer_combo.layerChanged.connect(dip_field_combo.setLayer)
                layout.addLayout(field_layout)
            button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            layout.addWidget(button_box)
            button_box.accepted.connect(dialog.accept)
            button_box.rejected.connect(dialog.reject)

            def on_accepted():
                """Handle the accepted signal from the dialog."""
                data = {}
                if layer_combo.currentLayer() is None:
                    return
                if type_combo.currentText() == "Orientation":
                    if not strike_field_combo.currentField() or not dip_field_combo.currentField():
                        return
                    data['strike_field'] = strike_field_combo.currentField()
                    data['dip_field'] = dip_field_combo.currentField()
                data['layer'] = layer_combo.currentLayer()
                data['type'] = type_combo.currentText()
                self.add_layer_to_data_manager(data)

            if dialog.exec_() == QDialog.Accepted:
                selected_layer = layer_combo.currentText()
                btn.setText(selected_layer)
                on_accepted()
                # Optionally, store selected layer/fields in table for later retrieval
                btn.selected_layer = selected_layer
                if strike_field_combo and dip_field_combo:
                    btn.strike_field = strike_field_combo.currentText()
                    btn.dip_field = dip_field_combo.currentText()
                else:
                    btn.strike_field = None
                    btn.dip_field = None

        btn.clicked.connect(open_layer_dialog)
        return btn

    def _create_type_combo(self):
        from PyQt5.QtWidgets import QComboBox

        combo = QComboBox()
        combo.addItems(["Form Line", "Orientation"])
        return combo

    def _create_delete_button(self, row):
        from PyQt5.QtWidgets import QPushButton

        btn = QPushButton("Delete")
        btn.clicked.connect(lambda: self.delete_item_row(row))
        return btn

    def delete_item_row(self, row):
        self.items_table.removeRow(row)

    def add_fold_frame(self):
        if not self.name_valid:
            self.data_manager.logger(f'Name is invalid: {self.name_error}', log_level=2)
            return
        if len(self.data_manager.fold_data[self.name]) == 0:
            self.data_manager.logger("No layers selected for the fold frame.", log_level=2)
            return
        folded_feature_name = None
        if self.modelFeatureComboBox.currentText() != "":
            folded_feature_name = self.modelFeatureComboBox.currentText()

        self.data_manager.add_fold_to_model(self.name, folded_feature_name=folded_feature_name)
        self.accept()  # Close the dialog
