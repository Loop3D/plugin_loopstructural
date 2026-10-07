"""A stack of collapsible sections that limits the height of a page.

`OpenSectionLimiter` has the rule and does not need Qt. `SectionStack` shows
the sections and saves the state in the widget settings of the data manager.
"""

from qgis.gui import QgsCollapsibleGroupBox
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QFrame, QScrollArea, QVBoxLayout, QWidget

from .section_limit import DEFAULT_MAX_OPEN, OpenSectionLimiter


def page_scroll_area(widget, parent=None):
    """Return the scroll area of a page. A page has only this one scroll area."""
    scroll = QScrollArea(parent)
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setWidget(widget)
    return scroll


class SectionStack(QWidget):
    """A vertical stack of `QgsCollapsibleGroupBox` sections.

    At most ``max_open`` sections are open. A collapsed section can show a
    summary of its value in its title, for example "Geology layer: Geology".

    Parameters
    ----------
    name : str
        The name for the saved state. Use one name for each stack.
    data_manager : optional
        The state of the sections is saved in its widget settings.
    """

    def __init__(self, parent=None, name='sections', data_manager=None, max_open=DEFAULT_MAX_OPEN):
        super().__init__(parent)
        self.name = name
        self.data_manager = data_manager
        self.limiter = OpenSectionLimiter(max_open)
        self._sections = {}  # key -> (group, title, summary)
        self._updating = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._layout = layout

    @property
    def _settings_key(self):
        return f'section_stack_{self.name}'

    def _saved_state(self):
        if self.data_manager is None:
            return {}
        return dict(self.data_manager.get_widget_settings(self._settings_key, {}) or {})

    def _save_state(self):
        if self.data_manager is not None:
            self.data_manager.set_widget_settings(
                self._settings_key, {key: self.is_open(key) for key in self._sections}
            )

    def add_section(
        self, widget, key, title, *, summary=None, collapsed=False, index=None
    ):
        """Add a section and return its group box.

        ``widget`` is the content, or a `QgsCollapsibleGroupBox` that the stack
        uses as the section. ``summary`` is a function that returns the text for
        the title of a collapsed section. A saved state replaces ``collapsed``.
        """
        if isinstance(widget, QgsCollapsibleGroupBox):
            group = widget
            group.setTitle(title)
        else:
            group = QgsCollapsibleGroupBox(title)
            group_layout = QVBoxLayout(group)
            group_layout.addWidget(widget)
        saved = self._saved_state()
        if key in saved:
            collapsed = not saved[key]
        self._sections[key] = (group, title, summary)
        if index is None:
            self._layout.addWidget(group)
        else:
            self._layout.insertWidget(index, group)
        self._updating = True
        try:
            group.setCollapsed(collapsed)
            for closed in self.limiter.set_open(key, not collapsed):
                self._set_group_collapsed(closed, True)
        finally:
            self._updating = False
        group.collapsedStateChanged.connect(
            lambda is_collapsed, k=key: self._on_collapsed_changed(k, is_collapsed)
        )
        self.refresh_summaries()
        return group

    def addWidget(self, widget):
        """Add a group box as a section, or any other widget as it is.

        This lets the code that fills a layout fill a stack.
        """
        if isinstance(widget, QgsCollapsibleGroupBox) and widget.title():
            title = widget.title()
            self.add_section(widget, title, title, collapsed=widget.isCollapsed())
        else:
            self._layout.addWidget(widget)

    def section(self, key):
        return self._sections[key][0]

    def is_open(self, key):
        return self.limiter.is_open(key)

    def set_open(self, key, is_open):
        """Open or close a section, with the same rules as a click of the user."""
        self.section(key).setCollapsed(not is_open)

    def _set_group_collapsed(self, key, collapsed):
        group = self._sections[key][0]
        group.setCollapsed(collapsed)
        self._update_title(key)

    def _on_collapsed_changed(self, key, is_collapsed):
        if self._updating:
            return
        self._updating = True
        try:
            for closed in self.limiter.set_open(key, not is_collapsed):
                self._set_group_collapsed(closed, True)
        finally:
            self._updating = False
        self.refresh_summaries()
        self._save_state()

    def _update_title(self, key):
        group, title, summary = self._sections[key]
        text = title
        if summary is not None and group.isCollapsed():
            try:
                value = summary()
            except Exception:
                value = ''
            if value:
                text = f"{title}: {value}"
        group.setTitle(text)

    def refresh_summaries(self):
        """Write the summary into the title of each collapsed section."""
        for key in self._sections:
            self._update_title(key)

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh_summaries()
