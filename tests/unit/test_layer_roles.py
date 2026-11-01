"""Pytest tests for the shared layer roles.

The layer roles do not import QGIS, so these tests use a fake layer and run
in the fast tests/unit/ job.
"""

import pytest

from loopstructural.main.layer_roles import (
    BASAL_CONTACTS,
    CONTACTS_FROM_GEOLOGY,
    CONTACTS_FROM_LAYER,
    GEOLOGY,
    GEOLOGY_UNIT_FIELD,
    LayerRoles,
)


class FakeLayer:
    def __init__(self, name, layer_id=None):
        self._name = name
        self._id = layer_id or f'{name}_id'
        self.deleted = False

    def name(self):
        if self.deleted:
            raise RuntimeError('wrapped C/C++ object has been deleted')
        return self._name

    def id(self):
        return self._id


@pytest.fixture
def project():
    return {
        'geology': FakeLayer('geology'),
        'contacts': FakeLayer('contacts'),
    }


@pytest.fixture
def roles(project):
    return LayerRoles(layer_resolver=project.get)


class TestStorage:
    def test_a_role_has_no_value_at_the_start(self, roles):
        assert roles.get(GEOLOGY) is None
        assert roles.get(GEOLOGY_UNIT_FIELD) is None

    def test_set_and_get_a_layer(self, roles, project):
        roles.set(GEOLOGY, project['geology'])
        assert roles.get(GEOLOGY) is project['geology']

    def test_set_and_get_a_field(self, roles):
        roles.set(GEOLOGY_UNIT_FIELD, 'UNITNAME')
        assert roles.get(GEOLOGY_UNIT_FIELD) == 'UNITNAME'

    def test_an_unknown_role_is_an_error(self, roles):
        with pytest.raises(ValueError):
            roles.set('not_a_role', None)
        with pytest.raises(ValueError):
            roles.get('not_a_role')

    def test_setting_none_clears_a_role(self, roles, project):
        roles.set(GEOLOGY, project['geology'])
        roles.set(GEOLOGY, None)
        assert roles.get(GEOLOGY) is None

    def test_a_deleted_layer_gives_none(self, roles, project):
        roles.set(GEOLOGY, project['geology'])
        project['geology'].deleted = True
        assert roles.get(GEOLOGY) is None

    def test_the_contacts_source_starts_with_the_geology(self, roles):
        assert roles.contacts_source == CONTACTS_FROM_GEOLOGY

    def test_an_unknown_contacts_source_is_an_error(self, roles):
        with pytest.raises(ValueError):
            roles.contacts_source = 'somewhere'


class TestChangeEvent:
    def test_a_change_calls_the_callback(self, roles, project):
        events = []
        roles.attach(lambda role, value: events.append((role, value)))
        roles.set(GEOLOGY, project['geology'])
        assert events == [(GEOLOGY, project['geology'])]

    def test_the_same_value_gives_no_event(self, roles, project):
        events = []
        roles.set(GEOLOGY, project['geology'])
        roles.attach(lambda role, value: events.append(role))
        assert roles.set(GEOLOGY, project['geology']) is False
        roles.set(GEOLOGY_UNIT_FIELD, 'UNITNAME')
        roles.set(GEOLOGY_UNIT_FIELD, 'UNITNAME')
        assert events == [GEOLOGY_UNIT_FIELD]

    def test_two_wrappers_of_one_layer_are_the_same_value(self, roles):
        events = []
        roles.set(GEOLOGY, FakeLayer('geology', layer_id='same'))
        roles.attach(lambda role, value: events.append(role))
        assert roles.set(GEOLOGY, FakeLayer('geology', layer_id='same')) is False
        assert events == []

    def test_a_change_of_the_contacts_source_gives_an_event(self, roles):
        events = []
        roles.attach(lambda role, value: events.append((role, value)))
        roles.contacts_source = CONTACTS_FROM_LAYER
        roles.contacts_source = CONTACTS_FROM_LAYER
        assert events == [('contacts_source', CONTACTS_FROM_LAYER)]

    def test_a_detached_callback_is_not_called(self, roles, project):
        events = []

        def callback(role, value):
            events.append(role)

        roles.attach(callback)
        roles.detach(callback)
        roles.set(GEOLOGY, project['geology'])
        assert events == []


class TestSaveAndLoad:
    def test_round_trip(self, roles, project):
        roles.set(GEOLOGY, project['geology'])
        roles.set(GEOLOGY_UNIT_FIELD, 'UNITNAME')
        roles.set(BASAL_CONTACTS, project['contacts'])
        roles.contacts_source = CONTACTS_FROM_LAYER
        data = roles.to_dict()
        assert data['geology'] == 'geology'
        assert data['basal_contacts'] == 'contacts'

        loaded = LayerRoles(layer_resolver=project.get)
        loaded.from_dict(data)
        assert loaded.get(GEOLOGY) is project['geology']
        assert loaded.get(GEOLOGY_UNIT_FIELD) == 'UNITNAME'
        assert loaded.get(BASAL_CONTACTS) is project['contacts']
        assert loaded.contacts_source == CONTACTS_FROM_LAYER

    def test_the_saved_data_is_json(self, roles, project):
        import json

        roles.set(GEOLOGY, project['geology'])
        assert json.loads(json.dumps(roles.to_dict())) == roles.to_dict()

    def test_a_layer_that_is_not_in_the_project_gives_an_empty_role(self, roles):
        roles.from_dict({'geology': 'removed'})
        assert roles.get(GEOLOGY) is None

    def test_an_old_state_file_does_not_change_the_roles(self, roles, project):
        roles.set(GEOLOGY, project['geology'])
        roles.from_dict({})
        roles.from_dict(None)
        assert roles.get(GEOLOGY) is project['geology']
        assert roles.contacts_source == CONTACTS_FROM_GEOLOGY

    def test_a_bad_contacts_source_gives_the_default(self, roles):
        roles.contacts_source = CONTACTS_FROM_LAYER
        roles.from_dict({'contacts_source': 'somewhere'})
        assert roles.contacts_source == CONTACTS_FROM_GEOLOGY

    def test_clear(self, roles, project):
        roles.set(GEOLOGY, project['geology'])
        roles.contacts_source = CONTACTS_FROM_LAYER
        roles.clear()
        assert roles.get(GEOLOGY) is None
        assert roles.contacts_source == CONTACTS_FROM_GEOLOGY
