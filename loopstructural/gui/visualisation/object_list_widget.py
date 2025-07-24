import geoh5py
import pyvista as pv
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,  # Add missing import
    QLabel,
    QMenu,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


class ObjectListWidget(QWidget):
    def __init__(self, parent=None, *, viewer=None):
        super().__init__(parent)
        self.mainLayout = QVBoxLayout(self)
        self.treeWidget = QTreeWidget(self)
        self.treeWidget.setHeaderHidden(True)  # Hide the header
        self.treeWidget.setSelectionMode(QTreeWidget.MultiSelection)  # Enable multi-selection
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
        if not hasattr(self.viewer.actors[actor_name], 'visibility'):
            return
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

        item_widget = self.treeWidget.itemWidget(selected_items[0], 0)
        object_label = item_widget.findChild(QLabel).text()
        object = self.viewer.objects.get(object_label, None)
        if object is None:
            return

        # Determine available formats based on object type and dependencies
        formats = []
        try:
            has_geoh5py = True
        except ImportError:
            has_geoh5py = False

        if hasattr(object, "points"):  # Likely a point cloud
            formats = ["vtp"]
            if has_geoh5py:
                formats.append("geoh5")
        elif hasattr(object, "faces"):  # Likely a surface/mesh
            formats = ["obj", "vtk", "ply"]
            if has_geoh5py:
                formats.append("geoh5")
        else:
            formats = ["vtk"]  # Default

        # Build file filter string
        filter_map = {
            "obj": "OBJ (*.obj)",
            "vtk": "VTK (*.vtk)",
            "ply": "PLY (*.ply)",
            "vtp": "VTP (*.vtp)",
            "geoh5": "Geoh5 (*.geoh5)",
        }
        filters = ";;".join([filter_map[f] for f in formats])

        file_path, selected_filter = QFileDialog.getSaveFileName(
            self, "Export Object", object_label, filters
        )
        if not file_path:
            return

        selected_format = None
        for fmt, desc in filter_map.items():
            if desc in selected_filter:
                selected_format = fmt
                break

        try:
            if selected_format == "obj":
                (
                    object.save(file_path)
                    if hasattr(object, "save")
                    else pv.save_meshio(file_path, object)
                )
            elif selected_format == "vtk":
                pv.save_meshio(file_path, object)
            elif selected_format == "ply":
                pv.save_meshio(file_path, object)
            elif selected_format == "vtp":
                (
                    object.save(file_path)
                    if hasattr(object, "save")
                    else pv.save_meshio(file_path, object)
                )
            elif selected_format == "geoh5":
                with geoh5py.Geoh5(file_path, overwrite=True) as geoh5:
                    if hasattr(object, "faces"):
                        geoh5.add_surface(
                            name=object_label, vertices=object.points, faces=object.faces
                        )
                    else:
                        geoh5.add_points(name=object_label, vertices=object.points)
            print(f"Exported {object_label} to {file_path} as {selected_format}")
        except Exception as e:
            print(f"Failed to export object: {e}")
        # Logic for exporting the object

    def remove_selected_object(self):
        selected_items = self.treeWidget.selectedItems()
        if not selected_items:
            return
        for item in selected_items:

            item_widget = self.treeWidget.itemWidget(item, 0)
            object_label = item_widget.findChild(QLabel).text()
            # Logic for removing the object
            self.viewer.remove_object(object_label)
            self.treeWidget.takeTopLevelItem(self.treeWidget.indexOfTopLevelItem(item))
            print(f"Removing object: {object_label}")

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
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Mesh File", "", "Mesh Files (*.vtk *.vtp *.obj *.stl *.ply)"
        )
        file_name = file_path.split("/")[-1] if file_path else "Unnamed Mesh"
        if not file_path:
            return

        try:
            mesh = pv.read(file_path)
            if not isinstance(mesh, pv.PolyData):
                raise ValueError("The file does not contain a valid mesh.")

            # Add the mesh to the viewer
            self.viewer.add_mesh(mesh, name=file_name)
            print(f"Loaded mesh from file: {file_path}")
        except Exception as e:
            print(f"Failed to load mesh: {e}")
