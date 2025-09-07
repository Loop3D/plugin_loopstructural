#! python3

"""Processing provider module.
"""

# PyQGIS
from qgis.core import QgsProcessingProvider
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtGui import QIcon

# project
from loopstructural.__about__ import __icon_path__, __title__, __version__

# ############################################################################
# ########## Classes ###############
# ##################################


class LoopstructuralProvider(QgsProcessingProvider):
    """Processing provider class."""

    def loadAlgorithms(self):
        """Loads all algorithms belonging to this provider."""
        pass

    def id(self) -> str:
        """Unique provider id.

        Returns
        -------
        str
            Provider ID string used for identifying the provider (must be short and
            non-localised).
        """
        return "loopstructural"

    def name(self) -> str:
        """Provider name used in the GUI.

        Returns
        -------
        str
            Short, localised provider name.
        """
        return __title__

    def longName(self) -> str:
        """Longer provider name (may include version information).

        Returns
        -------
        str
            Localised long name for display in the GUI.
        """
        return self.tr("{} - Tools".format(__title__))

    def icon(self) -> QIcon:
        """Icon used for the provider inside the Processing toolbox menu.

        Returns
        -------
        QIcon
            Icon for the provider.
        """
        return QIcon(str(__icon_path__))

    def tr(self, message: str) -> str:
        """Translate a string using Qt translation API.

        Parameters
        ----------
        message : str
            String to be translated.

        Returns
        -------
        str
            Translated version of message.
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate(self.__class__.__name__, message)

    def versionInfo(self) -> str:
        """Provider version information.

        Returns
        -------
        str
            Version string for the provider (plugin version).
        """
        return __version__
