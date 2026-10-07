"""The rule for the open sections of a page. This module does not import QGIS."""

DEFAULT_MAX_OPEN = 2


class OpenSectionLimiter:
    """Keep the number of open sections at or below a maximum.

    The sections are in the order in which the user opened them. When a section
    opens and the maximum is passed, the section that opened first closes.
    """

    def __init__(self, max_open=DEFAULT_MAX_OPEN):
        self.max_open = max_open
        self._open = []

    @property
    def open_keys(self):
        """The keys of the open sections, the oldest first."""
        return list(self._open)

    def is_open(self, key):
        return key in self._open

    def set_open(self, key, is_open):
        """Open or close a section. Return the keys of the sections that closed."""
        if not is_open:
            if key in self._open:
                self._open.remove(key)
            return []
        if key in self._open:
            return []
        self._open.append(key)
        closed = []
        while len(self._open) > self.max_open:
            closed.append(self._open.pop(0))
        return closed
