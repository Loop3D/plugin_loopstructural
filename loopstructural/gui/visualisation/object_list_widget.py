from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QMenu,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
)


class ObjectListWidget(QTreeWidget):
    def __init__(self, parent=None, *, viewer=None):
        super().__init__(parent)
        self.viewer = viewer
        self.viewer.objectAdded.connect(self.update_object_list)

        # Set header labels for the tree widget
        self.setHeaderLabels(["Object Name", "Visibility"])

    def update_object_list(self, new_object):
        for object_name in self.viewer.actors:
            print(f"Adding object: {object_name}")

            self.add_actor(object_name)

    def add_actor(self, actor_name):
        # Create a tree item for the object
        objectItem = QTreeWidgetItem(self)
        objectItem.setText(0, self.viewer.actors[actor_name].name)

        # Add a checkbox for visibility toggle
        visibilityCheckbox = QCheckBox()
        visibilityCheckbox.setChecked(self.viewer.actors[actor_name].visibility)
        visibilityCheckbox.stateChanged.connect(
            lambda state, name=self.viewer.actors[actor_name].name: self.set_object_visibility(
                name, state == Qt.Checked
            )
        )
        self.setItemWidget(objectItem, 1, visibilityCheckbox)

        # # Add child items for properties
        # properties = self.viewer.actors[
        #     actor_name
        # ].properties  # Assuming `properties` is a dictionary
        # for prop_name, prop_value in properties.items():
        #     propertyItem = QTreeWidgetItem(objectItem)
        #     propertyItem.setText(0, f"{prop_name}: {prop_value}")

        objectItem.setExpanded(False)  # Initially collapsed

    def set_object_visibility(self, object_name, visibility):
        self.viewer.actors[object_name].visibility = visibility

        # self.object_manager.set_object_visibility(object_name, visibility)
        # Logic to update visibility in the list widget

    def contextMenuEvent(self, event):
        menu = QMenu(self)

        export_action = menu.addAction("Export Object")
        remove_action = menu.addAction("Remove Object")

        action = menu.exec_(self.mapToGlobal(event.pos()))

        if action == export_action:
            self.export_selected_object()
        elif action == remove_action:
            self.remove_selected_object()

    def export_selected_object(self):
        selected_items = self.selectedItems()
        if not selected_items:
            return

        object_name = selected_items[0].text(0)
        # Logic for exporting the object
        print(f"Exporting object: {object_name}")

    def remove_selected_object(self):
        selected_items = self.selectedItems()
        if not selected_items:
            return

        object_name = selected_items[0].text(0)
        # Logic for removing the object
        self.viewer.remove_object(object_name)
        self.takeTopLevelItem(self.indexOfTopLevelItem(selected_items[0]))
        print(f"Removing object: {object_name}")
