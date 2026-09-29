from unittest.mock import Mock

import numpy as np
import pytest
from osgeo import gdal, osr
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsPointXY,
    QgsProject,
    QgsRasterLayer,
)

from loopstructural.main.data_manager import ModellingDataManager

DEM_VALUE = 460.0
MODEL_CRS = "EPSG:32755"


def _write_geographic_dem(path):
    """Write a small constant-value GeoTIFF in EPSG:4326 over (147E, 42S)."""
    driver = gdal.GetDriverByName("GTiff")
    dataset = driver.Create(str(path), 10, 10, 1, gdal.GDT_Float32)
    dataset.SetGeoTransform((146.9, 0.02, 0.0, -41.9, 0.0, -0.02))
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    dataset.SetProjection(srs.ExportToWkt())
    dataset.GetRasterBand(1).WriteArray(np.full((10, 10), DEM_VALUE, dtype=np.float32))
    dataset.FlushCache()
    dataset = None


@pytest.fixture
def data_manager(tmp_path):
    path = tmp_path / "dem.tif"
    _write_geographic_dem(path)
    dem_layer = QgsRasterLayer(str(path), "dem")
    assert dem_layer.isValid()
    manager = ModellingDataManager(project=QgsProject.instance(), mapCanvas=Mock(), logger=Mock())
    manager.set_model_manager(Mock())
    manager.set_model_crs(QgsCoordinateReferenceSystem(MODEL_CRS), use_project_crs=False)
    manager.set_dem_layer(dem_layer)
    manager.set_use_dem(True)
    return manager


def _dem_centre_in_model_crs():
    transform = QgsCoordinateTransform(
        QgsCoordinateReferenceSystem("EPSG:4326"),
        QgsCoordinateReferenceSystem(MODEL_CRS),
        QgsProject.instance(),
    )
    return transform.transform(QgsPointXY(147.0, -42.0))


def test_dem_in_another_crs_is_sampled_at_model_coordinates(data_manager):
    """The DEM is sampled after the model (x, y) is transformed to the DEM CRS."""
    centre = _dem_centre_in_model_crs()
    assert data_manager.dem_function(centre.x(), centre.y()) == pytest.approx(DEM_VALUE)


def test_point_outside_the_dem_gives_zero(data_manager):
    centre = _dem_centre_in_model_crs()
    assert data_manager.dem_function(centre.x() + 1e6, centre.y()) == 0.0
