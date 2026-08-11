import logging
from typing import Optional

import geopandas as gpd
import pandas as pd

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsGeometry,
    QgsProject,
    QgsRaster,
    QgsWkbTypes,
)

from loopstructural.gui.compatibility import QVariantCompat

logger = logging.getLogger(__name__)


def _get_crs_id(crs):
    """Get a safe string identifier for a CRS.

    Parameters
    ----------
    crs : QgsCoordinateReferenceSystem or None
        The CRS to get an ID for

    Returns
    -------
    str
        CRS authid or "Unknown" if unavailable
    """
    if crs and crs.isValid():
        try:
            return crs.authid() or "Unknown"
        except Exception:
            logger.debug("Could not read crs.authid()", exc_info=True)
            return "Unknown"
    return "Unknown"


def qgsLayerToGeoDataFrame(layer, target_crs=None) -> Optional[gpd.GeoDataFrame]:
    """Convert a QgsVectorLayer to a GeoDataFrame, optionally transforming to a target CRS.

    Parameters
    ----------
    layer : QgsVectorLayer
        The vector layer to convert
    target_crs : QgsCoordinateReferenceSystem, optional
        If provided, all geometries will be transformed to this CRS.
        If None, the layer's source CRS is used.

    Returns
    -------
    gpd.GeoDataFrame
        GeoDataFrame with geometries in the specified CRS
    """
    if layer is None:
        return None

    features = layer.getFeatures()
    fields = layer.fields()
    data = {'geometry': []}
    for f in fields:
        data[f.name()] = []

    # Set up coordinate transformation if needed
    transform = None
    source_crs = layer.sourceCrs()
    output_crs = source_crs

    if target_crs is not None and target_crs.isValid():
        if source_crs.isValid() and source_crs != target_crs:
            transform = QgsCoordinateTransform(source_crs, target_crs, QgsProject.instance())
            output_crs = target_crs
    for feature in features:
        geom = feature.geometry()
        if geom.isEmpty():
            continue

        # Transform geometry if needed
        if transform is not None:
            geom_copy = QgsGeometry(geom)
            try:
                result = geom_copy.transform(transform)
                if result == 0:
                    data['geometry'].append(geom_copy)
                if result != 0:
                    # Transform returned error code
                    logger.warning(
                        f"Failed to transform geometry (error code {result}). "
                        f"Source CRS: {_get_crs_id(source_crs)}, Target CRS: {_get_crs_id(target_crs)}. "
                        f"Skipping feature."
                    )
                    continue
            except Exception as e:
                # If transformation fails, log warning and skip this feature
                logger.exception(
                    f"Exception during CRS transformation: {e}. "
                    f"Source CRS: {_get_crs_id(source_crs)}, Target CRS: {_get_crs_id(target_crs)}. "
                    f"Skipping feature."
                )
                continue
        else:
            data['geometry'].append(geom)

        # Copy field values
        for f in fields:
            if f.type() == QVariantCompat.String:
                data[f.name()].append(str(feature[f.name()]))
            else:
                data[f.name()].append(feature[f.name()])

    return gpd.GeoDataFrame(data, crs=output_crs.authid())


