"""Pytest tests for the records of the inputs of derived data.

The module does not import QGIS, so these tests run in the fast tests/unit/ job.
The inputs here have the same shape as the inputs that the data manager gives
(see tests/qgis/test_derived_data_state.py for the tests with the data manager).
"""

import json

import pytest

from loopstructural.main.derived_data import (
    BASAL_CONTACTS,
    CALCULATED,
    CURRENT,
    NOT_RUN,
    OUT_OF_DATE,
    TYPED,
    DerivedData,
    ThicknessSources,
    hash_inputs,
)


class _Column:
    """A small stand-in for the inputs of the basal contacts."""

    def __init__(self):
        self.order = ['youngest', 'middle', 'oldest']
        self.colours = {'youngest': 'red', 'middle': 'green', 'oldest': 'blue'}
        self.geology = 'geology'

    def inputs(self):
        # the colours are not an input of the basal contacts
        return {'unit_order': list(self.order), 'geology': self.geology}


@pytest.fixture
def column():
    return _Column()


@pytest.fixture
def derived(column):
    derived = DerivedData()
    derived.register(BASAL_CONTACTS, column.inputs)
    return derived


class TestHash:
    def test_the_order_of_the_keys_does_not_change_the_hash(self):
        assert hash_inputs({'a': 1, 'b': 2}) == hash_inputs({'b': 2, 'a': 1})

    def test_the_order_of_a_list_changes_the_hash(self):
        assert hash_inputs({'order': ['a', 'b']}) != hash_inputs({'order': ['b', 'a']})


class TestStatus:
    def test_a_result_that_did_not_run_is_not_run(self, derived):
        assert derived.status(BASAL_CONTACTS) == NOT_RUN
        assert derived.out_of_date() == []

    def test_a_result_is_current_after_a_run(self, derived):
        derived.record(BASAL_CONTACTS)
        assert derived.status(BASAL_CONTACTS) == CURRENT

    def test_a_reorder_marks_the_contacts_out_of_date(self, derived, column):
        derived.record(BASAL_CONTACTS)
        column.order = ['middle', 'youngest', 'oldest']
        assert derived.status(BASAL_CONTACTS) == OUT_OF_DATE
        assert derived.out_of_date() == [BASAL_CONTACTS]

    def test_a_change_of_a_unit_colour_does_not(self, derived, column):
        derived.record(BASAL_CONTACTS)
        column.colours['youngest'] = 'purple'
        assert derived.status(BASAL_CONTACTS) == CURRENT

    def test_a_reorder_and_its_undo_give_the_same_hash(self, derived, column):
        derived.record(BASAL_CONTACTS)
        hash_before = derived.current_hash(BASAL_CONTACTS)
        column.order = ['middle', 'youngest', 'oldest']
        assert derived.status(BASAL_CONTACTS) == OUT_OF_DATE
        column.order = ['youngest', 'middle', 'oldest']
        assert derived.current_hash(BASAL_CONTACTS) == hash_before
        assert derived.status(BASAL_CONTACTS) == CURRENT

    def test_a_new_run_makes_the_result_current_again(self, derived, column):
        derived.record(BASAL_CONTACTS)
        column.order.reverse()
        derived.record(BASAL_CONTACTS)
        assert derived.status(BASAL_CONTACTS) == CURRENT

    def test_the_inputs_of_the_run_are_recorded(self, derived, column):
        # the user changes the column while the run is active
        run_inputs = column.inputs()
        column.order.reverse()
        derived.record(BASAL_CONTACTS, inputs=run_inputs)
        assert derived.status(BASAL_CONTACTS) == OUT_OF_DATE

    def test_forget(self, derived):
        derived.record(BASAL_CONTACTS)
        derived.forget(BASAL_CONTACTS)
        assert derived.status(BASAL_CONTACTS) == NOT_RUN

    def test_changed_inputs_name_the_inputs_that_changed(self, derived, column):
        derived.record(BASAL_CONTACTS)
        assert derived.changed_inputs(BASAL_CONTACTS) == []
        column.order.reverse()
        column.geology = 'other'
        assert derived.changed_inputs(BASAL_CONTACTS) == ['geology', 'unit_order']


class TestEvents:
    def test_refresh_sends_an_event_when_a_status_changes(self, derived, column):
        events = []
        derived.attach(lambda name, status: events.append((name, status)))
        derived.record(BASAL_CONTACTS)
        column.order.reverse()
        derived.refresh()
        derived.refresh()
        assert events == [(BASAL_CONTACTS, CURRENT), (BASAL_CONTACTS, OUT_OF_DATE)]

    def test_a_reorder_and_its_undo_send_two_events(self, derived, column):
        derived.record(BASAL_CONTACTS)
        events = []
        derived.attach(lambda name, status: events.append(status))
        column.order.reverse()
        derived.refresh()
        column.order.reverse()
        derived.refresh()
        assert events == [OUT_OF_DATE, CURRENT]


class TestSaveAndLoad:
    def test_round_trip(self, derived, column):
        derived.record(BASAL_CONTACTS, detail={'layer': 'geology'})
        data = json.loads(json.dumps(derived.to_dict()))

        loaded = DerivedData()
        loaded.register(BASAL_CONTACTS, column.inputs)
        loaded.from_dict(data)
        assert loaded.status(BASAL_CONTACTS) == CURRENT
        assert loaded.detail(BASAL_CONTACTS) == {'layer': 'geology'}
        column.order.reverse()
        assert loaded.status(BASAL_CONTACTS) == OUT_OF_DATE
        assert loaded.changed_inputs(BASAL_CONTACTS) == ['unit_order']

    def test_an_old_state_file_has_no_records(self, derived):
        derived.from_dict(None)
        assert derived.status(BASAL_CONTACTS) == NOT_RUN

    def test_a_bad_record_is_ignored(self, derived):
        derived.from_dict({BASAL_CONTACTS: 'bad', 'other': {'hash': 3}})
        assert derived.status(BASAL_CONTACTS) == NOT_RUN


class TestThicknessSources:
    def test_a_calculated_thickness_does_not_replace_a_typed_one(self):
        sources = ThicknessSources()
        sources.set('unit', TYPED)
        assert sources.can_overwrite('unit', 25.0) is False

    def test_a_calculated_thickness_replaces_a_calculated_one(self):
        sources = ThicknessSources()
        sources.set('unit', CALCULATED)
        assert sources.can_overwrite('unit', 25.0) is True

    def test_a_thickness_with_no_value_can_be_replaced(self):
        sources = ThicknessSources()
        sources.set('unit', TYPED)
        for empty in (None, 0.0, float('nan'), float('inf'), -1):
            assert sources.can_overwrite('unit', empty) is True

    def test_a_thickness_with_no_source_is_treated_as_typed(self):
        assert ThicknessSources().can_overwrite('unit', 25.0) is False

    def test_an_unknown_source_is_an_error(self):
        with pytest.raises(ValueError):
            ThicknessSources().set('unit', 'guessed')

    def test_round_trip(self):
        sources = ThicknessSources()
        sources.set('a', TYPED)
        sources.set('b', CALCULATED)
        loaded = ThicknessSources()
        loaded.from_dict(json.loads(json.dumps(sources.to_dict())))
        assert loaded.get('a') == TYPED
        assert loaded.get('b') == CALCULATED
        loaded.from_dict({'a': 'bad'})
        assert loaded.get('a') is None
