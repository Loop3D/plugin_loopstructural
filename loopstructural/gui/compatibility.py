# compat.py
from qgis.PyQt.QtCore import QVariant


def configure_layer_combo(combo, filters, allow_empty=None):
    """Apply a QgsMapLayerProxyModel filter to a QgsMapLayerComboBox.

    Centralises a `setFilters`/`setAllowEmptyLayer` pairing that was
    previously duplicated -- and inconsistently wrapped in try/except --
    across a dozen widgets. `allow_empty`, if given, also calls
    `setAllowEmptyLayer`.
    """
    try:
        combo.setFilters(filters)
        if allow_empty is not None:
            combo.setAllowEmptyLayer(allow_empty)
    except Exception:
        pass


if hasattr(QVariant, "Type"):
    # QGIS 3 / PyQt5: QVariant still exposes the legacy .Type enum.
    # (QMetaType is importable under PyQt5 too, and PyQt6's QVariant still
    # keeps scalar constants like QVariant.Int for convenience, so neither
    # of those can be used to detect QGIS 4 - .Type is the attribute QGIS 4
    # actually removed, so it's the only reliable signal.)
    QVariantCompat = QVariant
else:
    # QGIS 4 / PyQt6: QVariant.Type was removed; use QMetaType instead.
    from qgis.PyQt.QtCore import QMetaType

    # We create a proxy class to mimic the old QVariant.Type behavior
    class QVariantProxy:
        Type = QMetaType.Type
        # Add common types here if needed
        Int = QMetaType.Type.Int
        Double = QMetaType.Type.Double
        String = QMetaType.Type.QString
        Bool = QMetaType.Type.Bool
        DateTime = QMetaType.Type.QDateTime

    QVariantCompat = QVariantProxy
