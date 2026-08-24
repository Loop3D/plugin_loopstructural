"""Regression tests for using a fault as a stratigraphic domain boundary.

`GeologicalModelManager.update_foliation_features` normally closes each
built stratigraphic group with a flat isovalue unconformity
(`GeologicalModel.add_unconformity`). When the column boundary closing a
group has been linked to a fault (via `fault_boundaries`, populated through
`ModellingDataManager.set_fault_boundary`), the group should instead be
capped by that fault's own surface -- a non-displacing domain split, built
with `GeologicalModel.create_and_add_domain_fault` -- and that fault must be
skipped by the ordinary displacement-fault build loop
(`update_fault_features`), since a domain fault and a displacement fault are
mutually exclusive roles for the same fault name.
"""

import numpy as np
import pandas as pd
import pytest
from LoopStructural import FaultTopology, StratigraphicColumn
from LoopStructural.datatypes import BoundingBox

from loopstructural.main.model_manager import GeologicalModelManager
from loopstructural.toolbelt.preferences import PlgSettingsStructure


def _contact(unit_name):
    return pd.DataFrame({'X': [0.0], 'Y': [0.0], 'Z': [0.0], 'source_unit': [unit_name]})


def _fault_trace():
    return pd.DataFrame({'X': [0.0, 10.0], 'Y': [0.0, 10.0], 'Z': [0.0, 0.0]})


def _two_group_column():
    """basin_floor/basin_fill, then a named unconformity, then cover_lower/cover_upper."""
    column = StratigraphicColumn()
    column.clear(basement=False)
    column.add_unit(name='basin_floor', thickness=50.0, where='top')
    column.add_unit(name='basin_fill', thickness=150.0, where='top')
    boundary = column.add_unconformity(name='regional_unconformity', where='top')
    column.add_unit(name='cover_lower', thickness=80.0, where='top')
    column.add_unit(name='cover_upper', thickness=120.0, where='top')
    return column, boundary


@pytest.fixture
def manager(monkeypatch):
    manager = GeologicalModelManager()
    calls = {'foliation': [], 'unconformity': [], 'domain_fault': [], 'fault': []}

    def fake_create_and_add_foliation(name, data=None, **kwargs):
        calls['foliation'].append((name, data))
        return object()

    def fake_add_unconformity(feature, value, **kwargs):
        calls['unconformity'].append((feature, value))

    def fake_create_and_add_domain_fault(fault_surface_data, **kwargs):
        calls['domain_fault'].append(fault_surface_data)
        return object()

    def fake_create_and_add_fault(fault_name, displacement, **kwargs):
        calls['fault'].append(fault_name)
        return object()

    monkeypatch.setattr(manager.model, 'create_and_add_foliation', fake_create_and_add_foliation)
    monkeypatch.setattr(manager.model, 'add_unconformity', fake_add_unconformity)
    monkeypatch.setattr(
        manager.model, 'create_and_add_domain_fault', fake_create_and_add_domain_fault
    )
    monkeypatch.setattr(manager.model, 'create_and_add_fault', fake_create_and_add_fault)
    manager._calls = calls
    return manager


