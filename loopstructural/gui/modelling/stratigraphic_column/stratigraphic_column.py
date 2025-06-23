from PyQt5.QtWidgets import (
    QAbstractItemView,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from loopstructural.gui.modelling.stratigraphic_column.unconformity import UnconformityWidget
from loopstructural.main.stratigraphic_column import StratigraphicColumnElementType

from .stratigraphic_unit import StratigraphicUnitWidget


class StratColumnWidget(QWidget):
    """In control of building the stratigraphic column

    :param QWidget: _description_
    :type QWidget: _type_
    """

    def __init__(self, parent=None, data_manager=None):
        super().__init__()
        layout = QVBoxLayout(self)
        if data_manager is None:
            raise ValueError("Data manager must be provided.")
        self.data_manager = data_manager
        # Main list widget
        self.unitList = QListWidget()
        self.unitList.setDragDropMode(QAbstractItemView.InternalMove)
        self.unitList.model().rowsMoved.connect(self.update_order)
        layout.addWidget(self.unitList)

        # Add unit button
        addUnitButton = QPushButton("Add Unit")
        addUnitButton.clicked.connect(self.add_unit)
        layout.addWidget(addUnitButton)

        # Add unconformity button
        addUnconformityButton = QPushButton("Add Unconformity")
        addUnconformityButton.clicked.connect(self.add_unconformity)
        layout.addWidget(addUnconformityButton)

        # add init from basal contacts button
        initFromBasalContactsButton = QPushButton("Initialise from map")
        initFromBasalContactsButton.clicked.connect(
            self.init_stratigraphic_column_from_basal_contacts
        )
        layout.addWidget(initFromBasalContactsButton)

        # Update display from data manager
        self.update_display()

    def update_display(self):
        """Update the widget display based on the data manager's stratigraphic column."""
        self.unitList.clear()
        if self.data_manager and self.data_manager._stratigraphic_column:
            for unit in self.data_manager._stratigraphic_column.order:
                if unit.element_type == StratigraphicColumnElementType.UNIT:
                    self.add_unit(unit_data=unit.to_dict(), create_new=False)
                elif unit.element_type == StratigraphicColumnElementType.UNCONFORMITY:
                    self.add_unconformity(unconformity_data=unit.to_dict(),create_new=False)

    def init_stratigraphic_column_from_basal_contacts(self):
        if self.data_manager:
            self.data_manager.init_stratigraphic_column_from_basal_contacts()
            self.update_display()
        else:
            print("Error: Data manager is not initialized.")

    def add_unit(self, *, unit_data=None, create_new=True):
        if unit_data is None:
            unit_data = {'type': 'unit', 'name': ''}
        if create_new:
            unit = self.data_manager.add_to_stratigraphic_column(unit_data)
        else:
            if unit_data['name'] is not None or unit_data['name'] != '':

                unit = self.data_manager._stratigraphic_column.get_unit_by_name(
                    unit_data['name']
                )

        unit_widget = StratigraphicUnitWidget(uuid=unit.uuid)
        unit_widget.deleteRequested.connect(self.delete_unit)  # Connect delete signal
        item = QListWidgetItem()
        item.setSizeHint(unit_widget.sizeHint())
        self.unitList.addItem(item)
        self.unitList.setItemWidget(item, unit_widget)
        unit_widget.setData(unit_data)  # Set data for the unit widget
        # Update data manager

    def add_unconformity(self, *, unconformity_data=None, create_new=True):
        if unconformity_data is None:
            unconformity_data = {'type': 'unconformity', 'unconformity_type': 'erode'}
        if create_new:
            unconformity = self.data_manager.add_to_stratigraphic_column(unconformity_data)
        else:
            unconformity = self.data_manager._stratigraphic_column.get_unconformity_by_type(
                unconformity_data['unconformity_type']
            )
        unconformity_widget = UnconformityWidget(uuid=unconformity.uuid)
        unconformity_widget.deleteRequested.connect(self.delete_unit)
        item = QListWidgetItem()
        item.setSizeHint(unconformity_widget.sizeHint())
        self.unitList.addItem(item)
        self.unitList.setItemWidget(item, unconformity_widget)

        # Update data manager

    def delete_unit(self, unit_widget):
        for i in range(self.unitList.count()):
            item = self.unitList.item(i)
            if self.unitList.itemWidget(item) == unit_widget:
                self.unitList.takeItem(i)
                break

        # Update data manager
        if self.data_manager:
            self.data_manager.remove_from_stratigraphic_column(unit_widget.uuid)

    def update_order(self, parent, start, end, destination, row):
        """Update the data manager when the order of items changes."""
        if self.data_manager:
            ordered_uuids = []
            for i in range(self.unitList.count()):
                item = self.unitList.item(i)
                widget = self.unitList.itemWidget(item)
                if widget:
                    ordered_uuids.append(widget.uuid)
            self.data_manager.update_stratigraphic_column_order(ordered_uuids)
