from typing import Optional, Union

from PyQt5.QtWidgets import QMenu, QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from LoopStructural.datatypes import VectorPoints


class FeatureListWidget(QWidget):
    def __init__(self, parent=None, *, model_manager=None, viewer=None):
        super().__init__(parent)
        self.mainLayout = QVBoxLayout(self)
        self.treeWidget = QTreeWidget(self)
        self.treeWidget.setHeaderHidden(True)  # Hide the header
        self.mainLayout.addWidget(self.treeWidget)
        self.setLayout(self.mainLayout)
        self.model_manager = model_manager
        self.viewer = viewer

        # Add buttons
        self.addBoundingBoxButton = QPushButton("Add Model Bounding Box", self)
        self.addFaultSurfacesButton = QPushButton("Add Fault Surfaces", self)
        self.addStratigraphicSurfacesButton = QPushButton("Add Stratigraphic Surfaces", self)

        # Connect buttons to their respective methods
        self.addBoundingBoxButton.clicked.connect(self.add_model_bounding_box)
        self.addFaultSurfacesButton.clicked.connect(self.add_fault_surfaces)
        self.addStratigraphicSurfacesButton.clicked.connect(self.add_stratigraphic_surfaces)

        # Add buttons to the layout
        self.mainLayout.addWidget(self.addBoundingBoxButton)
        self.mainLayout.addWidget(self.addFaultSurfacesButton)
        self.mainLayout.addWidget(self.addStratigraphicSurfacesButton)

        # Populate the feature list
        self.update_feature_list()
        self.model_manager.observers.append(self.update_feature_list)

    def update_feature_list(self):
        if not self.model_manager:
            return

        self.treeWidget.clear()
        for feature in self.model_manager.features():
            if not feature.name.startswith('__'):
                self.add_feature(feature)

    def _get_vector_scale(self, scale: Optional[Union[float, int]] = None) -> float:
        autoscale = 1.0
        if self.model_manager.model is not None:
            # automatically scale vector data to be 5% of the bounding box length
            autoscale = self.model_manager.model.bounding_box.length.max() * 0.05
        if scale is None:
            scale = autoscale
        else:
            scale = scale * autoscale

        return scale

    def add_feature(self, feature):
        """Add a feature to the feature list widget.

        Parameters
        ----------
        feature : Feature
            The feature object to add to the list.
        """
        featureItem = QTreeWidgetItem(self.treeWidget)
        featureItem.setText(0, feature.name)

    def contextMenuEvent(self, event):
        menu = QMenu(self)

        add_scalar_action = menu.addAction("Add Scalar Field")
        add_surface_action = menu.addAction("Add Surface")
        add_vector_action = menu.addAction("Add Vector Field")
        add_data_action = menu.addAction("Add Data")

        action = menu.exec_(self.mapToGlobal(event.pos()))

        selected_items = self.treeWidget.selectedItems()
        if not selected_items:
            return

        feature_name = selected_items[0].text(0)

        if action == add_scalar_action:
            self.add_scalar_field(feature_name)
        elif action == add_surface_action:
            self.add_surface(feature_name)
        elif action == add_vector_action:
            self.add_vector_field(feature_name)
        elif action == add_data_action:
            self.add_data(feature_name)

    def add_scalar_field(self, feature_name):
        scalar_field = self.model_manager.model[feature_name].scalar_field()
        self.viewer.add_mesh_object(scalar_field.vtk(), name=f'{feature_name}_scalar_field')
        print(f"Adding scalar field to feature: {feature_name}")

    def add_surface(self, feature_name):
        surfaces = self.model_manager.model[feature_name].surfaces()
        for surface in surfaces:
            self.viewer.add_mesh_object(surface.vtk(), name=f'{feature_name}_surface')
        print(f"Adding surface to feature: {feature_name}")

    def add_vector_field(self, feature_name):
        vector_field = self.model_manager.model[feature_name].vector_field()
        scale = self._get_vector_scale()
        self.viewer.add_mesh_object(vector_field.vtk(scale=scale), name=f'{feature_name}_vector_field')
        print(f"Adding vector field to feature: {feature_name}")

    def add_data(self, feature_name):
        data = self.model_manager.model[feature_name].get_data()
        for d in data:
            if issubclass(type(d), VectorPoints):
                scale = self._get_vector_scale()
                # tolerance is None means all points are shown
                self.viewer.add_mesh_object(
                    d.vtk(scale=scale, tolerance=None), name=f'{feature_name}_{d.name}_points'
                )
            else:
                self.viewer.add_mesh_object(d.vtk(), name=f'{feature_name}_{d.name}')
        print(f"Adding data to feature: {feature_name}")

    def add_model_bounding_box(self):
        if not self.model_manager:
            print("Model manager is not set.")
            return
        bb = self.model_manager.model.bounding_box.vtk().outline()
        self.viewer.add_mesh_object(bb, name='model_bounding_box')
        # Logic for adding model bounding box
        print("Adding model bounding box...")

    def add_fault_surfaces(self):
        if not self.model_manager:
            print("Model manager is not set.")
            return
        fault_surfaces = self.model_manager.model.get_fault_surfaces()
        for surface in fault_surfaces:
            self.viewer.add_mesh_object(surface.vtk(), name=f'fault_surface_{surface.name}')
        print("Adding fault surfaces...")

    def add_stratigraphic_surfaces(self):
        if not self.model_manager:
            print("Model manager is not set.")
            return
        stratigraphic_surfaces = self.model_manager.model.get_stratigraphic_surfaces()
        for surface in stratigraphic_surfaces:
            self.viewer.add_mesh_object(surface.vtk(), name=surface.name)
        print("Adding stratigraphic surfaces...")
