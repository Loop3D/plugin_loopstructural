"""Pytest tests for the shared layer roles and the derived-data records in
`ModellingDataManager`.

The basal contacts and the thicknesses are calculated from the column and
the layers. When one of these inputs changes, the result is out of date.
"""

import json
from unittest.mock import Mock

import pytest
from qgis.core import QgsProject, QgsVectorLayer

from loopstructural.main import derived_data, layer_roles
from loopstructural.main.data_manager import ModellingDataManager
from loopstructural.main.model_manager import GeologicalModelManager


class _DebugManager:
    def log(self, *args, **kwargs):
        pass


def _layer(name, geometry='Polygon', fields='field=UNITNAME:string'):
    layer = QgsVectorLayer(f'{geometry}?crs=EPSG:32755&{fields}', name, 'memory')
    assert layer.isValid()
    QgsProject.instance().addMapLayer(layer)
    return layer


@pytest.fixture
def project():
    yield QgsProject.instance()
    QgsProject.instance().removeAllMapLayers()


@pytest.fixture
def data_manager(project):
    data_manager = ModellingDataManager(project=project, mapCanvas=Mock(), logger=Mock())
    data_manager.set_model_manager(GeologicalModelManager(debug_manager=_DebugManager()))
    column = data_manager.get_stratigraphic_column()
    column.clear(basement=False)
    for name in ('oldest', 'middle', 'youngest'):
        column.add_unit(name=name, colour='#ff0000', where='top')
    return data_manager


@pytest.fixture
def geology(project):
    return _layer('geology')


def _unit(data_manager, name):
    return data_manager.get_stratigraphic_column().get_unit_by_name(name=name)


def _reorder(data_manager, names_oldest_first):
    column = data_manager.get_stratigraphic_column()
    uuids = [column.get_unit_by_name(name=name).uuid for name in names_oldest_first]
    data_manager.update_stratigraphic_column_order(uuids)


class TestLayerRoles:
    def test_the_load_data_widgets_write_the_roles(self, data_manager, project):
        faults = _layer('faults', 'LineString')
        structure = _layer('structure', 'Point')
        contacts = _layer('contacts', 'LineString')
        data_manager.set_fault_trace_layer(faults, fault_name_field='UNITNAME')
        data_manager.set_structural_orientations(structure)
        data_manager.set_basal_contacts(contacts, unitname_field='UNITNAME')
        roles = data_manager.layer_roles
        assert roles.get(layer_roles.FAULT_TRACES) is faults
        assert roles.get(layer_roles.STRUCTURE) is structure
        assert roles.get(layer_roles.BASAL_CONTACTS) is contacts

    def test_a_role_change_sends_an_event(self, data_manager, geology):
        events = []
        data_manager.layer_roles.attach(lambda role, value: events.append(role))
        data_manager.layer_roles.set(layer_roles.GEOLOGY, geology)
        assert events == [layer_roles.GEOLOGY]

    def test_the_roles_are_saved_and_loaded(self, data_manager, geology, project):
        data_manager.layer_roles.set(layer_roles.GEOLOGY, geology)
        data_manager.layer_roles.set(layer_roles.GEOLOGY_UNIT_FIELD, 'UNITNAME')
        data_manager.layer_roles.contacts_source = layer_roles.CONTACTS_FROM_LAYER
        state = json.loads(json.dumps(data_manager.to_dict()))

        other = ModellingDataManager(project=project, mapCanvas=Mock(), logger=Mock())
        other.set_model_manager(GeologicalModelManager(debug_manager=_DebugManager()))
        other.update_from_dict(state)
        assert other.layer_roles.get(layer_roles.GEOLOGY) is geology
        assert other.layer_roles.get(layer_roles.GEOLOGY_UNIT_FIELD) == 'UNITNAME'
        assert other.layer_roles.contacts_source == layer_roles.CONTACTS_FROM_LAYER

    def test_an_old_state_file_loads_with_default_roles(self, data_manager, geology):
        data_manager.layer_roles.set(layer_roles.GEOLOGY, geology)
        state = data_manager.to_dict()
        for key in ('layer_roles', 'derived_data', 'thickness_sources'):
            state.pop(key)
        data_manager.update_from_dict(state)
        assert data_manager.layer_roles.get(layer_roles.GEOLOGY) is None
        assert data_manager.layer_roles.contacts_source == layer_roles.CONTACTS_FROM_GEOLOGY
        assert data_manager.derived.out_of_date() == []

    def test_a_tool_gives_the_geology_role_a_layer_that_has_none(self, data_manager, geology):
        other = _layer('other')
        data_manager.adopt_layer_roles(geology=geology)
        data_manager.adopt_layer_roles(geology=other)
        assert data_manager.layer_roles.get(layer_roles.GEOLOGY) is geology

    def test_reset_clears_the_roles(self, data_manager, geology):
        data_manager.layer_roles.set(layer_roles.GEOLOGY, geology)
        data_manager.reset()
        assert data_manager.layer_roles.get(layer_roles.GEOLOGY) is None


