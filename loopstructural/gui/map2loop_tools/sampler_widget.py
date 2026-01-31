"""Widget for running the sampler."""

import os

from PyQt5.QtWidgets import QMessageBox, QWidget
from qgis.core import QgsProject, QgsWkbTypes
from qgis.PyQt import uic

from loopstructural.toolbelt.preferences import PlgOptionsManager


class SamplerWidget(QWidget):
    """Widget for configuring and running the sampler.

    This widget provides a GUI interface for the map2loop sampler algorithms
    (Decimator and Spacing).
    """

    def __init__(self, parent=None, data_manager=None, debug_manager=None):
        """Initialize the sampler widget.

        Parameters
        ----------
        parent : QWidget, optional
            Parent widget.
        data_manager : object, optional
            Data manager for accessing shared data.
        """
        super().__init__(parent)
        self.data_manager = data_manager
        self._debug = debug_manager

        # Load the UI file
        ui_path = os.path.join(os.path.dirname(__file__), "sampler_widget.ui")
        uic.loadUi(ui_path, self)

        # Configure layer filters programmatically (avoid QgsMapLayerProxyModel in .ui)
        try:
            from qgis.core import QgsMapLayerProxyModel

            # DTM should show raster layers, geology polygons
            self.dtmLayerComboBox.setFilters(QgsMapLayerProxyModel.RasterLayer)
            self.geologyLayerComboBox.setFilters(QgsMapLayerProxyModel.PolygonLayer)
            self.spatialDataLayerComboBox.setFilters(
                QgsMapLayerProxyModel.LineLayer | QgsMapLayerProxyModel.PointLayer
            )

            # spatialData can be any type, leave default
        except Exception:
            # If QGIS isn't available, skip filter setup
            pass

        # Initialize sampler types
        self.sampler_types = ["Decimator", "Spacing"]
        self.samplerTypeComboBox.addItems(self.sampler_types)

        # Connect signals
        self.samplerTypeComboBox.currentIndexChanged.connect(self._on_sampler_type_changed)
        self.runButton.clicked.connect(self._run_sampler)
        # When user selects a spatial layer, automatically determine sampler type
        try:
            # Many QGIS widgets emit currentIndexChanged for layer changes
            self.spatialDataLayerComboBox.currentIndexChanged.connect(
                self._on_spatial_layer_changed
            )
        except Exception:
            pass

        # Initial state update
        self._on_sampler_type_changed()
        # Also ensure state reflects any preselected spatial layer
        try:
            self._on_spatial_layer_changed()
        except Exception:
            pass

    def set_debug_manager(self, debug_manager):
        """Attach a debug manager instance."""
        self._debug = debug_manager

    def _export_layer_for_debug(self, layer, name_prefix: str):
        # Prefer DebugManager.export_layer if available
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
        serialized = {}
        for key, value in params.items():
            if hasattr(value, "source") or hasattr(value, "id"):
                serialized[key] = self._serialize_layer(value, f"{context_label}_{key}")
            else:
                serialized[key] = value
        return serialized

    def _log_params(self, context_label: str):
        if getattr(self, "_debug", None):
            try:
                self._debug.log_params(
                    context_label=context_label,
                    params=self._serialize_params_for_logging(self.get_parameters(), context_label),
                )
            except Exception:
                pass

    def _on_sampler_type_changed(self):
        """Update UI based on selected sampler type."""
        sampler_type = self.samplerTypeComboBox.currentText()

        if sampler_type == "Decimator":
            self.decimationLabel.setVisible(True)
            self.decimationSpinBox.setVisible(True)
            self.spacingLabel.setVisible(False)
            self.spacingSpinBox.setVisible(False)
            # Decimator requires DTM and geology
            self.dtmLayerComboBox.setAllowEmptyLayer(False)
            self.geologyLayerComboBox.setAllowEmptyLayer(False)
        else:  # Spacing
            self.decimationLabel.setVisible(False)
            self.decimationSpinBox.setVisible(False)
            self.spacingLabel.setVisible(True)
            self.spacingSpinBox.setVisible(True)
            # Spacing can work with optional DTM and geology
            self.dtmLayerComboBox.setAllowEmptyLayer(True)
            self.geologyLayerComboBox.setAllowEmptyLayer(True)

    def _set_invalid_spatial_type(self, message: str = None):
        """Disable controls when an invalid spatial layer type is selected."""
        # Disable sampler selection and run to prevent usage with unsupported types
        try:
            self.samplerTypeComboBox.setEnabled(False)
        except Exception:
            pass
        try:
            self.runButton.setEnabled(False)
        except Exception:
            pass
        if message:
            QMessageBox.warning(self, "Invalid Spatial Data", message)

    def _on_spatial_layer_changed(self):
        """Automatically set sampler type based on spatial data layer geometry.

        - Point geometry -> Decimator
        - Other geometries -> disallowed
        """
        try:
            layer = self.spatialDataLayerComboBox.currentLayer()
        except Exception:
            layer = None

        if layer is None:
            return

        # Determine geometry type; only vector layers expose geometryType
        try:
            if not hasattr(layer, 'geometryType'):
                # Non-vector layer (raster, etc.) is not allowed
                self._set_invalid_spatial_type("Only point vector layers are allowed for sampling.")
                return

            geom_type = layer.geometryType()
            # QgsWkbTypes: PointGeometry = 0, LineGeometry = 1, PolygonGeometry = 2
            if geom_type == QgsWkbTypes.PointGeometry:
                # Use Decimator for point sets
                try:
                    idx = self.sampler_types.index("Decimator")
                    self.samplerTypeComboBox.setCurrentIndex(idx)
                except Exception as e:
                    print(e)
                    pass
                self.samplerTypeComboBox.setEnabled(False)
                self.runButton.setEnabled(True)
            elif geom_type == QgsWkbTypes.LineGeometry:
                # Line geometry is not allowed
                try:
                    idx = self.sampler_types.index("Spacing")
                    self.samplerTypeComboBox.setCurrentIndex(idx)
                except Exception as e:
                    print(e)
                    pass
                self.samplerTypeComboBox.setEnabled(False)
                self.runButton.setEnabled(False)
            else:
                # Line, polygon or other vector type -> disallowed
                self._set_invalid_spatial_type("Only point or line layers can be used")
                return
        except Exception:
            # On any error, be conservative and disable run
            self._set_invalid_spatial_type(
                "Selected layer type could not be determined. Only point vector layers are allowed."
            )
            return

    def _run_sampler(self):
        """Run the sampler algorithm using the map2loop API."""

        from qgis.core import (
            QgsCoordinateReferenceSystem,
            QgsFeature,
            QgsField,
            QgsFields,
            QgsGeometry,
            QgsPointXY,
            QgsVectorLayer,
        )
        from qgis.PyQt.QtCore import QVariant

        from ...main.m2l_api import sample_contacts

        self._log_params("sampler_widget_run")

        # Validate inputs
        if not self.spatialDataLayerComboBox.currentLayer():
            QMessageBox.warning(self, "Missing Input", "Please select a spatial data layer.")
            return False

        sampler_type = self.samplerTypeComboBox.currentText()

        if sampler_type == "Decimator":
            if not self.geologyLayerComboBox.currentLayer():
                QMessageBox.warning(
                    self, "Missing Input", "Geology layer is required for Decimator."
                )
                return False
            if not self.dtmLayerComboBox.currentLayer():
                QMessageBox.warning(self, "Missing Input", "DTM layer is required for Decimator.")
                return False

        # Run the sampler API
        try:
            kwargs = {
                'spatial_data': self.spatialDataLayerComboBox.currentLayer(),
                'sampler_type': sampler_type,
                'updater': lambda msg: QMessageBox.information(self, "Progress", msg),
            }

            if sampler_type == "Decimator":
                kwargs['decimation'] = self.decimationSpinBox.value()
                kwargs['dtm'] = self.dtmLayerComboBox.currentLayer()
                kwargs['geology'] = self.geologyLayerComboBox.currentLayer()
            else:  # Spacing
                kwargs['spacing'] = self.spacingSpinBox.value()
                if self.dtmLayerComboBox.currentLayer():
                    kwargs['dtm'] = self.dtmLayerComboBox.currentLayer()
                if self.geologyLayerComboBox.currentLayer():
                    kwargs['geology'] = self.geologyLayerComboBox.currentLayer()

            samples = sample_contacts(**kwargs)

            if self._debug and self._debug.is_debug():
                try:
                    if samples is not None:
                        csv_bytes = samples.to_csv(index=False).encode("utf-8")
                        self._debug.save_debug_file("sampler_contacts.csv", csv_bytes)
                except Exception as err:
                    self._debug.plugin.log(
                        message=f"[map2loop] Failed to save sampler debug output: {err}",
                        log_level=2,
                    )

            # Convert result back to QGIS layer and add to project
            if samples is not None and not samples.empty:
                layer_name = f"Sampled Contacts ({sampler_type})"

                fields = QgsFields()
                for column_name in samples.columns:
                    if column_name == 'geometry':
                        continue
                    dtype = samples[column_name].dtype
                    dtype_str = str(dtype)

                    if dtype_str in ['float16', 'float32', 'float64']:
                        field_type = QVariant.Double
                    elif dtype_str in ['int8', 'int16', 'int32', 'int64']:
                        field_type = QVariant.Int
                    else:
                        field_type = QVariant.String

                    fields.append(QgsField(column_name, field_type))

                crs = None
                if (
                    hasattr(self.spatialDataLayerComboBox.currentLayer(), 'crs')
                    and self.spatialDataLayerComboBox.currentLayer().crs() is not None
                ):
                    crs = QgsCoordinateReferenceSystem.fromWkt(
                        self.spatialDataLayerComboBox.currentLayer().crs().toWkt()
                    )
                # Create layer
                geom_type = "PointZ" if 'Z' in samples.columns else "Point"
                layer = QgsVectorLayer(
                    f"{geom_type}?crs={crs.authid() if crs else 'EPSG:4326'}", layer_name, "memory"
                )
                provider = layer.dataProvider()
                provider.addAttributes(fields)
                layer.updateFields()

                # Add features
                for _index, row in samples.iterrows():
                    feature = QgsFeature(fields)

                    # Add geometry
                    if 'Z' in samples.columns and __import__('pandas').notna(row.get('Z')):
                        wkt = f"POINT Z ({row['X']} {row['Y']} {row['Z']})"
                        feature.setGeometry(QgsGeometry.fromWkt(wkt))
                    else:
                        feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(row['X'], row['Y'])))

                    # Add attributes
                    attributes = []
                    for column_name in samples.columns:
                        if column_name == 'geometry':
                            continue
                        value = row.get(column_name)
                        dtype = samples[column_name].dtype
                        pd = __import__('pandas')

                        if pd.isna(value):
                            attributes.append(None)
                        elif dtype in ['float16', 'float32', 'float64']:
                            attributes.append(float(value))
                        elif dtype in ['int8', 'int16', 'int32', 'int64']:
                            attributes.append(int(value))
                        else:
                            attributes.append(str(value))

                    feature.setAttributes(attributes)
                    provider.addFeature(feature)

                layer.updateExtents()
                QgsProject.instance().addMapLayer(layer)

                QMessageBox.information(
                    self,
                    "Success",
                    f"Sampling completed! Layer '{layer_name}' added with {len(samples)} features.",
                )
            else:
                QMessageBox.warning(self, "Warning", "No samples were generated.")
                return False
            return True

        except Exception as e:
            if self._debug:
                self._debug.plugin.log(
                    message=f"[map2loop] Sampler run failed: {e}",
                    log_level=2,
                )
            if PlgOptionsManager.get_debug_mode():
                raise e
            QMessageBox.critical(self, "Error", f"An error occurred: {str(e)}")
            return False

    def get_parameters(self):
        """Get current widget parameters.

        Returns
        -------
        dict
            Dictionary of current widget parameters.
        """
        return {
            'sampler_type': self.samplerTypeComboBox.currentIndex(),
            'dtm_layer': self.dtmLayerComboBox.currentLayer(),
            'geology_layer': self.geologyLayerComboBox.currentLayer(),
            'spatial_data_layer': self.spatialDataLayerComboBox.currentLayer(),
            'decimation': self.decimationSpinBox.value(),
            'spacing': self.spacingSpinBox.value(),
        }

    def set_parameters(self, params):
        """Set widget parameters.

        Parameters
        ----------
        params : dict
            Dictionary of parameters to set.
        """
        if 'sampler_type' in params:
            self.samplerTypeComboBox.setCurrentIndex(params['sampler_type'])
        if 'dtm_layer' in params and params['dtm_layer']:
            self.dtmLayerComboBox.setLayer(params['dtm_layer'])
        if 'geology_layer' in params and params['geology_layer']:
            self.geologyLayerComboBox.setLayer(params['geology_layer'])
        if 'spatial_data_layer' in params and params['spatial_data_layer']:
            self.spatialDataLayerComboBox.setLayer(params['spatial_data_layer'])
        if 'decimation' in params:
            self.decimationSpinBox.setValue(params['decimation'])
        if 'spacing' in params:
            self.spacingSpinBox.setValue(params['spacing'])
