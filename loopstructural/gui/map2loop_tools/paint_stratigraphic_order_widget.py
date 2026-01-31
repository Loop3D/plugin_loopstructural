"""Widget for painting stratigraphic order onto geology polygons."""

import os

from PyQt5.QtWidgets import QMessageBox, QWidget
from qgis.core import QgsMapLayerProxyModel
from qgis.PyQt import uic


from ...main.m2l_api import paint_stratigraphic_order


class PaintStratigraphicOrderWidget(QWidget):
    """Widget for painting stratigraphic order or cumulative thickness onto polygons.

    This widget provides a GUI interface for the paint stratigraphic order tool,
    allowing users to visualize stratigraphic relationships on geology polygons.
    """

    def __init__(self, parent=None, data_manager=None, debug_manager=None):
        """Initialize the paint stratigraphic order widget.

        Parameters
        ----------
        parent : QWidget, optional
            Parent widget.
        data_manager : object, optional
            Data manager for accessing shared data.
        debug_manager : object, optional
            Debug manager for logging and debugging.
        """
        super().__init__(parent)
        self.data_manager = data_manager
        self._debug = debug_manager

        # Load the UI file
        ui_path = os.path.join(os.path.dirname(__file__), "paint_stratigraphic_order_widget.ui")
        uic.loadUi(ui_path, self)

        # Configure layer filters programmatically
        try:
            self.geologyLayerComboBox.setFilters(QgsMapLayerProxyModel.PolygonLayer)
            # stratigraphic column layer removed from UI
            pass
        except Exception:
            # If QGIS isn't available, skip filter setup
            pass

        # Initialize paint modes
        self.paint_modes = ["Stratigraphic Order (0=youngest)", "Cumulative Thickness"]
        self.paintModeComboBox.addItems(self.paint_modes)

        # New UI: duplicate layer and color ramp
        try:
            # Populate colour ramps from default style
            from qgis.core import QgsStyle

            ramps = QgsStyle().defaultStyle().colorRampNames()
            self.colorRampComboBox.addItems(sorted(ramps))
        except Exception as e:
            if self._debug.is_debug():
                raise e
            # if QGIS unavailable, leave empty
            pass

        # Default: no duplication
        try:
            self.duplicateLayerCheckBox.setChecked(False)
        except Exception:
            pass

        # Connect signals
        self.geologyLayerComboBox.layerChanged.connect(self._on_geology_layer_changed)
        self.runButton.clicked.connect(self._run_painter)

        # Set up field combo boxes
        self._setup_field_combo_boxes()

    def set_debug_manager(self, debug_manager):
        """Attach a debug manager instance."""
        self._debug = debug_manager

    def _export_layer_for_debug(self, layer, name_prefix: str):
        """Export layer for debugging purposes."""
        try:
            if getattr(self, '_debug', None) and hasattr(self._debug, 'export_layer'):
                exported = self._debug.export_layer(layer, name_prefix)
                return exported
        except Exception as err:
            if getattr(self, '_debug', None):
                self._debug.plugin.log(
                    message=f"[map2loop] Failed to export layer '{name_prefix}': {err}",
                    log_level=2,
                )
        return None

    def _serialize_layer(self, layer, name_prefix: str):
        """Serialize layer for logging."""
        try:
            export_path = self._export_layer_for_debug(layer, name_prefix)
            return {
                "name": layer.name(),
                "id": layer.id(),
                "provider": layer.providerType() if hasattr(layer, "providerType") else None,
                "source": layer.source() if hasattr(layer, "source") else None,
                "export_path": export_path,
            }
        except Exception:
            return str(layer)

    def _serialize_params_for_logging(self, params, context_label: str):
        """Serialize parameters for logging."""
        serialized = {}
        for key, value in params.items():
            if hasattr(value, "source") or hasattr(value, "id"):
                serialized[key] = self._serialize_layer(value, f"{context_label}_{key}")
            else:
                serialized[key] = value
        return serialized

    def _log_params(self, context_label: str):
        """Log parameters for debugging."""
        if getattr(self, "_debug", None):
            try:
                self._debug.log_params(
                    context_label=context_label,
                    params=self._serialize_params_for_logging(self.get_parameters(), context_label),
                )
            except Exception:
                pass

    def _setup_field_combo_boxes(self):
        """Set up field combo boxes based on current layers."""
        self._on_geology_layer_changed()
        # stratigraphic column layer removed from UI
        pass

    def _on_geology_layer_changed(self):
        """Update unit name field combo box when geology layer changes."""
        geology_layer = self.geologyLayerComboBox.currentLayer()
        self.unitNameFieldComboBox.setLayer(geology_layer)

        # Try to auto-select common field names
        if geology_layer:
            field_names = [field.name() for field in geology_layer.fields()]
            for common_name in ['UNITNAME', 'unitname', 'unit_name', 'UNIT', 'unit']:
                if common_name in field_names:
                    self.unitNameFieldComboBox.setField(common_name)
                    break

    def _run_painter(self):
        """Run the paint stratigraphic order algorithm.

        Returns
        -------
        bool
            True if operation completed without unhandled exceptions, False otherwise.
        """

        try:
            geology_layer = self.geologyLayerComboBox.currentLayer()
            unit_name_field = self.unitNameFieldComboBox.currentField()
            stratigraphic_order = self.data_manager.stratigraphic_order = (
                self.data_manager.get_stratigraphic_unit_names() if self.data_manager else []
            )
            paint_stratigraphic_order(
                geology_layer, stratigraphic_order, unit_name_field, debug_manager=self._debug
            )

            # If requested, duplicate layer and apply style using selected colour ramp
            try:
                duplicate = (
                    getattr(self, 'duplicateLayerCheckBox', None)
                    and self.duplicateLayerCheckBox.isChecked()
                )
            except Exception:
                duplicate = False

            if duplicate:
                # Get chosen ramp name
                try:
                    ramp_name = self.colorRampComboBox.currentText()
                except Exception:
                    ramp_name = None

                # Step 1: create a memory copy of the geology layer and copy attributes/geometry
                try:
                    from PyQt5.QtCore import QVariant
                    from qgis.core import (
                        QgsFeature,
                        QgsField,
                        QgsGraduatedSymbolRenderer,
                        QgsProject,
                        QgsRendererRange,
                        QgsStyle,
                        QgsSymbol,
                        QgsVectorLayer,
                        QgsWkbTypes,
                    )

                    geom_type = QgsWkbTypes.displayString(geology_layer.wkbType())
                    crs_auth = (
                        geology_layer.crs().authid() if hasattr(geology_layer, 'crs') else None
                    )
                    uri = f"{geom_type}?crs={crs_auth}" if crs_auth else f"{geom_type}"
                    mem_layer = QgsVectorLayer(uri, f"{geology_layer.name()}_strat", "memory")

                    mem_dp = mem_layer.dataProvider()
                    mem_dp.addAttributes(list(geology_layer.fields()))
                    mem_layer.updateFields()

                    # copy each feature and its attributes explicitly
                    src_field_names = [f.name() for f in geology_layer.fields()]
                    new_feats = []
                    for src_feat in geology_layer.getFeatures():
                        nf = QgsFeature()
                        nf.setGeometry(src_feat.geometry())
                        nf.setFields(mem_layer.fields())
                        attrs = []
                        for f in mem_layer.fields():
                            fname = f.name()
                            if fname in src_field_names:
                                try:
                                    attrs.append(src_feat[fname])
                                except Exception:
                                    attrs.append(None)
                            else:
                                attrs.append(None)
                        nf.setAttributes(attrs)
                        new_feats.append(nf)
                    mem_dp.addFeatures(new_feats)
                    mem_layer.updateExtents()
                    QgsProject.instance().addMapLayer(mem_layer)
                except Exception as e:
                    QMessageBox.warning(self, 'Duplicate Layer', f'Failed to create copy: {e}')
                    return False

                # Step 2: ensure 'strat_order' exists on memory layer and populate numeric values by matching geometries
                field_name = 'strat_order'
                try:
                    if field_name not in [f.name() for f in mem_layer.fields()]:
                        mem_layer.startEditing()
                        mem_dp.addAttributes([QgsField(field_name, QVariant.Int)])
                        mem_layer.updateFields()
                        mem_layer.commitChanges()

                    # build mapping from geometry WKB -> numeric strat value from original layer
                    geom_to_val = {}
                    for of in geology_layer.getFeatures():
                        try:
                            raw = of[field_name]
                        except Exception:
                            raw = None
                        if raw is None:
                            continue
                        try:
                            val = int(raw)
                        except Exception:
                            try:
                                val = int(float(raw))
                            except Exception:
                                continue
                        try:
                            geom_to_val[of.geometry().asWkb()] = val
                        except Exception:
                            try:
                                geom_to_val[of.geometry().asWkt()] = val
                            except Exception:
                                continue

                    if geom_to_val:
                        mem_layer.startEditing()
                        strat_idx = mem_layer.fields().indexFromName(field_name)
                        for mf in mem_layer.getFeatures():
                            try:
                                key = mf.geometry().asWkb()
                            except Exception:
                                try:
                                    key = mf.geometry().asWkt()
                                except Exception:
                                    key = None
                            if key is None:
                                continue
                            val = geom_to_val.get(key, None)
                            if val is not None:
                                mem_layer.changeAttributeValue(mf.id(), strat_idx, int(val))
                        mem_layer.commitChanges()
                except Exception:
                    # continue; styling will fallback if numeric data missing
                    pass

                # Step 3: build graduated renderer using explicit ranges per unique strat value
                try:
                    vals = set()
                    for f in mem_layer.getFeatures():
                        try:
                            v = f[field_name]
                        except Exception:
                            v = None
                        if v is None:
                            continue
                        try:
                            vals.add(float(v))
                        except Exception:
                            continue
                    unique_vals = sorted(vals)

                    if not unique_vals:
                        QMessageBox.information(
                            self,
                            'Styling',
                            "No 'strat_order' values found on duplicated layer; leaving default styling.",
                        )
                    else:
                        ramp = QgsStyle().defaultStyle().colorRamp(ramp_name) if ramp_name else None
                        ranges = []
                        n = len(unique_vals)
                        for i, v in enumerate(unique_vals):
                            lower = v - 0.5
                            upper = v + 0.5
                            symbol = QgsSymbol.defaultSymbol(mem_layer.geometryType())
                            if ramp:
                                try:
                                    color = ramp.color(i / (n - 1) if n > 1 else 0)
                                    symbol.setColor(color)
                                except Exception:
                                    pass
                            label = str(int(v)) if float(v).is_integer() else str(v)
                            ranges.append(QgsRendererRange(lower, upper, symbol, label))
                        renderer = QgsGraduatedSymbolRenderer(field_name, ranges)
                        mem_layer.setRenderer(renderer)
                        mem_layer.triggerRepaint()
                except Exception as e:
                    QMessageBox.warning(
                        self, 'Duplicate Layer', f'Failed to apply graduated styling: {e}'
                    )

        except Exception as e:
            QMessageBox.warning(self, 'Paint Stratigraphic Order', f'Operation failed: {e}')
            return False

        return True
