from PyQt5.QtWidgets import QTabWidget, QVBoxLayout, QWidget, QLabel, QTableWidget, QTableWidgetItem, QPushButton, QGroupBox
from PyQt5.QtCore import Qt
# from qgis.PyQt.QtWidgets import QgsCollapsibleGroupBox

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
        self.stratigraphic_table_group = QGroupBox("Stratigraphic Units Table", self)
        fault_table_layout = QVBoxLayout(self.fault_table_group)
        # Create the fault adjacency table
        self.create_fault_adjacency_table()
        fault_table_layout.addWidget(self.table)
        self.layout().addWidget(self.fault_table_group)

        # Create the stratigraphic units table
        self.create_stratigraphic_units_table()
        stratigraphic_table_layout = QVBoxLayout(self.stratigraphic_table_group)
        stratigraphic_table_layout.addWidget(self.stratigraphic_table)
        self.layout().addWidget(self.stratigraphic_table_group)

    def create_fault_adjacency_table(self):
        """Create a table with QPushButtons for fault adjacency."""
        faults = ['Fault A', 'Fault B', 'Fault C']  # Example fault names, replace with actual data

        self.table = QTableWidget(len(faults), len(faults), self)
        self.table.setHorizontalHeaderLabels(faults)
        self.table.setVerticalHeaderLabels(faults)

        for row in range(len(faults)):
            for col in range(len(faults)):
                button = QPushButton()
                button.setStyleSheet("background-color: white;")
                button.clicked.connect(lambda _, b=button: self.change_button_color(b))
                self.table.setCellWidget(row, col, button)

    def create_stratigraphic_units_table(self):
        """Create a table with QPushButtons for stratigraphic units."""
        units = ['unit1', 'unit2', 'unit3']
        faults = ['Fault A', 'Fault B', 'Fault C']  # Example fault names, replace with actual data

        self.stratigraphic_table = QTableWidget(len(units), len(faults), self)
        self.stratigraphic_table.setHorizontalHeaderLabels(units)
        self.stratigraphic_table.setVerticalHeaderLabels(faults)

        for row in range(len(units)):
            for col in range(len(faults)):
                button = QPushButton()
                button.setStyleSheet("background-color: white;")
                button.clicked.connect(lambda _, b=button: self.change_button_colour_binary(b))
                self.stratigraphic_table.setCellWidget(row, col, button)
    def change_button_colour_binary(self, button):
        """Cycle the button color between red, green, and black."""
        current_color = button.styleSheet()
        if "red" in current_color:
            button.setStyleSheet("background-color: white;")
        else:
            button.setStyleSheet("background-color: red;")
    def change_button_color(self, button):
        """Cycle the button color between red, green, and black."""
        current_color = button.styleSheet()
        if "red" in current_color:
            button.setStyleSheet("background-color: green;")
        elif "green" in current_color:
            button.setStyleSheet("background-color: white;")
        else:
            button.setStyleSheet("background-color: red;")