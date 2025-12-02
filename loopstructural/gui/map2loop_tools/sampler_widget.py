"""Widget for running the sampler."""

import os

from PyQt5.QtWidgets import QMessageBox, QWidget
from qgis.PyQt import uic
from loopstructural.toolbelt.preferences import PlgOptionsManager


class SamplerWidget(QWidget):
    """Widget for configuring and running the sampler.

    This widget provides a GUI interface for the map2loop sampler algorithms
    (Decimator and Spacing).
    """

    def __init__(self, parent=None, data_manager=None):
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

        # Load the UI file
        ui_path = os.path.join(os.path.dirname(__file__), "sampler_widget.ui")
        uic.loadUi(ui_path, self)

        # Configure layer filters programmatically (avoid QgsMapLayerProxyModel in .ui)
        try:
            from qgis.core import QgsMapLayerProxyModel

            # DTM should show raster layers, geology polygons
            self.dtmLayerComboBox.setFilters(QgsMapLayerProxyModel.RasterLayer)
            self.geologyLayerComboBox.setFilters(QgsMapLayerProxyModel.PolygonLayer)
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

        # Initial state update
        self._on_sampler_type_changed()

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

    def _run_sampler(self):
        """Run the sampler algorithm using the map2loop API."""
        from qgis.core import (
            QgsCoordinateReferenceSystem,
            QgsFeature,
            QgsField,
            QgsFields,
            QgsGeometry,
            QgsPointXY,
            QgsProject,
            QgsVectorLayer,
        )
        from qgis.PyQt.QtCore import QVariant

        from ...main.m2l_api import sample_contacts

        # Validate inputs
        if not self.spatialDataLayerComboBox.currentLayer():
            QMessageBox.warning(self, "Missing Input", "Please select a spatial data layer.")
            return

        sampler_type = self.samplerTypeComboBox.currentText()

        if sampler_type == "Decimator":
            if not self.geologyLayerComboBox.currentLayer():
                QMessageBox.warning(
                    self, "Missing Input", "Geology layer is required for Decimator."
                )
                return
            if not self.dtmLayerComboBox.currentLayer():
                QMessageBox.warning(self, "Missing Input", "DTM layer is required for Decimator.")
                return

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
                if hasattr(samples, 'crs') and samples.crs is not None:
                    crs = QgsCoordinateReferenceSystem.fromWkt(samples.crs.to_wkt())

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

        except Exception as e:
            if PlgOptionsManager.get_debug_mode():
                raise e
            QMessageBox.critical(self, "Error", f"An error occurred: {str(e)}")

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
