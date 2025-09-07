import re
from collections import defaultdict
from PyQt5.QtCore import pyqtSignal
from pyvistaqt import QtInteractor
from typing import Optional, Any, Dict, Tuple
import pyvista as pv


class LoopPyVistaQTPlotter(QtInteractor):
    objectAdded = pyqtSignal(QtInteractor)  # Signal to request deletion

    def __init__(self, parent):
        super().__init__(parent=parent)
        self.objects = {}
        self.add_axes()
        # maps name -> dict(mesh=..., actor=..., kwargs={...})
        self.meshes = {}
        # maintain an internal pyvista plotter

    def increment_name(self, name):
        parts = name.split('_')
        if len(parts) == 1:
            name = name + '_1'
        while name in self.actors:
            parts = name.split('_')
            try:
                parts[-1] = str(int(parts[-1]) + 1)
            except ValueError:
                parts.append('1')
            name = '_'.join(parts)
        return name

    def add_mesh_object(self, mesh, name: str, *, scalars: Optional[Any] = None, cmap: Optional[str] = None, clim: Optional[Tuple[float, float]] = None, opacity: Optional[float] = None, show_scalar_bar: bool = False, color: Optional[Tuple[float, float, float]] = None, **kwargs) -> None:
        """Add a mesh to the plotter.

        This wrapper stores metadata to allow robust re-adding and
        updating of visualization parameters.

        :param mesh: a pyvista mesh-like object
        :param name: unique name for the mesh
        :param scalars: name of scalar array or scalar values to map
        :param cmap: colormap name
        :param clim: tuple (min, max) for colormap
        :param opacity: float 0-1 for surface opacity
        :param show_scalar_bar: whether to show scalar bar
        :param color: tuple of 3 floats (r,g,b) in 0..1 for solid color; if provided, overrides scalars
        """
        # Remove any previous entry with the same name (to keep metadata consistent)
        # if name in self.meshes:
        #     try:
                
        #         self.remove_object(name)
        #     except Exception:
        #         # ignore removal errors and proceed to add
        #         pass

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

        # attempt to add to the underlying pyvista plotter
        actor = self.add_mesh(mesh, name=name, **add_kwargs)

        # store the mesh, actor and kwargs for future re-adds
        self.meshes[name] = {'mesh': mesh, 'actor': actor, 'kwargs': {**add_kwargs}}
        self.objectAdded.emit(self)

    def remove_object(self, name: str) -> None:
        """Remove an object by name and clean up stored metadata.

        This ensures names can be re-used and re-adding works predictably.
        """
        if name not in self.meshes:
            return
        entry = self.meshes[name]
        actor = entry.get('actor', None)
        try:
            if actor is not None:
                # pyvista.Plotter has remove_actor or remove_mesh depending on version
                if hasattr(self, 'remove_actor'):
                    try:
                        self.remove_actor(actor)
                    except Exception:
                        # fallback to remove_mesh by name
                        if hasattr(self, 'remove_mesh'):
                            self.remove_mesh(name)
                elif hasattr(self, 'remove_mesh'):
                    self.remove_mesh(name)
        except Exception:
            # ignore errors during actor removal
            pass
        # finally delete metadata
        try:
            del self.meshes[name]
        except Exception:
            pass

    def set_object_visibility(self, name: str, visibility):
        """Change the visibility of an object."""
        if name in self.meshes:
            self.meshes[name]['actor'].visibility = visibility
            self.update()
        else:
            raise ValueError(f"Object '{name}' not found in the plotter.")
