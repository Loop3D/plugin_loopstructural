import logging
import os
import tempfile

from osgeo import gdal
from qgis import processing
from qgis.core import QgsRasterLayer

logger = logging.getLogger(__name__)


def qgsRasterToGdalDataset(rlayer: QgsRasterLayer):
    """
    Convert a QgsRasterLayer to an osgeo.gdal.Dataset (read-only).
    If the raster is non-file-based (e.g. WMS/WCS/virtual), we create a temp GeoTIFF via gdal:translate.
    Returns a gdal.Dataset or None.
    """
    if rlayer is None or not rlayer.isValid():
        return None

    # Try direct open on file-backed layers
    candidates = []
    try:
        candidates.append(rlayer.source())
    except Exception:
        logger.debug("Could not read rlayer.source()", exc_info=True)
    try:
        if rlayer.dataProvider():
            candidates.append(rlayer.dataProvider().dataSourceUri())
    except Exception:
        logger.debug("Could not read rlayer.dataProvider().dataSourceUri()", exc_info=True)

    tried = set()
    for uri in candidates:
        if not uri:
            continue
        if uri in tried:
            continue
        tried.add(uri)

        # Strip QGIS pipe options: "path.tif|layername=..." → "path.tif"
        base_uri = uri.split("|")[0]

        # Some providers store “SUBDATASET:” URIs; gdal.OpenEx can usually handle them directly.
        ds = gdal.OpenEx(base_uri, gdal.OF_RASTER | gdal.OF_READONLY)
        if ds is not None:
            return ds

    # If we’re here, it’s likely non-file-backed. Export to a temp GeoTIFF.
    tmpdir = tempfile.gettempdir()
    tmp_path = os.path.join(tmpdir, f"m2l_dtm_{rlayer.id()}.tif")

    # Use GDAL Translate via QGIS processing (avoids CRS pitfalls)
    processing.run(
        "gdal:translate",
        {
            "INPUT": rlayer,  # QGIS accepts the layer object here
            "TARGET_CRS": None,
            "NODATA": None,
            "COPY_SUBDATASETS": False,
            "OPTIONS": "",
            "EXTRA": "",
            "DATA_TYPE": 0,  # Use input data type
            "OUTPUT": tmp_path,
        },
    )

    ds = gdal.OpenEx(tmp_path, gdal.OF_RASTER | gdal.OF_READONLY)
    return ds
