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
        unit_widget.deleteRequested.connect(self.delete_unit)  # Connect delete signal
        print("Unit added and delete signal connected")  # Debug print
        item = QListWidgetItem()
        item.setSizeHint(unit_widget.sizeHint())
        self.unitList.addItem(item)
        self.unitList.setItemWidget(item, unit_widget)

    def delete_unit(self, unit_widget):
        print("delete_unit method triggered")  # Debug print
        print("Delete unit requested")  # Debug print
        for i in range(self.unitList.count()):
            item = self.unitList.item(i)
            if self.unitList.itemWidget(item) == unit_widget:
                print(f"Deleting unit at index {i}")  # Debug print
                self.unitList.takeItem(i)
                break
