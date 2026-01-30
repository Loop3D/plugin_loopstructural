import logging
from typing import Optional, Union

import numpy as np
from LoopStructural.datatypes import VectorPoints
from PyQt5.QtWidgets import QMenu, QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

logger = logging.getLogger(__name__)


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
        # register observer to refresh list and viewer when model changes
        if self.model_manager is not None:
            # Attach to specific model events using the Observable framework
            try:
                # listeners will receive (observable, event, *args)
                # attach wrappers that match the Observable callback signature
                self._disp_update = self.model_manager.attach(
                    lambda _obs, _event, *a, **k: self.update_feature_list(), 'model_updated'
                )
                # also listen for model and feature updates so visualisation can refresh
                # forward event and args into the handler so it can act on specific surfaces
                self._disp_feature = self.model_manager.attach(
                    lambda _obs, _event, *a, **k: self._on_model_update(_event, *a), 'model_updated'
                )
                self._disp_feature2 = self.model_manager.attach(
                    lambda _obs, _event, *a, **k: self._on_model_update(_event, *a),
                    'feature_updated',
                )
            except Exception:
                # Fall back to legacy observers list if available
                try:
                    self.model_manager.observers.append(self.update_feature_list)
                    self.model_manager.observers.append(self._on_model_update)
                except Exception:
                    pass

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
        self.viewer.add_mesh_object(
            scalar_field.vtk(),
            name=f'{feature_name}_scalar_field',
            source_feature=feature_name,
            source_type='feature_scalar',
        )

    def add_surface(self, feature_name):
        surfaces = self.model_manager.model[feature_name].surfaces()
        for i, surface in enumerate(surfaces):
            # ensure unique names for multiple surfaces per feature
            mesh_name = f'{feature_name}_surface' if i == 0 else f'{feature_name}_surface_{i+1}'
            # try to determine an isovalue for this surface (may be an attribute or encoded in name)
            isovalue = None
            try:
                isovalue = getattr(surface, 'isovalue', None)
            except Exception:
                isovalue = None
            if isovalue is None:
                # attempt to parse trailing numeric suffix in the surface name
                try:
                    parts = str(surface.name).rsplit('_', 1)
                    if len(parts) == 2:
                        isovalue = float(parts[1])
                except Exception:
                    isovalue = None

            self.viewer.add_mesh_object(
                surface.vtk(),
                name=mesh_name,
                source_feature=feature_name,
                source_type='feature_surface',
                isovalue=isovalue,
            )

    def add_vector_field(self, feature_name):
        vector_field = self.model_manager.model[feature_name].vector_field()
        scale = self._get_vector_scale()
        self.viewer.add_mesh_object(
            vector_field.vtk(scale=scale),
            name=f'{feature_name}_vector_field',
            source_feature=feature_name,
            source_type='feature_vector',
        )

    def add_data(self, feature_name):
        data = self.model_manager.model[feature_name].get_data()
        for d in data:
            d.locations = self.model_manager.model.rescale(d.locations)
            if issubclass(type(d), VectorPoints):
                scale = self._get_vector_scale()
                # tolerance is None means all points are shown
                self.viewer.add_mesh_object(
                    d.vtk(scale=scale, tolerance=None),
                    name=f'{feature_name}_{d.name}_points',
                    source_feature=feature_name,
                    source_type='feature_points',
                )
            else:
                self.viewer.add_mesh_object(
                    d.vtk(),
                    name=f'{feature_name}_{d.name}',
                    source_feature=feature_name,
                    source_type='feature_data',
                )
        logger.info(f"Adding data to feature: {feature_name}")

    def add_model_bounding_box(self):
        if not self.model_manager:
            logger.info("Model manager is not set.")
            return
        bb = self.model_manager.model.bounding_box.vtk().outline()
        self.viewer.add_mesh_object(
            bb, name='model_bounding_box', source_feature='__model__', source_type='bounding_box'
        )
        # Logic for adding model bounding box
        logger.info("Adding model bounding box...")

    def add_fault_surfaces(self):
        if not self.model_manager:
            logger.info("Model manager is not set.")
            return
        self.model_manager.update_all_features(subset='faults')
        fault_surfaces = self.model_manager.model.get_fault_surfaces()
        for surface in fault_surfaces:
            self.viewer.add_mesh_object(
                surface.vtk(),
                name=f'fault_surface_{surface.name}',
                source_feature=surface.name,
                source_type='fault_surface',
                isovalue=0.0,
            )
        logger.info("Adding fault surfaces...")

    def add_stratigraphic_surfaces(self):
        if not self.model_manager:
            logger.info("Model manager is not set.")
            return
        stratigraphic_surfaces = self.model_manager.model.get_stratigraphic_surfaces()

        for surface in stratigraphic_surfaces:
            self.viewer.add_mesh_object(
                surface.vtk(),
                name=surface.name,
                color=surface.colour,
                source_feature=surface.name,
                isovalue=np.mean(surface.values),
                source_type='stratigraphic_surface',
            )

    def _on_model_update(self, event: str, *args):
        """Called when the underlying model_manager notifies observers.

        We remove any meshes that were created from model features and re-add
        them from the current model so visualisation follows model changes.

        If the notification is for a specific feature (event == 'feature_updated')
        and an isovalue is provided (either as second arg or stored in viewer
        metadata), only the matching surface will be re-added. For generic
        'model_updated' notifications the previous behaviour (re-add all
        affected feature representations) is preserved.
        """

        # Prefer the DebugManager for logging when available (it forwards to
        # the plugin/toolbelt logger and handles debug mode). Fall back to the
        # module logger if no debug manager is present.
        def _log(msg, level=0):
            try:
                dbg = None
                if getattr(self, 'model_manager', None) is not None:
                    dbg = getattr(self.model_manager, '_debug_manager', None)
                if dbg is not None and hasattr(dbg, 'log'):
                    # DebugManager.log expects message and log_level keyword
                    dbg.log(str(msg), log_level=level)
                else:
                    logger.info(str(msg))
            except Exception:
                try:
                    logger.info(str(msg))
                except Exception:
                    pass

        _log(f"Model update event received: {event} with args: {args}")
        try:
            _log([f"Mesh: {name}, Meta: {meta}" for name, meta in self.viewer.meshes.items()])
        except Exception:
            _log("Model update: failed to enumerate viewer meshes")

        if not self.model_manager or not self.viewer:
            return
        if event not in ('model_updated', 'feature_updated'):
            return
        feature_name = None
        if event == 'feature_updated' and len(args) >= 1:
            feature_name = args[0]

        # If the model was reset (None) or features referenced by viewer meshes
        # no longer exist in the current model, remove the linkage from those
        # meshes so they are not treated as feature-driven on subsequent updates.
        try:
            try:
                current_features = {f.name for f in self.model_manager.features()}
            except Exception:
                current_features = set()

            # If the model is None or a feature referenced by a mesh is missing,
            # decouple that mesh from the feature so it remains visible but won't
            # be auto-updated or re-added when the model changes.
            for mesh_name, meta in list(self.viewer.meshes.items()):
                sf = meta.get('source_feature', None)
                if sf is None:
                    continue
                if self.model_manager.model is None or sf not in current_features:
                    _log(f"Decoupling mesh '{mesh_name}' from missing feature '{sf}'")
                    meta.pop('source_feature', None)
                    meta.pop('source_type', None)
                    meta.pop('isovalue', None)
                    # mark as decoupled so other logic can detect it if needed
                    meta['decoupled_from_feature'] = True
        except Exception:
            _log('Failed while decoupling meshes from features')

        # Build a set of features that currently have viewer meshes
        affected_features = set()
        for _, meta in list(self.viewer.meshes.items()):
            if feature_name is not None:
                if meta.get('source_feature', None) == feature_name:
                    affected_features.add(feature_name)
                    _log(f"Updating visualisation for feature: {feature_name}")
                    continue

            sf = meta.get('source_feature', None)

            if sf is not None:
                affected_features.add(sf)
        _log(f"Affected features to update: {affected_features}")
        # For each affected feature, only update existing meshes tied to that feature
        for feature_name in affected_features:
            # collect mesh names that belong to this feature (snapshot to avoid mutation while iterating)
            meshes_for_feature = [
                name
                for name, meta in list(self.viewer.meshes.items())
                if meta.get('source_feature') == feature_name
            ]
            _log(f"Re-adding meshes for feature: {feature_name}: {meshes_for_feature}")

            for mesh_name in meshes_for_feature:
                meta = self.viewer.meshes.get(mesh_name, {})
                source_type = meta.get('source_type')
                kwargs = meta.get('kwargs', {}) or {}
                isovalue = meta.get('isovalue', None)

                # remove existing actor/entry so add_mesh_object can recreate with same name
                try:
                    self.viewer.remove_object(mesh_name)
                    _log(f"Removed existing mesh: {mesh_name}")
                except Exception:
                    _log(f"Failed to remove existing mesh: {mesh_name}")
                    pass

                try:
                    # Surfaces associated with individual features
                    if source_type == 'feature_surface':
                        surfaces = []
                        try:
                            if isovalue is not None:
                                surfaces = self.model_manager.model[feature_name].surfaces(isovalue)
                            else:
                                surfaces = self.model_manager.model[feature_name].surfaces()

                            if surfaces:
                                add_name = mesh_name
                                _log(
                                    f"Re-adding surface for feature: {feature_name} with isovalue: {isovalue} and {kwargs}"
                                )
                                kwargs['isovalue'] = isovalue

                                self.viewer.add_mesh_object(
                                    surfaces[0].vtk(),
                                    name=add_name,
                                    source_feature=feature_name,
                                    source_type='feature_surface',
                                    isovalue=isovalue,
                                    **kwargs,
                                )
                                continue
                        except Exception as e:
                            _log(
                                f"Failed to find matching surface for feature: {feature_name} with isovalue: {isovalue}, trying all surfaces. Error: {e}"
                            )

                    # Fault surfaces (added via add_fault_surfaces)
                    if source_type == 'fault_surface':
                        try:
                            fault_surfaces = self.model_manager.model.get_fault_surfaces()
                            match = next(
                                (s for s in fault_surfaces if str(s.name) == str(feature_name)),
                                None,
                            )
                            if match is not None:
                                _log(f"Re-adding fault surface for: {feature_name}")
                                self.viewer.add_mesh_object(
                                    match.vtk(),
                                    name=mesh_name,
                                    source_feature=feature_name,
                                    source_type='fault_surface',
                                    isovalue=meta.get('isovalue', 0.0),
                                    **kwargs,
                                )
                                continue
                        except Exception as e:
                            _log(f"Failed to re-add fault surface for {feature_name}: {e}")

                    # Stratigraphic surfaces (added via add_stratigraphic_surfaces)
                    if source_type == 'stratigraphic_surface':
                        try:
                            strat_surfaces = self.model_manager.model.get_stratigraphic_surfaces()
                            match = next(
                                (s for s in strat_surfaces if str(s.name) == str(feature_name)),
                                None,
                            )
                            if match is not None:
                                _log(f"Re-adding stratigraphic surface for: {feature_name}")
                                kwargs['color'] = getattr(match, 'colour', None)

                                self.viewer.add_mesh_object(
                                    match.vtk(),
                                    name=mesh_name,
                                    source_feature=feature_name,
                                    source_type='stratigraphic_surface',
                                    **kwargs,
                                )
                                continue
                        except Exception as e:
                            _log(f"Failed to re-add stratigraphic surface for {feature_name}: {e}")

                    # Vectors, points, scalar fields and other feature related objects
                    if source_type == 'feature_vector' or source_type == 'feature_vectors':
                        try:
                            self.add_vector_field(feature_name)
                            continue
                        except Exception as e:
                            _log(f"Failed to re-add vector field for {feature_name}: {e}")

                    if source_type in ('feature_points', 'feature_data'):
                        try:
                            self.add_data(feature_name)
                            continue
                        except Exception as e:
                            _log(f"Failed to re-add data for {feature_name}: {e}")

                    if source_type == 'feature_scalar':
                        try:
                            self.add_scalar_field(feature_name)
                            continue
                        except Exception as e:
                            _log(f"Failed to re-add scalar field for {feature_name}: {e}")

                    if source_type == 'bounding_box' or mesh_name == 'model_bounding_box':
                        try:
                            self.add_model_bounding_box()
                            continue
                        except Exception as e:
                            _log(f"Failed to re-add bounding box: {e}")

                    # Fallback: if nothing matched, attempt to re-add by using viewer metadata
                    # Many viewer entries store the vtk source under meta['vtk'] or similar; try best-effort
                    try:
                        vtk_src = meta.get('vtk')
                        if vtk_src is not None:
                            _log(f"Fallback re-add for mesh {mesh_name}")
                            self.viewer.add_mesh_object(vtk_src, name=mesh_name, **kwargs)
                    except Exception:
                        pass

                except Exception as e:
                    _log(f"Failed to update visualisation for feature: {feature_name}. Error: {e}")

        # Refresh the viewer
        try:
            self.viewer.update()
        except Exception:
            pass
