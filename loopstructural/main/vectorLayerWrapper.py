import logging
import os
import tempfile
from typing import Optional

import geopandas as gpd
import numpy as np
import pandas as pd

# PyQGIS / PyQt imports
from osgeo import gdal
from qgis import processing
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsFeature,
    QgsFeatureSink,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsPoint,
    QgsPointXY,
    QgsProcessingException,
    QgsProject,
    QgsRaster,
    QgsRasterLayer,
    QgsVectorLayer,
    QgsWkbTypes,
)
from qgis.PyQt.QtCore import QDateTime, QVariant
from shapely.geometry import LineString, MultiLineString, MultiPoint, MultiPolygon, Point, Polygon

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
        pass
    try:
        if rlayer.dataProvider():
            candidates.append(rlayer.dataProvider().dataSourceUri())
    except Exception:
        pass

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
            if f.type() == QVariant.String:
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


def GeoDataFrameToQgsLayer(
    qgs_algorithm, geodataframe, parameters=None, context=None, output_key=None, feedback=None
):
    """
    Write a GeoPandas GeoDataFrame to a QGIS layer (Processing or non-Processing context).

    When used in a Processing algorithm context (parameters, context, output_key provided):
        Returns the dest_id for a feature sink.

    When used outside Processing (parameters=None):
        Returns a QgsVectorLayer (memory layer).

    Parameters
    ----------
    qgs_algorithm : QgsProcessingAlgorithm (self) or None
        Processing algorithm instance. Can be None for non-processing usage.
    geodataframe : geopandas.GeoDataFrame
        The GeoDataFrame to convert
    parameters : dict (from processAlgorithm) or None
        If None, creates a memory layer instead of a sink
    context : QgsProcessingContext or None
    output_key : str or None
        e.g. self.OUTPUT (only needed for processing context)
    feedback : QgsProcessingFeedback | None

    Returns
    -------
    str or QgsVectorLayer
        dest_id if in processing context, QgsVectorLayer if non-processing context
    """

    # Non-processing context: delegate to geodataframeToMemoryLayer
    if parameters is None or context is None or output_key is None:
        layer_name = getattr(qgs_algorithm, 'name', lambda: 'GeoDataFrame Layer')()
        return geodataframeToMemoryLayer(geodataframe, layer_name)

    if feedback is None:

        class _Dummy:
            def pushInfo(self, *a, **k):
                pass

            def reportError(self, *a, **k):
                pass

            def setProgress(self, *a, **k):
                pass

            def isCanceled(self):
                return False

        feedback = _Dummy()

    if geodataframe is None:
        raise ValueError("GeoDataFrame is None")
    if geodataframe.empty:
        feedback.pushInfo("Input GeoDataFrame is empty; creating empty output layer.")

    # --- infer WKB type (family, Multi, Z)
    def _infer_wkb(series):
        base = None
        any_multi = False
        has_z = False
        for geom in series:
            if geom is None:
                continue
            if getattr(geom, "is_empty", False):
                continue
            # multi?
            if isinstance(geom, (MultiPoint, MultiLineString, MultiPolygon)):
                any_multi = True
                g0 = next(iter(getattr(geom, "geoms", [])), None)
                gt = getattr(g0, "geom_type", None) or None
            else:
                gt = getattr(geom, "geom_type", None)

            # base family
            if gt in ("Point", "LineString", "Polygon"):
                base = gt
                # z?
                try:
                    has_z = has_z or bool(getattr(geom, "has_z", False))
                except Exception:
                    pass
                if base:
                    break

        if base is None:
            # default safely to LineString if everything is empty; adjust if you prefer Point/Polygon
            base = "LineString"

        fam = {
            "Point": QgsWkbTypes.Point,
            "LineString": QgsWkbTypes.LineString,
            "Polygon": QgsWkbTypes.Polygon,
        }[base]

        if any_multi:
            fam = QgsWkbTypes.multiType(fam)
        if has_z:
            fam = QgsWkbTypes.addZ(fam)
        return fam

    wkb_type = _infer_wkb(geodataframe.geometry)

    # --- build CRS from gdf.crs
    crs = QgsCoordinateReferenceSystem()
    if geodataframe.crs is not None:
        try:
            crs = QgsCoordinateReferenceSystem.fromWkt(geodataframe.crs.to_wkt())
        except Exception:
            try:
                epsg = geodataframe.crs.to_epsg()
                if epsg:
                    crs = QgsCoordinateReferenceSystem.fromEpsgId(int(epsg))
            except Exception:
                pass

    # --- build QGIS fields from pandas dtypes
    fields = QgsFields()
    non_geom_cols = [c for c in geodataframe.columns if c != geodataframe.geometry.name]

    def _qvariant_type(dtype) -> QVariant.Type:
        if pd.api.types.is_integer_dtype(dtype):
            return QVariant.Int
        if pd.api.types.is_float_dtype(dtype):
            return QVariant.Double
        if pd.api.types.is_bool_dtype(dtype):
            return QVariant.Bool
        if pd.api.types.is_datetime64_any_dtype(dtype):
            return QVariant.DateTime
        return QVariant.String

    for col in non_geom_cols:
        fields.append(QgsField(str(col), _qvariant_type(geodataframe[col].dtype)))

    # --- create sink
    sink, dest_id = qgs_algorithm.parameterAsSink(
        parameters,
        output_key,
        context,
        fields,
        wkb_type,
        crs,
    )
    if sink is None:
        raise QgsProcessingException("Could not create output sink")

    # --- write features
    total = len(geodataframe.index)
    is_multi_sink = QgsWkbTypes.isMultiType(wkb_type)

    for i, (_, row) in enumerate(geodataframe.iterrows()):
        if feedback.isCanceled():
            break

        geom = row[geodataframe.geometry.name]
        if geom is None or getattr(geom, "is_empty", False):
            continue

        # promote single → multi if needed
        if is_multi_sink:
            if isinstance(geom, Point):
                geom = MultiPoint([geom])
            elif isinstance(geom, LineString):
                geom = MultiLineString([geom])
            elif isinstance(geom, Polygon):
                geom = MultiPolygon([geom])

        f = QgsFeature(fields)

        # attributes in declared order
        attrs = []
        for col in non_geom_cols:
            val = row[col]
            if isinstance(val, np.generic):
                try:
                    val = val.item()
                except Exception:
                    pass
            if pd.api.types.is_datetime64_any_dtype(geodataframe[col].dtype):
                if pd.isna(val):
                    val = None
                else:
                    val = QDateTime(val.to_pydatetime())
            attrs.append(val)
        f.setAttributes(attrs)

        # geometry (shapely → QGIS)
        try:
            f.setGeometry(QgsGeometry.fromWkb(geom.wkb))
        except Exception:
            f.setGeometry(QgsGeometry.fromWkt(geom.wkt))

        sink.addFeature(f, QgsFeatureSink.FastInsert)

        if total:
            feedback.setProgress(int(100.0 * (i + 1) / total))

    return dest_id


