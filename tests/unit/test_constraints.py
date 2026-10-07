"""Pytest tests for the constraint types of a feature.

`loopstructural.main.constraints` does not import QGIS, so the tests run in
the fast tests/unit/ job.
"""

import numpy as np
import pandas as pd
import pytest

from loopstructural.main import constraints


def sampler_of(points):
    """A sampler that ignores the layer and gives fixed points."""
    calls = []

    def sampler(df, dem, use_z):
        calls.append(use_z)
        return points.copy()

    sampler.calls = calls
    return sampler


@pytest.fixture
def points():
    return pd.DataFrame(
        {
            'X': [0.0, 1.0, 2.0, 3.0],
            'Y': [0.0, 1.0, 2.0, 3.0],
            'Z': [10.0, 11.0, 12.0, 13.0],
            'feature_id': [0, 0, 1, 1],
            'gx': [0.0, 0.0, 1.0, np.nan],
            'gy': [0.0, 0.0, 0.0, 1.0],
            'gz': [1.0, 0.0, 0.0, 1.0],
            'group': ['a', 'b', 'a', None],
            'order': [1, 1, 2, 2],
        }
    )


class TestTypes:
    def test_every_type_has_a_description_and_a_field_rule(self):
        for layer_type in constraints.CONSTRAINT_TYPES:
            assert constraints.DESCRIPTIONS[layer_type]
            assert layer_type in constraints.REQUIRED_FIELDS

    def test_the_six_types_of_the_plan_are_there(self):
        for name in (
            'Value',
            'Interface',
            'Gradient/Normal',
            'Tangent',
            'Inequality',
            'Pairwise Inequality',
        ):
            assert name in constraints.CONSTRAINT_TYPES

    def test_missing_fields(self):
        row = {'type': constraints.GRADIENT_NORMAL, 'vector_x_field': 'gx'}
        assert constraints.missing_fields(row) == ['vector_y_field', 'vector_z_field']
        assert constraints.missing_fields({'type': constraints.INTERFACE}) == []

    def test_only_inequality_types_need_the_admm_solver(self):
        assert constraints.solver_for(constraints.INEQUALITY) == 'admm'
        assert constraints.solver_for(constraints.PAIRWISE_INEQUALITY) == 'admm'
        assert constraints.solver_for(constraints.VALUE) is None


class TestZSource:
    def test_a_row_of_an_older_version_uses_the_default(self, points):
        sampler = sampler_of(points)
        constraints.sample_layer(sampler, {'df': None}, None, default_use_z=True)
        assert sampler.calls == [True]

    @pytest.mark.parametrize(
        'source, expected', [('layer', True), ('dem', False), ('constant', False)]
    )
    def test_the_source_decides_if_the_layer_z_is_used(self, points, source, expected):
        sampler = sampler_of(points)
        constraints.sample_layer(sampler, {'df': None, 'z_source': source}, None, True)
        assert sampler.calls == [expected]

    def test_a_constant_replaces_all_z(self, points):
        rows = constraints.sample_layer(
            sampler_of(points), {'df': None, 'z_source': 'constant', 'z_value': -50}, None
        )
        assert (rows['Z'] == -50.0).all()


class TestWeight:
    def test_no_weight_adds_no_column(self, points):
        assert 'w' not in constraints.add_weight(points[['X', 'Y', 'Z']], points, {})

    def test_the_weight_is_added(self, points):
        rows = constraints.add_weight(points[['X', 'Y', 'Z']], points, {'weight': 0.5})
        assert (rows['w'] == 0.5).all()

    def test_a_weight_in_the_rows_is_kept(self, points):
        rows = points[['X', 'Y', 'Z']].assign(w=0.1)
        assert (constraints.add_weight(rows, points, {'weight': 5})['w'] == 0.1).all()


class TestInterface:
    def test_each_feature_is_a_surface_without_a_group_field(self, points):
        rows, offset = constraints.interface_rows(points, {}, 'f')
        assert list(rows['interface']) == [0, 0, 1, 1]
        assert offset == 2

    def test_the_offset_keeps_the_surfaces_of_two_rows_apart(self, points):
        rows, offset = constraints.interface_rows(points, {}, 'f', offset=5)
        assert list(rows['interface']) == [5, 5, 6, 6]
        assert offset == 7

    def test_a_group_field_gives_the_surfaces_and_drops_empty_values(self, points):
        rows, offset = constraints.interface_rows(points, {'group_field': 'group'}, 'f')
        assert list(rows['interface']) == [0, 1, 0]
        assert offset == 2
        assert (rows['feature_name'] == 'f').all()


class TestVectors:
    def test_a_gradient_gives_the_g_columns_and_drops_bad_rows(self, points):
        row = {
            'type': constraints.GRADIENT_NORMAL,
            'vector_x_field': 'gx',
            'vector_y_field': 'gy',
            'vector_z_field': 'gz',
        }
        rows = constraints.constraint_rows(points, row, 'f')
        # row 1 is a zero vector and row 3 has no x
        assert list(rows.index) == [0, 2]
        assert {'gx', 'gy', 'gz'} <= set(rows.columns)

    def test_a_normal_gives_the_n_columns(self, points):
        row = {
            'type': constraints.GRADIENT_NORMAL,
            'vector_kind': constraints.KIND_NORMAL,
            'vector_x_field': 'gx',
            'vector_y_field': 'gy',
            'vector_z_field': 'gz',
            'weight': 2.0,
        }
        rows = constraints.constraint_rows(points, row, 'f')
        assert {'nx', 'ny', 'nz'} <= set(rows.columns)
        assert (rows['w'] == 2.0).all()

    def test_a_tangent_gives_the_t_columns(self, points):
        row = {
            'type': constraints.TANGENT,
            'vector_x_field': 'gx',
            'vector_y_field': 'gy',
            'vector_z_field': 'gz',
        }
        assert {'tx', 'ty', 'tz'} <= set(constraints.constraint_rows(points, row, 'f').columns)


class TestPairwise:
    def test_the_group_number_gives_the_pair_id(self, points):
        row = {'type': constraints.PAIRWISE_INEQUALITY, 'pair_field': 'order'}
        rows = constraints.constraint_rows(points, row, 'f')
        assert list(rows['pair_id']) == [1, 1, 2, 2]

    def test_a_row_without_a_number_is_dropped(self, points):
        points.loc[0, 'order'] = np.nan
        row = {'type': constraints.PAIRWISE_INEQUALITY, 'pair_field': 'order'}
        assert len(constraints.constraint_rows(points, row, 'f')) == 3


def test_an_unknown_type_is_an_error(points):
    with pytest.raises(ValueError):
        constraints.constraint_rows(points, {'type': 'Other'}, 'f')
