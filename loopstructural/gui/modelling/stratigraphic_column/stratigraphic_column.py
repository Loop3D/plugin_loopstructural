from PyQt5.QtWidgets import (
    QAbstractItemView,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from loopstructural.gui.modelling.stratigraphic_column.unconformity import UnconformityWidget

from .stratigraphic_unit import StratigraphicUnitWidget


class StratColumnWidget(QWidget):
    def __init__(self, parent=None, data_manager=None):
        super().__init__()
        layout = QVBoxLayout(self)
        self.data_manager = data_manager
        # Main list widget
        self.unitList = QListWidget()
        self.unitList.setDragDropMode(QAbstractItemView.InternalMove)
        layout.addWidget(self.unitList)

        # Add unit button
        addUnitButton = QPushButton("Add Unit")
        addUnitButton.clicked.connect(self.add_unit)
        layout.addWidget(addUnitButton)

        # Add unconformity button
        addUnconformityButton = QPushButton("Add Unconformity")
        addUnconformityButton.clicked.connect(self.add_unconformity)
        layout.addWidget(addUnconformityButton)

    def add_unit(self):
        unit_widget = StratigraphicUnitWidget()
        unit_widget.deleteRequested.connect(self.delete_unit)  # Connect delete signal
        item = QListWidgetItem()
        item.setSizeHint(unit_widget.sizeHint())
        self.unitList.addItem(item)
        self.unitList.setItemWidget(item, unit_widget)

    def add_unconformity(self):
        unconformity_widget = UnconformityWidget()
        unconformity_widget.deleteRequested.connect(self.delete_unit)
        item = QListWidgetItem()
        item.setSizeHint(unconformity_widget.sizeHint())
        self.unitList.addItem(item)
        self.unitList.setItemWidget(item, unconformity_widget)

    def delete_unit(self, unit_widget):

        for i in range(self.unitList.count()):
            item = self.unitList.item(i)
            if self.unitList.itemWidget(item) == unit_widget:
                self.unitList.takeItem(i)
                break