# ---------- helpers ----------


def _qvariant_type_from_dtype(dtype) -> QVariant.Type:
    """Map a pandas dtype to a QVariant type."""
    import numpy as np

    if np.issubdtype(dtype, np.integer):
        # prefer 64-bit when detected
        try:
            return QVariant.LongLong
        except AttributeError:
            return QVariant.Int
    if np.issubdtype(dtype, np.floating):
        return QVariant.Double
    if np.issubdtype(dtype, np.bool_):
        return QVariant.Bool
    # datetimes
    try:
        import pandas as pd

        if pd.api.types.is_datetime64_any_dtype(dtype):
            return QVariant.DateTime
        if pd.api.types.is_datetime64_ns_dtype(dtype):
            return QVariant.DateTime
        if pd.api.types.is_datetime64_dtype(dtype):
            return QVariant.DateTime
        if pd.api.types.is_timedelta64_dtype(dtype):
            # store as string "HH:MM:SS" fallback
            return QVariant.String
    except Exception:
        pass
    # default to string
    return QVariant.String


def _fields_from_dataframe(df, drop_cols=None) -> QgsFields:
    """Build QgsFields from DataFrame dtypes."""
    drop_cols = set(drop_cols or [])
    fields = QgsFields()
    for name, dtype in df.dtypes.items():
        if name in drop_cols:
            continue
        vtype = _qvariant_type_from_dtype(dtype)
        fields.append(QgsField(name, vtype))
    return fields


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
                data = None
            if data:
                try:
                    data = bytes(data)
                except Exception:
                    pass
                try:
                    return QgsGeometry.fromWkb(data)
                except Exception:
                    continue
    # Shapely geometries expose wkb/wkt attributes
    wkb_data = getattr(value, "wkb", None)
    if wkb_data is not None:
        try:
            return QgsGeometry.fromWkb(bytes(wkb_data))
        except Exception:
            pass
    wkt_data = getattr(value, "wkt", None)
    if wkt_data:
        try:
            return QgsGeometry.fromWkt(str(wkt_data))
        except Exception:
            pass
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
                text = None
            if text:
                break
    if text:
        try:
            return QgsCoordinateReferenceSystem.fromWkt(text)
        except Exception:
            temp = QgsCoordinateReferenceSystem()
            if hasattr(temp, "createFromWkt"):
                try:
                    if temp.createFromWkt(text):
                        return temp
                except Exception:
                    pass
    try:
        epsg = crs_info.to_epsg()
        if epsg:
            return QgsCoordinateReferenceSystem.fromEpsgId(int(epsg))
    except Exception:
        pass
    if isinstance(crs_info, str):
        try:
            temp = QgsCoordinateReferenceSystem(crs_info)
            if temp.isValid():
                return temp
        except Exception:
            pass
    return crs


