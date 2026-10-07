"""Pytest tests for the status and the check functions of the dock steps.

The modules do not import QGIS, so the tests use fake managers and run in the
fast tests/unit/ job.
"""

from types import SimpleNamespace

import pytest

from loopstructural.gui.modelling.steps import checks
from loopstructural.gui.modelling.steps.status import Status, StepCheck
from loopstructural.main import derived_data, layer_roles
from loopstructural.main.derived_data import DerivedData


class FakeRoles:
    def __init__(self):
        self.values = {}
        self.contacts_source = layer_roles.CONTACTS_FROM_GEOLOGY


class FakeDataManager:
    """The parts of the data manager that the checks read."""

    def __init__(self):
        self.bounding_box_set = False
        self.crs_valid = True
        self.units = []
        self.contact_units = []
        self.fault_traces = None
        self.changed_layers = []
        self.layer_roles = FakeRoles()
        self._fault_topology = SimpleNamespace(faults=[])
        self.inputs = {'unit_order': ['a']}
        self.derived = DerivedData()
        for name in (derived_data.BASAL_CONTACTS, derived_data.THICKNESS, derived_data.STYLED_FIELDS):
            self.derived.register(name, lambda: self.inputs)

    def is_bounding_box_set(self):
        return self.bounding_box_set

    def is_model_crs_valid(self):
        return self.crs_valid

    def get_layer_role(self, role):
        return self.layer_roles.values.get(role)

    def get_stratigraphic_unit_names(self):
        return list(self.units)

    def get_unique_basal_units(self):
        return list(self.contact_units)

    def get_fault_traces(self):
        return self.fault_traces

    def get_changed_layers(self):
        return list(self.changed_layers)


class FakeModelManager:
    def __init__(self, state='empty'):
        self.model_state = state


@pytest.fixture
def dm():
    return FakeDataManager()


class TestStepCheck:
    def test_no_message_is_done(self):
        assert StepCheck().status == Status.DONE
        assert StepCheck().summary == ''

    def test_a_todo_is_not_started(self):
        assert StepCheck(todo=('Select a layer.',)).status == Status.NOT_STARTED

    def test_a_problem_has_priority_over_a_todo(self):
        check = StepCheck(problems=('Bad CRS.',), todo=('Select a layer.',))
        assert check.status == Status.PROBLEM
        assert check.messages == ('Bad CRS.', 'Select a layer.')
        assert check.summary == 'Bad CRS. (+1 more)'


class TestDataStep:
    def test_a_new_project_is_not_started(self, dm):
        check = checks.check_data(dm)
        assert check.status == Status.NOT_STARTED
        assert 'Set the bounding box.' in check.todo

    def test_the_area_set_is_done(self, dm):
        dm.bounding_box_set = True
        assert checks.check_data(dm).status == Status.DONE

    def test_the_map_layers_are_not_a_todo_of_step_1(self, dm):
        dm.bounding_box_set = True
        assert checks.check_data(dm).todo == ()

    def test_a_geographic_crs_is_a_problem(self, dm):
        dm.crs_valid = False
        assert checks.check_data(dm).status == Status.PROBLEM


