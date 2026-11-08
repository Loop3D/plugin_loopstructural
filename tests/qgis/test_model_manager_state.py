"""Pytest tests for GeologicalModelManager.is_feature_built and model_state.

These exercise pure attribute-introspection logic over lightweight mock
feature/builder objects -- no LoopStructural solving is involved. Building a
GeologicalModelManager still requires LoopStructural/QGIS to be importable,
which is why this lives in tests/qgis/ rather than tests/unit/.
"""

import types

import pytest

from loopstructural.main.model_manager import GeologicalModelManager


class _FakeBuilder:
    """Stands in for a LoopStructural feature builder.

    Faults/structural frames delegate to per-coordinate sub-builders and
    never set their own `_up_to_date` flag (see `is_feature_built`'s
    docstring), so passing `sub_builders` omits `_up_to_date` to match.
    """

    def __init__(self, up_to_date=True, faults=None, sub_builders=None):
        self.faults = faults or []
        if sub_builders is not None:
            self.builders = sub_builders
        else:
            self._up_to_date = up_to_date


class _FakeFeature:
    def __init__(self, name, builder=None):
        self.name = name
        self.builder = builder


@pytest.fixture
def manager():
    return GeologicalModelManager()


class TestIsFeatureBuilt:
    def test_no_builder_returns_none(self, manager):
        feature = _FakeFeature('unbuilt', builder=None)
        assert manager.is_feature_built(feature) is None

    def test_up_to_date_builder_with_no_dependencies_is_built(self, manager):
        feature = _FakeFeature('a', builder=_FakeBuilder(up_to_date=True))
        assert manager.is_feature_built(feature) is True

    def test_stale_builder_is_not_built(self, manager):
        feature = _FakeFeature('a', builder=_FakeBuilder(up_to_date=False))
        assert manager.is_feature_built(feature) is False

    def test_built_feature_with_stale_fault_dependency_is_not_built(self, manager):
        stale_fault = _FakeFeature('fault_a', builder=_FakeBuilder(up_to_date=False))
        feature = _FakeFeature(
            'unit_a', builder=_FakeBuilder(up_to_date=True, faults=[stale_fault])
        )
        assert manager.is_feature_built(feature) is False

    def test_built_feature_with_built_fault_dependency_is_built(self, manager):
        built_fault = _FakeFeature('fault_a', builder=_FakeBuilder(up_to_date=True))
        feature = _FakeFeature(
            'unit_a', builder=_FakeBuilder(up_to_date=True, faults=[built_fault])
        )
        assert manager.is_feature_built(feature) is True

    def test_sub_builders_must_all_be_up_to_date(self, manager):
        sub_builders = [_FakeBuilder(up_to_date=True), _FakeBuilder(up_to_date=False)]
        feature = _FakeFeature('frame', builder=_FakeBuilder(sub_builders=sub_builders))
        assert manager.is_feature_built(feature) is False

    def test_cycle_is_treated_as_built(self, manager):
        # A feature that (indirectly) depends on itself shouldn't infinite-loop.
        builder = _FakeBuilder(up_to_date=True)
        feature = _FakeFeature('self_referential', builder=builder)
        builder.faults = [feature]
        assert manager.is_feature_built(feature) is True


class TestModelState:
    def test_empty_model_has_no_features(self, manager):
        assert manager.model_state == 'empty'

    def test_topology_dirty_reports_stale_even_with_built_features(self, manager):
        manager.model.features = [_FakeFeature('a', builder=_FakeBuilder(up_to_date=True))]
        manager._topology_dirty = True
        assert manager.model_state == 'stale'

    def test_all_features_built_reports_solved(self, manager):
        manager.model.features = [
            _FakeFeature('a', builder=_FakeBuilder(up_to_date=True)),
            _FakeFeature('b', builder=_FakeBuilder(up_to_date=True)),
        ]
        assert manager.model_state == 'solved'

    def test_any_unbuilt_feature_reports_initialized(self, manager):
        manager.model.features = [
            _FakeFeature('a', builder=_FakeBuilder(up_to_date=True)),
            _FakeFeature('b', builder=_FakeBuilder(up_to_date=False)),
        ]
        assert manager.model_state == 'initialized'

    def test_internal_features_are_ignored(self, manager):
        # names starting with '__' are internal bookkeeping features and
        # shouldn't affect the empty/solved verdict.
        manager.model.features = [_FakeFeature('__internal', builder=None)]
        assert manager.model_state == 'empty'


class TestInputChanges:
    """Contacts or orientations that change after a build make the model stale."""

    @staticmethod
    def _contacts(n, offset=0.0):
        import geopandas as gpd
        from shapely.geometry import LineString

        line = LineString([(offset, 0), (offset + n, 0)])
        return gpd.GeoDataFrame({'unit': ['u1']}, geometry=[line], crs='EPSG:28354')

    @staticmethod
    def _built(manager):
        manager.model.features = [_FakeFeature('Group_0', _FakeBuilder(up_to_date=True))]

    def test_no_features_means_nothing_is_stale(self, manager):
        manager.update_contact_traces(self._contacts(5), unit_name_field='unit')
        assert manager.model_state == 'empty'

    def test_new_contacts_after_a_build_make_the_model_stale(self, manager):
        manager.update_contact_traces(self._contacts(5), unit_name_field='unit')
        self._built(manager)
        assert manager.model_state == 'solved'
        manager.update_contact_traces(self._contacts(8), unit_name_field='unit')
        assert manager.model_state == 'stale'

    def test_the_same_contacts_again_keep_the_model_solved(self, manager):
        manager.update_contact_traces(self._contacts(5), unit_name_field='unit')
        self._built(manager)
        # a column that the build adds to the frames is not a change of the data
        manager.stratigraphy['u1']['contact']['val'] = 1.0
        manager.update_contact_traces(self._contacts(5), unit_name_field='unit')
        assert manager.model_state == 'solved'

    def test_removed_contacts_make_the_model_stale(self, manager):
        manager.update_contact_traces(self._contacts(5), unit_name_field='unit')
        self._built(manager)
        # the empty contacts are logged through the debug manager
        manager._debug_manager = types.SimpleNamespace(log=lambda *args, **kwargs: None)
        manager.update_contact_traces(self._contacts(5).iloc[0:0], unit_name_field='unit')
        assert manager.model_state == 'stale'

    def test_a_build_clears_the_flag(self, manager):
        manager.update_contact_traces(self._contacts(5), unit_name_field='unit')
        self._built(manager)
        manager.update_contact_traces(self._contacts(8), unit_name_field='unit')
        manager._inputs_changed = False  # what update_model does at its end
        assert manager.model_state == 'solved'
