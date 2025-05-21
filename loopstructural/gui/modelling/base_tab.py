from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QScrollArea, QSizePolicy, QVBoxLayout, QWidget
from qgis.gui import QgsCollapsibleGroupBox


class BaseTab(QWidget):
    def __init__(self, parent=None, scrollable=False):
        super().__init__(parent)
        self.data_manager = None
        # Initialize a default layout for all tabs
        if scrollable:
            self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            self.scroll_area = QScrollArea(self)
            self.scroll_area.setWidgetResizable(True)
            self.scroll_area.setAttribute(Qt.WA_TransparentForMouseEvents, False)
            # Create a container widget for the scroll area
            self.container_widget = QWidget()
            self.scroll_area.setWidget(self.container_widget)
            # Ensure the scroll area and its container widget can handle focus and mouse events
            self.scroll_area.setFocusPolicy(Qt.NoFocus)
            self.scroll_area.setFrameShape(QScrollArea.NoFrame)  # Remove any unnecessary frame

            # Explicitly set size policies to ensure proper interaction
            self.scroll_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            # Set up a layout for the container widget
            self.container_layout = QVBoxLayout(self.container_widget)
            # Set the main layout for the BaseTab
            self.main_layout = QVBoxLayout(self)
            self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
            self.main_layout.addWidget(self.scroll_area)

            self.container_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

            # Ensure the container widget propagates mouse events properly
            self.container_widget.setAttribute(Qt.WA_TransparentForMouseEvents, False)

            self.setLayout(self.main_layout)
        else:
            # If not scrollable, use a simple layout
            self.container_layout = QVBoxLayout(self)
            self.setLayout(self.container_layout)

        # Set the layout for the tab

    def add_widget(self, widget, name=None, group_box=True):
        """Add a widget to the tab."""
        if group_box:
            group_box = QgsCollapsibleGroupBox()
            group_box.setTitle(name)
            group_box_layout = QVBoxLayout()
            group_box.setLayout(group_box_layout)
            group_box_layout.addWidget(widget)
            widget = group_box
        self.container_layout.addWidget(widget)

    def set_data_manager(self, data_manager):
        """Set the shared data manager for the tab."""
        self.data_manager = data_manager

    def get_data_manager(self):
        """Get the shared data manager."""
        return self.data_manager
