import re

from PyQt5.QtCore import pyqtSignal
from pyvistaqt import QtInteractor


class LoopPyVistaQTPlotter(QtInteractor):
    objectAdded = pyqtSignal(QtInteractor)  # Signal to request deletion

    def __init__(self, parent):
        super().__init__(parent=parent)
        self.objects = {}

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

    def add_mesh(self, *args, **kwargs):
        """Add a mesh to the plotter."""
        if 'name' not in kwargs or not kwargs['name']:
            name = 'unnnamed_object'
            kwargs['name'] = name
        kwargs['name'] = kwargs['name'].replace(' ', '_')
        kwargs['name'] = re.sub(r'[^a-zA-Z0-9_$]', '_', kwargs['name'])
        if kwargs['name'][0].isdigit():
            kwargs['name'] = 'ls_' + kwargs['name']
        if kwargs['name'][0] == '_':
            kwargs['name'] = 'ls' + kwargs['name']
        kwargs['name'] = self.increment_name(kwargs['name'])
        if '__opacity' in kwargs['name']:
            raise ValueError('Cannot use __opacity in name')
        if '__visibility' in kwargs['name']:
            raise ValueError('Cannot use __visibility in name')
        if '__control_visibility' in kwargs['name']:
            raise ValueError('Cannot use __control_visibility in name')
        actor = super().add_mesh(*args, **kwargs)
        self.objects[kwargs['name']] = args[0]
        self.objectAdded.emit(self)
        return actor

    def remove_object(self, name):
        """Remove an object by name."""
        if name in self.actors:
            self.remove_actor(self.actors[name])
            self.update()
        else:
            raise ValueError(f"Object '{name}' not found in the plotter.")

    def change_object_name(self, old_name, new_name):
        """Change the name of an object."""
        if old_name in self.actors:
            if new_name in self.objects:
                raise ValueError(f"Object '{new_name}' already exists.")
            self.actors[new_name] = self.actors.pop(old_name)
            self.actors[new_name].name = new_name
        else:
            raise ValueError(f"Object '{old_name}' not found in the plotter.")

    def change_object_visibility(self, name, visibility):
        """Change the visibility of an object."""
        if name in self.actors:
            self.actors[name].visibility = visibility
            self.actors[name].actor.visibility = visibility
            self.update()
        else:
            raise ValueError(f"Object '{name}' not found in the plotter.")