class TestFaultDomainBoundary:
    def test_group_boundary_linked_to_fault_builds_domain_fault(self, manager):
        column, boundary = _two_group_column()
        manager.stratigraphic_column = column
        for name in ('basin_floor', 'basin_fill', 'cover_lower', 'cover_upper'):
            manager.stratigraphy[name]['contact'] = _contact(name)
        manager.faults['boundary_fault']['data'] = _fault_trace()
        manager.fault_boundaries[boundary.uuid] = 'boundary_fault'

        manager.update_foliation_features()

        assert manager._calls['domain_fault'] == ['boundary_fault']
        # Only the topmost group (nothing above it in the column) still
        # falls back to a flat unconformity.
        assert len(manager._calls['unconformity']) == 1

        registered = manager.model.data
        fault_rows = registered.loc[registered['feature_name'] == 'boundary_fault']
        # The default bounding box here (never set explicitly) is smaller
        # than the trace itself, so no synthetic edge-extension points get
        # added (see TestExtendFaultTraceToDomain for that, with a
        # realistic bounding box). What's registered is the 2 trace points
        # as value (val=0) constraints, plus the same 2 points again as
        # orientation (val=NaN, strike/dip) constraints -- a domain fault
        # needs both, see _domain_fault_dip / _extend_fault_trace_to_domain.
        assert len(fault_rows) == 4
        assert len(fault_rows.loc[fault_rows['val'] == 0]) == 2
        assert fault_rows['val'].isna().sum() == 2

    def test_group_boundary_without_fault_link_uses_flat_unconformity(self, manager):
        column, _boundary = _two_group_column()
        manager.stratigraphic_column = column
        for name in ('basin_floor', 'basin_fill', 'cover_lower', 'cover_upper'):
            manager.stratigraphy[name]['contact'] = _contact(name)

        manager.update_foliation_features()

        assert manager._calls['domain_fault'] == []
        assert len(manager._calls['unconformity']) == 2

    def test_missing_fault_data_falls_back_to_flat_unconformity(self, manager):
        column, boundary = _two_group_column()
        manager.stratigraphic_column = column
        for name in ('basin_floor', 'basin_fill', 'cover_lower', 'cover_upper'):
            manager.stratigraphy[name]['contact'] = _contact(name)
        # Linked to a fault, but no trace data was ever ingested for it.
        manager.fault_boundaries[boundary.uuid] = 'boundary_fault'

        manager.update_foliation_features()

        assert manager._calls['domain_fault'] == []
        assert len(manager._calls['unconformity']) == 2

    def test_domain_boundary_fault_skipped_by_displacement_fault_build(self, manager):
        _column, boundary = _two_group_column()
        manager.faults['boundary_fault']['data'] = _fault_trace()
        manager.fault_boundaries[boundary.uuid] = 'boundary_fault'
        manager.faults['normal_fault']['data'] = _fault_trace()

        manager.update_fault_features()

        assert manager._calls['fault'] == ['normal_fault']

    def test_abutting_relationships_skip_unbuilt_domain_boundary_fault(self, manager):
        """`update_fault_features` calls `apply_fault_abutting_relationships`
        before `update_foliation_features` has run, so a domain-boundary
        fault's feature (built there, not here) doesn't exist in the model
        yet. `GeologicalModel.get_feature_by_name` raises ValueError rather
        than returning None for a name that isn't built -- this must not
        propagate out of `apply_fault_abutting_relationships`.
        """
        column, boundary = _two_group_column()
        manager.fault_topology = FaultTopology(column)
        manager.fault_topology.add_fault('boundary_fault')
        manager.fault_topology.add_fault('normal_fault')
        manager.faults['boundary_fault']['data'] = _fault_trace()
        manager.faults['normal_fault']['data'] = _fault_trace()
        manager.fault_boundaries[boundary.uuid] = 'boundary_fault'

        # Neither fault has been built into manager.model yet.
        manager.apply_fault_abutting_relationships()  # must not raise


class TestDomainFaultBuildsAndSolves:
    """End-to-end regression test against the real LoopStructural build/solve
    path (nothing mocked here, unlike the other test classes in this module).

    `create_and_add_domain_fault` reads its points straight from
    `model.data` with no column normalisation, unlike
    `create_and_add_foliation`/`create_and_add_fault` (which run their
    `data=` argument through `GeologicalModel.prepare_data` internally) --
    so registering raw X/Y/Z/feature_name/val rows for a domain-boundary
    fault builds fine but crashes later, during Solve Model, with
    `KeyError: "None of [Index(['gx', 'gy', 'gz']...` deep inside
    `add_data_to_interpolator`. `_build_domain_fault_boundary` must run its
    data through `model.prepare_data` itself first.

    It also pins the fix for a second, more subtle bug: LoopStructural's
    `add_unconformity` backward crop walk only recognises FAULT/
    INACTIVEFAULT feature types as "already handled, skip" -- not
    DOMAINFAULT. `_two_group_column()`'s topmost group (cover) has no fault
    link, so it falls back to a plain `add_unconformity` call, which walks
    straight through the already-built `boundary_fault` domain fault and
    incorrectly adds itself as a region on it. Since
    `GeologicalFeature.evaluate_value` returns NaN wherever a feature's
    regions don't hold, this reads as the domain fault's own scalar field
    being NaN on whichever side that unrelated unconformity's condition
    fails. `_strip_spurious_regions_from_domain_faults` removes it.
    """

    def test_domain_fault_builds_and_solves(self, monkeypatch):
        monkeypatch.setattr(PlgSettingsStructure, 'interpolator_nelements', 200)
        manager = GeologicalModelManager()
        manager.update_bounding_box(BoundingBox(origin=[0, 0, -50], maximum=[100, 100, 50]))
        column, boundary = _two_group_column()
        manager.stratigraphic_column = column
        for name in ('basin_floor', 'basin_fill', 'cover_lower', 'cover_upper'):
            manager.stratigraphy[name]['contact'] = _contact(name)
        manager.faults['boundary_fault']['data'] = pd.DataFrame(
            {'X': [10.0, 90.0], 'Y': [10.0, 90.0], 'Z': [0.0, 0.0]}
        )
        manager.fault_boundaries[boundary.uuid] = 'boundary_fault'

        manager.update_model(notify_observers=False)
        manager.update_all_features(notify_observers=False)  # must not raise

        domain_fault = manager.model.get_feature_by_name('boundary_fault')
        assert domain_fault is not None
        assert domain_fault.regions == []

        xs, ys = np.meshgrid(np.linspace(0, 100, 11), np.linspace(0, 100, 11))
        pts = np.column_stack([xs.ravel(), ys.ravel(), np.zeros(xs.size)])
        values = domain_fault.evaluate_value(pts)
        assert not np.any(np.isnan(values)), (
            "domain fault scalar field is NaN somewhere in the model domain -- "
            "an unconformity region was incorrectly left on it"
        )