class TestDerivedData:
    @pytest.fixture
    def with_contacts(self, data_manager, geology):
        data_manager.layer_roles.set(layer_roles.GEOLOGY, geology)
        data_manager.layer_roles.set(layer_roles.GEOLOGY_UNIT_FIELD, 'UNITNAME')
        data_manager.derived.record(derived_data.BASAL_CONTACTS)
        data_manager.derived.record(derived_data.THICKNESS)
        return data_manager

    def test_a_result_that_did_not_run_is_not_out_of_date(self, data_manager):
        assert data_manager.get_derived_status(derived_data.BASAL_CONTACTS) == derived_data.NOT_RUN
        assert data_manager.derived.out_of_date() == []

    def test_a_reorder_marks_the_contacts_and_thicknesses_out_of_date(self, with_contacts):
        _reorder(with_contacts, ['middle', 'oldest', 'youngest'])
        assert with_contacts.derived.out_of_date() == [
            derived_data.BASAL_CONTACTS,
            derived_data.THICKNESS,
        ]
        assert with_contacts.derived.changed_inputs(derived_data.BASAL_CONTACTS) == ['unit_order']

    def test_a_move_and_the_move_back_keep_the_contacts_current(self, with_contacts):
        _reorder(with_contacts, ['middle', 'oldest', 'youngest'])
        assert with_contacts.derived.is_out_of_date(derived_data.BASAL_CONTACTS)
        _reorder(with_contacts, ['oldest', 'middle', 'youngest'])
        assert with_contacts.derived.out_of_date() == []

    def test_the_status_event_is_sent_through_the_column_callback(self, with_contacts):
        events = []
        with_contacts.derived.attach(lambda name, status: events.append((name, status)))
        _reorder(with_contacts, ['middle', 'oldest', 'youngest'])
        assert (derived_data.BASAL_CONTACTS, derived_data.OUT_OF_DATE) in events

    def test_a_unit_colour_does_not_mark_the_contacts_out_of_date(self, with_contacts):
        unit = _unit(with_contacts, 'middle')
        with_contacts.get_stratigraphic_column().update_element(
            {'uuid': unit.uuid, 'name': 'middle', 'colour': '#00ff00'}
        )
        with_contacts.stratigraphic_column_callback()
        assert with_contacts.derived.out_of_date() == []

    def test_a_new_unconformity_does_not_mark_the_contacts_out_of_date(self, with_contacts):
        with_contacts.add_to_stratigraphic_column({'type': 'unconformity', 'name': 'u'})
        assert with_contacts.derived.out_of_date() == []

    def test_a_change_of_the_geology_role_marks_the_contacts_out_of_date(self, with_contacts):
        with_contacts.layer_roles.set(layer_roles.GEOLOGY, _layer('geology 2'))
        assert with_contacts.derived.is_out_of_date(derived_data.BASAL_CONTACTS)
        assert with_contacts.derived.is_out_of_date(derived_data.THICKNESS)

    def test_a_change_of_the_unit_field_marks_the_contacts_out_of_date(self, with_contacts):
        with_contacts.layer_roles.set(layer_roles.GEOLOGY_UNIT_FIELD, 'other')
        assert with_contacts.derived.is_out_of_date(derived_data.BASAL_CONTACTS)

    def test_a_change_of_a_tool_setting_marks_the_contacts_out_of_date(self, with_contacts):
        with_contacts.set_widget_settings(
            'basal_contacts_widget', {'ignore_units': ['middle'], 'basal_override_units': []}
        )
        assert with_contacts.derived.is_out_of_date(derived_data.BASAL_CONTACTS)
        # the thickness uses the contacts, so it is out of date too
        assert with_contacts.derived.is_out_of_date(derived_data.THICKNESS)

    def test_a_change_of_the_thickness_settings_marks_only_the_thickness(self, with_contacts):
        with_contacts.set_widget_settings(
            'thickness_calculator_widget', {'calculator_type': 'StructuralPoint'}
        )
        assert with_contacts.derived.out_of_date() == [derived_data.THICKNESS]

    def test_the_inputs_of_the_run_are_recorded(self, data_manager, geology):
        data_manager.layer_roles.set(layer_roles.GEOLOGY, geology)
        # a tool gives its own inputs for the run
        inputs = data_manager.basal_contacts_inputs(geology=geology, unit_field='UNITNAME')
        data_manager.layer_roles.set(layer_roles.GEOLOGY_UNIT_FIELD, 'UNITNAME')
        data_manager.derived.record(derived_data.BASAL_CONTACTS, inputs=inputs)
        assert data_manager.derived.status(derived_data.BASAL_CONTACTS) == derived_data.CURRENT

    def test_styled_fields_follow_the_order_and_the_thickness(self, data_manager):
        data_manager.derived.record(derived_data.STYLED_FIELDS)
        _unit(data_manager, 'middle').thickness = 12.0
        data_manager.stratigraphic_column_callback()
        assert data_manager.derived.is_out_of_date(derived_data.STYLED_FIELDS)

    def test_the_records_are_saved_and_loaded(self, with_contacts, project):
        state = json.loads(json.dumps(with_contacts.to_dict()))
        _reorder(with_contacts, ['middle', 'oldest', 'youngest'])
        with_contacts.update_from_dict(state)
        # the saved column has the first order again
        assert with_contacts.derived.out_of_date() == []
        assert with_contacts.derived.status(derived_data.BASAL_CONTACTS) == derived_data.CURRENT

    def test_the_contacts_source_changes_the_inputs_of_the_thickness(self, with_contacts):
        contacts = _layer('contacts', 'LineString')
        with_contacts.set_basal_contacts(contacts, unitname_field='UNITNAME')
        with_contacts.derived.record(derived_data.THICKNESS)
        with_contacts.layer_roles.contacts_source = layer_roles.CONTACTS_FROM_LAYER
        assert with_contacts.derived.is_out_of_date(derived_data.THICKNESS)


