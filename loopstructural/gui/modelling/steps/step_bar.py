"""The row of step buttons at the top of the modelling dock."""

from qgis.core import QgsApplication
from qgis.PyQt.QtCore import QSize, Qt, pyqtSignal
from qgis.PyQt.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from qgis.PyQt.QtWidgets import QButtonGroup, QHBoxLayout, QSizePolicy, QToolButton, QWidget

from .status import Status, StepCheck

_STATUS_WORDS = {
    Status.DONE: 'done',
    Status.PROBLEM: 'has a problem',
    Status.NOT_STARTED: 'not done',
}


def _not_started_icon(size=16) -> QIcon:
    """Draw a hollow circle. The shape is not the same as the shape of the
    other two icons, so the status does not depend on colour."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(QColor('#7f7f7f'), 1.5))
    painter.drawEllipse(2, 2, size - 4, size - 4)
    painter.end()
    return QIcon(pixmap)


def status_icon(status: Status) -> QIcon:
    """Return the icon of a status: a check, a warning triangle or a hollow circle."""
    if status == Status.DONE:
        return QgsApplication.getThemeIcon('mIconSuccess.svg')
    if status == Status.PROBLEM:
        return QgsApplication.getThemeIcon('mIconWarning.svg')
    return _not_started_icon()


class StepBar(QWidget):
    """A row of buttons, one for each step, with the status of the step.

    Parameters
    ----------
    steps : list of tuple
        ``(key, title)`` for each step, in order.
    """

    currentChanged = pyqtSignal(int)

    def __init__(self, steps, parent=None):
        super().__init__(parent)
        self._keys = [key for key, _title in steps]
        self._titles = {key: title for key, title in steps}
        self._checks = {}
        self._buttons = []
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        for index, (key, title) in enumerate(steps):
            button = QToolButton(self)
            button.setCheckable(True)
            button.setText(f"{index + 1} {title}")
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            button.setIcon(status_icon(Status.NOT_STARTED))
            button.setIconSize(QSize(14, 14))
            button.setAutoRaise(True)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            button.setToolTip(f"Step {index + 1}: {title}")
            self._group.addButton(button, index)
            layout.addWidget(button)
            self._buttons.append(button)
        self._buttons[0].setChecked(True)
        self._group.idClicked.connect(self.currentChanged.emit)

    @property
    def count(self):
        return len(self._buttons)

    def current_index(self):
        return self._group.checkedId()

    def set_current_index(self, index):
        """Select a step. This does not emit `currentChanged`."""
        if 0 <= index < len(self._buttons):
            self._buttons[index].setChecked(True)

    def set_checks(self, checks):
        """Show the check result of each step.

        Parameters
        ----------
        checks : dict
            Step key -> `StepCheck`. The buttons change only if a result
            changed.
        """
        for index, key in enumerate(self._keys):
            check = checks.get(key)
            if check is None or check == self._checks.get(key):
                continue
            self._checks[key] = check
            button = self._buttons[index]
            button.setIcon(status_icon(check.status))
            title = self._titles[key]
            lines = [f"Step {index + 1}: {title} - {_STATUS_WORDS[check.status]}"]
            lines.extend(f"- {message}" for message in check.messages)
            button.setToolTip("\n".join(lines))

    def check(self, key) -> StepCheck:
        return self._checks.get(key, StepCheck())