def QgsLayerFromGeoDataFrame(geodataframe, layer_name: str = "Converted Data"):
    """Create an in-memory QgsVectorLayer from a GeoPandas GeoDataFrame."""
    if geodataframe is None:
        return None
    geometry_series = getattr(geodataframe, "geometry", None)
    if geometry_series is None:
        raise ValueError("GeoDataFrame must include a geometry column.")
    geometry_column = geometry_series.name
    wkb_type = _infer_wkb_type_from_geoms(geometry_series)
    geom_name = QgsWkbTypes.displayString(wkb_type) or "Point"
    crs = _crs_from_geodataframe_crs(getattr(geodataframe, "crs", None))
    uri = geom_name
    if crs.isValid():
        authid = crs.authid()
        if authid:
            uri = f"{geom_name}?crs={authid}"
    layer = QgsVectorLayer(uri, layer_name, "memory")
    if crs.isValid():
        layer.setCrs(crs)
    provider = layer.dataProvider()
    attribute_fields = []
    for column in geodataframe.columns:
        if column == geometry_column:
            continue
        attribute_fields.append(QgsField(str(column), _qvariant_type_from_dtype(geodataframe[column].dtype)))
    if attribute_fields:
        provider.addAttributes(attribute_fields)
        layer.updateFields()
    non_geom_cols = [col for col in geodataframe.columns if col != geometry_column]
    features = []
    for _, row in geodataframe.iterrows():
        feat = QgsFeature(layer.fields())
        attrs = []
        for column in non_geom_cols:
            val = row[column]
            if isinstance(val, np.generic):
                try:
                    val = val.item()
                except Exception:
                    pass
            if pd.isna(val):
                val = None
            attrs.append(val)
        feat.setAttributes(attrs)
        geom = _geometry_from_value(row[geometry_column])
        if geom is not None and not geom.isEmpty():
            feat.setGeometry(geom)
        features.append(feat)
    if features:
        provider.addFeatures(features)
        layer.updateExtents()
    return layer


