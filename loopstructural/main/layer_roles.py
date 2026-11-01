"""Shared layer roles.

A layer role is a name for the job that a layer has in the model, for example
the geology polygons. The user selects a layer for a role one time. Each tool
reads the role as its default value.

This module does not import QGIS. A layer is any object with a ``name()``
method, so the code can run in the unit tests.
"""

from typing import Callable, Optional

GEOLOGY = 'geology'
GEOLOGY_UNIT_FIELD = 'geology_unit_field'
FAULT_TRACES = 'fault_traces'
STRUCTURE = 'structure'
BASAL_CONTACTS = 'basal_contacts'
DEM = 'dem'

# Roles that hold a layer.
LAYER_ROLES = (GEOLOGY, FAULT_TRACES, STRUCTURE, BASAL_CONTACTS, DEM)
# Roles that hold a field name.
FIELD_ROLES = (GEOLOGY_UNIT_FIELD,)
ALL_ROLES = LAYER_ROLES + FIELD_ROLES

# Where the basal contacts come from.
CONTACTS_FROM_GEOLOGY = 'geology'
CONTACTS_FROM_LAYER = 'layer'
CONTACTS_SOURCES = (CONTACTS_FROM_GEOLOGY, CONTACTS_FROM_LAYER)


def _layer_name(layer):
    """Return the name of a layer, or None if the layer is gone."""
    if layer is None:
        return None
    try:
        return layer.name()
    except RuntimeError:
        # the C++ layer was deleted
        return None


class LayerRoles:
    """Store the layer and the field that each role has.

    Parameters
    ----------
    layer_resolver : callable, optional
        Function that gives a layer for a layer name. `from_dict` uses it.
    """

    def __init__(self, layer_resolver: Optional[Callable] = None):
        self._layer_resolver = layer_resolver
        self._values = {}
        self._callbacks = []
        self._contacts_source = CONTACTS_FROM_GEOLOGY

    def attach(self, callback: Callable):
        """Call ``callback(role, value)`` each time a role changes."""
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def detach(self, callback: Callable):
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def _notify(self, role, value):
        for callback in list(self._callbacks):
            callback(role, value)

    @staticmethod
    def _check_role(role):
        if role not in ALL_ROLES:
            raise ValueError(f"Unknown layer role '{role}'. Use one of {ALL_ROLES}.")

    @staticmethod
    def _same(old, new):
        """True if two role values are the same layer or the same field."""
        if old is new:
            return True
        if old is None or new is None:
            return False
        if isinstance(old, str) or isinstance(new, str):
            return old == new
        # two wrappers can point to one layer: compare the layer ids
        try:
            return old.id() == new.id()
        except (AttributeError, RuntimeError):
            return False

    def get(self, role):
        """Return the value of a role, or None if it is not set.

        A layer that was removed from the project gives None.
        """
        self._check_role(role)
        value = self._values.get(role)
        if value is not None and role in LAYER_ROLES and _layer_name(value) is None:
            return None
        return value

    def set(self, role, value):
        """Set the value of a role.

        Returns True if the value changed. The callbacks run only for a
        change, so a widget can write the role that it just read.
        """
        self._check_role(role)
        old = self._values.get(role)
        if self._same(old, value):
            return False
        if value is None:
            self._values.pop(role, None)
        else:
            self._values[role] = value
        self._notify(role, value)
        return True

    def clear(self):
        """Remove all roles and set the contacts source to its default."""
        for role in list(self._values):
            self.set(role, None)
        self.contacts_source = CONTACTS_FROM_GEOLOGY

    @property
    def contacts_source(self):
        return self._contacts_source

    @contacts_source.setter
    def contacts_source(self, source):
        if source not in CONTACTS_SOURCES:
            raise ValueError(f"Unknown contacts source '{source}'. Use one of {CONTACTS_SOURCES}.")
        if source != self._contacts_source:
            self._contacts_source = source
            self._notify('contacts_source', source)

    def to_dict(self):
        """Return the roles as a dictionary that is safe for JSON.

        A layer is saved by its name, like the other layers in the state.
        """
        data = {'contacts_source': self._contacts_source}
        for role in LAYER_ROLES:
            data[role] = _layer_name(self._values.get(role))
        for role in FIELD_ROLES:
            data[role] = self._values.get(role)
        return data

    def from_dict(self, data):
        """Set the roles from the output of `to_dict`.

        A key that is not in ``data`` does not change its role, so a state
        file from an older version of the plugin loads without errors. A
        layer that is not in the project gives an empty role.
        """
        data = data or {}
        if 'contacts_source' in data:
            source = data['contacts_source']
            self.contacts_source = source if source in CONTACTS_SOURCES else CONTACTS_FROM_GEOLOGY
        for role in LAYER_ROLES:
            if role not in data:
                continue
            name = data[role]
            layer = None
            if name is not None and self._layer_resolver is not None:
                layer = self._layer_resolver(name)
            self.set(role, layer)
        for role in FIELD_ROLES:
            if role in data:
                self.set(role, data[role])
