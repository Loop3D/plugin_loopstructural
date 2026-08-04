# compat.py
from qgis.PyQt.QtCore import QVariant

if hasattr(QVariant, "Int"):
    # QGIS 3 / PyQt5: QVariant still exposes the legacy .Type enum members.
    # (QMetaType is importable under PyQt5 too, so we can't use that import
    # to detect QGIS 4 - checking for the attribute QGIS 4 actually removed
    # is the only reliable signal.)
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
