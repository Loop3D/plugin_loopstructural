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
    def __init__(self, parent=None, *, viewer=None, properties_widget=None):
        super().__init__(parent)
        self.mainLayout = QVBoxLayout(self)
        self.treeWidget = QTreeWidget(self)
        self.treeWidget.setHeaderHidden(True)  # Hide the header
        self.mainLayout.addWidget(self.treeWidget)
        addButton = QPushButton("Add Object", self)
        addButton.setContextMenuPolicy(Qt.CustomContextMenu)
        addButton.clicked.connect(self.show_add_object_menu)
        self.mainLayout.addWidget(addButton)
        self.properties_widget = properties_widget
        self.setLayout(self.mainLayout)
        self.viewer = viewer
        self.viewer.objectAdded.connect(self.update_object_list)
        self.treeWidget.installEventFilter(self)
        self.treeWidget.itemSelectionChanged.connect(self.on_object_selected)
        self.treeWidget.itemDoubleClicked.connect(self.onDoubleClick)
    def onDoubleClick(self, item, column):
        self.viewer.reset_camera()
    def on_object_selected(self):
        selected_items = self.treeWidget.selectedItems()
        if not selected_items:
            # if nothing selected keep the previous selection.
            # Need to select a new object to change its properties
            return 

        # For simplicity, just handle the first selected item
        item = selected_items[0]
        item_widget = self.treeWidget.itemWidget(item, 0)
        object_label = item_widget.findChild(QLabel).text()

        if hasattr(self, 'properties_widget') and self.properties_widget:

            self.properties_widget.setCurrentObject(object_label)
    def update_object_list(self, new_object):
        """Rebuild the tree so top-level items are the entries in
        `viewer.meshes`. Each mesh gets a visibility checkbox and child
        items listing its point and cell data arrays.
        """
        if not self.viewer:
            return

        # Clear and rebuild the tree to reflect current meshes
        self.treeWidget.clear()

        meshes = getattr(self.viewer, 'meshes', {}) or {}
        for mesh_name in sorted(meshes.keys()):
            mesh = meshes[mesh_name]
            self.add_mesh_item(mesh_name, mesh)

    def add_mesh_item(self, mesh_name, mesh):
        """Add a top-level tree item for a mesh and populate children for
        point/cell data arrays.
        """
        top = QTreeWidgetItem(self.treeWidget)

        # Determine initial visibility. Prefer viewer.actors entry if available.
        initial_visibility = True
        try:
            if hasattr(self.viewer, 'actors') and mesh_name in getattr(self.viewer, 'actors', {}):
                initial_visibility = bool(self.viewer.actors[mesh_name].visibility)
            elif hasattr(mesh, 'visibility'):
                initial_visibility = bool(getattr(mesh, 'visibility'))
        except Exception:
            initial_visibility = True

        visibilityCheckbox = QCheckBox()
        visibilityCheckbox.setChecked(initial_visibility)

        # Connect checkbox: prefer viewer APIs, fallback to mesh attribute
        def _on_vis(state, name=mesh_name, m=mesh):
            checked = state == Qt.Checked
            if hasattr(self.viewer, 'actors') and name in getattr(self.viewer, 'actors', {}):
                self.set_object_visibility(name, checked)
                return
            if hasattr(self.viewer, 'set_object_visibility'):
                try:
                    self.viewer.set_object_visibility(name, checked)
                    return
                except Exception:
                    pass
            # Fallback: set on mesh if possible
            if hasattr(m, 'visibility'):
                try:
                    m.visibility = checked
                except Exception:
                    pass

        visibilityCheckbox.stateChanged.connect(_on_vis)

        # Compose widget (checkbox + label)
        itemWidget = QWidget()
        itemLayout = QHBoxLayout(itemWidget)
        itemLayout.setContentsMargins(0, 0, 0, 0)
        itemLayout.addWidget(visibilityCheckbox)
        itemLayout.addWidget(QLabel(mesh_name))
        itemWidget.setLayout(itemLayout)

        self.treeWidget.setItemWidget(top, 0, itemWidget)
        top.setExpanded(False)

        # Add children: Point Data and Cell Data groups
        try:
            point_data = getattr(mesh, 'point_data', None)
            cell_data = getattr(mesh, 'cell_data', None)

            if point_data is not None and len(point_data.keys()) > 0:
                pd_group = QTreeWidgetItem(top)
                pd_group.setText(0, 'Point Data')
                for array_name in sorted(point_data.keys()):
                    arr_item = QTreeWidgetItem(pd_group)
                    # show name and length/type if available
                    try:
                        vals = point_data[array_name]
                        meta = f" ({len(vals)})" if hasattr(vals, '__len__') else ''
                    except Exception:
                        meta = ''
                    arr_item.setText(0, f"{array_name}{meta}")

            if cell_data is not None and len(cell_data.keys()) > 0:
                cd_group = QTreeWidgetItem(top)
                cd_group.setText(0, 'Cell Data')
                for array_name in sorted(cell_data.keys()):
                    arr_item = QTreeWidgetItem(cd_group)
                    try:
                        vals = cell_data[array_name]
                        meta = f" ({len(vals)})" if hasattr(vals, '__len__') else ''
                    except Exception:
                        meta = ''
                    arr_item.setText(0, f"{array_name}{meta}")
        except Exception:
            # If mesh lacks expected attributes, silently continue
            pass

    def add_object_item(self, object_name, instance=None):
        """Add a generic object entry to the tree. This mirrors add_actor but works
        for objects/meshes that are not present in viewer.actors."""
        objectItem = QTreeWidgetItem(self.treeWidget)

        # Determine initial visibility
        visibility = False
        if instance is not None and hasattr(instance, 'visibility'):
            visibility = bool(getattr(instance, 'visibility'))

        visibilityCheckbox = QCheckBox()
        visibilityCheckbox.setChecked(visibility)

        # Connect checkbox to toggle visibility. Prefer using viewer APIs if available.
        def _on_visibility_change(state, name=object_name, inst=instance):
            checked = state == Qt.Checked
            # If there's an actor for this name, delegate to set_object_visibility
            if hasattr(self.viewer, 'actors') and name in getattr(self.viewer, 'actors', {}):
                self.set_object_visibility(name, checked)
                return
            # If viewer exposes a generic setter use it
            if hasattr(self.viewer, 'set_object_visibility'):
                try:
                    self.viewer.set_object_visibility(name, checked)
                    return
                except Exception:
                    pass
            # Fallback: set attribute on the instance if possible
            if inst is not None and hasattr(inst, 'visibility'):
                try:
                    inst.visibility = checked
                except Exception:
                    pass

        visibilityCheckbox.stateChanged.connect(_on_visibility_change)

        # Create a widget to hold the checkbox and name on a single line
        itemWidget = QWidget()
        itemLayout = QHBoxLayout(itemWidget)
        itemLayout.setContentsMargins(0, 0, 0, 0)
        itemLayout.addWidget(visibilityCheckbox)
        itemLayout.addWidget(QLabel(object_name))
        itemWidget.setLayout(itemLayout)

        self.treeWidget.setItemWidget(objectItem, 0, itemWidget)
        objectItem.setExpanded(False)  # Initially collapsed

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
        mesh_dict = self.viewer.meshes.get(object_label, None)
        if mesh_dict is None:
            return
        mesh = mesh_dict.get('mesh', None)
        if mesh is None:
            return
        # Determine available formats based on object type and dependencies
        formats = []
        try:
            import geoh5py  
            has_geoh5py = True
        except ImportError:
            has_geoh5py = False

        if hasattr(object, "faces"):  # Likely a surface/mesh
            formats = ["obj", "vtk", "ply"]
            if has_geoh5py:
                formats.append("geoh5")
        elif hasattr(object, "points"):  # Likely a point cloud
            formats = ["vtp"]
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
                    mesh.save(file_path)
                    if hasattr(mesh, "save")
                    else pv.save_meshio(file_path, mesh)
                )
            elif selected_format == "vtk":
                mesh.save(file_path) if hasattr(mesh, "save") else pv.save_meshio(file_path, mesh)
            elif selected_format == "ply":
                pv.save_meshio(file_path, mesh)
            elif selected_format == "vtp":
                (
                    mesh.save(file_path)
                    if hasattr(mesh, "save")
                    else pv.save_meshio(file_path, mesh)
                )
            elif selected_format == "geoh5":
                with geoh5py.Geoh5(file_path, overwrite=True) as geoh5:
                    if hasattr(mesh, "faces"):
                        geoh5.add_surface(
                            name=object_label, vertices=mesh.points, faces=mesh.faces
                        )
                    else:
                        geoh5.add_points(name=object_label, vertices=mesh.points)
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
            if self.viewer and hasattr(self.viewer, 'remove_object'):
                self.viewer.remove_object(object_label)
            else:
                print("Error: Viewer is not initialized or does not support object removal.")
            self.treeWidget.takeTopLevelItem(self.treeWidget.indexOfTopLevelItem(item))

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
            # Add the mesh to the viewer
            if self.viewer and hasattr(self.viewer, 'add_mesh'):
                self.viewer.add_mesh_object(mesh, name=file_name)
            else:
                print("Error: Viewer is not initialized or does not support adding meshes.")

            print(f"Loaded mesh from file: {file_path}")
        except Exception as e:
            print(f"Failed to load mesh: {e}")

    def eventFilter(self, source, event):
        if source == self.treeWidget and event.type() == event.KeyPress:
            if event.key() == Qt.Key_Space:
                selected_items = self.treeWidget.selectedItems()
                for item in selected_items:
                    item_widget = self.treeWidget.itemWidget(item, 0)
                    if item_widget:
                        checkbox = item_widget.findChild(QCheckBox)
                        if checkbox:
                            checkbox.setChecked(not checkbox.isChecked())
                return True
        return super().eventFilter(source, event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Space:
            selected_items = self.treeWidget.selectedItems()
            for item in selected_items:
                item_widget = self.treeWidget.itemWidget(item, 0)
                if item_widget:
                    checkbox = item_widget.findChild(QCheckBox)
                    if checkbox:
                        checkbox.setChecked(not checkbox.isChecked())
        elif event.key() == Qt.Key_Delete:
            selected_items = self.treeWidget.selectedItems()
            for item in selected_items:
                item_widget = self.treeWidget.itemWidget(item, 0)
                if item_widget:
                    object_label = item_widget.findChild(QLabel).text()
                    if self.viewer and hasattr(self.viewer, 'remove_object'):
                        self.viewer.remove_object(object_label)
                    self.treeWidget.takeTopLevelItem(self.treeWidget.indexOfTopLevelItem(item))
        else:
            super().keyPressEvent(event)
