"""Records of the inputs of derived data.

Some data is calculated from other inputs. For example, the basal contacts
come from the geology layer and the order of the stratigraphic column. When an
input changes, the result is out of date.

For each result, this module keeps a hash of the inputs of the last run. The
status is "current" when the hash of the inputs now is the same as the
recorded hash. A change and its undo (for example, two reorders) give the same
hash, so the result stays current.

This module does not import QGIS, so the unit tests can run it.
"""

import hashlib
import json
import math
from typing import Callable, Optional

BASAL_CONTACTS = 'basal_contacts'
THICKNESS = 'thickness'
STYLED_FIELDS = 'styled_fields'

NOT_RUN = 'not_run'
CURRENT = 'current'
OUT_OF_DATE = 'out_of_date'

TYPED = 'typed'
CALCULATED = 'calculated'

# Short names for the user interface.
DESCRIPTIONS = {
    BASAL_CONTACTS: 'Basal contacts',
    THICKNESS: 'Calculated thicknesses',
    STYLED_FIELDS: 'Styled map layer fields',
}


def normalise_inputs(inputs):
    """Return the inputs as plain JSON data (the same data as after a save and load)."""
    return json.loads(json.dumps(inputs, sort_keys=True, default=str))


def hash_inputs(inputs) -> str:
    """Return a stable hash of the inputs of a calculation.

    ``inputs`` can have dictionaries, lists, strings, numbers and None. The
    order of the keys of a dictionary does not change the hash. The order of a
    list does change it.
    """
    text = json.dumps(inputs, sort_keys=True, default=str, separators=(',', ':'))
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


class DerivedData:
    """Keep the inputs of each derived result and tell when it is out of date.

    A result has a name and an input provider. The provider is a function
    that gives the inputs now. `record` stores the hash of the inputs of a
    run. `status` compares the stored hash with the hash of the inputs now.
    """

    def __init__(self):
        self._providers = {}
        self._records = {}
        self._last_status = {}
        self._callbacks = []

    def register(self, name: str, provider: Callable[[], object]):
        """Register the function that gives the current inputs of a result."""
        self._providers[name] = provider
        self._last_status[name] = self.status(name)

    @property
    def names(self):
        return list(self._providers)

    def attach(self, callback: Callable[[str, str], None]):
        """Call ``callback(name, status)`` each time a status changes."""
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def detach(self, callback):
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def current_hash(self, name: str) -> Optional[str]:
        """Return the hash of the inputs now, or None if no provider exists."""
        provider = self._providers.get(name)
        if provider is None:
            return None
        return hash_inputs(provider())

    def record(self, name: str, inputs=None, detail=None):
        """Record that the result was calculated from ``inputs``.

        Parameters
        ----------
        name : str
            Name of the derived result.
        inputs : optional
            The inputs of the run. Use the inputs that the run read, so that a
            change during the run marks the result as out of date. If this is
            None, the inputs now are used.
        detail : dict, optional
            Extra information for the user interface, for example the name of
            the layer that was styled. It must be safe for JSON.
        """
        if inputs is None:
            provider = self._providers.get(name)
            inputs = provider() if provider is not None else None
        # The hash decides if the result is out of date. The inputs are
        # kept only to tell the user what changed.
        self._records[name] = {
            'hash': hash_inputs(inputs),
            'inputs': normalise_inputs(inputs),
            'detail': dict(detail or {}),
        }
        self.refresh()

    def forget(self, name: str):
        """Remove the record of a result. Its status is then "not run"."""
        if self._records.pop(name, None) is not None:
            self.refresh()

    def detail(self, name: str) -> dict:
        record = self._records.get(name)
        return dict(record['detail']) if record else {}

    def changed_inputs(self, name: str):
        """Return the keys of the inputs that are not the same as in the last run.

        The list is empty when the result is current, was never calculated,
        or has no kept inputs (for example, from an older state file).
        """
        record = self._records.get(name)
        provider = self._providers.get(name)
        if record is None or provider is None or not isinstance(record.get('inputs'), dict):
            return []
        old = record['inputs']
        new = normalise_inputs(provider())
        if not isinstance(new, dict):
            return []
        return sorted(key for key in set(old) | set(new) if old.get(key) != new.get(key))

    def status(self, name: str) -> str:
        record = self._records.get(name)
        if record is None:
            return NOT_RUN
        if record['hash'] == self.current_hash(name):
            return CURRENT
        return OUT_OF_DATE

    def is_out_of_date(self, name: str) -> bool:
        return self.status(name) == OUT_OF_DATE

    def out_of_date(self):
        """Return the names of all results that are out of date."""
        return [name for name in self._providers if self.is_out_of_date(name)]

    def refresh(self):
        """Compare the hashes again and send an event for each status change."""
        for name in self._providers:
            status = self.status(name)
            if status != self._last_status.get(name):
                self._last_status[name] = status
                for callback in list(self._callbacks):
                    callback(name, status)

    def clear(self):
        """Remove all records."""
        self._records.clear()
        self.refresh()

    def to_dict(self):
        return {name: dict(record) for name, record in self._records.items()}

    def from_dict(self, data):
        """Restore the records. Do not send events for the restored records."""
        self._records = {}
        for name, record in (data or {}).items():
            if isinstance(record, dict) and isinstance(record.get('hash'), str):
                self._records[name] = {
                    'hash': record['hash'],
                    'inputs': record.get('inputs'),
                    'detail': dict(record.get('detail') or {}),
                }
        self.refresh()


def thickness_is_set(value) -> bool:
    """Return True if a unit thickness is a usable number above zero."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(value) and value > 0


class ThicknessSources:
    """Record if the thickness of each unit was typed or calculated.

    A calculated thickness must not replace a typed one. The key is the uuid
    of the unit.
    """

    def __init__(self):
        self._sources = {}

    def get(self, uuid) -> Optional[str]:
        return self._sources.get(uuid)

    def set(self, uuid, source: str):
        if source not in (TYPED, CALCULATED):
            raise ValueError(f"Unknown thickness source '{source}'.")
        self._sources[uuid] = source

    def discard(self, uuid):
        self._sources.pop(uuid, None)

    def clear(self):
        self._sources.clear()

    def can_overwrite(self, uuid, current_thickness) -> bool:
        """Return True if a calculated thickness can replace the thickness.

        A thickness with no value can always be replaced. A calculated one can
        be replaced. A typed one cannot. A value with no source, for example
        from a state file of an older version, is treated as typed, because
        the plugin cannot know who made it.
        """
        if not thickness_is_set(current_thickness):
            return True
        return self._sources.get(uuid) == CALCULATED

    def to_dict(self):
        return dict(self._sources)

    def from_dict(self, data):
        self._sources = {
            uuid: source for uuid, source in (data or {}).items() if source in (TYPED, CALCULATED)
        }
