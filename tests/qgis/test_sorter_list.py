"""Regression tests guarding against main.m2l_api.SORTER_LIST and
processing.algorithms.sorter.SORTER_LIST drifting apart again.

The Sorter GUI dialog reads sorter names from main.m2l_api.SORTER_LIST; the
StratigraphySorterAlgorithm processing algorithm builds its own SORTER_LIST
from that same dict (see the comment in sorter.py) so the two names/classes
can't silently diverge, while still keeping its one legacy
"Hint (deprecated)" entry at a fixed index for saved QGIS processing models
that reference it by enum position.
"""

from loopstructural.main.m2l_api import SORTER_LIST as GUI_SORTER_LIST
from loopstructural.processing.algorithms.sorter import SORTER_LIST as ALGORITHM_SORTER_LIST


def test_gui_sorter_names_and_classes_are_a_subset_of_the_algorithm_list():
    for name, sorter_cls in GUI_SORTER_LIST.items():
        assert (
            name in ALGORITHM_SORTER_LIST
        ), f"{name!r} missing from the processing algorithm's SORTER_LIST"
        assert (
            ALGORITHM_SORTER_LIST[name] is sorter_cls
        ), f"{name!r} maps to a different sorter class in the GUI vs. the processing algorithm"


def test_algorithm_list_only_adds_the_deprecated_hint_entry():
    extra_keys = set(ALGORITHM_SORTER_LIST) - set(GUI_SORTER_LIST)
    assert extra_keys == {"Hint (deprecated)"}


def test_deprecated_hint_entry_keeps_its_historical_index():
    # Saved QGIS processing models reference this enum parameter by index,
    # so "Hint (deprecated)" moving would silently repoint them at a
    # different sorter.
    assert list(ALGORITHM_SORTER_LIST.keys()).index("Hint (deprecated)") == 2
