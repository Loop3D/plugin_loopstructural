import re
from collections import defaultdict
from PyQt5.QtCore import pyqtSignal
from pyvistaqt import QtInteractor


class LoopPyVistaQTPlotter(QtInteractor):
    objectAdded = pyqtSignal(QtInteractor)  # Signal to request deletion

    def __init__(self, parent):
        super().__init__(parent=parent)
        self.objects = {}
        self.add_axes()
        self.meshes = {}
        self.mesh_actors = defaultdict(list)
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

    def add_mesh_object(self, mesh, name:str):
        """Add a mesh to the plotter."""
        if name in self.meshes:
            name = self.increment_name(name)
        
        self.meshes[name] = {'mesh':mesh}
        actor = self.add_mesh(mesh)
        self.meshes[name]['actor'] = actor
        self.objectAdded.emit(self)
        return actor

    def remove_object(self, name):
        """Remove an object by name."""
        if name in self.meshes:
            self.remove_actor(self.meshes[name]['actor'])
            self.update()
        else:
            raise ValueError(f"Object '{name}' not found in the plotter.")

    

    def change_object_visibility(self, name, visibility):
        """Change the visibility of an object."""
        if name in self.meshes:
            self.meshes[name]['actor'].visibility = visibility
            self.update()
        else:
            raise ValueError(f"Object '{name}' not found in the plotter.")
