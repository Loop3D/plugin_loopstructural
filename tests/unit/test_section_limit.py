"""Pytest tests for the rule that limits the open sections of a page.

The module does not import QGIS, so the tests run in the fast tests/unit/ job.
"""

from loopstructural.gui.modelling.steps.section_limit import OpenSectionLimiter


class TestOpenSectionLimiter:
    def test_default_maximum_is_two(self):
        assert OpenSectionLimiter().max_open == 2

    def test_two_sections_stay_open(self):
        limiter = OpenSectionLimiter(2)
        assert limiter.set_open('a', True) == []
        assert limiter.set_open('b', True) == []
        assert limiter.open_keys == ['a', 'b']

    def test_third_section_closes_the_first_opened(self):
        limiter = OpenSectionLimiter(2)
        limiter.set_open('a', True)
        limiter.set_open('b', True)
        assert limiter.set_open('c', True) == ['a']
        assert limiter.open_keys == ['b', 'c']
        assert not limiter.is_open('a')

    def test_order_is_the_order_of_opening(self):
        limiter = OpenSectionLimiter(2)
        limiter.set_open('a', True)
        limiter.set_open('b', True)
        limiter.set_open('a', False)
        limiter.set_open('a', True)
        # b opened before the second opening of a
        assert limiter.set_open('c', True) == ['b']

    def test_closing_gives_no_other_closes(self):
        limiter = OpenSectionLimiter(2)
        limiter.set_open('a', True)
        assert limiter.set_open('a', False) == []
        assert limiter.set_open('never_opened', False) == []
        assert limiter.open_keys == []

    def test_open_again_does_nothing(self):
        limiter = OpenSectionLimiter(2)
        limiter.set_open('a', True)
        assert limiter.set_open('a', True) == []
        assert limiter.open_keys == ['a']

    def test_other_maximum(self):
        limiter = OpenSectionLimiter(1)
        limiter.set_open('a', True)
        assert limiter.set_open('b', True) == ['a']
