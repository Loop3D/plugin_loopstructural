"""Pytest tests for the primary action of the model step and for the choice of
the derived data that a build calculates again.

The modules do not import QGIS, so the tests use fake managers and run in the
fast tests/unit/ job.
"""

from types import SimpleNamespace

import pytest

from loopstructural.gui.modelling.steps import build_plan
from loopstructural.gui.modelling.steps.status import StepCheck
from loopstructural.main import derived_data, layer_roles
from loopstructural.main.derived_data import DerivedData
from loopstructural.main.derived_refresh import names_to_refresh, thickness_values
from loopstructural.main.workflow_mode import WORKFLOW_MODE_CONSTRAINTS, WORKFLOW_MODE_MAP


class TestPrimaryAction:
    def test_an_empty_model_is_built(self):
        action = build_plan.choose_primary_action('empty')
        assert (action.action, action.text) == (build_plan.ACTION_BUILD, "Build model")

    def test_an_initialized_model_is_solved(self):
        action = build_plan.choose_primary_action('initialized')
        assert (action.action, action.text) == (build_plan.ACTION_SOLVE, "Solve model")

    def test_a_solved_model_can_be_solved_again(self):
        action = build_plan.choose_primary_action('solved')
        assert action.action == build_plan.ACTION_SOLVE
        assert action.text == "Solve again"

    def test_a_stale_model_is_rebuilt(self):
        action = build_plan.choose_primary_action('stale')
        assert (action.action, action.text) == (build_plan.ACTION_BUILD, "Rebuild model")

    @pytest.mark.parametrize('state', ['initialized', 'solved'])
    def test_out_of_date_derived_data_makes_a_rebuild(self, state):
        action = build_plan.choose_primary_action(
            state, derived_out_of_date=[derived_data.BASAL_CONTACTS]
        )
        assert action.action == build_plan.ACTION_BUILD
        assert 'out of date' in action.tooltip

    def test_a_changed_layer_updates_the_data_and_solves(self):
        action = build_plan.choose_primary_action('solved', layers_changed=True)
        assert action.action == build_plan.ACTION_SOLVE
        assert action.text == "Update data and solve"

    def test_a_blocked_build_is_disabled_with_the_reason(self):
        action = build_plan.choose_primary_action('solved', blocked_reason="Set the bounding box.")
        assert action.action == build_plan.ACTION_NONE
        assert not action.enabled
        assert action.tooltip == "Set the bounding box."


class TestProblems:
    def test_problems_of_all_steps_in_the_order_of_the_steps(self):
        problems = build_plan.collect_problems(
            [
                ('data', StepCheck(problems=('Bad CRS.',))),
                ('stratigraphy', StepCheck(todo=('Add units.',))),
                ('faults', StepCheck(problems=('No faults.',))),
            ]
        )
        assert problems == [('data', 'Bad CRS.'), ('faults', 'No faults.')]

    def test_the_same_problem_shows_one_time(self):
        problems = build_plan.collect_problems(
            [
                ('stratigraphy', StepCheck(problems=('Contacts are out of date.',))),
                ('model', StepCheck(problems=('Contacts are out of date.',))),
            ]
        )
        assert problems == [('stratigraphy', 'Contacts are out of date.')]


class TestModes:
    ALL = ['data', 'stratigraphy', 'faults', 'model', 'view']

    def test_the_map_choice_shows_all_steps(self):
        assert build_plan.steps_for_mode(WORKFLOW_MODE_MAP, self.ALL) == self.ALL

    def test_the_constraints_choice_hides_steps_2_and_3(self):
        shown = build_plan.steps_for_mode(WORKFLOW_MODE_CONSTRAINTS, self.ALL)
        assert shown == ['data', 'model', 'view']


class FakeRoles:
    def __init__(self):
        self.values = {layer_roles.GEOLOGY: object(), layer_roles.GEOLOGY_UNIT_FIELD: 'UNITNAME'}
        self.contacts_source = layer_roles.CONTACTS_FROM_GEOLOGY


class FakeDataManager:
    """The parts of the data manager that `names_to_refresh` reads."""

    def __init__(self):
        self.units = ['a', 'b']
        self.layer_roles = FakeRoles()
        self.inputs = {'unit_order': ['a', 'b']}
        self.derived = DerivedData()
        for name in (derived_data.BASAL_CONTACTS, derived_data.THICKNESS):
            self.derived.register(name, lambda: self.inputs)

    def get_stratigraphic_unit_names(self):
        return list(self.units)

    def get_layer_role(self, role):
        return self.layer_roles.values.get(role)


@pytest.fixture
def dm():
    return FakeDataManager()


class TestNamesToRefresh:
    def test_contacts_that_were_never_calculated_are_calculated(self, dm):
        assert names_to_refresh(dm) == [derived_data.BASAL_CONTACTS]

    def test_current_contacts_are_not_calculated_again(self, dm):
        dm.derived.record(derived_data.BASAL_CONTACTS)
        assert names_to_refresh(dm) == []

    def test_a_reorder_makes_contacts_and_thickness_out_of_date_in_order(self, dm):
        dm.derived.record(derived_data.BASAL_CONTACTS)
        dm.derived.record(derived_data.THICKNESS)
        dm.inputs = {'unit_order': ['b', 'a']}
        assert names_to_refresh(dm) == [derived_data.BASAL_CONTACTS, derived_data.THICKNESS]

    def test_a_reorder_and_its_undo_calculate_nothing(self, dm):
        dm.derived.record(derived_data.BASAL_CONTACTS)
        dm.inputs = {'unit_order': ['b', 'a']}
        dm.inputs = {'unit_order': ['a', 'b']}
        assert names_to_refresh(dm) == []

    def test_a_thickness_that_was_never_calculated_can_be_typed(self, dm):
        dm.derived.record(derived_data.BASAL_CONTACTS)
        assert derived_data.THICKNESS not in names_to_refresh(dm)

    def test_a_contacts_layer_of_the_user_is_never_calculated(self, dm):
        dm.layer_roles.contacts_source = layer_roles.CONTACTS_FROM_LAYER
        assert derived_data.BASAL_CONTACTS not in names_to_refresh(dm)

    def test_no_column_calculates_no_contacts(self, dm):
        dm.units = []
        assert names_to_refresh(dm) == []

    def test_no_geology_layer_calculates_no_contacts(self, dm):
        dm.layer_roles.values[layer_roles.GEOLOGY] = None
        assert names_to_refresh(dm) == []


class TestThicknessValues:
    def test_the_median_is_used_and_a_unit_with_no_result_is_left_out(self):
        pd = pytest.importorskip('pandas')
        table = pd.DataFrame(
            {
                'name': ['a', 'b', 'c'],
                'ThicknessMedian': [10.0, -1.0, float('nan')],
                'ThicknessMean': [11.0, 12.0, 13.0],
            }
        )
        assert thickness_values(table) == {'a': 10.0}

    def test_the_mean_is_used_without_a_median(self):
        pd = pytest.importorskip('pandas')
        table = pd.DataFrame({'name': ['a'], 'ThicknessMean': [5.0]})
        assert thickness_values(table) == {'a': 5.0}

    def test_a_table_without_thickness_columns_gives_nothing(self):
        assert thickness_values(SimpleNamespace(columns=['name'])) == {}