def QgsLayerFromDataFrame(dataframe, layer_name: str = "Converted Table"):
    """Create an attribute-only memory layer from a pandas-compatible DataFrame."""
    if dataframe is None:
        return None
    df = dataframe.copy()
    geometry_series = getattr(df, "geometry", None)
    geometry_name = getattr(geometry_series, "name", None)
    if geometry_name and geometry_name in df.columns:
        df = df.drop(columns=[geometry_name])

    layer = QgsVectorLayer("None", layer_name, "memory")
    provider = layer.dataProvider()

    attributes = []
    for column in df.columns:
        attributes.append(QgsField(str(column), _qvariant_type_from_dtype(df[column].dtype)))
    if attributes:
        provider.addAttributes(attributes)
        layer.updateFields()

    features = []
    for _, row in df.iterrows():
        feat = QgsFeature(layer.fields())
        attrs = []
        for column in df.columns:
            val = row[column]
            if pd.isna(val):
                val = None
            elif isinstance(val, np.generic):
                try:
                    val = val.item()
                except Exception:
                    pass
            attrs.append(val)
        feat.setAttributes(attrs)
        features.append(feat)
    if features:
        provider.addFeatures(features)
        layer.updateExtents()
    return layer


# ---------- main function you'll call inside processAlgorithm ----------


def dataframeToQgsLayer(
    df,
    x_col: str,
    y_col: str,
    *,
    crs: QgsCoordinateReferenceSystem,
    algorithm,  # `self` inside a QgsProcessingAlgorithm
    parameters: dict,
    context,
    feedback,
    sink_param_name: str = "OUTPUT",
    z_col: str = None,
    m_col: str = None,
    include_coords_in_attrs: bool = False,
):
    """
    Write a pandas DataFrame to a point feature sink (QgsProcessingParameterFeatureSink).

    Params
    ------
    df : pandas.DataFrame                  Data with coordinate columns.
    x_col, y_col : str                     Column names for X/Easting/Longitude and Y/Northing/Latitude.
    crs : QgsCoordinateReferenceSystem     CRS of the coordinates (e.g., QgsCoordinateReferenceSystem('EPSG:4326')).
    algorithm : QgsProcessingAlgorithm     Use `self` from inside processAlgorithm.
    parameters, context, feedback          Standard Processing plumbing.
    sink_param_name : str                  Name of your sink output parameter (default "OUTPUT").
    z_col, m_col : str | None              Optional Z and M columns for 3D/M points.
    include_coords_in_attrs : bool         If False, x/y/z/m are not written as attributes.

    Returns
    -------
    (sink, sink_id)                        The created sink and its ID. Also returns feature count via feedback.
    """
    import pandas as pd

    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas.DataFrame")

    # Make a working copy; optionally drop coordinate columns from attributes
    attr_df = df.copy()
    drop_cols = []
    for col in [x_col, y_col, z_col, m_col]:
        if col and not include_coords_in_attrs:
            drop_cols.append(col)

    fields = _fields_from_dataframe(attr_df, drop_cols=drop_cols)

    # Geometry type (2D/3D/M)
    has_z = z_col is not None and z_col in df.columns
    has_m = m_col is not None and m_col in df.columns
    if has_z and has_m:
        wkb = QgsWkbTypes.PointZM
    elif has_z:
        wkb = QgsWkbTypes.PointZ
    elif has_m:
        wkb = QgsWkbTypes.PointM
    else:
        wkb = QgsWkbTypes.Point

    # Create the sink
    sink, sink_id = algorithm.parameterAsSink(
        parameters, sink_param_name, context, fields, wkb, crs
    )
    if sink is None:
        raise QgsProcessingException(
            "Could not create feature sink. Check output parameter and inputs."
        )

    total = len(df)
    feedback.pushInfo(f"Writing {total} features…")

    # Precompute attribute column order
    attr_columns = [f.name() for f in fields]

    # Iterate rows and write features
    for i, (_idx, row) in enumerate(df.iterrows(), start=1):
        if feedback.isCanceled():
            break

        # Build point geometry
        x = row[x_col]
        y = row[y_col]

        # skip rows with missing coords
        if pd.isna(x) or pd.isna(y):
            continue

        if has_z and not pd.isna(row[z_col]) and has_m and not pd.isna(row[m_col]):
            pt = QgsPoint(float(x), float(y), float(row[z_col]), float(row[m_col]))
        elif has_z and not pd.isna(row[z_col]):
            pt = QgsPoint(float(x), float(y), float(row[z_col]))
        elif has_m and not pd.isna(row[m_col]):
            # PointM constructor: setZValue not needed; M is the 4th ordinate
            pt = QgsPoint(float(x), float(y))
            pt.setM(float(row[m_col]))
        else:
            pt = QgsPointXY(float(x), float(y))

        feat = QgsFeature(fields)
        feat.setGeometry(
            QgsGeometry.fromPoint(pt) if isinstance(pt, QgsPoint) else QgsGeometry.fromPointXY(pt)
        )

        # Attributes in the same order as fields
        attrs = []
        for col in attr_columns:
            val = row[col] if col in row else None
            # Pandas NaN -> None
            if pd.isna(val):
                val = None
            # Convert numpy types to Python scalars to avoid QVariant issues
            try:
                import numpy as np

                if isinstance(val, (np.generic,)):
                    val = val.item()
            except Exception:
                pass
            # Convert pandas Timestamp to Python datetime
            if hasattr(val, "to_pydatetime"):
                try:
                    val = val.to_pydatetime()
                except Exception:
                    val = str(val)
            attrs.append(val)
        feat.setAttributes(attrs)

        sink.addFeature(feat, QgsFeature.FastInsert)

        if i % 1000 == 0:
            feedback.setProgress(int(100.0 * i / max(total, 1)))

    feedback.pushInfo("Done.")
    feedback.setProgress(100)
    return sink, sink_id


