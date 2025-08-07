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


class AddFoldFrameDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        ui_path = os.path.join(os.path.dirname(__file__), 'add_fold_frame_dialog.ui')
        loadUi(ui_path, self)
        self.setWindowTitle('Add Fold Frame')
        # Setup table columns
        self.items_table.setColumnCount(3)
        self.items_table.setHorizontalHeaderLabels(["Type", "Select Layer", "Delete"])
        # Connect add button
        self.add_item_button.clicked.connect(self.add_item_row)

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

    def _create_select_layer_button(self, row, type_combo):
        btn = QPushButton("Select Layer")

        def open_layer_dialog():
            dialog = QDialog(self)
            dialog.setWindowTitle("Select Layer")
            layout = QVBoxLayout(dialog)
            # Layer combo box (replace with QgsLayerComboBox in QGIS environment)
            layer_label = QLabel("Layer:")
            layout.addWidget(layer_label)
            layer_combo = QComboBox(dialog)
            # TODO: Populate with actual layer names from QGIS
            layer_combo.addItems(["Layer1", "Layer2", "Layer3"])
            layout.addWidget(layer_combo)

            strike_field_combo = None
            dip_field_combo = None
            field_layout = None

            def update_fields():
                nonlocal strike_field_combo, dip_field_combo, field_layout
                if type_combo.currentText() == "Orientation":
                    if not field_layout:
                        field_layout = QHBoxLayout()
                        strike_field_combo = QComboBox(dialog)
                        dip_field_combo = QComboBox(dialog)
                        # TODO: Populate with actual field names from selected layer
                        strike_field_combo.addItems(["strike1", "strike2"])
                        dip_field_combo.addItems(["dip1", "dip2"])
                        field_layout.addWidget(QLabel("Strike:"))
                        field_layout.addWidget(strike_field_combo)
                        field_layout.addWidget(QLabel("Dip:"))
                        field_layout.addWidget(dip_field_combo)
                        layout.addLayout(field_layout)
                else:
                    if field_layout:
                        # Remove field combo boxes if not orientation
                        for i in reversed(range(field_layout.count())):
                            widget = field_layout.itemAt(i).widget()
                            if widget:
                                widget.setParent(None)
                        layout.removeItem(field_layout)
                        strike_field_combo = None
                        dip_field_combo = None
                        field_layout = None

            type_combo.currentIndexChanged.connect(update_fields)
            update_fields()

            button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            layout.addWidget(button_box)
            button_box.accepted.connect(dialog.accept)
            button_box.rejected.connect(dialog.reject)

            if dialog.exec_() == QDialog.Accepted:
                selected_layer = layer_combo.currentText()
                btn.setText(selected_layer)
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

    def get_fold_frame_data(self):
        # Collect feature name and all items from the table
        feature_name = (
            self.feature_name_input.text() if hasattr(self, 'feature_name_input') else None
        )
        items = []
        for row in range(self.items_table.rowCount()):
            type_widget = self.items_table.cellWidget(row, 0)
            select_layer_btn = self.items_table.cellWidget(row, 1)
            item_type = type_widget.currentText() if type_widget else None
            layer = getattr(select_layer_btn, 'selected_layer', None) if select_layer_btn else None
            strike_field = (
                getattr(select_layer_btn, 'strike_field', None) if select_layer_btn else None
            )
            dip_field = getattr(select_layer_btn, 'dip_field', None) if select_layer_btn else None
            items.append(
                {
                    'type': item_type,
                    'layer': layer,
                    'strike_field': strike_field,
                    'dip_field': dip_field,
                }
            )
        return {'feature_name': feature_name, 'items': items}
