from .vectorLayerWrapper import qgsLayerToDataFrame
from qgis.core import (QgsWkbTypes, QgsProcessingParameterField)
import numpy as np
import pandas as pd
from LoopStructural.interpolation import InterpolatorBuilder
def interpolate_scalar_field(value_layer = None, value_field = None,
                             gradient_layer = None, strike_field = None, dip_field = None,
                             inequality_layer = None, upper_field = None, lower_field = None,
                             extent = None, cell_size = 100,
                             output_path = None):
    """
    Interpolates a scalar field using the provided value points/lines,
    optional gradient (orientation) data, and optional inequality constraints.
    
    Parameters:
    - value_layer: QgsVectorLayer with point/line features containing values to interpolate.
    - value_field: Name of the numeric field in value_layer to interpolate.
    - gradient_layer: Optional QgsVectorLayer with point features containing orientation data.
    - strike_field: Name of the numeric field in gradient_layer for strike angles (degrees).
    - dip_field: Name of the numeric field in gradient_layer for dip angles (degrees).
    - inequality_layer: Optional QgsVectorLayer with point/line features for inequality constraints.
    - upper_field: Name of the numeric field in inequality_layer for upper bounds.
    - lower_field: Name of the numeric field in inequality_layer for lower bounds.
    - extent: QgsRectangle defining the interpolation extent. If None, use value_layer extent.
    - cell_size: Cell size for the output raster grid.
    - output_path: File path to save the output raster. If None, returns raster object.
    
    Returns:
    - If output_path is provided, saves raster to file and returns None.
    - If output_path is None, returns the generated raster object.
    """
    extent 
    # Validate input layers and fields
    if value_layer is None or value_field is None:
        raise ValueError("Value layer and value field must be provided.")
    
    if value_layer.geometryType() not in [QgsWkbTypes.PointGeometry, QgsWkbTypes.LineGeometry]:
        raise ValueError("Value layer must be of point or line geometry type.")
    
    if gradient_layer is not None:
        if strike_field is None or dip_field is None:
            raise ValueError("Both strike and dip fields must be provided if gradient layer is used.")
        if gradient_layer.geometryType() != QgsWkbTypes.PointGeometry:
            raise ValueError("Gradient layer must be of point geometry type.")
    
    if inequality_layer is not None:
        if upper_field is None and lower_field is None:
            raise ValueError("At least one of upper or lower fields must be provided if inequality layer is used.")
        if inequality_layer.geometryType() not in [QgsWkbTypes.PointGeometry, QgsWkbTypes.LineGeometry]:
            raise ValueError("Inequality layer must be of point or line geometry type.")
    
    if inequality_layer is None and gradient_layer is None and value_layer is None:
        raise ValueError("At least one of value, gradient, or inequality layers must be provided.")

    interpolator_builder = InterpolatorBuilder()
    
    # Convert layers to DataFrames
    value_df = qgsLayerToDataFrame(value_layer) if value_layer else None
    gradient_df = qgsLayerToDataFrame(gradient_layer) if gradient_layer else None
    inequality_df = qgsLayerToDataFrame(inequality_layer) if inequality_layer else None

    