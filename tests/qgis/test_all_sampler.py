"""Pytest tests for the AllSampler geometry-sampling helper.

AllSampler doesn't touch any QGIS or LoopStructural object -- it only
operates on a geopandas GeoDataFrame -- but it lives in model_manager.py,
which imports LoopStructural/QGIS at module level, so this test can only
run where those are installed (hence tests/qgis/ rather than tests/unit/).
"""

import geopandas as gpd
import pytest
from shapely.geometry import LineString, MultiLineString, Point

from loopstructural.main.model_manager import AllSampler


@pytest.fixture
def sampler():
    return AllSampler()


@pytest.fixture
def constant_dem():
    """A DEM function that always returns the same elevation."""
    return lambda x, y: 100.0


class TestAllSamplerNoneInput:
    def test_none_line_returns_empty_dataframe_with_expected_columns(self, sampler, constant_dem):
        result = sampler(None, constant_dem, use_z=False)

        assert result.empty
        assert list(result.columns) == ['X', 'Y', 'Z', 'feature_id']


class TestAllSamplerLineString:
    def test_samples_every_vertex_and_uses_dem_for_z(self, sampler, constant_dem):
        gdf = gpd.GeoDataFrame(
            {'name': ['fault_a'], 'geometry': [LineString([(0, 0), (1, 1), (2, 2)])]}
        )

        result = sampler(gdf, constant_dem, use_z=False)

        assert list(result['X']) == [0.0, 1.0, 2.0]
        assert list(result['Y']) == [0.0, 1.0, 2.0]
        # use_z=False -> Z always comes from the DEM, even for a 2D geometry
        assert list(result['Z']) == [100.0, 100.0, 100.0]
        assert list(result['feature_id']) == [0, 0, 0]
        # non-geometry attributes are copied onto every sampled point
        assert list(result['name']) == ['fault_a', 'fault_a', 'fault_a']

    def test_multiple_features_increment_feature_id(self, sampler, constant_dem):
        gdf = gpd.GeoDataFrame(
            {
                'unit': ['a', 'b'],
                'geometry': [
                    LineString([(0, 0), (1, 1)]),
                    LineString([(9, 9), (8, 8)]),
                ],
            }
        )

        result = sampler(gdf, constant_dem, use_z=False)

        assert list(result['feature_id']) == [0, 0, 1, 1]
        assert list(result['unit']) == ['a', 'a', 'b', 'b']


class TestAllSamplerMultiLineString:
    def test_samples_every_vertex_of_every_part(self, sampler, constant_dem):
        mls = MultiLineString([[(0, 0), (1, 0)], [(2, 2), (3, 3)]])
        gdf = gpd.GeoDataFrame({'id': [7], 'geometry': [mls]})

        result = sampler(gdf, constant_dem, use_z=False)

        assert list(zip(result['X'], result['Y'])) == [
            (0.0, 0.0),
            (1.0, 0.0),
            (2.0, 2.0),
            (3.0, 3.0),
        ]
        # all points belong to the same (single) feature
        assert set(result['feature_id']) == {0}


class TestAllSamplerPoint:
    def test_use_z_true_prefers_geometry_z_but_falls_back_to_dem(self, sampler, constant_dem):
        gdf = gpd.GeoDataFrame({'name': ['p1', 'p2'], 'geometry': [Point(5, 5, 50), Point(6, 6)]})

        result = sampler(gdf, constant_dem, use_z=True)

        # p1 has an explicit Z, so it's used as-is
        assert result.loc[0, 'Z'] == 50.0
        # p2 has no Z, so even with use_z=True it falls back to the DEM
        assert result.loc[1, 'Z'] == 100.0

    def test_use_z_false_always_uses_dem(self, sampler, constant_dem):
        gdf = gpd.GeoDataFrame({'geometry': [Point(5, 5, 50)]})

        result = sampler(gdf, constant_dem, use_z=False)

        assert result.loc[0, 'Z'] == 100.0

    def test_no_dem_and_no_z_defaults_to_zero(self, sampler):
        gdf = gpd.GeoDataFrame({'geometry': [Point(5, 5)]})

        result = sampler(gdf, dem=None, use_z=False)

        assert result.loc[0, 'Z'] == 0
