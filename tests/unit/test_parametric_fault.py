"""Pytest tests for the faults that the user gives by numbers.

`loopstructural.main.parametric_fault` does not import QGIS, so the tests run
in the fast tests/unit/ job.
"""

import json

import numpy as np
import pytest

from loopstructural.main import parametric_fault


def good_spec(**changes):
    spec = {
        'name': 'F1',
        'strike': 0.0,
        'dip': 60.0,
        'pitch': 90.0,
        'displacement': 50.0,
        'centre': (5.0, 6.0, 7.0),
        'major_axis': 100.0,
        'intermediate_axis': 80.0,
        'minor_axis': 20.0,
    }
    spec.update(changes)
    return spec


class TestPlaneVectors:
    def test_a_vertical_plane_that_strikes_north_has_an_east_normal(self):
        normal, _ = parametric_fault.plane_vectors(0, 90, 0)
        assert np.allclose(normal, [1, 0, 0], atol=1e-9)

    def test_a_flat_plane_has_an_up_normal(self):
        normal, _ = parametric_fault.plane_vectors(123, 0, 0)
        assert np.allclose(normal, [0, 0, 1], atol=1e-9)

    def test_the_plane_dips_to_the_right_of_the_strike(self):
        # strike east, so the dip direction is south: the normal tilts to the south
        normal, _ = parametric_fault.plane_vectors(90, 45, 0)
        assert normal[1] < 0 < normal[2]

    @pytest.mark.parametrize('strike', [0, 37, 90, 210])
    @pytest.mark.parametrize('dip', [10, 45, 90])
    @pytest.mark.parametrize('pitch', [0, 30, 90, -45])
    def test_the_slip_is_a_unit_vector_in_the_plane(self, strike, dip, pitch):
        normal, slip = parametric_fault.plane_vectors(strike, dip, pitch)
        assert np.isclose(np.linalg.norm(normal), 1)
        assert np.isclose(np.linalg.norm(slip), 1)
        assert np.isclose(normal @ slip, 0, atol=1e-9)

    def test_pitch_0_is_along_the_strike_and_pitch_90_is_down_the_dip(self):
        _, along = parametric_fault.plane_vectors(0, 90, 0)
        _, down = parametric_fault.plane_vectors(0, 90, 90)
        assert np.allclose(along, [0, 1, 0], atol=1e-9)
        assert np.allclose(down, [0, 0, -1], atol=1e-9)


class TestProblems:
    def test_a_good_fault_has_no_problem(self):
        assert parametric_fault.problems(good_spec()) == []

    def test_the_name_is_needed_and_must_be_new(self):
        assert parametric_fault.problems(good_spec(name='  '))
        assert 'already used' in parametric_fault.problems(good_spec(), ['F1'])[0]

    @pytest.mark.parametrize('dip', [0, -5, 91])
    def test_the_dip_must_be_in_range(self, dip):
        assert parametric_fault.problems(good_spec(dip=dip))

    @pytest.mark.parametrize('axis', ['major_axis', 'intermediate_axis', 'minor_axis'])
    def test_a_size_must_be_above_zero(self, axis):
        assert parametric_fault.problems(good_spec(**{axis: 0}))

    def test_the_centre_needs_three_numbers(self):
        assert parametric_fault.problems(good_spec(centre=(1.0, 2.0)))
        assert parametric_fault.problems(good_spec(centre=(1.0, 2.0, float('nan'))))


class TestLoopStructuralArguments:
    def test_the_frame_data_is_the_centre_on_the_fault_surface(self):
        data = parametric_fault.frame_data(good_spec())
        row = data.iloc[0]
        assert (row['X'], row['Y'], row['Z']) == (5.0, 6.0, 7.0)
        assert row['val'] == 0 and row['coord'] == 0 and row['feature_name'] == 'F1'

    def test_the_arguments(self):
        arguments = parametric_fault.fault_arguments(good_spec())
        assert arguments['displacement'] == 50.0
        assert arguments['major_axis'] == 100.0
        assert arguments['intermediate_axis'] == 80.0
        assert arguments['minor_axis'] == 20.0
        assert list(arguments['fault_center']) == [5.0, 6.0, 7.0]
        assert np.isclose(arguments['fault_normal_vector'] @ arguments['fault_slip_vector'], 0)


class TestSaving:
    def test_a_spec_survives_json(self):
        spec = good_spec(name=' F1 ', centre=(np.float64(5.0), 6, 7))
        written = json.loads(json.dumps(parametric_fault.clean_spec(spec)))
        loaded = parametric_fault.spec_from_dict(written)
        assert loaded['name'] == 'F1'
        assert loaded['centre'] == (5.0, 6.0, 7.0)
        assert loaded['dip'] == 60.0

    def test_the_default_spec_is_in_the_middle_of_the_area(self):
        spec = parametric_fault.default_spec([0, 0, -100], [1000, 400, 100])
        assert spec['centre'] == (500.0, 200.0, 0.0)
        assert spec['major_axis'] == 1000.0
        assert spec['minor_axis'] == 500.0
        assert parametric_fault.problems({**spec, 'name': 'F'}) == []
