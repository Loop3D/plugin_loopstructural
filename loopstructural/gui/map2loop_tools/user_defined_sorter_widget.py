"""Widget for user-defined stratigraphic column."""

import os

from PyQt5.QtWidgets import QWidget, QTableWidgetItem, QMessageBox
from qgis.PyQt import uic


class UserDefinedSorterWidget(QWidget):
    """Widget for creating a user-defined stratigraphic column.

    This widget allows users to manually define the stratigraphic order
    of units from youngest to oldest.
    """

    def __init__(self, parent=None, data_manager=None):
        """Initialize the user-defined sorter widget.

        Parameters
        ----------
        parent : QWidget, optional
            Parent widget.
        data_manager : object, optional
            Data manager for accessing shared data.
        """
        super().__init__(parent)
        self.data_manager = data_manager

        # Load the UI file
        ui_path = os.path.join(os.path.dirname(__file__), "user_defined_sorter_widget.ui")
        uic.loadUi(ui_path, self)

        # Connect signals
        self.addRowButton.clicked.connect(self._add_row)
        self.removeRowButton.clicked.connect(self._remove_row)
        self.moveUpButton.clicked.connect(self._move_up)
        self.moveDownButton.clicked.connect(self._move_down)
        self.runButton.clicked.connect(self._run_sorter)

        # Initialize with a few empty rows
        for _ in range(3):
            self._add_row()

    def _add_row(self):
        """Add a new row to the stratigraphic column table."""
        row_count = self.stratiColumnTable.rowCount()
        self.stratiColumnTable.insertRow(row_count)
        self.stratiColumnTable.setItem(row_count, 0, QTableWidgetItem(""))

    def _remove_row(self):
        """Remove the selected row from the stratigraphic column table."""
        current_row = self.stratiColumnTable.currentRow()
        if current_row >= 0:
            self.stratiColumnTable.removeRow(current_row)

    def _move_up(self):
        """Move the selected row up in the stratigraphic column table."""
        current_row = self.stratiColumnTable.currentRow()
        if current_row > 0:
            # Get current row data
            item = self.stratiColumnTable.takeItem(current_row, 0)

            # Remove current row
            self.stratiColumnTable.removeRow(current_row)

            # Insert row above
            self.stratiColumnTable.insertRow(current_row - 1)
            self.stratiColumnTable.setItem(current_row - 1, 0, item)

            # Select the moved row
            self.stratiColumnTable.setCurrentCell(current_row - 1, 0)

    def _move_down(self):
        """Move the selected row down in the stratigraphic column table."""
        current_row = self.stratiColumnTable.currentRow()
        if current_row >= 0 and current_row < self.stratiColumnTable.rowCount() - 1:
            # Get current row data
            item = self.stratiColumnTable.takeItem(current_row, 0)

            # Remove current row
            self.stratiColumnTable.removeRow(current_row)

            # Insert row below
            self.stratiColumnTable.insertRow(current_row + 1)
            self.stratiColumnTable.setItem(current_row + 1, 0, item)

            # Select the moved row
            self.stratiColumnTable.setCurrentCell(current_row + 1, 0)

    def _run_sorter(self):
        """Run the user-defined stratigraphic sorter algorithm."""
        from qgis.core import QgsProcessingFeedback
        from qgis import processing

        # Get stratigraphic column data
        strati_column = []
        for row in range(self.stratiColumnTable.rowCount()):
            item = self.stratiColumnTable.item(row, 0)
            if item and item.text().strip():
                strati_column.append(item.text().strip())

        if not strati_column:
            QMessageBox.warning(
                self, "Missing Input", "Please define at least one stratigraphic unit."
            )
            return

        # Prepare parameters
        params = {
            'INPUT_STRATI_COLUMN': strati_column,
            'OUTPUT': 'TEMPORARY_OUTPUT',
        }

        # Run the algorithm
        try:
            feedback = QgsProcessingFeedback()
            result = processing.run(
                "plugin_map2loop:loop_sorter_2", params, feedback=feedback
            )

            if result:
                QMessageBox.information(
                    self, "Success", "User-defined stratigraphic column created successfully!"
                )
            else:
                QMessageBox.warning(
                    self, "Error", "Failed to create user-defined stratigraphic column."
                )

        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred: {str(e)}")

    def get_stratigraphic_column(self):
        """Get the current stratigraphic column.

        Returns
        -------
        list
            List of unit names from youngest to oldest.
        """
        strati_column = []
        for row in range(self.stratiColumnTable.rowCount()):
            item = self.stratiColumnTable.item(row, 0)
            if item and item.text().strip():
                strati_column.append(item.text().strip())
        return strati_column

    def set_stratigraphic_column(self, units):
        """Set the stratigraphic column.

        Parameters
        ----------
        units : list
            List of unit names from youngest to oldest.
        """
        # Clear existing rows
        self.stratiColumnTable.setRowCount(0)

        # Add new rows
        for unit in units:
            row_count = self.stratiColumnTable.rowCount()
            self.stratiColumnTable.insertRow(row_count)
            self.stratiColumnTable.setItem(row_count, 0, QTableWidgetItem(unit))
