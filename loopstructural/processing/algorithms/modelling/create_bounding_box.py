"""
***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

from typing import Any, Optional

from qgis import processing
from qgis.core import (
    QgsFeatureSink,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingContext,
    QgsProcessingException,
    QgsProcessingFeedback,
    QgsProcessingParameterString,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterNumber,
    QgsProcessingOutputString,
)
from loopstructural.main.api import create_bounding_box_json

class CreateBoundingBoxAlgorithm(QgsProcessingAlgorithm):
    """Processing algorithm to create bounding box."""

    LAYER = "LAYER"
    XMIN = "XMIN"
    XMAX = "XMAX"
    YMIN = "YMIN"
    YMAX = "YMAX"
    ZMIN = "ZMIN"
    ZMAX = "ZMAX"
    BBOX_JSON = "BBOX_JSON"

    def name(self) -> str:
        """Return the algorithm name."""
        return "loopstructural:create_bounding_box"

    def displayName(self) -> str:
        """Return the algorithm display name."""
        return "Loop3d: Create Bounding Box"

    def group(self) -> str:
        """Return the algorithm group name."""
        return "Loop3d"

    def groupId(self) -> str:
        """Return the algorithm group ID."""
        return "loop3d"

    def initAlgorithm(self, config: Optional[dict[str, Any]] = None) -> None:
        """Initialize the algorithm parameters."""
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.LAYER,
                "Geology Polygons",
               
                optional=True
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.XMIN,
                "X Minimum",
                type=QgsProcessingParameterNumber.Double,
                optional=True,
                defaultValue=-9999,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.XMAX,
                "X Maximum",
                type=QgsProcessingParameterNumber.Double,
                optional=True,
                defaultValue=-9999,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.YMIN,
                "Y Minimum",
                type=QgsProcessingParameterNumber.Double,
                optional=True,
                defaultValue=-9999,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.YMAX,
                "Y Maximum",
                type=QgsProcessingParameterNumber.Double,
                optional=True,
                defaultValue=-9999,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.ZMIN,
                "Z Minimum",
                type=QgsProcessingParameterNumber.Double,
                optional=True,
                defaultValue=-9999,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.ZMAX,
                "Z Maximum",
                type=QgsProcessingParameterNumber.Double,
                optional=True,
                defaultValue=-9999,
            )
        )

        # Declare the bounding box JSON output so the processing framework can expose it
        # Add as an output so it can be connected to downstream algorithms
        self.addOutput(
            QgsProcessingOutputString(
                self.BBOX_JSON,
                "Bounding Box (JSON)"
            )
        )
       
        

    def processAlgorithm(
        self,
        parameters: dict[str, Any],
        context: QgsProcessingContext,
        feedback: QgsProcessingFeedback,
    ) -> dict[str, Any]:
        # parameterAsVectorLayer returns a QgsVectorLayer which has an extent() method
        value_layer = self.parameterAsVectorLayer(parameters, self.LAYER, context)
        xmin = self.parameterAsDouble(parameters, self.XMIN, context)
        xmax = self.parameterAsDouble(parameters, self.XMAX, context)
        ymin = self.parameterAsDouble(parameters, self.YMIN, context)
        ymax = self.parameterAsDouble(parameters, self.YMAX, context)
        zmin = self.parameterAsDouble(parameters, self.ZMIN, context)
        zmax = self.parameterAsDouble(parameters, self.ZMAX, context)
        bbox_json = create_bounding_box_json(value_layer, xmin, xmax, ymin, ymax, zmin, zmax)
        if bbox_json is None:
            raise QgsProcessingException("Failed to create bounding box JSON.")
        print(f"Created bounding box JSON: {type(bbox_json)}")
        # Return the JSON string as the algorithm result so it can be piped to other processing tools
        return { self.BBOX_JSON: bbox_json }

    def createInstance(self) -> QgsProcessingAlgorithm:
        """Create a new instance of the algorithm."""
        return self.__class__()  # BasalContactsAlgorithm()
