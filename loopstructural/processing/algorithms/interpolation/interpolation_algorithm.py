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
import tempfile
import dill as pickle

from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingContext,
    QgsProcessingException,
    QgsProcessingFeedback,
    QgsProcessingParameterExtent,
    QgsProcessingParameterNumber,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsProcessingParameterFileDestination,
)

from LoopStructural import GeologicalModel
from LoopStructural.datatypes import BoundingBox
import pandas as pd


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
            QgsProcessingParameterFileDestination(
                self.OUTPUT,
                "Output interpolator file (pickle)",
                fileFilter='Pickle files (*.pkl)'
            )
        )

    def processAlgorithm(
        self,
        parameters: dict[str, Any],
        context: QgsProcessingContext,
        feedback: QgsProcessingFeedback,
    ) -> dict[str, Any]:
        # Get input parameters
        value_layer = self.parameterAsSource(parameters, self.VALUE, context)
        value_field = self.parameterAsFields(parameters, self.VALUE_FIELD, context)

        gradient_layer = self.parameterAsSource(parameters, self.GRADIENT, context)
        strike_field = self.parameterAsFields(parameters, self.STRIKE_FIELD, context)
        dip_field = self.parameterAsFields(parameters, self.DIP_FIELD, context)
        
        extent = self.parameterAsExtent(parameters, self.EXTENT, context)
        pixel_size = self.parameterAsDouble(parameters, self.PIXEL_SIZE, context)
        
        # Validate that we have at least some data
        if value_layer is None and gradient_layer is None:
            raise QgsProcessingException(
                "At least one of value or gradient layers must be provided."
            )
        
        # Extract field names from lists
        value_field_name = value_field[0] if value_field else None
        strike_field_name = strike_field[0] if strike_field else None
        dip_field_name = dip_field[0] if dip_field else None
        
        feedback.pushInfo("Building interpolator from constraints...")
        
        # Create bounding box from extent
        if extent is None:
            raise QgsProcessingException("Output extent must be provided.")
        
        # Calculate z extent based on pixel size (arbitrary choice: 10x pixel size for depth)
        z_min = 0
        z_max = pixel_size * 10
        
        bbox = BoundingBox(
            origin=[extent.xMinimum(), extent.yMinimum(), z_min],
            maximum=[extent.xMaximum(), extent.yMaximum(), z_max]
        )
        
        # Build data DataFrame
        dfs = []
        
        # Add value constraints
        if value_layer is not None and value_field_name:
            feedback.pushInfo(f"Adding value constraints from field '{value_field_name}'...")
            value_df = self._extract_value_data(
                value_layer, value_field_name, feedback
            )
            if len(value_df) > 0:
                dfs.append(value_df)
                feedback.pushInfo(f"Added {len(value_df)} value constraints.")
            else:
                feedback.pushWarning("No valid value constraints found.")
        
        # Add gradient constraints from strike/dip
        if gradient_layer is not None and strike_field_name and dip_field_name:
            feedback.pushInfo(
                f"Adding gradient constraints from strike/dip fields '{strike_field_name}'/'{dip_field_name}'..."
            )
            gradient_df = self._extract_gradient_data(
                gradient_layer, strike_field_name, dip_field_name, feedback
            )
            if len(gradient_df) > 0:
                dfs.append(gradient_df)
                feedback.pushInfo(f"Added {len(gradient_df)} gradient constraints.")
            else:
                feedback.pushWarning("No valid gradient constraints found.")
        
        if not dfs:
            raise QgsProcessingException("No valid constraints found to build interpolator.")
        
        # Combine all data
        data = pd.concat(dfs, ignore_index=True)
        
        # Create geological model and build interpolator
        feedback.pushInfo("Building interpolator using GeologicalModel...")
        try:
            model = GeologicalModel(bbox)
            model.create_and_add_foliation('interpolated_field', data=data)
            feature = model['interpolated_field']
            interpolator = feature.interpolator
        except Exception as e:
            raise QgsProcessingException(f"Failed to build interpolator: {e}")
        
        # Save interpolator to pickle file
        out_path = self.parameterAsString(parameters, self.OUTPUT, context)
        if not out_path:
            tmp = tempfile.NamedTemporaryFile(suffix='.pkl', delete=False)
            out_path = tmp.name
            tmp.close()
        
        feedback.pushInfo(f"Saving interpolator to {out_path}...")
        try:
            with open(out_path, 'wb') as fh:
                pickle.dump(interpolator, fh)
        except Exception as e:
            raise QgsProcessingException(f"Failed to save interpolator to '{out_path}': {e}")
        
        feedback.pushInfo("Interpolator saved successfully.")
        return {self.OUTPUT: out_path}
    
    def _extract_value_data(
        self, 
        source,
        value_field: str,
        feedback: QgsProcessingFeedback
    ) -> pd.DataFrame:
        """Extract value constraints as pandas DataFrame."""
        rows = []
        for feat in source.getFeatures():
            geom = feat.geometry()
            if geom is None or geom.isEmpty():
                continue
            
            # Get value
            try:
                value = feat.attribute(value_field)
                if value is None:
                    continue
                value = float(value)
            except (ValueError, TypeError):
                continue
            
            # Extract points from geometry
            points = []
            if geom.isMultipart():
                if geom.type() == 0:  # Point
                    points = geom.asMultiPoint()
                elif geom.type() == 1:  # Line
                    for line in geom.asMultiPolyline():
                        points.extend(line)
            else:
                if geom.type() == 0:  # Point
                    points = [geom.asPoint()]
                elif geom.type() == 1:  # Line
                    points = geom.asPolyline()
            
            # Add data for each point
            for p in points:
                try:
                    x = p.x()
                    y = p.y()
                    z = p.z() if hasattr(p, 'z') else 0.0
                    rows.append({'X': x, 'Y': y, 'Z': z, 'val': value, 'feature_name': 'interpolated_field'})
                except Exception:
                    continue
        
        return pd.DataFrame(rows)
    
    def _extract_gradient_data(
        self,
        source,
        strike_field: str,
        dip_field: str,
        feedback: QgsProcessingFeedback
    ) -> pd.DataFrame:
        """Extract gradient constraints from strike/dip as pandas DataFrame."""
        rows = []
        for feat in source.getFeatures():
            geom = feat.geometry()
            if geom is None or geom.isEmpty():
                continue
            
            # Get strike and dip
            try:
                strike = feat.attribute(strike_field)
                dip = feat.attribute(dip_field)
                if strike is None or dip is None:
                    continue
                strike = float(strike)
                dip = float(dip)
            except (ValueError, TypeError):
                continue
            
            # Extract points from geometry (should be point geometry)
            points = []
            if geom.isMultipart():
                if geom.type() == 0:  # Point
                    points = geom.asMultiPoint()
            else:
                if geom.type() == 0:  # Point
                    points = [geom.asPoint()]
            
            # Add data for each point
            for p in points:
                try:
                    x = p.x()
                    y = p.y()
                    z = p.z() if hasattr(p, 'z') else 0.0
                    rows.append({
                        'X': x, 'Y': y, 'Z': z,
                        'strike': strike, 'dip': dip,
                        'feature_name': 'interpolated_field'
                    })
                except Exception:
                    continue
        
        return pd.DataFrame(rows)

    def createInstance(self) -> QgsProcessingAlgorithm:
        """Create a new instance of the algorithm."""
        return self.__class__()  # BasalContactsAlgorithm()