class TestThicknessSource:
    def test_a_typed_thickness_is_not_overwritten(self, data_manager):
        unit = _unit(data_manager, 'middle')
        data_manager.note_thickness_edit({'uuid': unit.uuid, 'thickness': 40.0})
        unit.thickness = 40.0
        assert data_manager.get_thickness_source(unit.uuid) == derived_data.TYPED
        applied, skipped = data_manager.apply_calculated_thicknesses({'middle': 99.0})
        assert applied == []
        assert skipped == ['middle']
        assert unit.thickness == 40.0

    def test_a_calculated_thickness_is_set_and_can_be_calculated_again(self, data_manager):
        unit = _unit(data_manager, 'middle')
        applied, skipped = data_manager.apply_calculated_thicknesses({'middle': 25.0})
        assert applied == ['middle']
        assert unit.thickness == 25.0
        assert data_manager.get_thickness_source(unit.uuid) == derived_data.CALCULATED
        data_manager.apply_calculated_thicknesses({'middle': 30.0})
        assert unit.thickness == 30.0

    def test_a_value_that_is_not_calculated_is_ignored(self, data_manager):
        applied, skipped = data_manager.apply_calculated_thicknesses(
            {'middle': -1, 'oldest': float('nan'), 'unknown unit': 5.0}
        )
        assert applied == [] and skipped == []

    def test_a_row_that_sends_the_calculated_value_back_is_not_a_typed_value(self, data_manager):
        unit = _unit(data_manager, 'middle')
        data_manager.apply_calculated_thicknesses({'middle': 25.4567})
        # the row shows two decimals and sends that value back
        data_manager.note_thickness_edit({'uuid': unit.uuid, 'thickness': 25.46})
        assert data_manager.get_thickness_source(unit.uuid) == derived_data.CALCULATED

    def test_a_user_edit_of_a_calculated_thickness_makes_it_typed(self, data_manager):
        unit = _unit(data_manager, 'middle')
        data_manager.apply_calculated_thicknesses({'middle': 25.0})
        data_manager.note_thickness_edit({'uuid': unit.uuid, 'thickness': 60.0})
        assert data_manager.get_thickness_source(unit.uuid) == derived_data.TYPED

    def test_clearing_a_typed_thickness_allows_a_calculated_one(self, data_manager):
        unit = _unit(data_manager, 'middle')
        data_manager.note_thickness_edit({'uuid': unit.uuid, 'thickness': 40.0})
        unit.thickness = 40.0
        data_manager.note_thickness_edit({'uuid': unit.uuid, 'thickness': 0.0})
        unit.thickness = 0.0
        applied, _ = data_manager.apply_calculated_thicknesses({'middle': 25.0})
        assert applied == ['middle']

    def test_the_sources_are_saved_and_loaded(self, data_manager):
        unit = _unit(data_manager, 'middle')
        data_manager.apply_calculated_thicknesses({'middle': 25.0})
        state = json.loads(json.dumps(data_manager.to_dict()))
        data_manager.thickness_sources.clear()
        data_manager.update_from_dict(state)
        assert data_manager.get_thickness_source(unit.uuid) == derived_data.CALCULATED