class TestExtendFaultTraceToDomain:
    """`_extend_fault_trace_to_domain` is what makes a domain-boundary fault
    behave as an "infinite" cut: it adds two synthetic points extending the
    trace's own trend out to the model's bounding box edges, so the
    interpolated surface isn't only reliable near the digitised trace.
    """

    def test_extends_a_short_trace_to_the_domain_edges(self, manager):
        manager.update_bounding_box(BoundingBox(origin=[0, 0, 0], maximum=[100, 100, 100]))
        # A short trace entirely inside the domain, running along y=x.
        trace = pd.DataFrame({'X': [40.0, 60.0], 'Y': [40.0, 60.0], 'Z': [0.0, 0.0]})

        extended = manager._extend_fault_trace_to_domain(trace)

        assert len(extended) == 4
        xy = extended[['X', 'Y']].to_numpy()
        # Two of the four points must sit on the bounding box boundary.
        on_boundary = [
            np.isclose(x, 0) or np.isclose(x, 100) or np.isclose(y, 0) or np.isclose(y, 100)
            for x, y in xy
        ]
        assert sum(on_boundary) == 2

    def test_extends_a_dipping_trace_keeping_its_trend(self, manager):
        manager.update_bounding_box(BoundingBox(origin=[0, 0, 0], maximum=[100, 100, 100]))
        # Trace along y=x with Z increasing 1:1 with distance along the line.
        trace = pd.DataFrame({'X': [40.0, 60.0], 'Y': [40.0, 60.0], 'Z': [-10.0, 10.0]})

        extended = manager._extend_fault_trace_to_domain(trace)

        synthetic = extended.iloc[2:]
        # The synthetic points should extrapolate the same Z-vs-along-line
        # trend rather than reusing the nearest original Z value.
        assert synthetic['Z'].max() > 10.0
        assert synthetic['Z'].min() < -10.0

    def test_single_point_trace_is_left_unchanged(self, manager):
        manager.update_bounding_box(BoundingBox(origin=[0, 0, 0], maximum=[100, 100, 100]))
        trace = pd.DataFrame({'X': [50.0], 'Y': [50.0], 'Z': [0.0]})

        extended = manager._extend_fault_trace_to_domain(trace)

        assert len(extended) == 1

    def test_direction_parallel_to_axis_outside_domain_is_left_unchanged(self, manager):
        manager.update_bounding_box(BoundingBox(origin=[0, 0, 0], maximum=[10, 10, 10]))
        # A vertical (constant-X) trace entirely outside the domain in X.
        trace = pd.DataFrame({'X': [500.0, 500.0], 'Y': [1.0, 2.0], 'Z': [0.0, 0.0]})

        extended = manager._extend_fault_trace_to_domain(trace)

        assert len(extended) == 2

    def test_local_tangent_varies_along_a_curved_trace(self, manager):
        """Regression test for a real bug: fitting one global best-fit line
        through a curved trace (the old approach) flattens its curvature
        out, and can extrapolate/orient the interpolated surface on the
        wrong side of real nearby data. Confirmed on a live project where
        a global-line fit put a stratigraphic unit's own contact data on
        the opposite side of its domain-boundary fault from a bounding-box
        corner that a correct local (nearest-segment) classification put
        on the *same* side. Each point's strike must instead follow its
        own local tangent.
        """
        manager.update_bounding_box(BoundingBox(origin=[0, 0, 0], maximum=[100, 100, 100]))
        # An L-shaped trace: a horizontal leg then a vertical leg.
        trace = pd.DataFrame(
            {'X': [20.0, 50.0, 50.0], 'Y': [50.0, 50.0, 80.0], 'Z': [0.0, 0.0, 0.0]}
        )

        extended = manager._extend_fault_trace_to_domain(trace)

        strikes = extended['strike'].to_numpy()
        # Row 0's local tangent is horizontal (towards row 1); row 2's is
        # vertical (away from row 1) -- these must differ substantially. A
        # single global best-fit line would instead give every point close
        # to the same strike.
        assert abs(((strikes[0] - strikes[2] + 180) % 360) - 180) > 45
