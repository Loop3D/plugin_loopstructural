#! python3

"""Processing provider for LoopStructural plugin."""

# PyQGIS
from qgis.core import QgsProcessingProvider
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtGui import QIcon

# project
from loopstructural.__about__ import __icon_path__, __title__, __version__
from .algorithms.interpolation.interpolation_algorithm import (
    LoopStructuralInterpolationAlgorithm,
)
from .algorithms.modelling.create_bounding_box import CreateBoundingBoxAlgorithm
from .algorithms.modelling.create_model import CreateModelAlgorithm
from .algorithms.modelling.create_and_add_foliation import CreateAndAddFoliationAlgorithm
from .algorithms.modelling.add_fault_topology import AddFaultTopologyAlgorithm
from .algorithms.modelling.create_and_add_fault import CreateAndAddFaultAlgorithm
# ############################################################################
# ########## Classes ###############
# ##################################


class LoopstructuralProvider(QgsProcessingProvider):
    """Processing provider class."""

    def loadAlgorithms(self):
        """Loads all algorithms belonging to this provider."""
        self.addAlgorithm(LoopStructuralInterpolationAlgorithm())
        self.addAlgorithm(CreateBoundingBoxAlgorithm())
        self.addAlgorithm(CreateModelAlgorithm())
        self.addAlgorithm(CreateAndAddFoliationAlgorithm())
        self.addAlgorithm(CreateAndAddFaultAlgorithm())
        self.addAlgorithm(AddFaultTopologyAlgorithm())
        pass

    def id(self) -> str:
        """Return unique provider id.

        Returns
        -------
        str
            Provider ID string used for identifying the provider (must be short and
            non-localised).
        """
        return "loopstructural"

    def name(self) -> str:
        """Return provider name used in the GUI.

        Returns
        -------
        str
            Short, localised provider name.
        """
        return __title__

    def longName(self) -> str:
        """Return longer provider name (may include version information).

        Returns
        -------
        str
            Localised long name for display in the GUI.
        """
        return self.tr("{} - Tools".format(__title__))

    def icon(self) -> QIcon:
        """Return icon used for the provider inside the Processing toolbox menu.

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
        """Return provider version information.

        Returns
        -------
        str
            Version string for the provider (plugin version).
        """
        return __version__
