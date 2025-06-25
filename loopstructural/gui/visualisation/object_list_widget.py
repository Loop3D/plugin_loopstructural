from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox,
    QVBoxLayout,
    QLabel,
    QMenu,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
    QPushButton,
    QFileDialog,
    QHBoxLayout,  # Add missing import
)
import pyvista as pv


class ObjectListWidget(QWidget):
    def __init__(self, parent=None, *, viewer=None):
        super().__init__(parent)
        self.mainLayout = QVBoxLayout(self)
        self.treeWidget = QTreeWidget(self)
        self.treeWidget.setHeaderHidden(True)  # Hide the header
        self.mainLayout.addWidget(self.treeWidget)
        addButton = QPushButton("Add Object", self)
        addButton.setContextMenuPolicy(Qt.CustomContextMenu)
        addButton.clicked.connect(self.show_add_object_menu)
        self.mainLayout.addWidget(addButton)

        self.setLayout(self.mainLayout)
        self.viewer = viewer
        self.viewer.objectAdded.connect(self.update_object_list)

    def update_object_list(self, new_object):

        for object_name in self.viewer.actors:
            # Check if object already exists in tree
            exists = False
            for i in range(self.treeWidget.topLevelItemCount()):
                item = self.treeWidget.topLevelItem(i)
                widget = self.treeWidget.itemWidget(item, 0)
                if widget and widget.findChild(QLabel).text() == object_name:
                    exists = True
                    break
            if not exists:
                self.add_actor(object_name)

    def add_actor(self, actor_name):
        # Create a tree item for the object
        objectItem = QTreeWidgetItem(self.treeWidget)

        # Add a checkbox for visibility toggle in front of the name
        visibilityCheckbox = QCheckBox()
        visibilityCheckbox.setChecked(self.viewer.actors[actor_name].visibility)
        visibilityCheckbox.stateChanged.connect(
            lambda state, name=self.viewer.actors[actor_name].name: self.set_object_visibility(
                name, state == Qt.Checked
            )
        )

        # Create a widget to hold the checkbox and name on a single line
        itemWidget = QWidget()
        itemLayout = QHBoxLayout(itemWidget)  # Use horizontal layout for single line
        itemLayout.setContentsMargins(0, 0, 0, 0)
        itemLayout.addWidget(visibilityCheckbox)
        itemLayout.addWidget(QLabel(self.viewer.actors[actor_name].name))
        itemWidget.setLayout(itemLayout)

        self.treeWidget.setItemWidget(objectItem, 0, itemWidget)
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
        selected_items = self.treeWidget.selectedItems()
        if not selected_items:
            return

        object_name = selected_items[0].text(0)
        # Logic for exporting the object
        print(f"Exporting object: {object_name}")

    def remove_selected_object(self):
        selected_items = self.treeWidget.selectedItems()
        if not selected_items:
            return

        object_name = selected_items[0].text(0)
        # Logic for removing the object
        self.viewer.remove_object(object_name)
        self.treeWidget.takeTopLevelItem(self.treeWidget.indexOfTopLevelItem(selected_items[0]))
        print(f"Removing object: {object_name}")

    def show_add_object_menu(self):
        menu = QMenu(self)

        addFeatureAction = menu.addAction("Surface from model")
        loadFeatureAction = menu.addAction("Load from file")

        buttonPosition = self.sender().mapToGlobal(self.sender().rect().bottomLeft())
        action = menu.exec_(buttonPosition)

        if action == addFeatureAction:
            self.add_feature_from_geological_model()
        elif action == loadFeatureAction:
            self.load_feature_from_file()

    def add_feature_from_geological_model(self):
        # Logic to add a feature from the geological model
        print("Adding feature from geological model")

    def load_feature_from_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Mesh File", "", "Mesh Files (*.vtk *.vtp *.obj *.stl *.ply)")
        file_name = file_path.split("/")[-1] if file_path else "Unnamed Mesh"
        if not file_path:
            return

        try:
            mesh = pv.read(file_path)
            if not isinstance(mesh, pv.PolyData):
                raise ValueError("The file does not contain a valid mesh.")

            # Add the mesh to the viewer
            self.viewer.add_mesh(mesh,name=file_name)
            print(f"Loaded mesh from file: {file_path}")
        except Exception as e:
            print(f"Failed to load mesh: {e}")
