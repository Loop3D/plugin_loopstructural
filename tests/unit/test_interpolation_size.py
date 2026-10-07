"""Pytest tests for the choice of the number of interpolation elements.

The module does not import QGIS, so the tests run in the fast tests/unit/ job.
"""

import numpy as np
import pandas as pd

from loopstructural.main.interpolation_size import (
    MAX_NELEMENTS,
    MIN_NELEMENTS,
    DataSummary,
    orientation_spread,
    suggest_nelements,
    summarise_data,
)


class TestSuggestNelements:
    def test_no_data_gives_the_minimum(self):
        assert suggest_nelements(DataSummary()) == MIN_NELEMENTS

    def test_more_data_gives_more_or_equal_elements(self):
        previous = 0
        for n in (1, 10, 100, 1_000, 10_000, 100_000):
            value = suggest_nelements(DataSummary(n_value=n, n_orientation=n, n_surfaces=3))
            assert value >= previous
            previous = value

    def test_limits(self):
        assert suggest_nelements(DataSummary(n_value=1)) == MIN_NELEMENTS
        assert suggest_nelements(DataSummary(n_value=10**7)) == MAX_NELEMENTS

    def test_result_is_a_multiple_of_1000(self):
        assert suggest_nelements(DataSummary(n_value=777, n_orientation=33)) % 1000 == 0

    def test_spread_gives_more_elements(self):
        parallel = suggest_nelements(DataSummary(n_value=200, n_orientation=200, spread=0))
        spread = suggest_nelements(DataSummary(n_value=200, n_orientation=200, spread=1))
        assert spread > parallel

    def test_surfaces_give_more_elements_and_stop_at_ten(self):
        one = suggest_nelements(DataSummary(n_value=200, n_surfaces=1))
        five = suggest_nelements(DataSummary(n_value=200, n_surfaces=5))
        ten = suggest_nelements(DataSummary(n_value=200, n_surfaces=10))
        twenty = suggest_nelements(DataSummary(n_value=200, n_surfaces=20))
        assert one < five < ten
        assert ten == twenty

    def test_small_and_large_data_differ(self):
        small = summarise_data(_values(20))
        large = summarise_data(_values(5_000))
        assert suggest_nelements(small) < suggest_nelements(large)


def _values(n):
    return pd.DataFrame({'X': range(n), 'val': [0.0] * n, 'feature_name': 'a'})


class TestOrientationSpread:
    def test_parallel_planes_have_no_spread(self):
        assert orientation_spread(np.tile([0, 0, 1], (10, 1))) == 0

    def test_all_directions_have_spread_near_one(self):
        rng = np.random.default_rng(0)
        normals = rng.normal(size=(5_000, 3))
        assert orientation_spread(normals) > 0.95

    def test_sign_does_not_matter(self):
        rng = np.random.default_rng(1)
        normals = rng.normal(size=(50, 3))
        flipped = normals.copy()
        flipped[::2] *= -1
        assert np.isclose(orientation_spread(normals), orientation_spread(flipped))

    def test_one_orientation_has_no_spread(self):
        assert orientation_spread([[1, 0, 0]]) == 0


class TestSummariseData:
    def test_none_and_empty(self):
        assert summarise_data(None) == DataSummary()
        assert summarise_data(pd.DataFrame()) == DataSummary()

    def test_counts_and_surfaces(self):
        df = pd.DataFrame(
            {
                'val': [0.0, 0.0, 10.0, np.nan],
                'nx': [np.nan, np.nan, np.nan, 0.0],
                'ny': [np.nan, np.nan, np.nan, 0.0],
                'nz': [np.nan, np.nan, np.nan, 1.0],
            }
        )
        summary = summarise_data(df)
        assert summary.n_value == 3
        assert summary.n_orientation == 1
        assert summary.n_surfaces == 2

    def test_strike_dip_spread(self):
        parallel = pd.DataFrame({'strike': [10.0] * 5, 'dip': [30.0] * 5})
        mixed = pd.DataFrame({'strike': [0.0, 90.0, 180.0, 270.0], 'dip': [60.0] * 4})
        assert summarise_data(parallel).spread == 0
        assert summarise_data(mixed).spread > 0.3

    def test_opposite_dip_directions_spread(self):
        a = summarise_data(pd.DataFrame({'strike': [0.0, 180.0], 'dip': [30.0, 30.0]}))
        assert a.spread > 0
