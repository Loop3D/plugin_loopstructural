from typing import Any, Dict, Optional, Tuple

from pyvistaqt import QtInteractor
from qgis.PyQt.QtCore import pyqtSignal

from .mesh_scalar_utils import threshold_mesh
from .object_registry import ObjectRegistry, ViewerObject


class LoopPyVistaQTPlotter(QtInteractor):
    objectAdded = pyqtSignal(QtInteractor)  # Signal to request deletion
    # emitted when objects are marked out of date, or brought up to date
    outOfDateChanged = pyqtSignal()

    def __init__(self, parent):
        super().__init__(parent=parent)
        self.add_axes()
        # the objects in the viewer, and the information to build them again
        self.registry = ObjectRegistry()

    def add_mesh_object(
        self,
        mesh,
        name: str,
        *,
        scalars: Optional[Any] = None,
        cmap: Optional[str] = None,
        clim: Optional[Tuple[float, float]] = None,
        opacity: Optional[float] = None,
        show_scalar_bar: bool = False,
        color: Optional[Tuple[float, float, float]] = None,
        source_feature: Optional[str] = None,
        source_type: Optional[str] = None,
        isovalue: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        out_of_date: bool = False,
        threshold: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> None:
        """Add a mesh to the plotter.

        This wrapper stores metadata to allow robust re-adding and
        updating of visualization parameters.

        Parameters
        ----------
        mesh : pyvista.PolyData or similar
            Mesh-like object to add.
        name : str
            Unique name for the mesh.
        scalars : Optional[Any]
            Name of scalar array or scalar values to map (optional).
        cmap : Optional[str]
            Colormap name (optional).
        clim : Optional[tuple(float, float)]
            Color limits as (min, max) for the colormap (optional).
        opacity : Optional[float]
            Surface opacity in the range 0-1 (optional).
        show_scalar_bar : bool
            Whether to show a scalar bar for mapped scalars.
        color : Optional[tuple(float, float, float)]
            Solid color as (r, g, b) in 0..1; if provided, overrides scalars.
        source_feature : Optional[str]
            Name of the geological feature (or other source identifier) that
            generated this mesh. Stored for later updates.
        source_type : Optional[str]
            A short tag describing the kind of source (e.g. 'feature_surface',
            'fault_surface', 'bounding_box').
        metadata : Optional[dict]
            Extra values needed to build the mesh again from the model (for
            example the number of blocks of a block model).
        out_of_date : bool
            True if the mesh no longer matches the model.
        threshold : Optional[dict]
            Show only the part of the mesh whose values are in a range (see
            `mesh_scalar_utils.threshold_mesh`). The full mesh is still
            stored, so the filter can be changed or removed later. Raises
            ValueError if no cells are in the range.

        Returns
        -------
        None
        """
        # Decide rendering mode: color (solid) if color provided else scalar mapping
        scalars = scalars if scalars is not None else mesh.active_scalars_name
        use_scalar = color is None and scalars is not None

        # Build add_mesh kwargs
        add_kwargs: Dict[str, Any] = {}

        if use_scalar:
            add_kwargs['scalars'] = scalars
            add_kwargs['cmap'] = cmap
            if clim is not None:
                add_kwargs['clim'] = clim
            add_kwargs['show_scalar_bar'] = show_scalar_bar
        else:
            # solid color
            if color is not None:
                add_kwargs['color'] = color
            # ensure scalar bar is disabled if color is used
            add_kwargs['show_scalar_bar'] = False

        if opacity is not None:
            add_kwargs['opacity'] = opacity

        # merge any extra kwargs (allow caller to override default choices)
        add_kwargs.update(kwargs)

        display_mesh = mesh
        if threshold:
            display_mesh = threshold_mesh(mesh, threshold)
            if display_mesh.n_cells == 0:
                raise ValueError("No cells are in the filter range")

        # attempt to add to the underlying pyvista plotter
        actor = self.add_mesh(display_mesh, name=name, **add_kwargs)

        self.registry.add(
            ViewerObject(
                name,
                mesh,
                actor=actor,
                kwargs=add_kwargs,
                source_feature=source_feature,
                source_type=source_type,
                isovalue=isovalue,
                metadata=metadata,
                out_of_date=out_of_date,
                threshold=threshold,
                display_mesh=display_mesh,
            )
        )
        self.objectAdded.emit(self)

    def get_source_metadata(self, name: str) -> Dict[str, Any]:
        """Return the source values of an object as keyword arguments for
        `add_mesh_object`, so that an object removed and added again (for
        example to change its colour map) can still be built again from the
        model.
        """
        obj = self.registry.get(name)
        return obj.source_values() if obj else {}

    def replace_mesh_object(self, name: str, mesh=None, overrides=None, **source_updates) -> None:
        """Add the object `name` again, and keep its source values, viewer
        settings (colour map, opacity, colour picked by the user, ...) and
        visibility.

        Parameters
        ----------
        name : str
            Name of an object in the viewer.
        mesh : optional
            A new mesh for the object (e.g. built again from the model). If
            None, the current mesh is used.
        overrides : Optional[dict]
            Viewer settings that replace the stored ones (e.g. a new unit
            colour). A colour picked by the user still has priority.
        **source_updates
            Source values to change, e.g. `threshold=...` or
            `out_of_date=False`.

        pyvista replaces the actor that has the same name, so if the new
        object cannot be added, the old object stays and the error is raised.
        """
        obj = self.registry.get(name)
        if mesh is None:
            mesh = obj.mesh
        source = self.get_source_metadata(name)
        source.update(source_updates)
        kwargs = {
            key: value for key, value in obj.kwargs.items() if key not in source and key != 'name'
        }
        kwargs.update(overrides or {})
        user_colour = obj.color
        if user_colour is not None:
            kwargs['color'] = user_colour
        visible = bool(getattr(obj.actor, 'visibility', True))

        try:
            self.add_mesh_object(mesh, name=name, **source, **kwargs)
        except Exception:
            # e.g. a scalar array selected in the properties panel that the
            # new mesh does not have; add it with the default colouring
            for key in ('scalars', 'cmap', 'clim', 'rgb'):
                kwargs.pop(key, None)
            self.add_mesh_object(mesh, name=name, **source, **kwargs)

        new_obj = self.registry.get(name)
        if user_colour is not None:
            new_obj.color = user_colour
        if not visible and new_obj.actor is not None:
            new_obj.actor.visibility = False

    def set_out_of_date(self, names, out_of_date: bool = True) -> None:
        """Mark the named objects as out of date (or up to date)."""
        changed = False
        for name in names:
            obj = self.registry.get(name)
            if obj is not None and bool(obj.out_of_date) != out_of_date:
                obj.out_of_date = out_of_date
                changed = True
        if changed:
            self.outOfDateChanged.emit()

    def out_of_date_objects(self):
        """Return the names of the objects that are out of date."""
        return self.registry.out_of_date()

    def remove_object(self, name: str) -> None:
        """Remove an object by name and clean up stored metadata.

        This ensures names can be re-used and re-adding works predictably.
        """
        obj = self.registry.get(name)
        if obj is None:
            return
        try:
            if obj.actor is not None:
                try:
                    self.remove_actor(obj.actor)
                except Exception:
                    self.remove_mesh(name)
        except Exception:
            # ignore errors during actor removal
            pass
        self.registry.remove(name)
        if obj.out_of_date:
            self.outOfDateChanged.emit()

    def set_object_visibility(self, name: str, visibility):
        """Change the visibility of an object."""
        obj = self.registry.get(name)
        if obj is None:
            raise ValueError(f"Object '{name}' not found in the plotter.")
        obj.actor.visibility = visibility
        self.update()
