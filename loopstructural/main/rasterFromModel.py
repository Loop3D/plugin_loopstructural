import os
import tempfile
import uuid

import numpy as np
from osgeo import gdal, osr
from qgis.core import QgsRasterLayer

from .geometry.mapGrid import createGrid


def callableToRaster(callable, dtm, bounding_box, crs, layer_name):
    """Convert a feature to a raster and store it in QGIS as a temporary layer.

    :param feature: The object that has an `evaluate_value` method for computing values.
    :param dtm: Digital terrain model (if needed for processing).
    :param bounding_box: Object with `origin`, `maximum`, `step_vector`, and `nsteps`.
    :param crs: Coordinate reference system (QGIS CRS object).
    """
    # Create grid of points based on bounding_box
    points = createGrid(bounding_box, dtm)  # This function should return a list of coordinates

    # Evaluate feature at each point
    values = callable(points)
    # Reshape values into a 2D NumPy array (Fortran order)
    values = np.array(values).reshape((bounding_box.nsteps[1], bounding_box.nsteps[0]), order='F')

    # Define raster metadata
    rows, cols = values.shape
    values = np.flipud(values)  # Flip array vertically to match raster orientation
    geotransform = [
        bounding_box.global_origin[0],  # x_min
        bounding_box.step_vector[0],  # Pixel width (step in X)
        0,  # No rotation (affine transform)
        bounding_box.global_origin[1]
        + bounding_box.step_vector[1] * bounding_box.nsteps[1],  # y_min (origin at bottom-left)
        0,  # No rotation
        -bounding_box.step_vector[1],  # Pixel height (negative so origin is bottom-left)
    ]

    # Create an in-memory raster using `/vsimem/`
    temp_dir = tempfile.gettempdir()
    temp_raster_path = os.path.join(temp_dir, f'temp_raster_{uuid.uuid4().hex}.tif')
    driver = gdal.GetDriverByName("GTiff")
    ds = driver.Create(temp_raster_path, cols, rows, 1, gdal.GDT_Float32)

    # Set georeferencing
    ds.SetGeoTransform(geotransform)
    srs = osr.SpatialReference()
    srs.ImportFromWkt(crs.toWkt())  # Convert QGIS CRS to GDAL WKT
    ds.SetProjection(srs.ExportToWkt())

    # Write data to raster band
    band = ds.GetRasterBand(1)
    band.WriteArray(values)
    band.SetNoDataValue(-9999)  # Optional: Set NoData value
    band.FlushCache()

    # Close dataset
    ds = None

    # Load raster into QGIS as a temporary layer
    temp_layer = QgsRasterLayer(temp_raster_path, layer_name, "gdal")
    temp_layer.setCustomProperty("temporary", True)

    return temp_layer