def qgsLayerToDataFrame(src, dtm=None) -> Optional[pd.DataFrame]:
    """
    Convert a vector layer or processing feature source to a pandas DataFrame.
    Samples geometry using points or vertices of lines/polygons.
    Optionally samples Z from a DTM raster.

    :param src: QgsVectorLayer or QgsProcessingFeatureSource
    :param dtm: QgsRasterLayer or None
    :return: pd.DataFrame with columns: X, Y, Z, and all layer fields
    """

    if src is None:
        return None

    # --- Resolve fields and source CRS (works for both layer and feature source) ---
    fields = src.fields() if hasattr(src, "fields") else None
    if fields is None:
        # Fallback: take fields from first feature if needed
        feat_iter = src.getFeatures()
        try:
            first = next(feat_iter)
        except StopIteration:
            return pd.DataFrame(columns=["X", "Y", "Z"])
        fields = first.fields()
        # Rewind iterator by building a new one
        feats = [first] + list(src.getFeatures())
    else:
        feats = src.getFeatures()

    # Get source CRS
    if hasattr(src, "crs"):
        src_crs = src.crs()
    elif hasattr(src, "sourceCrs"):
        src_crs = src.sourceCrs()
    else:
        src_crs = None

    # --- Prepare optional transform to DTM CRS for sampling ---
    to_dtm = None
    if dtm is not None and src_crs is not None and dtm.crs().isValid() and src_crs.isValid():
        if src_crs != dtm.crs():
            to_dtm = QgsCoordinateTransform(src_crs, dtm.crs(), QgsProject.instance())

    # --- Helper: sample Z from DTM (returns float or -9999) ---
    # Called once per vertex, so deliberately not logged on failure (unlike
    # the rest of this module) -- on a large layer that would flood the log.
    def sample_dtm_xy(x, y):
        if dtm is None:
            return 0.0
        # Transform coordinate if needed
        if to_dtm is not None:
            try:
                from qgis.core import QgsPointXY

                x, y = to_dtm.transform(QgsPointXY(x, y))
            except Exception:
                return -9999.0
        from qgis.core import QgsPointXY

        ident = dtm.dataProvider().identify(QgsPointXY(x, y), QgsRaster.IdentifyFormatValue)
        if not ident.isValid():
            return -9999.0
        res = ident.results()
        if not res:
            return -9999.0
        # take first band value (band keys are 1-based)
        try:
            # Prefer band 1 if present
            return float(res.get(1, next(iter(res.values()))))
        except Exception:
            return -9999.0

    # --- Geometry -> list of vertices (QgsPoint or QgsPointXY) ---
    def vertices_from_geometry(geom):
        if geom is None or geom.isEmpty():
            return []
        gtype = QgsWkbTypes.geometryType(geom.wkbType())
        is_multi = QgsWkbTypes.isMultiType(geom.wkbType())

        if gtype == QgsWkbTypes.PointGeometry:
            if is_multi:
                return list(geom.asMultiPoint())
            else:
                return [geom.asPoint()]

        elif gtype == QgsWkbTypes.LineGeometry:
            pts = []
            if is_multi:
                for line in geom.asMultiPolyline():
                    pts.extend(line)
            else:
                pts.extend(geom.asPolyline())
            return pts

        elif gtype == QgsWkbTypes.PolygonGeometry:
            pts = []
            if is_multi:
                mpoly = geom.asMultiPolygon()
                for poly in mpoly:
                    for ring in poly:  # exterior + interior rings
                        pts.extend(ring)
            else:
                poly = geom.asPolygon()
                for ring in poly:
                    pts.extend(ring)
            return pts

        # Other geometry types not handled
        return []

    # --- Build rows safely (one dict per sampled point) ---
    rows = []
    field_names = [f.name() for f in fields]

    for f in feats:
        geom = f.geometry()
        pts = vertices_from_geometry(geom)

        if not pts:
            # If you want to keep attribute rows even when no vertices: uncomment below
            # row = {name: f[name] for name in field_names}
            # row.update({"X": None, "Y": None, "Z": None})
            # rows.append(row)
            continue

        # Cache attributes once per feature and reuse for each sampled point
        base_attrs = {name: f[name] for name in field_names}

        for p in pts:
            # QgsPoint vs QgsPointXY both have x()/y()
            x, y = float(p.x()), float(p.y())
            z = sample_dtm_xy(x, y)

            row = {"X": x, "Y": y, "Z": z}
            row.update(base_attrs)
            rows.append(row)

    # Create DataFrame; if empty, return with expected columns
    if not rows:
        cols = ["X", "Y", "Z"] + field_names
        return pd.DataFrame(columns=cols)

    return pd.DataFrame.from_records(rows)


