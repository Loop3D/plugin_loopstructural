import logging

from qgis.core import NULL, QgsField, QgsFields

from loopstructural.gui.compatibility import QVariantCompat

logger = logging.getLogger(__name__)


def _qvariant_type_from_dtype(dtype) -> QVariantCompat.Type:
    """Map a pandas dtype to a QVariant type."""
    import numpy as np

    if np.issubdtype(dtype, np.integer):
        # prefer 64-bit when detected
        try:
            return QVariantCompat.LongLong
        except AttributeError:
            return QVariantCompat.Int
    if np.issubdtype(dtype, np.floating):
        return QVariantCompat.Double
    if np.issubdtype(dtype, np.bool_):
        return QVariantCompat.Bool
    # datetimes
    try:
        import pandas as pd

        if pd.api.types.is_datetime64_any_dtype(dtype):
            return QVariantCompat.DateTime
        if pd.api.types.is_datetime64_ns_dtype(dtype):
            return QVariantCompat.DateTime
        if pd.api.types.is_datetime64_dtype(dtype):
            return QVariantCompat.DateTime
        if pd.api.types.is_timedelta64_dtype(dtype):
            # store as string "HH:MM:SS" fallback
            return QVariantCompat.String
    except Exception:
        logger.debug("Error checking pandas datetime dtype for %r", dtype, exc_info=True)
    # default to string
    return QVariantCompat.String


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
    if isinstance(val, QVariantCompat):
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
        logger.debug("Could not convert %r to float in qvariantToFloat", val, exc_info=True)
        return None
