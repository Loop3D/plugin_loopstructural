from PyQt5.QtWidgets import QScrollArea, QVBoxLayout, QWidget


class BaseTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.data_manager = None
        # Initialize a default layout for all tabs
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)

        # Create a container widget for the scroll area
        self.container_widget = QWidget()
        self.scroll_area.setWidget(self.container_widget)

        # Set up a layout for the container widget
        self.container_layout = QVBoxLayout(self.container_widget)

        # Set the main layout for the BaseTab
        self.main_layout = QVBoxLayout(self)
        self.main_layout.addWidget(self.scroll_area)

        # self.layout = QVBoxLayout(self)
        # self.setLayout(self.layout)  # Set the layout for the tab

    def set_data_manager(self, data_manager):
        """Set the shared data manager for the tab."""
        self.data_manager = data_manager

    def get_data_manager(self):
        """Get the shared data manager."""
        return self.data_manager