class TestWorkflowMode:
    def test_the_default_is_the_map(self, data_manager):
        assert data_manager.workflow_mode == 'map'

    def test_the_choice_is_saved_and_loaded(self, data_manager):
        data_manager.set_workflow_mode('constraints')
        state = json.loads(json.dumps(data_manager.to_dict()))
        data_manager.set_workflow_mode('map')
        data_manager.update_from_dict(state)
        assert data_manager.workflow_mode == 'constraints'

    def test_a_state_file_of_an_older_version_gives_the_map(self, data_manager):
        data_manager.set_workflow_mode('constraints')
        state = json.loads(json.dumps(data_manager.to_dict()))
        del state['workflow_mode']
        data_manager.update_from_dict(state)
        assert data_manager.workflow_mode == 'map'

    def test_a_change_calls_the_listeners_one_time(self, data_manager):
        seen = []
        data_manager.add_workflow_mode_callback(seen.append)
        data_manager.set_workflow_mode('constraints')
        data_manager.set_workflow_mode('constraints')
        assert seen == ['constraints']

    def test_an_unknown_choice_is_an_error(self, data_manager):
        with pytest.raises(ValueError):
            data_manager.set_workflow_mode('other')

    def test_reset_gives_the_map(self, data_manager):
        data_manager.set_workflow_mode('constraints')
        data_manager.reset()
        assert data_manager.workflow_mode == 'map'