def matrixToDict(matrix, headers=("minx", "miny", "maxx", "maxy")) -> dict:
    """
    Convert a QgsProcessingParameterMatrix value to a dict with float values.
    Accepts: [[minx,miny,maxx,maxy]] or [minx,miny,maxx,maxy].
    Raises a clear error if an enum index (int) was passed by mistake.
    """
    # Guard: common mistake → using parameterAsEnum
    if isinstance(matrix, int):
        raise QgsProcessingException(
            "Bounding Box was read with parameterAsEnum (got an int). "
            "Use parameterAsMatrix for QgsProcessingParameterMatrix."
        )

    if matrix is None:
        raise QgsProcessingException("Bounding box matrix is None.")

    # Allow empty string from settings/defaults
    if isinstance(matrix, str) and not matrix.strip():
        raise QgsProcessingException("Bounding box matrix is empty.")

    # Accept single-row matrix or flat list
    if isinstance(matrix, (list, tuple)):
        if matrix and isinstance(matrix[0], (list, tuple)):
            row = matrix[0]
        else:
            row = matrix
    else:
        # last resort: try comma-separated string "minx,miny,maxx,maxy"
        if isinstance(matrix, str) and "," in matrix:
            row = [v.strip() for v in matrix.split(",")]
        else:
            raise QgsProcessingException(f"Unrecognized bounding box value: {type(matrix)}")

    if len(row) < 4:
        raise QgsProcessingException(f"Bounding box needs 4 numbers, got {len(row)}: {row}")

    def _to_float(v):
        if isinstance(v, str):
            v = v.strip()
        return float(v)

    vals = list(map(_to_float, row[:4]))
    bbox = dict(zip(headers, vals))

    if not (bbox["minx"] < bbox["maxx"] and bbox["miny"] < bbox["maxy"]):
        raise QgsProcessingException(
            f"Invalid bounding box: {bbox} (expect minx<maxx and miny<maxy)"
        )

    return bbox


