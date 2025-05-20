from PyQt5 import uic
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .stratigraphic_unit import StratigraphicUnitWidget


class StratColumnWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__()
        layout = QVBoxLayout(self)

        # Main list widget
        self.unitList = QListWidget()
        self.unitList.setDragDropMode(QAbstractItemView.InternalMove)
        layout.addWidget(self.unitList)

        # Add unit button
        addButton = QPushButton("Add Unit")
        addButton.clicked.connect(self.add_unit)
        layout.addWidget(addButton)

    def add_unit(self):
        unit_widget = StratigraphicUnitWidget()
        item = QListWidgetItem()
        item.setSizeHint(unit_widget.sizeHint())
        self.unitList.addItem(item)
        self.unitList.setItemWidget(item, unit_widget)
