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
import numpy as np
import dill as pickle

from qgis.core import (
    QgsFeature,
    QgsFeatureSink,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsPointXY,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingContext,
    QgsProcessingException,
    QgsProcessingFeedback,
    QgsProcessingParameterEnum,
    QgsProcessingParameterExtent,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterFile,
    QgsProcessingParameterNumber,
    QgsWkbTypes,
)
from qgis.PyQt.QtCore import QVariant


class LoopStructuralInterpolationEvaluationAlgorithm(QgsProcessingAlgorithm):
    """Processing algorithm to evaluate a LoopStructural interpolator."""

    INTERPOLATOR_FILE = "INTERPOLATOR_FILE"
    EVALUATION_TYPE = "EVALUATION_TYPE"
    EXTENT = "EXTENT"
    PIXEL_SIZE = "PIXEL_SIZE"
    Z_MIN = "Z_MIN"
    Z_MAX = "Z_MAX"
    Z_STEP = "Z_STEP"
    POINT_LAYER = "POINT_LAYER"
    OUTPUT = "OUTPUT"

    # Evaluation types
    EVAL_RASTER = 0
    EVAL_3D_GRID = 1
    EVAL_POINTS = 2

    def name(self) -> str:
        """Return the algorithm name."""
        return "loop: interpolation_evaluation"

    def displayName(self) -> str:
        """Return the algorithm display name."""
        return "Loop3d: Interpolation Evaluation"

    def group(self) -> str:
        """Return the algorithm group name."""
        return "Loop3d"

    def groupId(self) -> str:
        """Return the algorithm group ID."""
        return "loop3d"

    def initAlgorithm(self, config: Optional[dict[str, Any]] = None) -> None:
        """Initialize the algorithm parameters."""
        # Input interpolator file
        self.addParameter(
            QgsProcessingParameterFile(
                self.INTERPOLATOR_FILE,
                "Input interpolator file (pickle)",
                behavior=QgsProcessingParameterFile.File,
                fileFilter='Pickle files (*.pkl)'
            )
        )

        # Evaluation type
        self.addParameter(
            QgsProcessingParameterEnum(
                self.EVALUATION_TYPE,
                "Evaluation type",
                options=['Raster (2D)', '3D Grid (Points)', 'Point Layer'],
                defaultValue=self.EVAL_RASTER
            )
        )

        # For raster and 3D grid evaluation
        self.addParameter(
            QgsProcessingParameterExtent(
                self.EXTENT,
                "Evaluation extent",
                optional=True
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                self.PIXEL_SIZE,
                "Pixel/grid size",
                type=QgsProcessingParameterNumber.Double,
                defaultValue=100.0,
                optional=True
            )
        )

        # For 3D grid evaluation
        self.addParameter(
            QgsProcessingParameterNumber(
                self.Z_MIN,
                "Z minimum (for 3D grid)",
                type=QgsProcessingParameterNumber.Double,
                defaultValue=0.0,
                optional=True
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                self.Z_MAX,
                "Z maximum (for 3D grid)",
                type=QgsProcessingParameterNumber.Double,
                defaultValue=1000.0,
                optional=True
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                self.Z_STEP,
                "Z step size (for 3D grid)",
                type=QgsProcessingParameterNumber.Double,
                defaultValue=100.0,
                optional=True
            )
        )

        # For point layer evaluation
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.POINT_LAYER,
                "Point layer to evaluate",
                [QgsProcessing.TypeVectorPoint],
                optional=True
            )
        )

        # Output - feature sink for points, raster for raster output
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                "Output",
            )
        )

    def processAlgorithm(
        self,
        parameters: dict[str, Any],
        context: QgsProcessingContext,
        feedback: QgsProcessingFeedback,
    ) -> dict[str, Any]:
        # Load interpolator
        interpolator_path = self.parameterAsString(parameters, self.INTERPOLATOR_FILE, context)
        if not interpolator_path:
            raise QgsProcessingException("Interpolator file must be provided.")

        feedback.pushInfo(f"Loading interpolator from {interpolator_path}...")
        try:
            with open(interpolator_path, 'rb') as fh:
                interpolator = pickle.load(fh)
        except Exception as e:
            raise QgsProcessingException(f"Failed to load interpolator from '{interpolator_path}': {e}")

        # Get evaluation type
        eval_type = self.parameterAsEnum(parameters, self.EVALUATION_TYPE, context)

        if eval_type == self.EVAL_RASTER:
            return self._evaluate_raster(parameters, context, feedback, interpolator)
        elif eval_type == self.EVAL_3D_GRID:
            return self._evaluate_3d_grid(parameters, context, feedback, interpolator)
        elif eval_type == self.EVAL_POINTS:
            return self._evaluate_points(parameters, context, feedback, interpolator)
        else:
            raise QgsProcessingException(f"Unknown evaluation type: {eval_type}")

    def _evaluate_raster(
        self,
        parameters: dict[str, Any],
        context: QgsProcessingContext,
        feedback: QgsProcessingFeedback,
        interpolator
    ) -> dict[str, Any]:
        """Evaluate interpolator on a 2D raster grid at z=0."""
        extent = self.parameterAsExtent(parameters, self.EXTENT, context)
        if extent is None or extent.isNull():
            raise QgsProcessingException("Extent must be provided for raster evaluation.")

        pixel_size = self.parameterAsDouble(parameters, self.PIXEL_SIZE, context)

        feedback.pushInfo("Evaluating interpolator on raster grid...")

        # Create grid of evaluation points
        x_coords = np.arange(extent.xMinimum(), extent.xMaximum() + pixel_size, pixel_size)
        y_coords = np.arange(extent.yMinimum(), extent.yMaximum() + pixel_size, pixel_size)
        xx, yy = np.meshgrid(x_coords, y_coords)
        
        # Flatten and create evaluation points (x, y, z=0)
        points = np.column_stack([xx.ravel(), yy.ravel(), np.zeros(xx.size)])

        # Evaluate interpolator
        try:
            values = interpolator.evaluate_value(points)
        except Exception as e:
            raise QgsProcessingException(f"Failed to evaluate interpolator: {e}")

        # Create output as point layer with values
        fields = QgsFields()
        fields.append(QgsField('value', QVariant.Double))

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            fields,
            QgsWkbTypes.Point,
            context.project().crs() if context.project() else None
        )

        if sink is None:
            raise QgsProcessingException("Could not create output sink.")

        # Add features
        total = len(points)
        for i, (point, value) in enumerate(zip(points, values)):
            if feedback.isCanceled():
                break

            feat = QgsFeature()
            feat.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(point[0], point[1])))
            feat.setAttributes([float(value)])
            sink.addFeature(feat, QgsFeatureSink.FastInsert)

            if i % 100 == 0:
                feedback.setProgress(int(100 * i / total))

        feedback.pushInfo(f"Evaluated {len(points)} points.")
        return {self.OUTPUT: dest_id}

    def _evaluate_3d_grid(
        self,
        parameters: dict[str, Any],
        context: QgsProcessingContext,
        feedback: QgsProcessingFeedback,
        interpolator
    ) -> dict[str, Any]:
        """Evaluate interpolator on a 3D grid."""
        extent = self.parameterAsExtent(parameters, self.EXTENT, context)
        if extent is None or extent.isNull():
            raise QgsProcessingException("Extent must be provided for 3D grid evaluation.")

        pixel_size = self.parameterAsDouble(parameters, self.PIXEL_SIZE, context)
        z_min = self.parameterAsDouble(parameters, self.Z_MIN, context)
        z_max = self.parameterAsDouble(parameters, self.Z_MAX, context)
        z_step = self.parameterAsDouble(parameters, self.Z_STEP, context)

        feedback.pushInfo("Evaluating interpolator on 3D grid...")

        # Create grid of evaluation points
        x_coords = np.arange(extent.xMinimum(), extent.xMaximum() + pixel_size, pixel_size)
        y_coords = np.arange(extent.yMinimum(), extent.yMaximum() + pixel_size, pixel_size)
        z_coords = np.arange(z_min, z_max + z_step, z_step)
        
        xx, yy, zz = np.meshgrid(x_coords, y_coords, z_coords)
        
        # Flatten and create evaluation points
        points = np.column_stack([xx.ravel(), yy.ravel(), zz.ravel()])

        # Evaluate interpolator
        try:
            values = interpolator.evaluate_value(points)
        except Exception as e:
            raise QgsProcessingException(f"Failed to evaluate interpolator: {e}")

        # Create output as 3D point layer with values
        fields = QgsFields()
        fields.append(QgsField('x', QVariant.Double))
        fields.append(QgsField('y', QVariant.Double))
        fields.append(QgsField('z', QVariant.Double))
        fields.append(QgsField('value', QVariant.Double))

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            fields,
            QgsWkbTypes.PointZ,
            context.project().crs() if context.project() else None
        )

        if sink is None:
            raise QgsProcessingException("Could not create output sink.")

        # Add features
        total = len(points)
        for i, (point, value) in enumerate(zip(points, values)):
            if feedback.isCanceled():
                break

            feat = QgsFeature()
            feat.setGeometry(
                QgsGeometry.fromPointXY(QgsPointXY(point[0], point[1]))
            )
            feat.setAttributes([float(point[0]), float(point[1]), float(point[2]), float(value)])
            sink.addFeature(feat, QgsFeatureSink.FastInsert)

            if i % 100 == 0:
                feedback.setProgress(int(100 * i / total))

        feedback.pushInfo(f"Evaluated {len(points)} points.")
        return {self.OUTPUT: dest_id}

    def _evaluate_points(
        self,
        parameters: dict[str, Any],
        context: QgsProcessingContext,
        feedback: QgsProcessingFeedback,
        interpolator
    ) -> dict[str, Any]:
        """Evaluate interpolator on an existing point layer."""
        point_layer = self.parameterAsSource(parameters, self.POINT_LAYER, context)
        if point_layer is None:
            raise QgsProcessingException("Point layer must be provided for point evaluation.")

        feedback.pushInfo("Evaluating interpolator on point layer...")

        # Extract points
        points = []
        features = []
        for feat in point_layer.getFeatures():
            geom = feat.geometry()
            if geom is None or geom.isEmpty():
                continue

            if geom.isMultipart():
                pts = geom.asMultiPoint()
            else:
                pts = [geom.asPoint()]

            for p in pts:
                try:
                    x = p.x()
                    y = p.y()
                    z = p.z() if hasattr(p, 'z') else 0.0
                    points.append([x, y, z])
                    features.append(feat)
                except Exception:
                    continue

        if not points:
            raise QgsProcessingException("No valid points found in input layer.")

        points = np.array(points)

        # Evaluate interpolator
        try:
            values = interpolator.evaluate_value(points)
        except Exception as e:
            raise QgsProcessingException(f"Failed to evaluate interpolator: {e}")

        # Create output fields (copy from input + add value field)
        fields = QgsFields(point_layer.fields())
        fields.append(QgsField('interpolated_value', QVariant.Double))

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            fields,
            point_layer.wkbType(),
            point_layer.sourceCrs()
        )

        if sink is None:
            raise QgsProcessingException("Could not create output sink.")

        # Add features with interpolated values
        for i, (feat, value) in enumerate(zip(features, values)):
            if feedback.isCanceled():
                break

            out_feat = QgsFeature(fields)
            out_feat.setGeometry(feat.geometry())
            out_feat.setAttributes(feat.attributes() + [float(value)])
            sink.addFeature(out_feat, QgsFeatureSink.FastInsert)

            if i % 100 == 0:
                feedback.setProgress(int(100 * i / len(features)))

        feedback.pushInfo(f"Evaluated {len(points)} points.")
        return {self.OUTPUT: dest_id}

    def createInstance(self) -> QgsProcessingAlgorithm:
        """Create a new instance of the algorithm."""
        return self.__class__()
