import logging

from qgis.core import QgsApplication
from qgis.PyQt.QtWidgets import (
    QDialog,
    QMenu,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..background_task import finish_background_task, start_background_task
from ..messages import push_info, push_warning
from .isosurface_dialog import IsosurfaceDialog
from .isovalues import isosurface_name
from .mesh_builders import FOLD_CONSTRAINT_COLOURS, FOLD_CONSTRAINT_LABELS, MeshBuilder
from .viewer_actions_widget import ViewerActionsWidget

logger = logging.getLogger(__name__)


class FeatureListWidget(QWidget):
    """The features of the model, with the actions to add their meshes to the
    viewer, and the button that builds out-of-date objects again.

    The meshes come from `MeshBuilder`. The viewer-wide actions (bounding box,
    topography, cross sections, block model) are in `ViewerActionsWidget`.
    """

    FOLD_CONSTRAINT_LABELS = FOLD_CONSTRAINT_LABELS

    def __init__(self, parent=None, *, model_manager=None, viewer=None, data_manager=None):
        super().__init__(parent)
        self.mainLayout = QVBoxLayout(self)
        self.treeWidget = QTreeWidget(self)
        self.treeWidget.setHeaderHidden(True)  # Hide the header
        self.mainLayout.addWidget(self.treeWidget)
        self.setLayout(self.mainLayout)
        self.model_manager = model_manager
        self.viewer = viewer
        self.data_manager = data_manager
        self.builder = MeshBuilder(model_manager)

        self.actionsWidget = ViewerActionsWidget(
            self, model_manager=model_manager, viewer=viewer, data_manager=data_manager
        )
        self.mainLayout.addWidget(self.actionsWidget)

        # Objects in the viewer are not rebuilt automatically when the model
        # changes (that can re-solve the whole model after each small edit).
        # They are marked out of date, and this button rebuilds them.
        self.updateObjectsButton = QPushButton(self)
        self.updateObjectsButton.setIcon(QgsApplication.getThemeIcon("mActionRefresh.svg"))
        self.updateObjectsButton.clicked.connect(self.update_out_of_date_objects)
        self.mainLayout.addWidget(self.updateObjectsButton)
        self._update_objects_thread = None
        self._update_objects_worker = None
        self._update_objects_progress = None
        if self.viewer is not None:
            self.viewer.outOfDateChanged.connect(self._refresh_update_objects_button)
        self._refresh_update_objects_button()

        # background task handles for the isosurfaces (only one task at a time)
        self._isosurface_thread = None
        self._isosurface_worker = None
        self._isosurface_progress = None
        self._pending_isosurface = None

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
                # also listen for model and feature updates so the viewer
                # objects built from the model can be marked out of date
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
        self.actionsWidget.on_model_updated()

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
        add_isosurface_action = menu.addAction("Add Isosurface...")
        add_vector_action = menu.addAction("Add Vector Field")
        add_data_action = menu.addAction("Add Data")

        selected_items = self.treeWidget.selectedItems()
        fold_actions = {}
        if selected_items and self.builder.get_fold(selected_items[0].text(0)) is not None:
            fold_menu = menu.addMenu("Add Fold Constraints")
            for constraint, label in self.FOLD_CONSTRAINT_LABELS.items():
                fold_actions[fold_menu.addAction(label)] = constraint
            fold_menu.addSeparator()
            fold_actions[fold_menu.addAction("All")] = None

        action = menu.exec(self.mapToGlobal(event.pos()))

        if not selected_items:
            return

        feature_name = selected_items[0].text(0)

        if action in fold_actions:
            constraint = fold_actions[action]
            constraints = [constraint] if constraint else list(self.FOLD_CONSTRAINT_LABELS)
            try:
                for c in constraints:
                    self.add_fold_constraint(feature_name, c)
            except Exception as e:
                logger.exception("Failed to add fold constraints")
                QMessageBox.warning(
                    self, "Fold Constraints", f"Cannot show the fold constraints:\n{e}"
                )
        elif action == add_scalar_action:
            self.add_scalar_field(feature_name)
        elif action == add_surface_action:
            self.add_surface(feature_name)
        elif action == add_isosurface_action:
            self.add_isosurfaces(feature_name)
        elif action == add_vector_action:
            self.add_vector_field(feature_name)
        elif action == add_data_action:
            self.add_data(feature_name)

    # -- meshes of one feature -------------------------------------------

    def add_scalar_field(self, feature_name):
        self.viewer.add_mesh_object(
            self.builder.scalar_field(feature_name),
            name=f'{feature_name}_scalar_field',
            source_feature=feature_name,
            source_type='feature_scalar',
        )

    def add_surface(self, feature_name):
        surfaces = self.builder.feature_surfaces(feature_name)
        for i, surface in enumerate(surfaces):
            # ensure unique names for multiple surfaces per feature
            mesh_name = f'{feature_name}_surface' if i == 0 else f'{feature_name}_surface_{i+1}'
            # try to determine an isovalue for this surface (may be an attribute or encoded in name)
            isovalue = getattr(surface, 'isovalue', None)
            if isovalue is None:
                # attempt to parse trailing numeric suffix in the surface name
                try:
                    isovalue = float(str(surface.name).rsplit('_', 1)[1])
                except (IndexError, ValueError):
                    isovalue = None

            self.viewer.add_mesh_object(
                surface.vtk(),
                name=mesh_name,
                source_feature=feature_name,
                source_type='feature_surface',
                isovalue=isovalue,
            )

    def add_vector_field(self, feature_name):
        self.viewer.add_mesh_object(
            self.builder.vector_field(feature_name),
            name=f'{feature_name}_vector_field',
            source_feature=feature_name,
            source_type='feature_vector',
        )

    def add_fold_constraint(self, feature_name, constraint):
        """Add the vectors of one fold constraint of a folded feature to the viewer.

        Parameters
        ----------
        feature_name : str
            Name of the folded feature.
        constraint : str
            One of 'direction', 'axis' or 'norm'.
        """
        mesh = self.builder.fold_constraint(feature_name, constraint)
        if mesh is None:
            return
        self.viewer.add_mesh_object(
            mesh,
            name=f'{feature_name}_fold_{constraint}',
            color=FOLD_CONSTRAINT_COLOURS[constraint],
            source_feature=feature_name,
            source_type=f'fold_constraint_{constraint}',
        )

    def add_data(self, feature_name):
        for name, mesh, source_type in self.builder.data_meshes(feature_name):
            self.viewer.add_mesh_object(
                mesh, name=name, source_feature=feature_name, source_type=source_type
            )
        logger.info(f"Adding data to feature: {feature_name}")

    # -- isosurfaces -----------------------------------------------------

    def add_isosurfaces(self, feature_name):
        """Ask for the values, and add one isosurface object for each value."""
        if self.model_manager is None or self.model_manager.model is None:
            return
        low = high = None
        try:
            low, high = self.builder.scalar_range(feature_name)
        except Exception:
            logger.info(f"Cannot find the range of the scalar field of {feature_name}")
        dialog = IsosurfaceDialog(feature_name, low, high, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._start_isosurface_task(feature_name, dialog.values())

    def change_isovalue(self, object_name, value):
        """Build the isosurface object `object_name` again at a new value."""
        obj = self.viewer.registry.get(object_name)
        if obj is None or not obj.is_isosurface or obj.source_feature is None:
            return
        self._start_isosurface_task(obj.source_feature, [value], existing_name=object_name)

    def _start_isosurface_task(self, feature_name, values, existing_name=None):
        if self._isosurface_thread is not None:
            push_info("Isosurfaces", "Wait for the isosurfaces that are being built.")
            return
        if not values:
            return

        def target(progress_callback):
            results = []
            for i, value in enumerate(values):
                progress_callback(f"Isosurface {value:.4g} ({i + 1} of {len(values)})...")
                try:
                    results.append((value, self.builder.isosurface(feature_name, value), None))
                except Exception as e:
                    results.append((value, None, str(e)))
            return results

        self._pending_isosurface = (feature_name, existing_name)
        self._isosurface_thread, self._isosurface_worker, self._isosurface_progress = (
            start_background_task(
                self,
                target,
                title="Isosurfaces",
                initial_label="Building isosurfaces...",
                on_progress=self._on_isosurface_progress,
                on_finished=self._on_isosurfaces_finished,
                on_error=self._on_isosurfaces_error,
            )
        )

    def _on_isosurface_progress(self, message):
        try:
            self._isosurface_progress.setLabelText(message)
        except Exception:
            pass

    def _finish_isosurface_task(self):
        finish_background_task(
            self._isosurface_thread, self._isosurface_worker, self._isosurface_progress
        )
        self._isosurface_thread = None
        self._isosurface_worker = None
        self._isosurface_progress = None

    def _on_isosurfaces_finished(self, results):
        self._finish_isosurface_task()
        feature_name, existing_name = self._pending_isosurface
        self._pending_isosurface = None
        added, failed = [], []
        for value, mesh, error in results:
            if mesh is None:
                failed.append(value)
                continue
            if existing_name is not None:
                if existing_name not in self.viewer.registry:
                    continue  # removed from the viewer while the surface was built
                self.viewer.replace_mesh_object(
                    existing_name, mesh, None, isovalue=float(value), out_of_date=False
                )
            else:
                name = self.viewer.registry.unique_name(isosurface_name(feature_name, value))
                self.viewer.add_mesh_object(
                    mesh,
                    name=name,
                    source_feature=feature_name,
                    source_type='feature_isosurface',
                    isovalue=float(value),
                )
            added.append(value)
        self._render_viewer()
        if failed:
            values_text = ", ".join(f"{v:.4g}" for v in failed)
            push_warning(
                "Isosurfaces",
                f"No surface for {feature_name} at {values_text}. "
                "The value may be outside the range of the scalar field.",
            )
        elif added:
            logger.info(f"Added {len(added)} isosurface(s) of {feature_name}")

    def _on_isosurfaces_error(self, traceback_text):
        self._finish_isosurface_task()
        self._pending_isosurface = None
        logger.error(f"Failed to build isosurfaces: {traceback_text}")
        push_warning("Isosurfaces", "Cannot build the isosurfaces. See the log for details.")

    def _render_viewer(self):
        try:
            self.viewer.render()
        except Exception:
            pass

    # -- update out-of-date objects --------------------------------------

    def _on_model_update(self, event: str, *args):
        """Mark the viewer objects built from the model as out of date.

        The objects are not rebuilt here: rebuilding can solve the model
        again, which is slow after each small edit. The user rebuilds them
        with the update button (see `update_out_of_date_objects`).
        """
        if not self.viewer:
            return
        if event not in ('model_updated', 'feature_updated'):
            return
        names = [obj.name for obj in self.viewer.registry.rebuildable()]
        self.viewer.set_out_of_date(names, True)

    def _refresh_update_objects_button(self):
        count = len(self.viewer.out_of_date_objects()) if self.viewer is not None else 0
        if self._update_objects_thread is not None:
            self.updateObjectsButton.setText("Updating Viewer Objects...")
            self.updateObjectsButton.setEnabled(False)
        elif count:
            noun = "Object" if count == 1 else "Objects"
            self.updateObjectsButton.setText(f"Update {count} Out-of-Date {noun}")
            self.updateObjectsButton.setToolTip(
                "The model changed after these objects were added to the viewer. "
                "Build them again from the current model."
            )
            self.updateObjectsButton.setEnabled(True)
        else:
            self.updateObjectsButton.setText("Viewer Objects Up to Date")
            self.updateObjectsButton.setToolTip("")
            self.updateObjectsButton.setEnabled(False)

    def update_out_of_date_objects(self):
        """Build all out-of-date viewer objects again from the current model.

        The objects are built on a background thread (this can solve the
        model), then added to the viewer again on the GUI thread with the
        same name and viewer settings (see `_on_update_objects_finished`).
        """
        if not self.model_manager or self.viewer is None:
            return
        if self.model_manager.model is None:
            logger.info("No model available to update the viewer objects.")
            return
        objects = [self.viewer.registry.get(n) for n in self.viewer.out_of_date_objects()]
        if not objects:
            return
        specs = []
        for obj in objects:
            spec = {
                'name': obj.name,
                'source_type': obj.source_type_text,
                'source_feature': obj.source_feature,
                'isovalue': obj.isovalue,
                'metadata': dict(obj.metadata),
            }
            if spec['source_type'] in ('cross_section_plane', 'cross_section_line'):
                # the section geometry does not change; copy it so the
                # background thread does not change the mesh on screen
                spec['mesh'] = obj.mesh.copy()
            specs.append(spec)

        if any(obj.uses_stratigraphy_colours for obj in objects):
            missing = self.model_manager.get_units_without_colour()
            if missing:
                QMessageBox.warning(
                    self,
                    "Missing unit colour",
                    "Cannot update the objects coloured by stratigraphy. These units "
                    "have no valid colour in the stratigraphic column:\n\n"
                    + "\n".join(missing)
                    + "\n\nSet a colour for each unit and try again.",
                )
                return

        def target(progress_callback):
            results = []
            for i, spec in enumerate(specs):
                progress_callback(f"Updating {spec['name']} ({i + 1} of {len(specs)})...")
                try:
                    mesh, overrides = self.builder.rebuild(spec)
                    results.append((spec['name'], mesh, overrides, spec['metadata'], None))
                except Exception as e:
                    results.append((spec['name'], None, {}, None, str(e)))
            return results

        self._update_objects_thread, self._update_objects_worker, self._update_objects_progress = (
            start_background_task(
                self,
                target,
                title="Update Viewer Objects",
                initial_label="Updating viewer objects...",
                on_progress=self._on_update_objects_progress,
                on_finished=self._on_update_objects_finished,
                on_error=self._on_update_objects_error,
            )
        )
        self._refresh_update_objects_button()

    def _on_update_objects_progress(self, message):
        try:
            self._update_objects_progress.setLabelText(message)
        except Exception:
            pass

    def _finish_update_objects_task(self):
        finish_background_task(
            self._update_objects_thread, self._update_objects_worker, self._update_objects_progress
        )
        self._update_objects_thread = None
        self._update_objects_worker = None
        self._update_objects_progress = None

    def _on_update_objects_finished(self, results):
        self._finish_update_objects_task()
        failed = []
        for name, mesh, overrides, metadata, error in results:
            if name not in self.viewer.registry:
                # removed from the viewer while the update ran
                continue
            if error is not None:
                failed.append(f"{name}: {error}")
                continue
            try:
                self.viewer.replace_mesh_object(
                    name, mesh, overrides, out_of_date=False, metadata=metadata
                )
            except Exception as e:
                logger.exception(f"Cannot add updated object '{name}' to the viewer")
                failed.append(f"{name}: {e}")
        self._render_viewer()
        self._refresh_update_objects_button()
        if failed:
            logger.warning("Cannot update viewer objects:\n" + "\n".join(failed))
            QMessageBox.warning(
                self,
                "Update Viewer Objects",
                "These objects were not updated and are still out of date:\n\n" + "\n".join(failed),
            )

    def _on_update_objects_error(self, traceback_text):
        self._finish_update_objects_task()
        self._refresh_update_objects_button()
        logger.error(f"Failed to update viewer objects: {traceback_text}")
        QMessageBox.warning(
            self,
            "Update Viewer Objects",
            "Cannot update the viewer objects. See the log for details.",
        )
