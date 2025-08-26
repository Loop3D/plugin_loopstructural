import os

from PyQt5.QtWidgets import QDialog, QDialogButtonBox
from PyQt5.uic import loadUi

from .layer_selection_table import LayerSelectionTable


class AddFoliationDialog(QDialog):
    def __init__(self, parent=None, *, data_manager=None, model_manager=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.model_manager = model_manager
        ui_path = os.path.join(os.path.dirname(__file__), 'add_foliation_dialog.ui')
        loadUi(ui_path, self)
        self.setWindowTitle('Add Foliation')
        
        # Create the layer selection table widget
        self.layer_table = LayerSelectionTable(
            data_manager=self.data_manager,
            feature_name_provider=lambda: self.name,
            name_validator=lambda: (self.name_valid, self.name_error)
        )
        
        # Replace or integrate with existing UI
        self._integrate_layer_table()
        
        self.buttonBox.accepted.connect(self.add_foliation)
        self.buttonBox.rejected.connect(self.cancel)

        self.modelFeatureComboBox.addItems(
            [f.name for f in self.model_manager.features() if not f.name.startswith("__")]
        )
        self.name_valid = False
        self.name_error = ""

        def validate_name_field(text):
            """Validate the feature name field."""
            valid = True
            old_name = self.name
            new_name = text.strip()
            
            if not new_name:
                valid = False
                self.name_error = "Feature name cannot be empty."
            elif new_name in [f.name for f in self.model_manager.features()]:
                valid = False
                self.name_error = "Feature name must be unique."
            elif new_name in self.data_manager.feature_data:
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

            # If the name changes, update the data manager key and reinitialize table
            if old_name != new_name and old_name in self.data_manager.feature_data:
                # Save current table data
                old_data = self.layer_table.get_table_data()
                
                # Remove old key and set new key
                self.data_manager.feature_data.pop(old_name, None)
                if new_name and valid:
                    self.data_manager.feature_data[new_name] = old_data
                    
                    # Update table to reflect new feature name
                    self.layer_table.initialize_feature_data()
                    self.layer_table.restore_table_state()

        self.feature_name_input.textChanged.connect(validate_name_field)

    @property
    def name(self):
        return self.feature_name_input.text().strip()

    def add_foliation(self):
        if not self.name_valid:
            self.data_manager.logger(f'Name is invalid: {self.name_error}', log_level=2)
            return
        
        # Ensure table state is synchronized with data manager
        self.layer_table.sync_table_with_data()
        
        # Check if we have any layers selected
        if not self.layer_table.has_layers():
            self.data_manager.logger("No layers selected for the foliation.", log_level=2)
            return
            
        folded_feature_name = None
        if self.modelFeatureComboBox.currentText() != "":
            folded_feature_name = self.modelFeatureComboBox.currentText()

        self.data_manager.add_foliation_to_model(self.name, folded_feature_name=folded_feature_name)
        self.accept()  # Close the dialog

    def cancel(self):
        # Clean up any temporary data if necessary
        if self.name in self.data_manager.feature_data:
            self.data_manager.feature_data.pop(self.name, None)
        self.reject()

    def _integrate_layer_table(self):
        """Integrate the layer table widget with the existing UI."""
        # Try to replace existing table widget if it exists
        if hasattr(self, 'items_table'):
            table_parent = self.items_table.parent()
            
            # Get the position of the original table
            if hasattr(table_parent, 'layout') and table_parent.layout():
                layout = table_parent.layout()
                
                # Find the index of the original table in the layout
                table_index = -1
                for i in range(layout.count()):
                    item = layout.itemAt(i)
                    if item and item.widget() == self.items_table:
                        table_index = i
                        break
                
                # Remove original widgets
                if hasattr(self, 'items_table'):
                    self.items_table.setParent(None)
                if hasattr(self, 'add_item_button'):
                    self.add_item_button.setParent(None)
                
                # Insert new widget at the same position
                if table_index >= 0:
                    layout.insertWidget(table_index, self.layer_table)
                else:
                    layout.addWidget(self.layer_table)
            else:
                # Fallback: add to parent widget directly
                if hasattr(table_parent, 'layout') and not table_parent.layout():
                    from PyQt5.QtWidgets import QVBoxLayout
                    layout = QVBoxLayout(table_parent)
                    table_parent.setLayout(layout)
                    layout.addWidget(self.layer_table)
        
        # If no existing table found, try to add to main layout
        elif hasattr(self, 'layout') and self.layout():
            self.layout().addWidget(self.layer_table)