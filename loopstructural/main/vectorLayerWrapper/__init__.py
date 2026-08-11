"""QGIS <-> GeoPandas/pandas conversion helpers.

Split from a single 1262-line module into one file per concern:

- `_raster.py`: QgsRasterLayer -> GDAL dataset bridging
- `_dtype.py`: pandas dtype <-> QVariant type mapping and attribute conversion
- `_geometry.py`: QGIS <-> shapely geometry/CRS conversion
- `_sinks.py`: writing GeoDataFrames/DataFrames back out as QGIS layers/sinks

This `__init__` re-exports every previously public name so existing imports
(`from loopstructural.main.vectorLayerWrapper import qgsLayerToGeoDataFrame`,
etc.) keep working unchanged.
"""

from ._dtype import qvariantToFloat
from ._geometry import qgsLayerToDataFrame, qgsLayerToGeoDataFrame
from ._raster import qgsRasterToGdalDataset
from ._sinks import (
    GeoDataFrameToQgsLayer,
    QgsLayerFromDataFrame,
    QgsLayerFromGeoDataFrame,
    addGeoDataFrameToproject,
    dataframeToQgsLayer,
    dataframeToQgsTable,
    geodataframeToMemoryLayer,
    matrixToDict,
)

__all__ = [
    'GeoDataFrameToQgsLayer',
    'QgsLayerFromDataFrame',
    'QgsLayerFromGeoDataFrame',
    'addGeoDataFrameToproject',
    'dataframeToQgsLayer',
    'dataframeToQgsTable',
    'geodataframeToMemoryLayer',
    'matrixToDict',
    'qgsLayerToDataFrame',
    'qgsLayerToGeoDataFrame',
    'qgsRasterToGdalDataset',
    'qvariantToFloat',
]
