import logging

import pyvista as pv
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

# Text for the type of an object in the list, by source type
SOURCE_TYPE_LABELS = {
    'feature_scalar': 'scalar field',
    'feature_surface': 'surface',
    'feature_isosurface': 'isosurface',
    'feature_vector': 'vector field',
    'feature_vectors': 'vector field',
    'feature_points': 'data',
    'feature_data': 'data',
    'bounding_box': 'bounding box',
    'fault_surface': 'fault surface',
    'stratigraphic_surface': 'stratigraphic surface',
    'cross_section_plane': 'cross section',
    'cross_section_line': 'cross section',
    'block_model': 'block model',
    'topography_surface': 'topography',
}


def describe_object(obj) -> str:
    """Short text for the list: the type of the object and its isovalue."""
    source_type = obj.source_type or ''
    if source_type.startswith('fold_constraint_'):
        text = 'fold constraint'
    else:
        text = SOURCE_TYPE_LABELS.get(source_type, '')
    if obj.isovalue is not None and source_type in ('feature_isosurface', 'feature_surface'):
        text = f"{text}, value {obj.isovalue:.4g}"
    return text


class ObjectListWidget(QWidget):
    """The objects in the viewer, in groups by source feature.

    The list reads the objects from the registry of the viewer.
    """

    def __init__(self, parent=None, *, viewer=None, properties_widget=None):
        super().__init__(parent)
        self.mainLayout = QVBoxLayout(self)
        self.treeWidget = QTreeWidget(self)
        self.treeWidget.setHeaderHidden(True)  # Hide the header
        self.treeWidget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.mainLayout.addWidget(self.treeWidget)
        addButton = QPushButton("Add Object", self)
        addButton.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        addButton.clicked.connect(self.show_add_object_menu)
        self.mainLayout.addWidget(addButton)
        self.properties_widget = properties_widget
        self.setLayout(self.mainLayout)
        self.viewer = viewer
        self.viewer.objectAdded.connect(self.update_object_list)
        self.viewer.outOfDateChanged.connect(self._on_out_of_date_changed)
        # groups that the user closed; they stay closed when the list is built again
        self._collapsed_groups = set()
        self.treeWidget.installEventFilter(self)
        self.treeWidget.itemSelectionChanged.connect(self.on_object_selected)
        self.treeWidget.itemDoubleClicked.connect(self.onDoubleClick)
        self.treeWidget.itemCollapsed.connect(self._on_group_collapsed)
        self.treeWidget.itemExpanded.connect(self._on_group_expanded)

    def onDoubleClick(self, item, column):
        self.viewer.reset_camera()

    def _on_group_collapsed(self, item):
        if item.parent() is None:
            self._collapsed_groups.add(item.text(0))

    def _on_group_expanded(self, item):
        if item.parent() is None:
            self._collapsed_groups.discard(item.text(0))

    def _selected_object_items(self):
        """Return the selected items that are objects (rows with a
        checkbox/label widget), not the group rows."""
        return [
            item
            for item in self.treeWidget.selectedItems()
            if self.treeWidget.itemWidget(item, 0) is not None
        ]

    def _object_name_for_item(self, item):
        return item.data(0, Qt.ItemDataRole.UserRole)

    def on_object_selected(self):
        selected_items = self._selected_object_items()
        if not selected_items:
            # if nothing selected keep the previous selection.
            # Need to select a new object to change its properties
            return

        # For simplicity, just handle the first selected item
        object_name = self._object_name_for_item(selected_items[0])
        if object_name and self.properties_widget:
            self.properties_widget.setCurrentObject(object_name)

    def update_object_list(self, new_object=None):
        """Build the tree again from the registry of the viewer: a group for
        each source feature, with the objects of the feature. Each object has
        a visibility check box, its name, its type and its isovalue.
        """
        if not self.viewer:
            return
        selected = {self._object_name_for_item(i) for i in self._selected_object_items()}
        self.treeWidget.clear()
        for group_name, objects in self.viewer.registry.grouped_by_feature():
            group = QTreeWidgetItem(self.treeWidget)
            group.setText(0, group_name)
            font = group.font(0)
            font.setBold(True)
            group.setFont(0, font)
            for obj in objects:
                item = self.add_object_item(group, obj)
                if obj.name in selected:
                    item.setSelected(True)
            group.setExpanded(group_name not in self._collapsed_groups)

    def _on_out_of_date_changed(self):
        self.update_object_list()

    def add_object_item(self, group, obj):
        """Add a row for an object to a group row of the tree."""
        item = QTreeWidgetItem(group)
        item.setData(0, Qt.ItemDataRole.UserRole, obj.name)

        visibilityCheckbox = QCheckBox()
        visibilityCheckbox.setChecked(bool(getattr(obj.actor, 'visibility', True)))
        visibilityCheckbox.toggled.connect(
            lambda checked, name=obj.name: self._set_visibility(name, checked)
        )

        itemWidget = QWidget()
        itemLayout = QHBoxLayout(itemWidget)
        itemLayout.setContentsMargins(0, 0, 0, 0)
        itemLayout.addWidget(visibilityCheckbox)
        nameLabel = QLabel(obj.name)
        itemLayout.addWidget(nameLabel)
        description = describe_object(obj)
        if description:
            typeLabel = QLabel(f"({description})")
            typeLabel.setStyleSheet("color: gray;")
            itemLayout.addWidget(typeLabel)
        itemLayout.addStretch(1)
        if obj.out_of_date:
            # show the state with the style and tooltip only
            nameLabel.setStyleSheet("color: gray; font-style: italic;")
            nameLabel.setToolTip("Out of date: the model changed after this object was added")
        self.treeWidget.setItemWidget(item, 0, itemWidget)
        return item

    def _set_visibility(self, object_name, visible):
        try:
            self.viewer.set_object_visibility(object_name, visible)
        except ValueError:
            logger.info(f"Object '{object_name}' is not in the viewer")

    def contextMenuEvent(self, event):
        selected_items = self._selected_object_items()
        multiple = len(selected_items) > 1

        menu = QMenu(self)

        zoom_action = None
        export_action = None
        if not multiple:
            zoom_action = menu.addAction("Zoom to Object")
            export_action = menu.addAction("Export Object")
            menu.addSeparator()

        show_action = menu.addAction("Show Selected")
        hide_action = menu.addAction("Hide Selected")
        menu.addSeparator()
        remove_action = menu.addAction("Remove Selected" if multiple else "Remove Object")

        action = menu.exec(self.mapToGlobal(event.pos()))

        if action is None:
            return
        elif action == zoom_action:
            self.zoom_to_selected_object()
        elif action == export_action:
            self.export_selected_object()
        elif action == show_action:
            self.set_selected_objects_visibility(True)
        elif action == hide_action:
            self.set_selected_objects_visibility(False)
        elif action == remove_action:
            self.remove_selected_object()

    def set_selected_objects_visibility(self, visible):
        """Show or hide every currently-selected object by driving each
        item's visibility checkbox (so viewer state and checkbox state stay
        in sync)."""
        for item in self._selected_object_items():
            item_widget = self.treeWidget.itemWidget(item, 0)
            checkbox = item_widget.findChild(QCheckBox) if item_widget else None
            if checkbox is not None:
                checkbox.setChecked(visible)

    def _first_selected_object(self):
        """The first selected object in the registry, or None."""
        selected_items = self._selected_object_items()
        if not selected_items:
            return None
        return self.viewer.registry.get(self._object_name_for_item(selected_items[0]))

    def zoom_to_selected_object(self):
        obj = self._first_selected_object()
        if obj is None or not hasattr(obj.mesh, 'bounds'):
            return
        try:
            self.viewer.reset_camera(bounds=obj.mesh.bounds)
        except Exception as e:
            logger.error(f"Failed to zoom to object {obj.name}: {e}")

    def export_selected_object(self):
        obj = self._first_selected_object()
        if obj is None or obj.mesh is None:
            return
        object_label = obj.name
        mesh = obj.mesh
        # Determine available formats based on object type and dependencies
        formats = []
        try:
            import geoh5py

            has_geoh5py = True
        except ImportError:
            has_geoh5py = False

        # Check if this is a grid/voxel type (UniformGrid, ImageData, StructuredGrid, RectilinearGrid)
        is_grid = type(mesh).__name__ in [
            'UniformGrid',
            'ImageData',
            'StructuredGrid',
            'RectilinearGrid',
        ]

        if is_grid:
            # Grid/voxel meshes support ASCII export
            formats = ["vtk", "ascii"]
            if has_geoh5py:
                formats.append("geoh5")
        elif hasattr(mesh, "faces"):  # Likely a surface/mesh
            formats = ["obj", "vtk", "ply"]
            if has_geoh5py:
                formats.append("geoh5")
        elif hasattr(mesh, "points"):  # Likely a point cloud
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
            "ascii": "ASCII Grid (*.txt)",
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
            if selected_format == "obj" or selected_format == "vtk":
                (mesh.save(file_path) if hasattr(mesh, "save") else pv.save_meshio(file_path, mesh))
            elif selected_format == "ply":
                pv.save_meshio(file_path, mesh)
            elif selected_format == "vtp":
                (mesh.save(file_path) if hasattr(mesh, "save") else pv.save_meshio(file_path, mesh))
            elif selected_format == "ascii":
                # Export grid/voxel as ASCII: x, y, z, value format
                self._export_grid_ascii(mesh, file_path, object_label)
            elif selected_format == "geoh5":
                with geoh5py.Geoh5(file_path, overwrite=True) as geoh5:
                    if hasattr(mesh, "faces"):
                        geoh5.add_surface(name=object_label, vertices=mesh.points, faces=mesh.faces)
                    else:
                        geoh5.add_points(name=object_label, vertices=mesh.points)
            logger.info(f"Exported {object_label} to {file_path} as {selected_format}")
        except Exception as e:
            logger.error(f"Failed to export object: {e}")
        # Logic for exporting the object

    def _export_grid_ascii(self, mesh, file_path, object_label):
        """Export a grid/voxel mesh to ASCII format.

        Format: x, y, z, value (one line per cell center)

        Parameters
        ----------
        mesh : pyvista grid mesh
            The grid mesh to export
        file_path : str
            Path to the output file
        object_label : str
            Name of the object (used to determine which scalar array to export)
        """
        import numpy as np

        # Get cell centers
        cell_centers = mesh.cell_centers()
        centers = cell_centers.points

        # Get scalar values - try to use the active scalars or the first available array
        scalar_name = mesh.active_scalars_name
        if scalar_name is None:
            # Try to find any cell data array
            if mesh.cell_data:
                scalar_name = list(mesh.cell_data.keys())[0]

        if scalar_name is not None:
            values = mesh.cell_data[scalar_name]
        else:
            # If no scalar data, use zeros
            values = np.zeros(mesh.n_cells)

        # Write to file
        with open(file_path, 'w') as f:
            f.write(f"# ASCII Grid Export: {object_label}\n")
            f.write("# Format: x y z value\n")
            f.write(f"# Number of cells: {mesh.n_cells}\n")
            if scalar_name:
                f.write(f"# Scalar field: {scalar_name}\n")
            f.write("#\n")

            for i in range(len(centers)):
                x, y, z = centers[i]
                value = values[i]
                f.write(f"{x:.6f} {y:.6f} {z:.6f} {value:.6f}\n")

    def remove_selected_object(self):
        names = [self._object_name_for_item(i) for i in self._selected_object_items()]
        for name in names:
            self.viewer.remove_object(name)
        if names:
            self.update_object_list()

    def show_add_object_menu(self):
        menu = QMenu(self)

        loadFeatureAction = menu.addAction("Load from file")
        addQgsLayerAction = menu.addAction("Add from QGIS layer")

        buttonPosition = self.sender().mapToGlobal(self.sender().rect().bottomLeft())
        action = menu.exec(buttonPosition)

        if action == loadFeatureAction:
            self.load_feature_from_file()
        elif action == addQgsLayerAction:
            self.add_object_from_qgis_layer()

    def add_object_from_qgis_layer(self):
        """Show a dialog to pick a QGIS point vector layer, convert it to a VTK/PyVista
        point cloud and copy numeric attributes as point scalars.
        """
        # Local imports so the module can still be imported when QGIS GUI isn't available
        try:
            from qgis.core import QgsMapLayerProxyModel, QgsWkbTypes
            from qgis.gui import QgsMapLayerComboBox

            from loopstructural.gui.compatibility import configure_layer_combo
        except Exception as e:
            print("QGIS GUI components are not available:", e)
            return

        try:
            from loopstructural.main.vectorLayerWrapper import qgsLayerToGeoDataFrame
        except Exception as e:
            print("Could not import qgsLayerToGeoDataFrame:", e)
            return
        import numpy as np
        import pandas as pd
        from qgis.PyQt.QtWidgets import QDialog, QDialogButtonBox, QMessageBox, QVBoxLayout

        from loopstructural.main.model_manager import AllSampler

        dialog = QDialog(self)
        dialog.setWindowTitle("Add from QGIS layer")
        layout = QVBoxLayout(dialog)

        layout.addWidget(QLabel("Select point layer:"))
        layer_combo = QgsMapLayerComboBox(dialog)
        # Restrict to point layers only
        configure_layer_combo(layer_combo, QgsMapLayerProxyModel.Filter.PointLayer)
        layout.addWidget(layer_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        layer = layer_combo.currentLayer()
        if layer is None or not layer.isValid():
            QMessageBox.warning(self, "Invalid layer", "No valid layer selected.")
            return

        # Basic geometry check - ensure the layer contains point geometry
        try:
            if (
                layer.wkbType() != QgsWkbTypes.Type.Point
                and QgsWkbTypes.geometryType(layer.wkbType())
                != QgsWkbTypes.GeometryType.PointGeometry
            ):
                # Some QGIS versions use different enums; allow via proxy filter primarily
                # If the check fails, continue but warn
                print("Selected layer does not appear to be a point layer. Proceeding anyway.")
        except Exception:
            # ignore strict checks - rely on conversion result
            pass

        # Convert layer to a DataFrame (no DTM)
        gdf = qgsLayerToGeoDataFrame(layer)
        sampler = AllSampler()
        # sample the points from the gdf with no DTM and include Z if present
        df = sampler(gdf, None, True)
        if df is None or df.empty:
            QMessageBox.warning(self, "No data", "Selected layer contains no points.")
            return

        # Ensure X,Y,Z columns present
        if not {"X", "Y", "Z"}.issubset(df.columns):
            QMessageBox.warning(
                self, "Invalid data", "Layer conversion did not produce X/Y/Z columns."
            )
            return

        # Build points array
        try:
            pts = np.vstack([df["X"].to_numpy(), df["Y"].to_numpy(), df["Z"].to_numpy()]).T.astype(
                float
            )
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to build point coordinates: {e}")
            return

        # Create PyVista point cloud / PolyData
        try:
            mesh = pv.PolyData(pts)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to create mesh: {e}")
            return

        # Add numeric attributes as point scalars
        for col in df.columns:
            if col in ("X", "Y", "Z"):
                continue
            try:
                ser = pd.to_numeric(df[col], errors='coerce')
                if ser.isnull().all():
                    # no numeric values present
                    continue
                arr = ser.to_numpy().astype(float)
                # Ensure length matches points
                if len(arr) != mesh.n_points:
                    # skip columns that don't match
                    continue
                mesh.point_data[col] = arr
            except Exception:
                # skip non-numeric or problematic fields
                continue

        # Add to viewer
        try:
            self.viewer.add_mesh_object(mesh, name=layer.name())
        except Exception as e:
            logger.error(f"Failed to add mesh to viewer: {e}")

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
            self.viewer.add_mesh_object(mesh, name=file_name)
            logger.info(f"Loaded mesh from file: {file_path}")
        except Exception as e:
            logger.error(f"Failed to load mesh: {e}")

    def _toggle_selected_visibility(self):
        for item in self._selected_object_items():
            item_widget = self.treeWidget.itemWidget(item, 0)
            checkbox = item_widget.findChild(QCheckBox) if item_widget else None
            if checkbox is not None:
                checkbox.setChecked(not checkbox.isChecked())

    def eventFilter(self, source, event):
        if source == self.treeWidget and event.type() == event.KeyPress:
            if event.key() == Qt.Key.Key_Space:
                self._toggle_selected_visibility()
                return True
            elif event.key() == Qt.Key.Key_Delete:
                self.remove_selected_object()
                return True
        return super().eventFilter(source, event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Space:
            self._toggle_selected_visibility()
        elif event.key() == Qt.Key.Key_Delete:
            self.remove_selected_object()
        else:
            super().keyPressEvent(event)
