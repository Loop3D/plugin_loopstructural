# compat.py
from qgis.PyQt.QtCore import QVariant

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
