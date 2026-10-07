"""Tests for the isosurface values (see loopstructural/gui/visualisation/isovalues.py)."""

import numpy as np
import pytest

from loopstructural.gui.visualisation.isovalues import (
    default_range_values,
    isosurface_name,
    split_by_range,
    values_from_list,
    values_from_range,
)


def test_list_of_values():
    assert values_from_list("0.1, 0.5; 2 3") == [0.1, 0.5, 2.0, 3.0]


def test_list_removes_repeated_values_and_keeps_order():
    assert values_from_list("1, 0.5, 1.0, 0.5") == [1.0, 0.5]


@pytest.mark.parametrize("text", ["", "   ", ",,"])
def test_empty_list_is_an_error(text):
    with pytest.raises(ValueError):
        values_from_list(text)


@pytest.mark.parametrize("text", ["1, abc", "nan", "inf"])
def test_list_with_a_bad_value_is_an_error(text):
    with pytest.raises(ValueError):
        values_from_list(text)


def test_range_of_values():
    np.testing.assert_allclose(values_from_range(0, 1, 5), [0, 0.25, 0.5, 0.75, 1])


def test_range_with_one_value_is_the_start():
    assert values_from_range(2.0, 10.0, 1) == [2.0]


def test_range_with_equal_ends_gives_one_value():
    assert values_from_range(3.0, 3.0, 4) == [3.0]


def test_range_needs_a_count():
    with pytest.raises(ValueError):
        values_from_range(0, 1, 0)


def test_default_values_are_inside_the_field_range():
    values = default_range_values(0.0, 6.0, 5)
    assert len(values) == 5
    assert min(values) > 0.0 and max(values) < 6.0
    np.testing.assert_allclose(np.diff(values), np.diff(values)[0])


@pytest.mark.parametrize("low,high", [(1.0, 1.0), (2.0, 1.0), (np.nan, 1.0), (None, 1.0)])
def test_default_values_need_a_range(low, high):
    with pytest.raises((ValueError, TypeError)):
        default_range_values(low, high)


def test_values_outside_the_range():
    inside, outside = split_by_range([-1.0, 0.0, 0.5, 1.0, 2.0], 0.0, 1.0)
    assert inside == [0.0, 0.5, 1.0]
    assert outside == [-1.0, 2.0]


def test_isosurface_name_has_the_value():
    assert isosurface_name("Fault_1", 0.5) == "Fault_1_iso_0.50"
