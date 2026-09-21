from qgis.core import QgsMapLayerProxyModel
from qgis.gui import QgsFieldComboBox, QgsMapLayerComboBox
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from loopstructural.gui.compatibility import configure_layer_combo


class LayerSelectionTable(QWidget):
    """
    Self-contained widget for layer selection table functionality for geological features.

    This widget includes:
    - A table for displaying selected layers with Type, Layer, and Delete columns
    - An "Add Data" button at the bottom for adding new layers
    - Complete data management integration with data_manager.feature_data

    Usage example:
        # Create the widget
        layer_table = LayerSelectionTable(
            data_manager=my_data_manager,
            feature_name_provider=lambda: "my_feature_name",
            name_validator=lambda: (True, "")  # or your validation logic
        )

        # Add to your layout
        layout.addWidget(layer_table)

        # Access data
        if layer_table.has_layers():
            data = layer_table.get_table_data()
    """

    def __init__(self, data_manager, feature_name_provider, name_validator, parent=None):
        """
        Initialize the layer selection table widget.

        Args:
            data_manager: Data manager instance
            feature_name_provider: Callable that returns the current feature name
            name_validator: Callable that returns (is_valid, error_message)
            parent: Parent widget (optional)
        """
        super().__init__(parent)
        self.data_manager = data_manager
        self.get_feature_name = feature_name_provider
        self.validate_name = name_validator

        self._setup_ui()
        self.initialize_feature_data()
        self.restore_table_state()

    def _setup_ui(self):
        """Setup the widget UI with table and add button."""
        layout = QVBoxLayout(self)

        # Create the table widget
        self.table = QTableWidget()
        self._setup_table()
        layout.addWidget(self.table)

        # Create add button
        self.add_button = QPushButton("Add Data")
        self.add_button.clicked.connect(self.add_item_row)
        layout.addWidget(self.add_button)

    def _setup_table(self):
        """Setup table columns and headers."""
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Type", "Select Layer", "Delete"])

    def initialize_feature_data(self):
        """Initialize feature data in the data manager if it doesn't exist."""
        feature_name = self.get_feature_name()
        if feature_name and feature_name not in self.data_manager.feature_data:
            self.data_manager.feature_data[feature_name] = {}

    def restore_table_state(self):
        """Restore table state from data manager."""
        feature_name = self.get_feature_name()
        if not feature_name or feature_name not in self.data_manager.feature_data:
            return

        # Clear existing table rows
        self.table.setRowCount(0)

        # Restore rows from data
        feature_data = self.data_manager.feature_data[feature_name]
        for _layer_name, layer_data in feature_data.items():
            self._add_row_from_data(layer_data)

    def _add_row_from_data(self, layer_data):
        """Add a row to the table from existing data."""
        row = self.table.rowCount()
        self.table.insertRow(row)

        if layer_data.get('processed'):
            self._add_processed_row(row, layer_data)
            return

        # Type dropdown
        type_combo = self._create_type_combo()
        type_combo.setCurrentText(layer_data.get('type', 'Value'))
        self.table.setCellWidget(row, 0, type_combo)

        # Select Layer button
        select_layer_btn = self._create_select_layer_button(row, type_combo)
        self._update_button_with_selection(select_layer_btn, layer_data)
        self.table.setCellWidget(row, 1, select_layer_btn)

        # Delete button
        del_btn = self._create_delete_button(row)
        self.table.setCellWidget(row, 2, del_btn)

    def _add_processed_row(self, row, layer_data):
        """Render a row added automatically by the data-processing workflow
        (basal contacts / structural orientations / fault traces).

        These rows aren't backed by a per-row layer/field selection made
        through this table -- they mirror what `data_manager` synced in from
        the model manager -- so they're read-only: no field picker to edit,
        and nothing here to delete (that data is managed by the map2loop
        tool widgets, not this table).
        """
        type_label = QLabel(layer_data.get('type', 'Processed'))
        self.table.setCellWidget(row, 0, type_label)

        layer_btn = QPushButton(layer_data.get('layer_name', 'Unknown'))
        layer_btn.setEnabled(False)
        layer_btn.selected_layer = layer_data.get('layer_name')
        layer_btn.setToolTip(
            "Added automatically by the data processing workflow. Use "
            "'View Data Used by Interpolator' below to inspect it on the map."
        )
        self.table.setCellWidget(row, 1, layer_btn)

        del_btn = QPushButton("Delete")
        del_btn.setEnabled(False)
        del_btn.setToolTip("Managed by the data processing workflow, not editable here.")
        self.table.setCellWidget(row, 2, del_btn)

    def add_item_row(self):
        """Add a new row to the table."""
        self.initialize_feature_data()  # Ensure feature data exists

        row = self.table.rowCount()
        self.table.insertRow(row)

        # Type dropdown
        type_combo = self._create_type_combo()
        self.table.setCellWidget(row, 0, type_combo)

        # Select Layer button
        select_layer_btn = self._create_select_layer_button(row, type_combo)
        self.table.setCellWidget(row, 1, select_layer_btn)

        # Delete button
        del_btn = self._create_delete_button(row)
        self.table.setCellWidget(row, 2, del_btn)

    def _create_type_combo(self):
        """Create type selection combo box."""
        combo = QComboBox()
        combo.addItems(["Value", "Form Line", "Orientation", "Inequality"])
        return combo

    def _create_select_layer_button(self, row, type_combo):
        """Create select layer button."""
        btn = QPushButton("Select Layer")

        def open_layer_dialog():
            name_valid, name_error = self.validate_name()
            if not name_valid:
                self.data_manager.logger(f'Name is invalid: {name_error}', log_level=2)
                return

            dialog = LayerSelectionDialog(
                parent=self.table,
                data_manager=self.data_manager,
                feature_name=self.get_feature_name(),
                layer_type=type_combo.currentText(),
                existing_data=self._get_existing_data_for_button(btn),
            )

            if dialog.exec_() == QDialog.Accepted:
                layer_data = dialog.get_layer_data()
                if layer_data:
                    self._update_button_with_selection(btn, layer_data)
                    self._add_layer_to_data_manager(layer_data)

        btn.clicked.connect(open_layer_dialog)
        return btn

    def _create_delete_button(self, row):
        """Create delete button for a row."""
        btn = QPushButton("Delete")
        btn.clicked.connect(lambda: self._delete_item_row(row))
        return btn

    def _delete_item_row(self, row):
        """Delete a row from the table and update data manager."""
        # Find the select layer button in the same row to get layer name
        select_btn = self.table.cellWidget(row, 1)
        if hasattr(select_btn, 'selected_layer'):
            layer_name = select_btn.selected_layer
            feature_name = self.get_feature_name()
            if feature_name in self.data_manager.feature_data:
                self.data_manager.feature_data[feature_name].pop(layer_name, None)
                print(f'Removing layer: {layer_name} for feature: {feature_name}')

        # Remove the row from table
        self.table.removeRow(row)

        # Update delete button connections for remaining rows
        self._update_delete_button_connections()

    def _update_delete_button_connections(self):
        """Update delete button connections after row deletion to maintain correct row indices."""
        for row in range(self.table.rowCount()):
            delete_btn = self.table.cellWidget(row, 2)
            # Processed rows' delete buttons are disabled and were never
            # connected in the first place -- disconnect() with no prior
            # connection raises, and there's no row-index-dependent state to
            # refresh on them anyway.
            if delete_btn and delete_btn.isEnabled():
                # Disconnect old connections
                delete_btn.clicked.disconnect()
                # Reconnect with correct row index
                delete_btn.clicked.connect(lambda checked, r=row: self._delete_item_row(r))

    def _get_existing_data_for_button(self, btn):
        """Get existing data for a button if it has been configured."""
        if btn.text() != "Select Layer" and hasattr(btn, 'selected_layer'):
            feature_name = self.get_feature_name()
            if feature_name and feature_name in self.data_manager.feature_data:
                return self.data_manager.feature_data[feature_name].get(btn.selected_layer, {})
        return {}

    def _update_button_with_selection(self, btn, layer_data):
        """Update button text and store selection data."""
        layer_name = layer_data.get('layer_name', 'Unknown')
        btn.setText(layer_name)
        btn.selected_layer = layer_name

        # Store field information for different types
        btn.strike_field = layer_data.get('strike_field')
        btn.dip_field = layer_data.get('dip_field')
        btn.value_field = layer_data.get('value_field')
        btn.lower_field = layer_data.get('lower_field')
        btn.upper_field = layer_data.get('upper_field')

    def _add_layer_to_data_manager(self, layer_data):
        """Add selected layer data to the data manager."""
        if not isinstance(layer_data, dict):
            raise ValueError("layer_data must be a dictionary.")
        if self.data_manager:
            feature_name = self.get_feature_name()
            self.data_manager.update_feature_data(feature_name, layer_data)
        else:
            raise RuntimeError("Data manager is not set.")

    def clear_table(self):
        """Clear all rows from the table and reset feature data."""
        feature_name = self.get_feature_name()
        if feature_name and feature_name in self.data_manager.feature_data:
            self.data_manager.feature_data[feature_name].clear()

        # Clear all table rows
        self.table.setRowCount(0)

    def get_table_data(self):
        """Get all table data as a dictionary."""
        feature_name = self.get_feature_name()
        if feature_name and feature_name in self.data_manager.feature_data:
            return self.data_manager.feature_data[feature_name].copy()
        return {}

    def set_table_data(self, data):
        """Set table data and restore table state."""
        feature_name = self.get_feature_name()
        if not feature_name:
            return

        # Clear existing table
        self.clear_table()

        # Update data manager
        self.initialize_feature_data()
        self.data_manager.feature_data[feature_name] = data.copy()

        # Restore table state
        self.restore_table_state()

    def validate_table_state(self):
        """Validate that table state matches data manager state."""
        feature_name = self.get_feature_name()
        if not feature_name or feature_name not in self.data_manager.feature_data:
            return True

        feature_data = self.data_manager.feature_data[feature_name]
        table_layers = []

        # Collect layers from table
        for row in range(self.table.rowCount()):
            select_btn = self.table.cellWidget(row, 1)
            if hasattr(select_btn, 'selected_layer'):
                table_layers.append(select_btn.selected_layer)

        # Compare with data manager
        data_layers = list(feature_data.keys())

        if set(table_layers) != set(data_layers):
            print(f"Table state inconsistency detected for feature '{feature_name}':")
            print(f"  Table layers: {table_layers}")
            print(f"  Data layers: {data_layers}")
            return False

        return True

    def sync_table_with_data(self):
        """Synchronize table state with data manager state."""
        if not self.validate_table_state():
            print("Syncing table with data manager...")
            self.restore_table_state()

    def get_layer_count(self):
        """Get the number of layers currently in the table."""
        feature_name = self.get_feature_name()
        if feature_name and feature_name in self.data_manager.feature_data:
            return len(self.data_manager.feature_data[feature_name])
        return 0

    def has_layers(self):
        """Check if there are any layers in the table."""
        return self.get_layer_count() > 0

    def get_layer_names(self):
        """Get a list of all layer names in the table."""
        feature_name = self.get_feature_name()
        if feature_name and feature_name in self.data_manager.feature_data:
            return list(self.data_manager.feature_data[feature_name].keys())
        return []

    def get_table_widget(self):
        """Get the internal table widget for direct access if needed."""
        return self.table

    def get_add_button(self):
        """Get the add button widget for customization if needed."""
        return self.add_button

    def set_add_button_text(self, text):
        """Set the text of the add button."""
        self.add_button.setText(text)

    def set_table_headers(self, headers):
        """Set custom table headers."""
        if len(headers) == 3:
            self.table.setHorizontalHeaderLabels(headers)
        else:
            raise ValueError("Headers list must contain exactly 3 items")

    def set_add_button_enabled(self, enabled):
        """Enable or disable the add button."""
        self.add_button.setEnabled(enabled)

    def is_add_button_enabled(self):
        """Check if the add button is enabled."""
        return self.add_button.isEnabled()


