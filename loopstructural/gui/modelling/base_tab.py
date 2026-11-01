from qgis.gui import QgsCollapsibleGroupBox
from qgis.PyQt.QtWidgets import QVBoxLayout, QWidget


class BaseTab(QWidget):
    """A tab with a vertical layout. The page that holds the tab has the scroll area."""

    def __init__(self, parent=None, data_manager=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.container_layout = QVBoxLayout(self)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.container_layout)

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
