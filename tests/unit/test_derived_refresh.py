"""Pytest tests for the refresh of the derived data before a build.

`loopstructural.main.derived_refresh` imports `m2l_api` only when it
calculates, so the tests put a fake `m2l_api` in `sys.modules` and run in the
fast tests/unit/ job.
"""

import sys
from types import ModuleType, SimpleNamespace

import pandas as pd
import pytest

from loopstructural.main import derived_data, layer_roles
from loopstructural.main.derived_refresh import BASAL_CONTACT_UNIT_FIELD, DerivedRefresh

UNITS = ['young', 'old']


class FakeLayer:
    def __init__(self, name):
        self._name = name

    def name(self):
        return self._name


class FakeDerived:
    def __init__(self):
        self.recorded = []

    def record(self, name, inputs):
        self.recorded.append((name, inputs))


class FakeDataManager:
    def __init__(self):
        self.layer_roles = SimpleNamespace(contacts_source=layer_roles.CONTACTS_FROM_GEOLOGY)
        self.derived = FakeDerived()
        self.old_contacts = FakeLayer('Basal contacts')
        self.roles = {
            layer_roles.GEOLOGY: FakeLayer('geology'),
            layer_roles.GEOLOGY_UNIT_FIELD: 'UNITNAME',
            layer_roles.BASAL_CONTACTS: self.old_contacts,
        }
        self.settings = {
            'basal_contacts_widget': {},
            'thickness_calculator_widget': {
                'calculator_type': 'InterpolatedStructure',
                'basal_contacts_layer': 'Basal contacts',
                'basal_unit_field': 'basal_unit',
            },
        }
        self.stratigraphy_updates = []
        self.applied = []

    def get_widget_settings(self, name, default=None):
        return self.settings.get(name, default)

    def get_layer_role(self, role):
        return self.roles.get(role)

    def find_layer_by_name(self, name):
        return self.old_contacts if name == 'Basal contacts' else FakeLayer(name)

    def basal_contacts_inputs(self):
        return {'geology': 'geology', 'unit_field': 'UNITNAME', 'unit_order': UNITS}

    def thickness_inputs(self):
        return {'contacts': 'calculated', 'unit_order': UNITS}

    def get_model_crs(self):
        return SimpleNamespace(isValid=lambda: True)

    def get_stratigraphic_unit_names(self):
        return list(UNITS)

    def get_stratigraphic_unit_colours(self):
        return {}

    def update_stratigraphy(self, basal_contacts=None, unit_name_field=None):
        self.stratigraphy_updates.append((basal_contacts, unit_name_field))

    def apply_calculated_thicknesses(self, values):
        self.applied.append(values)
        return values, []


@pytest.fixture
def contacts():
    return pd.DataFrame({BASAL_CONTACT_UNIT_FIELD: ['young'], 'X': [1.0]})


@pytest.fixture
def m2l_api(monkeypatch, contacts):
    """A fake `m2l_api` that records the calls."""
    module = ModuleType('loopstructural.main.m2l_api')
    module.calls = []

    def extract_basal_contacts(updater=None, **params):
        module.calls.append(('contacts', params))
        return {'basal_contacts': contacts}

    def calculate_thickness(updater=None, **params):
        module.calls.append(('thickness', params))
        return {'thicknesses': pd.DataFrame({'name': ['young'], 'ThicknessMedian': [10.0]})}

    module.extract_basal_contacts = extract_basal_contacts
    module.calculate_thickness = calculate_thickness
    monkeypatch.setitem(sys.modules, 'loopstructural.main.m2l_api', module)
    return module


@pytest.fixture
def dm():
    return FakeDataManager()


def _refresh(dm, names):
    refresh = DerivedRefresh(dm, None, names)
    refresh._update_contacts_layer = lambda contacts: None
    return refresh


BOTH = [derived_data.BASAL_CONTACTS, derived_data.THICKNESS]


class TestRefreshOrder:
    def test_the_inputs_are_read_from_the_data_manager(self, dm, m2l_api):
        refresh = _refresh(dm, BOTH)
        assert refresh._contacts['inputs'] == dm.basal_contacts_inputs()
        assert refresh._thickness['inputs'] == dm.thickness_inputs()

    def test_the_thickness_uses_the_new_contacts_not_the_old_layer(self, dm, m2l_api, contacts):
        _refresh(dm, BOTH).run()
        assert [name for name, _params in m2l_api.calls] == ['contacts', 'thickness']
        params = m2l_api.calls[1][1]
        assert params['basal_contacts'] is contacts
        assert params['basal_contacts'] is not dm.old_contacts
        assert params['basal_contacts_unit_name'] is None

    def test_the_thickness_alone_uses_the_contacts_layer(self, dm, m2l_api):
        _refresh(dm, [derived_data.THICKNESS]).run()
        params = m2l_api.calls[0][1]
        assert params['basal_contacts'] is dm.old_contacts
        assert params['basal_contacts_unit_name'] == 'basal_unit'


class TestThreads:
    def test_run_does_not_change_the_data_manager(self, dm, m2l_api):
        _refresh(dm, BOTH).run()
        assert dm.stratigraphy_updates == []
        assert dm.applied == []
        assert dm.derived.recorded == []

    def test_finish_puts_the_contacts_in_the_model_and_records_the_inputs(
        self, dm, m2l_api, contacts
    ):
        refresh = _refresh(dm, BOTH)
        refresh.run()
        refresh.finish()
        assert dm.stratigraphy_updates == [(contacts, BASAL_CONTACT_UNIT_FIELD)]
        assert dm.applied == [{'young': 10.0}]
        assert [name for name, _inputs in dm.derived.recorded] == BOTH