class LayerSelectionDialog(QDialog):
    """Dialog for selecting layers and configuring their fields."""

    def __init__(
        self, parent=None, data_manager=None, feature_name="", layer_type="", existing_data=None
    ):
        super().__init__(parent)
        self.data_manager = data_manager
        self.feature_name = feature_name
        self.layer_type = layer_type
        self.existing_data = existing_data or {}
        self.layer_data = {}

        self.setWindowTitle("Select Layer")
        self._setup_ui()

    def _setup_ui(self):
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)

        # Layer selection
        layer_label = QLabel("Layer:")
        layout.addWidget(layer_label)

        self.layer_combo = QgsMapLayerComboBox()
        configure_layer_combo(
            self.layer_combo, QgsMapLayerProxyModel.LineLayer | QgsMapLayerProxyModel.PointLayer
        )
        layout.addWidget(self.layer_combo)

        # Set existing layer if available
        if 'layer' in self.existing_data:
            self.layer_combo.setLayer(self.existing_data['layer'])

        # Type-specific field selection
        self._setup_type_specific_fields(layout)

        # Dialog buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(self.button_box)

        self.button_box.accepted.connect(self._on_accepted)
        self.button_box.rejected.connect(self.reject)

        # Validation
        self.layer_combo.layerChanged.connect(self._validate_layer_selection)
        self._validate_layer_selection()

    def _setup_type_specific_fields(self, layout):
        """Setup fields specific to the layer type."""
        self.field_combos = {}

        if self.layer_type == "Orientation":
            self._setup_orientation_fields(layout)
        elif self.layer_type == "Value":
            self._setup_value_fields(layout)
        elif self.layer_type == "Inequality":
            self._setup_inequality_fields(layout)
        elif self.layer_type == "Form Line":
            self._setup_form_line_fields(layout)

    def _setup_orientation_fields(self, layout):
        """Setup fields for orientation data type."""
        field_layout = QHBoxLayout()

        # Format selection
        self.format_combo = QComboBox()
        self.format_combo.addItems(["Strike", "Dip Direction"])
        if 'orientation_format' in self.existing_data:
            self.format_combo.setCurrentText(self.existing_data['orientation_format'])
        field_layout.addWidget(self.format_combo)

        # Strike/Dip Direction field
        self.strike_field_label = QLabel("Strike:")
        self.strike_field_combo = QgsFieldComboBox()
        self.strike_field_combo.setLayer(self.layer_combo.currentLayer())
        if 'strike_field' in self.existing_data:
            self.strike_field_combo.setField(self.existing_data['strike_field'])

        field_layout.addWidget(self.strike_field_label)
        field_layout.addWidget(self.strike_field_combo)

        # Dip field
        dip_field_label = QLabel("Dip:")
        self.dip_field_combo = QgsFieldComboBox()
        self.dip_field_combo.setLayer(self.layer_combo.currentLayer())
        if 'dip_field' in self.existing_data:
            self.dip_field_combo.setField(self.existing_data['dip_field'])

        field_layout.addWidget(dip_field_label)
        field_layout.addWidget(self.dip_field_combo)

        layout.addLayout(field_layout)

        # Update strike label based on format
        def update_strike_label(text):
            if text == "Dip Direction":
                self.strike_field_label.setText("Dip Direction:")
            else:
                self.strike_field_label.setText("Strike:")

        self.format_combo.currentTextChanged.connect(update_strike_label)
        self.layer_combo.layerChanged.connect(self.strike_field_combo.setLayer)
        self.layer_combo.layerChanged.connect(self.dip_field_combo.setLayer)

        self.field_combos = {
            'strike_field': self.strike_field_combo,
            'dip_field': self.dip_field_combo,
            'format': self.format_combo,
        }

    def _setup_value_fields(self, layout):
        """Setup fields for value data type."""
        field_layout = QHBoxLayout()

        value_field_label = QLabel("Value Field:")
        self.value_field_combo = QgsFieldComboBox()
        self.value_field_combo.setLayer(self.layer_combo.currentLayer())
        if 'value_field' in self.existing_data:
            self.value_field_combo.setField(self.existing_data['value_field'])

        field_layout.addWidget(value_field_label)
        field_layout.addWidget(self.value_field_combo)
        layout.addLayout(field_layout)

        self.layer_combo.layerChanged.connect(self.value_field_combo.setLayer)

        self.field_combos = {'value_field': self.value_field_combo}

    def _setup_form_line_fields(self, layout):
        """Setup fields for form line data type.

        A form line has no attribute field to pick -- its geometry *is* the
        constraint. The only choice is what the line means to the scalar
        field: that it's constant (but unknown) along the line, or that the
        line marks the local strike direction of the field.

        "Constrain Strike" can optionally add a dip magnitude too (e.g. an
        axial surface known to dip ~60 degrees). This is added as a
        low-weight constraint alongside the (hard) per-vertex strike from
        the line, rather than replacing it: the line's own direction is a
        precisely known fact, but the dip is usually only a rough regional
        estimate, and digitising direction leaves which way the surface
        dips ambiguous -- "Reverse dip direction" flips between the two
        mirror-image planes that share the same strike and dip magnitude.
        """
        field_layout = QHBoxLayout()

        constraint_label = QLabel("Constraint:")
        self.constraint_combo = QComboBox()
        self.constraint_combo.addItems(["Constant Value", "Constrain Strike"])
        if self.existing_data.get('form_line_constraint') == 'strike':
            self.constraint_combo.setCurrentText("Constrain Strike")

        field_layout.addWidget(constraint_label)
        field_layout.addWidget(self.constraint_combo)
        layout.addLayout(field_layout)

        self.dip_group = QWidget()
        dip_layout = QFormLayout(self.dip_group)

        self.constrain_dip_checkbox = QCheckBox("Also constrain dip (weak)")
        self.constrain_dip_checkbox.setChecked(
            self.existing_data.get('form_line_dip') is not None
        )
        dip_layout.addRow(self.constrain_dip_checkbox)

        self.dip_spin = QDoubleSpinBox()
        self.dip_spin.setRange(0, 90)
        self.dip_spin.setValue(self.existing_data.get('form_line_dip') or 60.0)
        dip_layout.addRow("Dip", self.dip_spin)

        self.reverse_dip_checkbox = QCheckBox("Reverse dip direction")
        self.reverse_dip_checkbox.setChecked(
            bool(self.existing_data.get('form_line_reverse_dip', False))
        )
        dip_layout.addRow(self.reverse_dip_checkbox)

        self.dip_weight_spin = QDoubleSpinBox()
        self.dip_weight_spin.setRange(0.001, 1.0)
        self.dip_weight_spin.setSingleStep(0.01)
        self.dip_weight_spin.setDecimals(3)
        self.dip_weight_spin.setValue(self.existing_data.get('form_line_dip_weight', 0.1))
        dip_layout.addRow("Weight", self.dip_weight_spin)

        self.dip_spin.setEnabled(self.constrain_dip_checkbox.isChecked())
        self.reverse_dip_checkbox.setEnabled(self.constrain_dip_checkbox.isChecked())
        self.dip_weight_spin.setEnabled(self.constrain_dip_checkbox.isChecked())
        self.constrain_dip_checkbox.toggled.connect(self.dip_spin.setEnabled)
        self.constrain_dip_checkbox.toggled.connect(self.reverse_dip_checkbox.setEnabled)
        self.constrain_dip_checkbox.toggled.connect(self.dip_weight_spin.setEnabled)

        layout.addWidget(self.dip_group)

        def update_dip_visibility(text):
            self.dip_group.setVisible(text == "Constrain Strike")

        self.constraint_combo.currentTextChanged.connect(update_dip_visibility)
        update_dip_visibility(self.constraint_combo.currentText())

        self.field_combos = {
            'constraint_combo': self.constraint_combo,
            'constrain_dip_checkbox': self.constrain_dip_checkbox,
            'dip_spin': self.dip_spin,
            'reverse_dip_checkbox': self.reverse_dip_checkbox,
            'dip_weight_spin': self.dip_weight_spin,
        }

    def _setup_inequality_fields(self, layout):
        """Setup fields for inequality data type."""
        field_layout = QHBoxLayout()

        lower_field_label = QLabel("Lower:")
        self.lower_field_combo = QgsFieldComboBox()
        self.lower_field_combo.setLayer(self.layer_combo.currentLayer())
        if 'lower_field' in self.existing_data:
            self.lower_field_combo.setField(self.existing_data['lower_field'])

        upper_field_label = QLabel("Upper:")
        self.upper_field_combo = QgsFieldComboBox()
        self.upper_field_combo.setLayer(self.layer_combo.currentLayer())
        if 'upper_field' in self.existing_data:
            self.upper_field_combo.setField(self.existing_data['upper_field'])

        field_layout.addWidget(lower_field_label)
        field_layout.addWidget(self.lower_field_combo)
        field_layout.addWidget(upper_field_label)
        field_layout.addWidget(self.upper_field_combo)
        layout.addLayout(field_layout)

        self.layer_combo.layerChanged.connect(self.lower_field_combo.setLayer)
        self.layer_combo.layerChanged.connect(self.upper_field_combo.setLayer)

        self.field_combos = {
            'lower_field': self.lower_field_combo,
            'upper_field': self.upper_field_combo,
        }

    def _validate_layer_selection(self):
        """Validate the current layer selection."""
        if self.layer_combo.currentLayer() is None:
            self.button_box.button(QDialogButtonBox.Ok).setEnabled(False)
            return False

        layer_name = self.layer_combo.currentLayer().name()
        is_layer_being_edited = layer_name == self.existing_data.get('layer_name')
        if not is_layer_being_edited and layer_name in self.data_manager.feature_data.get(
            self.feature_name, {}
        ):
            self.data_manager.logger("Layer already selected.", log_level=2)
            self.button_box.button(QDialogButtonBox.Ok).setEnabled(False)
            return False

        self.button_box.button(QDialogButtonBox.Ok).setEnabled(True)
        return True

    def _on_accepted(self):
        """Handle dialog acceptance."""
        if self.layer_combo.currentLayer() is None:
            return

        self.layer_data = {
            'layer': self.layer_combo.currentLayer(),
            'layer_name': self.layer_combo.currentLayer().name(),
            'type': self.layer_type,
        }

        # Add type-specific data
        if self.layer_type == "Orientation":
            if (
                not self.field_combos['strike_field'].currentField()
                or not self.field_combos['dip_field'].currentField()
            ):
                return
            self.layer_data['strike_field'] = self.field_combos['strike_field'].currentField()
            self.layer_data['dip_field'] = self.field_combos['dip_field'].currentField()
            self.layer_data['orientation_format'] = self.field_combos['format'].currentText()

        elif self.layer_type == "Value":
            if not self.field_combos['value_field'].currentField():
                return
            self.layer_data['value_field'] = self.field_combos['value_field'].currentField()

        elif self.layer_type == "Inequality":
            if (
                not self.field_combos['lower_field'].currentField()
                or not self.field_combos['upper_field'].currentField()
            ):
                return
            self.layer_data['lower_field'] = self.field_combos['lower_field'].currentField()
            self.layer_data['upper_field'] = self.field_combos['upper_field'].currentField()

        elif self.layer_type == "Form Line":
            constraint_text = self.field_combos['constraint_combo'].currentText()
            is_strike = constraint_text == "Constrain Strike"
            self.layer_data['form_line_constraint'] = 'strike' if is_strike else 'value'
            if is_strike and self.field_combos['constrain_dip_checkbox'].isChecked():
                self.layer_data['form_line_dip'] = self.field_combos['dip_spin'].value()
                self.layer_data['form_line_reverse_dip'] = self.field_combos[
                    'reverse_dip_checkbox'
                ].isChecked()
                self.layer_data['form_line_dip_weight'] = self.field_combos[
                    'dip_weight_spin'
                ].value()

        self.accept()

    def get_layer_data(self):
        """Get the configured layer data."""
        return self.layer_data
