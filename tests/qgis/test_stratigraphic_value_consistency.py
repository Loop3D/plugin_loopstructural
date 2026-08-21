"""Regression test for the basal-contact training-value direction.

`GeologicalModelManager.update_foliation_features` assigns a scalar `val` to
each unit's basal contact before handing the data to the interpolator.
`StratigraphicColumn.update_unit_values` (LoopStructural core) computes each
unit's `min()`/`max()` by walking the column youngest-to-oldest, accumulating
thickness from 0 -- forced by the fact that a basement unit's open-ended
range (`thickness=inf`) only works when it's the *last* unit processed in
that walk (an infinite thickness earlier would poison every unit after it).
That makes `u.min()` the boundary shared with the next *younger* neighbour
(a unit's top) and `u.max()` the boundary shared with the next *older*
neighbour (a unit's true base).

A digitised "basal contact" represents a unit's base, so it must be trained
at `val = u.max()`, not `u.min()`. Training at `u.min()` (the old behaviour)
anchors every unit's own contact points to its top boundary instead of its
base -- confirmed on a live project: every unit's own mapped points
evaluated into its next-younger neighbour's bracket instead of its own,
e.g. "Formacao Betari"'s own contact data landing inside "Formacao
Guaricanga"'s value range.

Note `get_isovalues()` also reports `u.min()` per unit -- that's a separate
concern (naming which unit an *extracted isosurface* belongs to), not a
statement about which value basal-contact training data should use, so this
test does not compare against it.

This direction has flipped back and forth as this plugin and LoopStructural
evolved independently -- see the "stratigraphic column was reversed" fixes
in model_manager.py (2025-07-21) and the widget (2025-08-21, reverted
2025-09-08). This test pins the invariant so a future change fails loudly
here instead of silently inverting a user's model.
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


class TestTrainingValueIsUnitsOwnBase:
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
        expected_values = self._own_base_by_unit(column, ('oldest', 'middle', 'youngest'))

        for unit_name in ('oldest', 'middle', 'youngest'):
            assert training_values[unit_name] == pytest.approx(expected_values[unit_name]), (
                f"'{unit_name}' was trained with val={training_values[unit_name]} but its "
                f"own base (boundary with the next-older neighbour) is "
                f"{expected_values[unit_name]} -- basal-contact data must train at a unit's "
                f"own max(), not min(), or extracted surfaces get the wrong unit name."
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
        expected_values = self._own_base_by_unit(
            column, ('basin_floor', 'basin_fill', 'cover_lower', 'cover_upper')
        )

        for unit_name in ('basin_floor', 'basin_fill', 'cover_lower', 'cover_upper'):
            assert training_values[unit_name] == pytest.approx(expected_values[unit_name])

    def test_undigitised_unit_does_not_shift_later_units_in_group(self, manager):
        """Regression test for a real bug: a unit with no digitised contact
        or orientation data (e.g. a "Top" unit nobody has mapped points for)
        must still contribute its own thickness to `val` for every unit
        that follows it in the group -- `update_foliation_features` used to
        `continue` past an undigitised unit before accumulating its
        thickness, which shifted every later unit's trained value by that
        unit's thickness relative to its own true base.
        """
        column = StratigraphicColumn()
        column.clear(basement=False)
        # Added first so it ends up last in `group.units` (each `add_unit`
        # prepends) and therefore *first* in the `reversed(group.units)`
        # build loop -- matching the live project, where the undigitised
        # unit was the one whose skipped increment shifted every unit
        # after it.
        column.add_unit(name='Top', thickness=999.0, where='top')
        column.add_unit(name='basin_fill', thickness=150.0, where='top')
        column.add_unit(name='basin_floor', thickness=50.0, where='top')

        manager.stratigraphic_column = column
        for name in ('basin_floor', 'basin_fill'):
            manager.stratigraphy[name]['contact'] = _contact(name)
        # 'Top' deliberately has no entry in manager.stratigraphy at all.

        manager.update_foliation_features()

        training_values = self._training_values_by_unit(manager._captured_calls)
        expected_values = self._own_base_by_unit(column, ('basin_floor', 'basin_fill'))

        for unit_name in ('basin_floor', 'basin_fill'):
            assert training_values[unit_name] == pytest.approx(expected_values[unit_name]), (
                f"'{unit_name}' was trained with val={training_values[unit_name]} but its "
                f"own base is {expected_values[unit_name]} -- an undigitised unit earlier in "
                f"the group must still shift later units' trained values by its own thickness."
            )

    @staticmethod
    def _own_base_by_unit(column, unit_names):
        """Each unit's own base: the boundary with the next-*older* neighbour,
        i.e. `u.max()` -- see module docstring for why max() (not min(), which
        `get_isovalues()` reports) is the correct target for basal-contact
        training data."""
        units_by_name = {
            u.name: u for group in column.get_groups() for u in group.units
        }
        return {name: units_by_name[name].max() for name in unit_names}

    @staticmethod
    def _training_values_by_unit(captured_calls):
        combined = pd.concat(captured_calls, ignore_index=True)
        return dict(zip(combined['source_unit'], combined['val']))