def dataframeToQgsTable(self, df, parameters, context, feedback, param_name):
    if df is None or df.empty:
        raise QgsProcessingException("Empty DataFrame.")

    # 1) Field schema
    fields = QgsFields()

    def to_qvariant_type(s):
        if pd.api.types.is_bool_dtype(s):
            return QVariant.Bool
        if pd.api.types.is_integer_dtype(s):
            return QVariant.LongLong
        if pd.api.types.is_float_dtype(s):
            return QVariant.Double
        return QVariant.String

    for col in df.columns:
        fields.append(QgsField(str(col), to_qvariant_type(df[col])))

    # 2) CRS: use project CRS if available, otherwise empty CRS
    crs = (
        context.project().crs() if context and context.project() else QgsCoordinateReferenceSystem()
    )

    sink, dest_id = self.parameterAsSink(
        parameters, param_name, context, fields, QgsWkbTypes.NoGeometry, crs
    )
    if sink is None:
        raise QgsProcessingException("Canot create output table (sink=None).")

    # 3) Write features
    for _, row in df.iterrows():
        f = QgsFeature(fields)
        attrs = []
        for col in df.columns:
            v = row[col]
            # Convert numpy scalars to native Python types
            if isinstance(v, (np.generic,)):
                v = v.item()
            # NaN/NaT → None
            if pd.isna(v):
                v = None
            attrs.append(v)
        f.setAttributes(attrs)
        sink.addFeature(f)

    return sink, dest_id


from PyQt5.QtCore import QVariant
from qgis.core import NULL


def qvariantToFloat(f, field_name):
    val = f.attribute(field_name)  # usually returns a native Python type
    # null / empty values
    if val in (None, NULL, ''):
        return None
    # strings with decimal comma (depending on locale)
    if isinstance(val, str):
        val = val.strip()
        if val == '':
            return None
        val = val.replace(',', '.')  # replace comma with dot if present
        try:
            return float(val)
        except ValueError:
            pass
    # residual QVariant
    if isinstance(val, QVariant):
        # toDouble() -> (value, ok)
        d, ok = val.toDouble()
        return float(d) if ok else None
    # native int/float
    if isinstance(val, (int, float)):
        return float(val)
    # fallback conversion attempt
    try:
        return float(val)
    except Exception:
        return None


