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
    QgsProcessingParameterExtent,
    QgsProcessingParameterNumber,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField
)


class LoopStructuralInterpolationAlgorithm(QgsProcessingAlgorithm):
    """Processing algorithm to create basal contacts."""

    VALUE = "VALUE"
    GRADIENT = "GRADIENT"
    INEQUALITY = "INEQUALITY"
    STRIKE_FIELD = "STRIKE_FIELD"
    DIP_FIELD = "DIP_FIELD"
    INEQUALITY_UPPER_FIELD = "INEQUALITY_UPPER_FIELD"
    INEQUALITY_LOWER_FIELD = "INEQUALITY_LOWER_FIELD"
    VALUE_FIELD = "VALUE_FIELD"
    OUTPUT = "OUTPUT"
    EXTENT = "EXTENT"
    PIXEL_SIZE = "PIXEL_SIZE"

    def name(self) -> str:
        """Return the algorithm name."""
        return "loop: interpolation"

    def displayName(self) -> str:
        """Return the algorithm display name."""
        return "Loop3d: Interpolation"

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
                self.VALUE,
                "Value data",
                [QgsProcessing.TypeVectorPoint, QgsProcessing.TypeVectorLine],
                optional=True
            )
        )
        self.addParameter(
            QgsProcessingParameterField(
                self.VALUE_FIELD,
                "Field to interpolate",
                parentLayerParameterName=self.VALUE,
                type=QgsProcessingParameterField.DataType.Numeric,
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.GRADIENT,
                "Orientation data",
                [QgsProcessing.TypeVectorPoint],
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterField(
                self.STRIKE_FIELD,
                "Strike field",
                parentLayerParameterName=self.GRADIENT,
                type=QgsProcessingParameterField.DataType.Numeric,
                optional=True,
            )
        )
        self.addParameter(
                QgsProcessingParameterField(
                    self.DIP_FIELD,
                    "Dip field",
                    parentLayerParameterName=self.GRADIENT,
                    type=QgsProcessingParameterField.DataType.Numeric,
                    optional=True,
                )
            )
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INEQUALITY,
                "Inequality data",
                [QgsProcessing.TypeVectorPoint, QgsProcessing.TypeVectorLine],
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterField(
                self.INEQUALITY_UPPER_FIELD,
                "Upper bound field",
                parentLayerParameterName=self.INEQUALITY,
                type=QgsProcessingParameterField.DataType.Numeric,
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterField(
                self.INEQUALITY_LOWER_FIELD,
                "Lower bound field",
                parentLayerParameterName=self.INEQUALITY,
                type=QgsProcessingParameterField.DataType.Numeric,
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterExtent(
                self.EXTENT,
                "Output extent",
                defaultValue=None,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.PIXEL_SIZE,
                "Pixel size",
                type=QgsProcessingParameterNumber.Double,
                defaultValue=1.0,
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                "Interpolated Surface",
            )
        )
        pass

    def processAlgorithm(
        self,
        parameters: dict[str, Any],
        context: QgsProcessingContext,
        feedback: QgsProcessingFeedback,
    ) -> dict[str, Any]:
        value_layer = self.parameterAsSource(parameters, self.VALUE, context)
        value_field = self.parameterAsFields(parameters, self.VALUE_FIELD, context)

        gradient_layer = self.parameterAsSource(parameters, self.GRADIENT, context)
        strike_field = self.parameterAsFields(parameters, self.STRIKE_FIELD, context)
        dip_field = self.parameterAsFields(parameters, self.DIP_FIELD, context)

        inequality_layer = self.parameterAsSource(parameters, self.INEQUALITY, context)
        upper_field = self.parameterAsFields(parameters, self.INEQUALITY_UPPER_FIELD, context)
        lower_field = self.parameterAsFields(parameters, self.INEQUALITY_LOWER_FIELD, context)
        
        extent = self.parameterAsExtent(parameters, self.EXTENT, context)
        
        print(extent)

    def createInstance(self) -> QgsProcessingAlgorithm:
        """Create a new instance of the algorithm."""
        return self.__class__()  # BasalContactsAlgorithm()