class TestStratigraphyStep:
    @pytest.fixture(autouse=True)
    def map_layers(self, dm, request):
        if request.node.name not in ('test_an_empty_column_is_not_started', 'test_missing_map_layers_are_a_todo'):
            dm.layer_roles.values = {
                layer_roles.GEOLOGY: object(),
                layer_roles.STRUCTURE: object(),
            }

    def test_an_empty_column_is_not_started(self, dm):
        check = checks.check_stratigraphy(dm)
        assert check.status == Status.NOT_STARTED
        assert any(t.startswith('Add units to the stratigraphic column.') for t in check.todo)
        assert 'optional' in check.todo[0]

    def test_an_empty_column_does_not_ask_for_layers_or_contacts(self, dm):
        todo = checks.check_stratigraphy(dm).todo
        assert len(todo) == 1
        assert not checks.check_stratigraphy(dm).problems

    def test_missing_map_layers_are_a_todo(self, dm):
        dm.units = ['a']
        todo = checks.check_stratigraphy(dm).todo
        assert 'Select the geology layer.' in todo
        assert 'Select the structure layer.' in todo

    def test_units_without_contacts_are_a_problem(self, dm):
        dm.units = ['a', 'b', 'c']
        dm.contact_units = ['a']
        dm.layer_roles.values[layer_roles.BASAL_CONTACTS] = object()
        check = checks.check_stratigraphy(dm)
        assert check.status == Status.PROBLEM
        assert check.problems == ('2 units have no basal contacts: b, c.',)

    def test_one_unit_uses_the_singular(self, dm):
        dm.units = ['a', 'b']
        dm.contact_units = ['a']
        dm.layer_roles.values[layer_roles.BASAL_CONTACTS] = object()
        assert checks.check_stratigraphy(dm).problems == ('1 unit has no basal contacts: b.',)

    def test_long_list_of_names_is_cut(self, dm):
        dm.units = ['a', 'b', 'c', 'd', 'e']
        dm.contact_units = ['z']
        dm.layer_roles.values[layer_roles.BASAL_CONTACTS] = object()
        assert 'a, b, c, ...' in checks.check_stratigraphy(dm).problems[0]

    def test_no_contacts_layer_is_a_todo(self, dm):
        dm.units = ['a']
        assert checks.check_stratigraphy(dm).todo == ('Extract the basal contacts.',)

    def test_out_of_date_contacts_are_a_problem(self, dm):
        dm.units = ['a']
        dm.layer_roles.values[layer_roles.BASAL_CONTACTS] = object()
        dm.derived.record(derived_data.BASAL_CONTACTS)
        assert checks.check_stratigraphy(dm).status == Status.DONE
        dm.inputs = {'unit_order': ['b', 'a']}
        check = checks.check_stratigraphy(dm)
        assert check.status == Status.PROBLEM
        assert check.problems == (
            'Basal contacts are out of date (the order of the units changed).',
        )

    def test_a_move_and_its_undo_is_not_a_problem(self, dm):
        dm.units = ['a']
        dm.layer_roles.values[layer_roles.BASAL_CONTACTS] = object()
        dm.derived.record(derived_data.BASAL_CONTACTS)
        dm.inputs = {'unit_order': ['b', 'a']}
        dm.inputs = {'unit_order': ['a']}
        assert checks.check_stratigraphy(dm).status == Status.DONE

    def test_contacts_from_a_layer_are_an_input_and_never_out_of_date(self, dm):
        dm.units = ['a']
        dm.layer_roles.values[layer_roles.BASAL_CONTACTS] = object()
        dm.layer_roles.contacts_source = layer_roles.CONTACTS_FROM_LAYER
        dm.derived.record(derived_data.BASAL_CONTACTS)
        dm.inputs = {'unit_order': ['b', 'a']}
        assert checks.check_stratigraphy(dm).status == Status.DONE


class TestFaultsStep:
    def test_faults_are_optional(self, dm):
        check = checks.check_faults(dm)
        assert check.status == Status.NOT_STARTED
        assert 'optional' in check.todo[0]

    def test_a_layer_without_a_name_field_is_a_todo(self, dm):
        dm.fault_traces = {'layer': object(), 'fault_name_field': None}
        assert checks.check_faults(dm).todo == ('Select the fault name field.',)

    def test_a_layer_without_faults_is_a_problem(self, dm):
        dm.fault_traces = {'layer': object(), 'fault_name_field': 'id'}
        assert checks.check_faults(dm).status == Status.PROBLEM

    def test_faults_found_is_done(self, dm):
        dm.fault_traces = {'layer': object(), 'fault_name_field': 'id'}
        dm._fault_topology.faults = ['F1']
        assert checks.check_faults(dm).status == Status.DONE


class TestModelStep:
    @pytest.mark.parametrize(
        'state, status',
        [
            ('empty', Status.NOT_STARTED),
            ('initialized', Status.NOT_STARTED),
            ('stale', Status.PROBLEM),
            ('solved', Status.DONE),
        ],
    )
    def test_status_follows_the_model_state(self, dm, state, status):
        dm.bounding_box_set = True
        assert checks.check_model(dm, FakeModelManager(state)).status == status

    def test_no_bounding_box_is_a_problem(self, dm):
        check = checks.check_model(dm, FakeModelManager('empty'))
        assert check.status == Status.PROBLEM
        assert check.problems[0] == 'Set the bounding box in step 1.'

    def test_out_of_date_data_is_a_problem_before_the_build(self, dm):
        dm.bounding_box_set = True
        dm.derived.record(derived_data.THICKNESS)
        dm.inputs = {'unit_order': ['b', 'a']}
        check = checks.check_model(dm, FakeModelManager('solved'))
        assert check.status == Status.PROBLEM

    def test_changed_layers_are_a_problem(self, dm):
        dm.bounding_box_set = True
        dm.changed_layers = ['geology']
        check = checks.check_model(dm, FakeModelManager('solved'))
        assert check.status == Status.PROBLEM
        assert 'geology' in check.problems[0]


class TestViewStep:
    def test_needs_a_solved_model(self, dm):
        assert checks.check_view(dm, FakeModelManager('initialized')).status == Status.NOT_STARTED
        assert checks.check_view(dm, FakeModelManager('solved')).status == Status.DONE


def test_every_step_has_a_check():
    assert set(checks.STEP_CHECKS) == {
        checks.STEP_DATA,
        checks.STEP_STRATIGRAPHY,
        checks.STEP_FAULTS,
        checks.STEP_MODEL,
        checks.STEP_VIEW,
    }
