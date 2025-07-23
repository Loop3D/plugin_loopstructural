from ast import arg
from PyQt5.QtWidgets import QTabWidget, QVBoxLayout, QWidget, QLabel, QTableWidget, QTableWidgetItem, QPushButton, QGroupBox
from PyQt5.QtCore import Qt
from enum import Enum

class FaultRelationshipType(Enum):
    NO_EDGE = "no_edge"
    ABUTTING = "abutting"
    FAULTED = "faulted"

class FaultAdjacencyTab(QWidget):
    def __init__(self, parent=None, data_manager=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.setLayout(QVBoxLayout())

        # Initialize the UI components for fault adjacency
        self.init_ui()
        # self.data_manager.set
    def init_ui(self):
        """Initialize the user interface components for fault adjacency."""
       

        # Create collapsible group boxes for the tables
        self.fault_table_group = QGroupBox("Fault Adjacency Table", self)
        self.fault_table_layout = QVBoxLayout(self.fault_table_group)
        self.stratigraphic_table_group = QGroupBox("Stratigraphic Units Table", self)
        self.stratigraphic_table_layout = QVBoxLayout(self.stratigraphic_table_group)
        # Create the fault adjacency table
        self.fault_fault_instructions = (
            "Rows: faults being affected\n"
            "Columns: affecting faults\n"
            "Toggle cell colour to indicate fault interaction:\n"
            "Green: row fault is cut by column fault\n"
            "Red: row fault stops at column fault\n"
            "White: no interaction"
        )
        self.fault_fault_instructions_label = QLabel(self.fault_fault_instructions)
        self.fault_fault_instructions_label.setWordWrap(True)
        self.update_fault_adjacency_table()
        self.layout().addWidget(self.fault_table_group)

        # Create the stratigraphic units table
        self.strat_fault_instructions = (
            "Rows: stratigraphic units\n"
            "Columns: faults\n"
            "Toggle cell colour to indicate interaction:\n"
            "Red: unit is faulted by fault\n" 
            "White: no interaction"
        )
        self.strat_fault_instructions_label = QLabel(self.strat_fault_instructions)
        self.strat_fault_instructions_label.setWordWrap(True)
        self.update_stratigraphic_units_table()

        self.layout().addWidget(self.stratigraphic_table_group)
        self.update = self._update
        self.data_manager._stratigraphic_column.attach(self.update)
        self.data_manager._fault_topology.attach(self.update)

    def _update(self, event,*args,**kwargs):
        if args[0] == "fault_relationship_updated" or args[0] == "stratigraphy_fault_relationship_updated":
            return
    
        self.update_fault_adjacency_table()
        self.update_stratigraphic_units_table()

    def change_button_color(self, button, row, col):
        """Cycle the button color and update the fault relationship."""
        current_color = button.styleSheet()
        if "red" in current_color:
            new_color = "green"
            relationship = FaultRelationshipType.FAULTED
        elif "green" in current_color:
            new_color = "white"
            relationship = FaultRelationshipType.NO_EDGE
        else:
            new_color = "red"
            relationship = FaultRelationshipType.ABUTTING

        button.setStyleSheet(f"background-color: {new_color};")
        f1 = self.data_manager._fault_topology.faults[row]
        f2 = self.data_manager._fault_topology.faults[col]
        self.data_manager._fault_topology.update_fault_relationship(f1, f2, relationship)

    def update_fault_adjacency_table(self):
        """Update the fault adjacency table with QPushButtons."""
        faults = self.data_manager._fault_topology.faults  # Assuming faults is a list of fault names
        if not faults:
            self.fault_table_group.hide()
            return

        self.fault_table_group.show()
        self.fault_fault_instructions_label.setText(self.fault_fault_instructions)

        if not hasattr(self, 'table'):
            self.table = QTableWidget(self)
            self.fault_table_layout.addWidget(self.table)

        self.table.setRowCount(len(faults))
        self.table.setColumnCount(len(faults))
        self.table.setHorizontalHeaderLabels(faults)
        self.table.setVerticalHeaderLabels(faults)

        for row in range(len(faults)):
            for col in range(len(faults)):
                if row == col:
                    # If it's the same fault, set a label instead of a button
                    item = QTableWidgetItem(faults[row])
                    item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    self.table.setItem(row, col, item)
                else:
                    button = QPushButton()
                    if self.data_manager._fault_topology.get_fault_relationship(faults[row], faults[col]) == FaultRelationshipType.FAULTED:
                        button.setStyleSheet("background-color: green;")
                    elif self.data_manager._fault_topology.get_fault_relationship(faults[row], faults[col]) == FaultRelationshipType.ABUTTING:
                        button.setStyleSheet("background-color: red;")
                    else:
                        button.setStyleSheet("background-color: white;")
                    button.clicked.connect(lambda _, b=button, r=row, c=col: self.change_button_color(b, r, c))
                    self.table.setCellWidget(row, col, button)

    def update_stratigraphic_units_table(self):
        """Update the stratigraphic units table with QPushButtons."""
        faults = self.data_manager._fault_topology.faults  # Assuming faults is a list of fault names
        group_units_pairs = self.data_manager._stratigraphic_column.get_group_unit_pairs()

        if not faults or not group_units_pairs:
            self.stratigraphic_table_group.hide()
            return

        self.stratigraphic_table_group.show()
        self.strat_fault_instructions_label.setText(self.strat_fault_instructions)

        units = [u[1] for u in group_units_pairs]  # Extracting unit names

        if not hasattr(self, 'stratigraphic_table'):
            self.stratigraphic_table = QTableWidget(self)
            self.stratigraphic_table_layout.addWidget(self.stratigraphic_table)

        self.stratigraphic_table.setRowCount(len(units))
        self.stratigraphic_table.setColumnCount(len(faults))
        self.stratigraphic_table.setHorizontalHeaderLabels(faults)
        self.stratigraphic_table.setVerticalHeaderLabels(units)

        for row in range(len(units)):
            for col in range(len(faults)):
                button = QPushButton()
                if self.data_manager._fault_topology.get_fault_stratigraphic_relationship(units[row], faults[col]):
                    button.setStyleSheet("background-color: red;")
                else:
                    # Default to white if no relationship or not faulted
                    button.setStyleSheet("background-color: white;")
                button.clicked.connect(lambda _, b=button, r=row, c=col: self.change_button_colour_binary(b, r, c))
                self.stratigraphic_table.setCellWidget(row, col, button)
    def change_button_colour_binary(self, button, row, col):
        """Cycle the button color between red, green, and black."""

        current_color = button.styleSheet()
        if "red" in current_color:
            button.setStyleSheet("background-color: white;")
            flag = False
        else:
            button.setStyleSheet("background-color: red;")
            flag = True
        fault = self.data_manager._fault_topology.faults[col]  
        unit = self.data_manager._stratigraphic_column.get_group_unit_pairs()[row]
        self.data_manager._fault_topology.update_fault_stratigraphy_relationship(unit[1], fault, flag)
