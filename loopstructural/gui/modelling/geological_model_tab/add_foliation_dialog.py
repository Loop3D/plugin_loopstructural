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


class AddFoliationDialog(QDialog):
    def __init__(self, parent=None, *, data_manager=None, model_manager=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.model_manager = model_manager
        ui_path = os.path.join(os.path.dirname(__file__), 'add_foliation_dialog.ui')
        loadUi(ui_path, self)
        self.setWindowTitle('Add Foliation')
        # Setup table columns
        self.items_table.setColumnCount(3)
        self.items_table.setHorizontalHeaderLabels(["Type", "Select Layer", "Delete"])
        # Connect add button
        self.add_item_button.clicked.connect(self.add_item_row)
        self.buttonBox.accepted.connect(self.add_foliation)
        self.buttonBox.rejected.connect(self.reject)

        self.modelFeatureComboBox.addItems(
            [f.name for f in self.model_manager.features() if not f.name.startswith("__")]
        )
        self.name_valid = False
        self.name_error = ""

        def validate_name_field(text):
            """Validate the feature name field."""
            valid = True
            old_name = self.name
            if not text.strip():
                valid = False
                self.name_error = "Feature name cannot be empty."
            elif text.strip() in [f.name for f in self.model_manager.features()]:
                valid = False
                self.name_error = "Feature name must be unique."
            elif text.strip() in self.data_manager.feature_data:
                valid = False
                self.name_error = "Layer already exists in the data manager."

            if not valid:
                self.name_valid = False
                self.feature_name_input.setStyleSheet("border: 1px solid red;")
            else:
                self.feature_name_input.setStyleSheet("")
                self.name_valid = True

            # Enable/disable the OK button based on validation
            self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(self.name_valid)

            # if the name changes make sure the data manager updates the key
            if old_name in self.data_manager.feature_data and old_name != self.name:
                self.data_manager.feature_data[self.name] = self.data_manager.feature_data.pop(
                    old_name
                )

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
            self.data_manager.update_feature_data(self.name, layer_data)
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
            data = {}
            button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)

            def validate_layer_selection():
                if layer_combo.currentLayer().name() in self.data_manager.feature_data[self.name]:
                    self.data_manager.logger("Layer already selected.", log_level=2)
                    button_box.button(QDialogButtonBox.Ok).setEnabled(False)
                    return False
                button_box.button(QDialogButtonBox.Ok).setEnabled(True)
                return True

            layer_combo.layerChanged.connect(validate_layer_selection)
            if btn.text() != "Select Layer" and hasattr(btn, 'selected_layer'):
                data = self.data_manager.feature_data[self.name].get(btn.text(), {})
            if 'layer' in data:
                layer_combo.setLayer(data['layer'])

            if type_combo.currentText() == "Orientation":
                field_layout = QHBoxLayout()

                strike_field_label = QLabel("Strike:")
                dip_field_label = QLabel("Dip:")
                format_combo = QComboBox()
                format_combo.addItems(["Strike", "Dip Direction"])

                def update_strike_label(text):
                    if text == "Dip Direction":
                        strike_field_label.setText("Dip Direction:")
                    else:
                        strike_field_label.setText("Strike:")

                format_combo.currentTextChanged.connect(update_strike_label)
                field_layout.addWidget(format_combo)
                strike_field_combo = QgsFieldComboBox()
                dip_field_combo = QgsFieldComboBox()
                strike_field_combo.setLayer(layer_combo.currentLayer())
                dip_field_combo.setLayer(layer_combo.currentLayer())
                field_layout.addWidget(strike_field_label)
                field_layout.addWidget(strike_field_combo)
                field_layout.addWidget(dip_field_label)
                field_layout.addWidget(dip_field_combo)
                layer_combo.layerChanged.connect(strike_field_combo.setLayer)
                layer_combo.layerChanged.connect(dip_field_combo.setLayer)
                layout.addLayout(field_layout)

                # Populate fields with pre-existing data
                if 'strike_field' in data:
                    strike_field_combo.setField(data['strike_field'])
                if 'dip_field' in data:
                    dip_field_combo.setField(data['dip_field'])
                if 'orientation_format' in data:
                    format_combo.setCurrentText(data['orientation_format'])
            if type_combo.currentText() == "Value":
                field_layout = QHBoxLayout()
                value_field_label = QLabel("Value Field:")
                value_field_combo = QgsFieldComboBox()
                value_field_combo.setLayer(layer_combo.currentLayer())
                field_layout.addWidget(value_field_label)
                field_layout.addWidget(value_field_combo)
                layout.addLayout(field_layout)
                layer_combo.layerChanged.connect(value_field_combo.setLayer)

                # Populate fields with pre-existing data
                if 'value_field' in data:
                    value_field_combo.setField(data['value_field'])

            if type_combo.currentText() == "Inequality":
                field_layout = QHBoxLayout()
                lower_field_label = QLabel("Lower")
                upper_field_label = QLabel("Upper")
                lower_field_combo = QgsFieldComboBox()
                upper_field_combo = QgsFieldComboBox()
                lower_field_combo.setLayer(layer_combo.currentLayer())
                upper_field_combo.setLayer(layer_combo.currentLayer())
                field_layout.addWidget(lower_field_label)
                field_layout.addWidget(lower_field_combo)
                field_layout.addWidget(upper_field_label)
                field_layout.addWidget(upper_field_combo)
                layout.addLayout(field_layout)
                layer_combo.layerChanged.connect(lower_field_combo.setLayer)
                layer_combo.layerChanged.connect(upper_field_combo.setLayer)

                # Populate fields with pre-existing data
                if 'lower_field' in data:
                    lower_field_combo.setField(data['lower_field'])
                if 'upper_field' in data:
                    upper_field_combo.setField(data['upper_field'])

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
                    data['orientation_format'] = format_combo.currentText()
                elif type_combo.currentText() == "Value":
                    if not value_field_combo.currentField():
                        return
                    data['value_field'] = value_field_combo.currentField()
                elif type_combo.currentText() == "Inequality":
                    if not lower_field_combo.currentField() or not upper_field_combo.currentField():
                        return
                    data['lower_field'] = lower_field_combo.currentField()
                    data['upper_field'] = upper_field_combo.currentField()

                data['layer'] = layer_combo.currentLayer()
                data['layer_name'] = layer_combo.currentLayer().name()
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
        combo.addItems(["Value", "Form Line", "Orientation", "Inequality"])
        return combo

    def _create_delete_button(self, row):
        from PyQt5.QtWidgets import QPushButton

        btn = QPushButton("Delete")
        btn.clicked.connect(lambda: self.delete_item_row(row))
        return btn

    def delete_item_row(self, row, layer_name):
        self.items_table.removeRow(row)
        print(f'removing layer: {layer_name} for foliation: {self.name}')
        self.data_manager.feature_data[self.name].pop(layer_name, None)
        print(self.data_manager.feature_data[self.name].keys())

    def add_foliation(self):
        if not self.name_valid:
            self.data_manager.logger(f'Name is invalid: {self.name_error}', log_level=2)
            return
        if len(self.data_manager.feature_data[self.name]) == 0:
            self.data_manager.logger("No layers selected for the foliation.", log_level=2)
            return
        folded_feature_name = None
        if self.modelFeatureComboBox.currentText() != "":
            folded_feature_name = self.modelFeatureComboBox.currentText()

        self.data_manager.add_foliation_to_model(self.name, folded_feature_name=folded_feature_name)
        self.accept()  # Close the dialog
