"""Regression test for the training-value / isovalue direction bug.

`GeologicalModelManager.update_foliation_features` assigns a scalar `val` to
each unit's basal contact before handing the data to the interpolator.
`StratigraphicColumn.get_isovalues` (LoopStructural core) later decides which
name to stamp on each extracted isosurface, using its own idea of which
value belongs to which unit.

These two must agree on direction (does value increase from oldest-to-
youngest, or youngest-to-oldest?), or every extracted surface gets labelled
with the wrong unit while keeping correct geometry -- see the "stratigraphic
column was reversed" fixes in model_manager.py (2025-07-21) and the widget
(2025-08-21, reverted 2025-09-08). This has flipped back and forth as this
plugin and LoopStructural evolved independently; this test pins the
invariant so a future change on either side fails loudly here instead of
silently inverting a user's model.
"""

import pandas as pd
import pytest
from LoopStructural import StratigraphicColumn

from loopstructural.main.model_manager import GeologicalModelManager


def _contact(unit_name):
    """A minimal single-point basal contact, tagged with its unit name so
    the test can recover which row came from which unit after the group
    DataFrames get concatenated."""
    return pd.DataFrame({'X': [0.0], 'Y': [0.0], 'Z': [0.0], 'source_unit': [unit_name]})


@pytest.fixture
def manager(monkeypatch):
    manager = GeologicalModelManager()

    captured_calls = []

    def fake_create_and_add_foliation(name, data=None, **kwargs):
        captured_calls.append(data)
        return object()  # stand-in foliation, only passed back into add_unconformity

    monkeypatch.setattr(manager.model, 'create_and_add_foliation', fake_create_and_add_foliation)
    monkeypatch.setattr(manager.model, 'add_unconformity', lambda *a, **k: None)
    manager._captured_calls = captured_calls
    return manager


class TestTrainingValueMatchesIsovalue:
    def test_single_group_three_units(self, manager):
        column = StratigraphicColumn()
        column.clear(basement=False)  # single flat group, no unconformities
        column.add_unit(name='oldest', thickness=100.0, where='top')
        column.add_unit(name='middle', thickness=200.0, where='top')
        column.add_unit(name='youngest', thickness=300.0, where='top')

        manager.stratigraphic_column = column
        for name in ('oldest', 'middle', 'youngest'):
            manager.stratigraphy[name]['contact'] = _contact(name)

        manager.update_foliation_features()

        training_values = self._training_values_by_unit(manager._captured_calls)
        expected_values = {name: entry['value'] for name, entry in column.get_isovalues().items()}

        for unit_name in ('oldest', 'middle', 'youngest'):
            assert training_values[unit_name] == pytest.approx(expected_values[unit_name]), (
                f"'{unit_name}' was trained with val={training_values[unit_name]} but "
                f"get_isovalues() will label the value={expected_values[unit_name]} surface "
                f"with this unit's name -- the trained field and the isosurface labels "
                f"disagree on direction, so extracted surfaces will get the wrong unit name."
            )

    def test_two_groups_split_by_unconformity(self, manager):
        column = StratigraphicColumn()
        column.clear(basement=False)
        column.add_unit(name='basin_floor', thickness=50.0, where='top')
        column.add_unit(name='basin_fill', thickness=150.0, where='top')
        column.add_unconformity(name='regional_unconformity', where='top')
        column.add_unit(name='cover_lower', thickness=80.0, where='top')
        column.add_unit(name='cover_upper', thickness=120.0, where='top')

        manager.stratigraphic_column = column
        for name in ('basin_floor', 'basin_fill', 'cover_lower', 'cover_upper'):
            manager.stratigraphy[name]['contact'] = _contact(name)

        manager.update_foliation_features()

        training_values = self._training_values_by_unit(manager._captured_calls)
        expected_values = {name: entry['value'] for name, entry in column.get_isovalues().items()}

        for unit_name in ('basin_floor', 'basin_fill', 'cover_lower', 'cover_upper'):
            assert training_values[unit_name] == pytest.approx(expected_values[unit_name])

    @staticmethod
    def _training_values_by_unit(captured_calls):
        combined = pd.concat(captured_calls, ignore_index=True)
        return dict(zip(combined['source_unit'], combined['val']))
