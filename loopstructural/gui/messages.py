"""Show the result of an action without a modal dialog."""

from qgis.core import Qgis, QgsMessageLog
from qgis.utils import iface


def push_success(title: str, text: str, duration: int = 5):
    """Show a success message in the message bar of QGIS.

    Use a `QMessageBox` only for an error that stops an action, and for the
    confirmation before a destructive action.
    """
    if iface is not None:
        iface.messageBar().pushSuccess(title, text, duration=duration)
    else:
        # No main window, for example in the tests
        QgsMessageLog.logMessage(f"{title}: {text}", "LoopStructural", Qgis.MessageLevel.Success)


def push_info(title: str, text: str, duration: int = 5):
    """Show an information message in the message bar of QGIS."""
    if iface is not None:
        iface.messageBar().pushInfo(title, text, duration=duration)
    else:
        QgsMessageLog.logMessage(f"{title}: {text}", "LoopStructural", Qgis.MessageLevel.Info)


def push_warning(title: str, text: str, duration: int = 10):
    """Show a warning in the message bar of QGIS, for a result that is not an error."""
    if iface is not None:
        iface.messageBar().pushWarning(title, text, duration=duration)
    else:
        QgsMessageLog.logMessage(f"{title}: {text}", "LoopStructural", Qgis.MessageLevel.Warning)