def geodataframeToMemoryLayer(geodataframe, layer_name: str = "GeoDataFrame Layer"):
    """
    Convert a GeoPandas GeoDataFrame to a QGIS memory layer (non-processing context).

    This function works outside of the QGIS Processing framework and can be used
    in GUI components, plugins, or standalone scripts.

    Parameters
    ----------
    geodataframe : geopandas.GeoDataFrame
        The GeoDataFrame to convert
    layer_name : str
        Name for the created layer

    Returns
    -------
    QgsVectorLayer
        The created QGIS vector layer with features from the GeoDataFrame
    """
    from qgis.core import QgsFeature, QgsGeometry, QgsVectorLayer

    if geodataframe is None or geodataframe.empty:
        raise ValueError("GeoDataFrame is None or empty")

    # --- Infer WKB type (family, Multi, Z)
    def _infer_wkb(series):
        base = None
        any_multi = False
        has_z = False
        for geom in series:
            if geom is None:
                continue
            if getattr(geom, "is_empty", False):
                continue
            # multi?
            if isinstance(geom, (MultiPoint, MultiLineString, MultiPolygon)):
                any_multi = True
                g0 = next(iter(getattr(geom, "geoms", [])), None)
                gt = getattr(g0, "geom_type", None) or None
            else:
                gt = getattr(geom, "geom_type", None)

            # base family
            if gt in ("Point", "LineString", "Polygon"):
                base = gt
                # z?
                try:
                    has_z = has_z or bool(getattr(geom, "has_z", False))
                except Exception as e:
                    print("Error checking geometry Z value", e)
                if base:
                    break

        if base is None:
            # default safely to LineString if everything is empty
            base = "LineString"

        fam = {
            "Point": QgsWkbTypes.Point,
            "LineString": QgsWkbTypes.LineString,
            "Polygon": QgsWkbTypes.Polygon,
        }[base]

        if any_multi:
            fam = QgsWkbTypes.multiType(fam)
        if has_z:
            fam = QgsWkbTypes.addZ(fam)
        return fam

    wkb_type = _infer_wkb(geodataframe.geometry)

    # --- Build CRS from gdf.crs
    crs = QgsCoordinateReferenceSystem()
    if geodataframe.crs is not None:
        try:
            crs = QgsCoordinateReferenceSystem.fromWkt(geodataframe.crs.to_wkt())
        except Exception:
            try:
                epsg = geodataframe.crs.to_epsg()
                if epsg:
                    crs = QgsCoordinateReferenceSystem.fromEpsgId(int(epsg))
            except Exception as e:
                print("Error building CRS from EPSG", e)
                pass

    # --- Build QGIS fields from pandas dtypes
    fields = QgsFields()
    non_geom_cols = [c for c in geodataframe.columns if c != geodataframe.geometry.name]

    def _qvariant_type(dtype) -> QVariant.Type:
        if pd.api.types.is_integer_dtype(dtype):
            return QVariant.Int
        if pd.api.types.is_float_dtype(dtype):
            return QVariant.Double
        if pd.api.types.is_bool_dtype(dtype):
            return QVariant.Bool
        if pd.api.types.is_datetime64_any_dtype(dtype):
            return QVariant.DateTime
        return QVariant.String

    for col in non_geom_cols:
        fields.append(QgsField(str(col), _qvariant_type(geodataframe[col].dtype)))

    # --- Create memory layer
    geom_type_str = QgsWkbTypes.displayString(wkb_type)
    crs_str = crs.authid() if crs.isValid() else "EPSG:4326"
    uri = f"{geom_type_str}?crs={crs_str}"

    layer = QgsVectorLayer(uri, layer_name, "memory")
    if not layer.isValid():
        raise RuntimeError(f"Failed to create memory layer: {layer_name}")

    # Add fields to the layer
    layer.dataProvider().addAttributes(list(fields))
    layer.updateFields()

    # --- Write features
    is_multi_wkb = QgsWkbTypes.isMultiType(wkb_type)
    features = []

    for _, row in geodataframe.iterrows():
        geom = row[geodataframe.geometry.name]
        if geom is None or getattr(geom, "is_empty", False):
            continue

        # Promote single → multi if needed
        if is_multi_wkb:
            if isinstance(geom, Point):
                geom = MultiPoint([geom])
            elif isinstance(geom, LineString):
                geom = MultiLineString([geom])
            elif isinstance(geom, Polygon):
                geom = MultiPolygon([geom])

        f = QgsFeature(fields)

        # Attributes in declared order
        attrs = []
        for col in non_geom_cols:
            val = row[col]
            if isinstance(val, np.generic):
                try:
                    val = val.item()
                except Exception:
                    # don't crash UI on conversion failure
                    pass
            if pd.api.types.is_datetime64_any_dtype(geodataframe[col].dtype):
                if pd.isna(val):
                    val = None
                else:
                    val = QDateTime(val.to_pydatetime())
            attrs.append(val)
        f.setAttributes(attrs)

        # Geometry (shapely → QGIS)
        try:
            f.setGeometry(QgsGeometry.fromWkb(geom.wkb))
        except Exception:
            f.setGeometry(QgsGeometry.fromWkt(geom.wkt))

        features.append(f)

    # Add all features at once
    layer.dataProvider().addFeatures(features)
    layer.updateExtents()

    return layer


def addGeoDataFrameToproject(geodataframe, layer_name: str = "GeoDataFrame Layer"):
    """
    Add a GeoPandas GeoDataFrame as a temporary layer to the current QGIS project.

    Parameters
    ----------
    geodataframe : geopandas.GeoDataFrame
        The GeoDataFrame to add to the project
    layer_name : str
        Name of the layer in QGIS (default: "GeoDataFrame Layer")

    Returns
    -------
    QgsVectorLayer
        The created and added QGIS vector layer.
    """
    from qgis.core import QgsProject

    # Create the memory layer
    layer = geodataframeToMemoryLayer(geodataframe, layer_name)

    # Add to project
    QgsProject.instance().addMapLayer(layer)

    return layer