def _geometry_from_value(value):
    """Convert shapely/QGIS geometry objects into QgsGeometry instances."""
    if value is None:
        return None
    if isinstance(value, QgsGeometry):
        return QgsGeometry(value)
    # QgsGeometry with asWkb
    for attr in ("asWkb", "exportToWkb"):
        method = getattr(value, attr, None)
        if callable(method):
            try:
                data = method()
            except Exception:
                logger.debug("%s() raised in _geometry_from_value", attr, exc_info=True)
                data = None
            if data:
                try:
                    data = bytes(data)
                except Exception:
                    # Best-effort conversion to bytes; if this fails, leave data as-is
                    logger.debug("Could not coerce %s() result to bytes", attr, exc_info=True)
                try:
                    return QgsGeometry.fromWkb(data)
                except Exception:
                    # Best-effort conversion to bytes; if this fails, fall back to using the
                    # original data and let the subsequent fromWkb call handle it.
                    logger.debug(
                        "Failed to convert WKB data to bytes in _geometry_from_value",
                        exc_info=True,
                    )
                    continue
    # Shapely geometries expose wkb/wkt attributes
    wkb_data = getattr(value, "wkb", None)
    if wkb_data is not None:
        try:
            return QgsGeometry.fromWkb(bytes(wkb_data))
        except Exception:
            logger.debug("QgsGeometry.fromWkb(value.wkb) failed", exc_info=True)
    wkt_data = getattr(value, "wkt", None)
    if wkt_data:
        try:
            return QgsGeometry.fromWkt(str(wkt_data))
        except Exception:
            # last fallback attempted -- the caller gets None and the row's
            # geometry is dropped.
            logger.debug("QgsGeometry.fromWkt(value.wkt) failed", exc_info=True)
    return None


def _infer_wkb_type_from_geoms(geoms) -> QgsWkbTypes.Type:
    """Infer a WKB type from a GeoSeries or iterable of geometries."""
    for geom in geoms:
        qgs_geom = _geometry_from_value(geom)
        if qgs_geom is not None and not qgs_geom.isEmpty():
            return qgs_geom.wkbType()
    return QgsWkbTypes.Point


def _crs_from_geodataframe_crs(crs_info) -> QgsCoordinateReferenceSystem:
    """Best-effort conversion of GeoPandas CRS metadata to QgsCoordinateReferenceSystem."""
    crs = QgsCoordinateReferenceSystem()
    if crs_info is None:
        return crs
    # pyproj CRS exposes helpers like to_wkt/to_epsg
    text = None
    for attr in ("to_wkt", "to_string"):
        method = getattr(crs_info, attr, None)
        if callable(method):
            try:
                text = method()
            except Exception:
                logger.debug("%s() raised in _crs_from_geodataframe_crs", attr, exc_info=True)
                text = None
            if text:
                break
    if text:
        try:
            return QgsCoordinateReferenceSystem.fromWkt(text)
        except Exception:
            logger.debug("QgsCoordinateReferenceSystem.fromWkt(text) failed", exc_info=True)
            temp = QgsCoordinateReferenceSystem()
            if hasattr(temp, "createFromWkt"):
                try:
                    if temp.createFromWkt(text):
                        return temp
                except Exception:
                    logger.debug("temp.createFromWkt(text) failed", exc_info=True)
    try:
        epsg = crs_info.to_epsg()
        if epsg:
            return QgsCoordinateReferenceSystem.fromEpsgId(int(epsg))
    except Exception:
        logger.debug("Failed to convert EPSG code to QgsCoordinateReferenceSystem", exc_info=True)
    if isinstance(crs_info, str):
        try:
            temp = QgsCoordinateReferenceSystem(crs_info)
            if temp.isValid():
                return temp
        except Exception:
            # last fallback attempted -- the caller gets an invalid/empty CRS.
            logger.debug("QgsCoordinateReferenceSystem(crs_info) failed", exc_info=True)
    return crs
