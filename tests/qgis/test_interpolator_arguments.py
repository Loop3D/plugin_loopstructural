"""Pytest tests for the number of elements that `interpolator_arguments` gives.

The order is: the number that the user set for the feature, then the number
from the data (with the setting "automatic"), then the fixed number.
"""

import json

import pandas as pd
import pytest
from LoopStructural.datatypes import BoundingBox

from loopstructural.main import model_manager as model_manager_module
from loopstructural.main.interpolation_size import suggest_nelements, summarise_data
from loopstructural.main.model_manager import GeologicalModelManager
from loopstructural.toolbelt.preferences import PlgSettingsStructure

DATA = pd.DataFrame(
    {
        'X': [10.0, 50.0, 90.0],
        'Y': [10.0, 50.0, 90.0],
        'Z': [0.0, 0.0, 0.0],
        'val': [0.0, 0.0, 1.0],
    }
)


class _DebugManager:
    def log(self, *args, **kwargs):
        pass


def _use_settings(monkeypatch, **values):
    settings = PlgSettingsStructure(**values)
    monkeypatch.setattr(
        model_manager_module.PlgOptionsManager, 'get_plg_settings', staticmethod(lambda: settings)
    )


@pytest.fixture
def manager():
    manager = GeologicalModelManager(debug_manager=_DebugManager())
    manager.update_bounding_box(BoundingBox(origin=[0, 0, -50], maximum=[100, 100, 50]))
    return manager


def test_the_number_of_the_user_comes_first(manager, monkeypatch):
    _use_settings(monkeypatch, interpolator_nelements_auto=True, interpolator_nelements=7000)
    manager.set_nelements_override('s1', 12345)
    assert manager.interpolator_arguments('s1', DATA)['nelements'] == 12345
    assert manager.nelements_used['s1'] == (12345, False)


def test_automatic_uses_the_data(manager, monkeypatch):
    _use_settings(monkeypatch, interpolator_nelements_auto=True, interpolator_nelements=7000)
    expected = suggest_nelements(summarise_data(DATA), 100.0 * 100.0)
    assert manager.interpolator_arguments('s1', DATA)['nelements'] == expected
    assert manager.nelements_used['s1'] == (expected, True)


def test_the_fixed_number_without_automatic(manager, monkeypatch):
    _use_settings(monkeypatch, interpolator_nelements_auto=False, interpolator_nelements=7000)
    assert manager.interpolator_arguments('s1', DATA)['nelements'] == 7000
    assert manager.nelements_used['s1'] == (7000, False)


def test_the_default_is_not_the_number_of_the_user(manager, monkeypatch):
    _use_settings(monkeypatch, interpolator_nelements_auto=True, interpolator_nelements=7000)
    manager.set_nelements_override('s1', 12345)
    manager.interpolator_arguments('s1', DATA)
    expected = suggest_nelements(summarise_data(DATA), 100.0 * 100.0)
    assert manager.default_nelements('s1') == (expected, True)


def test_the_overrides_are_saved_and_loaded(manager):
    manager.set_nelements_override('s1', 12345)
    manager.set_nelements_override('f1', 6000)
    saved = json.loads(json.dumps(manager.nelements_overrides_to_dict()))

    other = GeologicalModelManager(debug_manager=_DebugManager())
    other.nelements_overrides_from_dict(saved)
    assert other.nelements_overrides == {'s1': 12345, 'f1': 6000}
    other.set_nelements_override('s1', None)
    assert other.nelements_overrides == {'f1': 6000}
