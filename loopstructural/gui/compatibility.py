# compat.py
from qgis.PyQt.QtCore import QVariant

try:
    from qgis.PyQt.QtCore import QMetaType

    # We create a proxy class to mimic the old QVariant.Type behavior
    class QVariantProxy:
        Type = QMetaType.Type
        # Add common types here if needed
        Int = QMetaType.Type.Int
        Double = QMetaType.Type.Double
        String = QMetaType.Type.QString
        Bool = QMetaType.Type.Bool

    # In QGIS 4, we use our proxy
    QVariantCompat = QVariantProxy
except (ImportError, AttributeError):
    # In QGIS 3, QVariant already has .Type
    QVariantCompat = QVariant
