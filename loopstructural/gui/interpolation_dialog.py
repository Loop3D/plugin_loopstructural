"""Dialog for building and evaluating LoopStructural interpolators."""

import os
import numpy as np
import pandas as pd

from qgis.PyQt.QtWidgets import QDialog, QFileDialog, QMessageBox
from qgis.PyQt.uic import loadUi
from qgis.core import (
    QgsProject,
    QgsVectorLayer,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsField,
    QgsFields,
    QgsMapLayerProxyModel
)
from qgis.PyQt.QtCore import QVariant

from LoopStructural import GeologicalModel
from LoopStructural.datatypes import BoundingBox


class InterpolationDialog(QDialog):
    """Dialog for building and evaluating LoopStructural interpolators.
    
    This dialog provides a user interface for:
    - Building new interpolators from QGIS layers
    - Evaluating existing interpolators on grids or point sets
    - Managing stored interpolators
    """

    def __init__(self, parent=None, interpolator_manager=None, logger=None):
        """Initialize the interpolation dialog.
        
        Parameters
        ----------
        parent : QWidget, optional
            Parent widget
        interpolator_manager : InterpolatorManager, optional
            Manager for storing interpolators
        logger : callable, optional
            Logger function for messages
        """
        super().__init__(parent)
        self.interpolator_manager = interpolator_manager
        self.logger = logger if logger else print
        
        # Load UI
        ui_path = os.path.join(os.path.dirname(__file__), 'interpolation_dialog.ui')
        loadUi(ui_path, self)
        self.setWindowTitle('LoopStructural Interpolation')
        
        # Connect signals
        self._connect_signals()
        
        # Initialize UI
        self._initialize_ui()

    def _connect_signals(self):
        """Connect UI signals to slots."""
        # Build tab
        self.valueLayerCombo.layerChanged.connect(self._on_value_layer_changed)
        self.gradientLayerCombo.layerChanged.connect(self._on_gradient_layer_changed)
        self.buildButton.clicked.connect(self._on_build_interpolator)
        
        # Evaluate tab
        self.evaluationTypeCombo.currentIndexChanged.connect(self._on_evaluation_type_changed)
        self.loadInterpolatorButton.clicked.connect(self._on_load_interpolator)
        self.evaluateButton.clicked.connect(self._on_evaluate_interpolator)
        
        # Manage tab
        self.saveInterpolatorButton.clicked.connect(self._on_save_interpolator)
        self.deleteInterpolatorButton.clicked.connect(self._on_delete_interpolator)
        
        # Dialog buttons
        self.buttonBox.rejected.connect(self.reject)

    def _initialize_ui(self):
        """Initialize UI elements."""
        # Set up extent widgets to use map canvas
        try:
            from qgis.utils import iface
            if iface:
                canvas = iface.mapCanvas()
                self.extentWidget.setMapCanvas(canvas)
                self.rasterExtentWidget.setMapCanvas(canvas)
                self.grid3DExtentWidget.setMapCanvas(canvas)
        except:
            pass
        self.valueLayerCombo.setFilters(QgsMapLayerProxyModel.PointLayer | QgsMapLayerProxyModel.LineLayer)
        self.gradientLayerCombo.setFilters(QgsMapLayerProxyModel.PointLayer)
        self.pointLayerCombo.setFilters(QgsMapLayerProxyModel.PointLayer)
        # Allow empty selection for layer combos
        self.valueLayerCombo.setAllowEmptyLayer(True)
        self.gradientLayerCombo.setAllowEmptyLayer(True)
        self.pointLayerCombo.setAllowEmptyLayer(True)
        # Allow empty selection for field combos
        self.valueFieldCombo.setLayer(None)
        self.strikeFieldCombo.setLayer(None)
        self.dipFieldCombo.setLayer(None)
        
        # Update interpolator list
        self._update_interpolator_list()
        self._update_interpolator_combo()
        
        # Set initial evaluation page
        self.evaluationStackedWidget.setCurrentIndex(0)

    def _on_value_layer_changed(self, layer):
        """Handle value layer selection change."""
        self.valueFieldCombo.setLayer(layer)

    def _on_gradient_layer_changed(self, layer):
        """Handle gradient layer selection change."""
        self.strikeFieldCombo.setLayer(layer)
        self.dipFieldCombo.setLayer(layer)

    def _on_evaluation_type_changed(self, index):
        """Handle evaluation type selection change."""
        self.evaluationStackedWidget.setCurrentIndex(index)

    def _on_build_interpolator(self):
        """Build a new interpolator from the input data."""
        try:
            # Get interpolator name
            name = self.interpolatorNameInput.text().strip()
            if not name:
                QMessageBox.warning(self, "Invalid Input", "Please enter an interpolator name.")
                return
            
            # Check if name already exists
            if self.interpolator_manager and self.interpolator_manager.has_interpolator(name):
                reply = QMessageBox.question(
                    self, 
                    "Interpolator Exists",
                    f"An interpolator named '{name}' already exists. Overwrite?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply != QMessageBox.Yes:
                    return
            
            # Get input layers
            value_layer = self.valueLayerCombo.currentLayer()
            value_field = self.valueFieldCombo.currentField()
            gradient_layer = self.gradientLayerCombo.currentLayer()
            strike_field = self.strikeFieldCombo.currentField()
            dip_field = self.dipFieldCombo.currentField()
            
            # Validate inputs
            if not value_layer and not gradient_layer:
                QMessageBox.warning(
                    self, 
                    "Invalid Input", 
                    "Please provide at least value or gradient data."
                )
                return
            
            if value_layer and not value_field:
                QMessageBox.warning(self, "Invalid Input", "Please select a value field.")
                return
            
            if gradient_layer:
                if not strike_field or not dip_field:
                    QMessageBox.warning(
                        self, 
                        "Invalid Input", 
                        "Please select both strike and dip fields for gradient data."
                    )
                    return
            
            # Get extent and pixel size
            extent = self.extentWidget.outputExtent()
            pixel_size = self.pixelSizeSpinBox.value()
            
            if extent.isNull():
                QMessageBox.warning(self, "Invalid Input", "Please specify an extent.")
                return
            
            # Build interpolator
            self.logger(f"Building interpolator '{name}'...", log_level=3)
            interpolator = self._build_interpolator(
                value_layer, value_field,
                gradient_layer, strike_field, dip_field,
                extent, pixel_size
            )
            
            # Store interpolator
            if self.interpolator_manager:
                self.interpolator_manager.add_interpolator(name, interpolator)
                self.logger(f"Interpolator '{name}' built successfully!", log_level=3)
                
                # Update UI
                self._update_interpolator_list()
                self._update_interpolator_combo()
                
                QMessageBox.information(
                    self, 
                    "Success", 
                    f"Interpolator '{name}' built successfully!"
                )
            
        except Exception as e:
            self.logger(f"Error building interpolator: {e}", log_level=2)
            QMessageBox.critical(self, "Error", f"Failed to build interpolator:\n{str(e)}")

    def _build_interpolator(self, value_layer, value_field, gradient_layer, 
                           strike_field, dip_field, extent, pixel_size):
        """Build an interpolator from the provided data.
        
        Parameters
        ----------
        value_layer : QgsVectorLayer
            Layer containing value points
        value_field : str
            Field name for values
        gradient_layer : QgsVectorLayer
            Layer containing gradient points
        strike_field : str
            Field name for strike
        dip_field : str
            Field name for dip
        extent : QgsRectangle
            Spatial extent
        pixel_size : float
            Resolution parameter
            
        Returns
        -------
        interpolator
            Built interpolator object
        """
        # Create bounding box
        z_min = 0
        z_max = pixel_size * 10
        bbox = BoundingBox(
            origin=[extent.xMinimum(), extent.yMinimum(), z_min],
            maximum=[extent.xMaximum(), extent.yMaximum(), z_max]
        )
        
        # Extract data
        dfs = []
        
        if value_layer and value_field:
            value_df = self._extract_value_data(value_layer, value_field)
            if len(value_df) > 0:
                dfs.append(value_df)
        
        if gradient_layer and strike_field and dip_field:
            gradient_df = self._extract_gradient_data(gradient_layer, strike_field, dip_field)
            if len(gradient_df) > 0:
                dfs.append(gradient_df)
        
        if not dfs:
            raise ValueError("No valid constraints found in input layers")
        
        # Combine data
        data = pd.concat(dfs, ignore_index=True)
        
        # Build interpolator using GeologicalModel
        model = GeologicalModel(bbox)
        model.create_and_add_foliation('interpolated_field', data=data)
        feature = model['interpolated_field']
        interpolator = feature.interpolator
        
        return interpolator

    def _extract_value_data(self, layer, field_name):
        """Extract value constraints from a layer."""
        rows = []
        for feat in layer.getFeatures():
            geom = feat.geometry()
            if geom is None or geom.isEmpty():
                continue
            
            try:
                value = float(feat.attribute(field_name))
            except (ValueError, TypeError):
                continue
            
            # Extract points
            points = []
            if geom.isMultipart():
                if geom.type() == 0:  # Point
                    points = geom.asMultiPoint()
                elif geom.type() == 1:  # Line
                    for line in geom.asMultiPolyline():
                        points.extend(line)
            else:
                if geom.type() == 0:  # Point
                    points = [geom.asPoint()]
                elif geom.type() == 1:  # Line
                    points = geom.asPolyline()
            
            for p in points:
                try:
                    x = p.x()
                    y = p.y()
                    z = p.z() if hasattr(p, 'z') else 0.0
                    rows.append({
                        'X': x, 'Y': y, 'Z': z, 
                        'val': value, 
                        'feature_name': 'interpolated_field'
                    })
                except:
                    continue
        
        return pd.DataFrame(rows)

    def _extract_gradient_data(self, layer, strike_field, dip_field):
        """Extract gradient constraints from a layer."""
        rows = []
        for feat in layer.getFeatures():
            geom = feat.geometry()
            if geom is None or geom.isEmpty():
                continue
            
            try:
                strike = float(feat.attribute(strike_field))
                dip = float(feat.attribute(dip_field))
            except (ValueError, TypeError):
                continue
            
            # Extract points
            points = []
            if geom.isMultipart():
                if geom.type() == 0:  # Point
                    points = geom.asMultiPoint()
            else:
                if geom.type() == 0:  # Point
                    points = [geom.asPoint()]
            
            for p in points:
                try:
                    x = p.x()
                    y = p.y()
                    z = p.z() if hasattr(p, 'z') else 0.0
                    rows.append({
                        'X': x, 'Y': y, 'Z': z,
                        'strike': strike, 'dip': dip,
                        'feature_name': 'interpolated_field'
                    })
                except:
                    continue
        
        return pd.DataFrame(rows)

    def _on_load_interpolator(self):
        """Load an interpolator from a pickle file."""
        try:
            filepath, _ = QFileDialog.getOpenFileName(
                self,
                "Load Interpolator",
                "",
                "Pickle Files (*.pkl);;All Files (*)"
            )
            
            if not filepath:
                return
            
            # Ask for name
            from qgis.PyQt.QtWidgets import QInputDialog
            name, ok = QInputDialog.getText(
                self,
                "Interpolator Name",
                "Enter a name for this interpolator:"
            )
            
            if not ok or not name.strip():
                return
            
            name = name.strip()
            
            # Check if exists
            if self.interpolator_manager and self.interpolator_manager.has_interpolator(name):
                reply = QMessageBox.question(
                    self,
                    "Interpolator Exists",
                    f"An interpolator named '{name}' already exists. Overwrite?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply != QMessageBox.Yes:
                    return
            
            # Load interpolator
            if self.interpolator_manager:
                self.interpolator_manager.load_interpolator(name, filepath)
                self.logger(f"Loaded interpolator '{name}' from {filepath}", log_level=3)
                
                # Update UI
                self._update_interpolator_list()
                self._update_interpolator_combo()
                
                # Select the loaded interpolator
                index = self.interpolatorCombo.findText(name)
                if index >= 0:
                    self.interpolatorCombo.setCurrentIndex(index)
                
                QMessageBox.information(
                    self,
                    "Success",
                    f"Loaded interpolator '{name}' successfully!"
                )
            
        except Exception as e:
            self.logger(f"Error loading interpolator: {e}", log_level=2)
            QMessageBox.critical(self, "Error", f"Failed to load interpolator:\n{str(e)}")

    def _on_evaluate_interpolator(self):
        """Evaluate the selected interpolator."""
        try:
            # Get selected interpolator
            interpolator_name = self.interpolatorCombo.currentText()
            if not interpolator_name:
                QMessageBox.warning(
                    self,
                    "No Interpolator Selected",
                    "Please select an interpolator to evaluate."
                )
                return
            
            if not self.interpolator_manager:
                raise ValueError("No interpolator manager available")
            
            interpolator = self.interpolator_manager.get_interpolator(interpolator_name)
            if interpolator is None:
                raise ValueError(f"Interpolator '{interpolator_name}' not found")
            
            # Get evaluation type
            eval_type = self.evaluationTypeCombo.currentIndex()
            
            self.logger(f"Evaluating interpolator '{interpolator_name}'...", log_level=3)
            
            if eval_type == 0:  # Raster
                layer = self._evaluate_raster(interpolator, interpolator_name)
            elif eval_type == 1:  # 3D Grid
                layer = self._evaluate_3d_grid(interpolator, interpolator_name)
            elif eval_type == 2:  # Point Layer
                layer = self._evaluate_point_layer(interpolator, interpolator_name)
            else:
                raise ValueError(f"Unknown evaluation type: {eval_type}")
            
            # Add layer to project
            if layer:
                QgsProject.instance().addMapLayer(layer)
                self.logger(f"Added layer '{layer.name()}' to project", log_level=3)
                QMessageBox.information(
                    self,
                    "Success",
                    f"Created layer '{layer.name()}' with interpolated values!"
                )
            
        except Exception as e:
            self.logger(f"Error evaluating interpolator: {e}", log_level=2)
            QMessageBox.critical(self, "Error", f"Failed to evaluate interpolator:\n{str(e)}")

    def _evaluate_raster(self, interpolator, name):
        """Evaluate interpolator on a raster grid."""
        extent = self.rasterExtentWidget.outputExtent()
        pixel_size = self.rasterPixelSizeSpinBox.value()
        
        if extent.isNull():
            raise ValueError("Please specify an extent")
        
        # Create grid
        x_coords = np.arange(extent.xMinimum(), extent.xMaximum() + pixel_size, pixel_size)
        y_coords = np.arange(extent.yMinimum(), extent.yMaximum() + pixel_size, pixel_size)
        xx, yy = np.meshgrid(x_coords, y_coords)
        points = np.column_stack([xx.ravel(), yy.ravel(), np.zeros(xx.size)])
        
        # Evaluate
        values = interpolator.evaluate_value(points)
        
        # Create layer
        layer = QgsVectorLayer("Point?crs=EPSG:4326", f"{name}_raster_evaluation", "memory")
        provider = layer.dataProvider()
        
        # Add fields
        provider.addAttributes([QgsField('value', QVariant.Double)])
        layer.updateFields()
        
        # Add features
        features = []
        for point, value in zip(points, values):
            feat = QgsFeature()
            feat.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(point[0], point[1])))
            feat.setAttributes([float(value)])
            features.append(feat)
        
        provider.addFeatures(features)
        layer.updateExtents()
        
        return layer

    def _evaluate_3d_grid(self, interpolator, name):
        """Evaluate interpolator on a 3D grid."""
        extent = self.grid3DExtentWidget.outputExtent()
        pixel_size = self.grid3DPixelSizeSpinBox.value()
        z_min = self.zMinSpinBox.value()
        z_max = self.zMaxSpinBox.value()
        z_step = self.zStepSpinBox.value()
        
        if extent.isNull():
            raise ValueError("Please specify an extent")
        
        # Create grid
        x_coords = np.arange(extent.xMinimum(), extent.xMaximum() + pixel_size, pixel_size)
        y_coords = np.arange(extent.yMinimum(), extent.yMaximum() + pixel_size, pixel_size)
        z_coords = np.arange(z_min, z_max + z_step, z_step)
        xx, yy, zz = np.meshgrid(x_coords, y_coords, z_coords)
        points = np.column_stack([xx.ravel(), yy.ravel(), zz.ravel()])
        
        # Evaluate
        values = interpolator.evaluate_value(points)
        
        # Create layer
        layer = QgsVectorLayer("PointZ?crs=EPSG:4326", f"{name}_3d_grid_evaluation", "memory")
        provider = layer.dataProvider()
        
        # Add fields
        provider.addAttributes([
            QgsField('x', QVariant.Double),
            QgsField('y', QVariant.Double),
            QgsField('z', QVariant.Double),
            QgsField('value', QVariant.Double)
        ])
        layer.updateFields()
        
        # Add features
        features = []
        for point, value in zip(points, values):
            feat = QgsFeature()
            feat.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(point[0], point[1])))
            feat.setAttributes([float(point[0]), float(point[1]), float(point[2]), float(value)])
            features.append(feat)
        
        provider.addFeatures(features)
        layer.updateExtents()
        
        return layer

    def _evaluate_point_layer(self, interpolator, name):
        """Evaluate interpolator on an existing point layer."""
        point_layer = self.pointLayerCombo.currentLayer()
        
        if not point_layer:
            raise ValueError("Please select a point layer")
        
        # Extract points
        points = []
        features = []
        for feat in point_layer.getFeatures():
            geom = feat.geometry()
            if geom is None or geom.isEmpty():
                continue
            
            if geom.isMultipart():
                pts = geom.asMultiPoint()
            else:
                pts = [geom.asPoint()]
            
            for p in pts:
                try:
                    x = p.x()
                    y = p.y()
                    z = p.z() if hasattr(p, 'z') else 0.0
                    points.append([x, y, z])
                    features.append(feat)
                except:
                    continue
        
        if not points:
            raise ValueError("No valid points found in layer")
        
        points = np.array(points)
        
        # Evaluate
        values = interpolator.evaluate_value(points)
        
        # Create output layer
        layer = QgsVectorLayer(
            f"Point?crs={point_layer.crs().authid()}",
            f"{name}_point_evaluation",
            "memory"
        )
        provider = layer.dataProvider()
        
        # Copy fields and add value field
        fields = QgsFields(point_layer.fields())
        fields.append(QgsField('interpolated_value', QVariant.Double))
        provider.addAttributes(fields.toList())
        layer.updateFields()
        
        # Add features
        out_features = []
        for feat, value in zip(features, values):
            out_feat = QgsFeature(fields)
            out_feat.setGeometry(feat.geometry())
            out_feat.setAttributes(feat.attributes() + [float(value)])
            out_features.append(out_feat)
        
        provider.addFeatures(out_features)
        layer.updateExtents()
        
        return layer

    def _on_save_interpolator(self):
        """Save selected interpolator to file."""
        try:
            # Get selected interpolator
            selected_items = self.interpolatorListWidget.selectedItems()
            if not selected_items:
                QMessageBox.warning(
                    self,
                    "No Selection",
                    "Please select an interpolator to save."
                )
                return
            
            name = selected_items[0].text()
            
            # Get file path
            filepath, _ = QFileDialog.getSaveFileName(
                self,
                "Save Interpolator",
                f"{name}.pkl",
                "Pickle Files (*.pkl);;All Files (*)"
            )
            
            if not filepath:
                return
            
            # Save interpolator
            if self.interpolator_manager:
                self.interpolator_manager.save_interpolator(name, filepath)
                self.logger(f"Saved interpolator '{name}' to {filepath}", log_level=3)
                QMessageBox.information(
                    self,
                    "Success",
                    f"Saved interpolator '{name}' successfully!"
                )
            
        except Exception as e:
            self.logger(f"Error saving interpolator: {e}", log_level=2)
            QMessageBox.critical(self, "Error", f"Failed to save interpolator:\n{str(e)}")

    def _on_delete_interpolator(self):
        """Delete selected interpolator."""
        try:
            # Get selected interpolator
            selected_items = self.interpolatorListWidget.selectedItems()
            if not selected_items:
                QMessageBox.warning(
                    self,
                    "No Selection",
                    "Please select an interpolator to delete."
                )
                return
            
            name = selected_items[0].text()
            
            # Confirm deletion
            reply = QMessageBox.question(
                self,
                "Confirm Deletion",
                f"Are you sure you want to delete interpolator '{name}'?",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply != QMessageBox.Yes:
                return
            
            # Delete interpolator
            if self.interpolator_manager:
                self.interpolator_manager.remove_interpolator(name)
                self.logger(f"Deleted interpolator '{name}'", log_level=3)
                
                # Update UI
                self._update_interpolator_list()
                self._update_interpolator_combo()
                
                QMessageBox.information(
                    self,
                    "Success",
                    f"Deleted interpolator '{name}' successfully!"
                )
            
        except Exception as e:
            self.logger(f"Error deleting interpolator: {e}", log_level=2)
            QMessageBox.critical(self, "Error", f"Failed to delete interpolator:\n{str(e)}")

    def _update_interpolator_list(self):
        """Update the interpolator list widget."""
        self.interpolatorListWidget.clear()
        if self.interpolator_manager:
            for name in self.interpolator_manager.list_interpolators():
                self.interpolatorListWidget.addItem(name)

    def _update_interpolator_combo(self):
        """Update the interpolator combo box."""
        self.interpolatorCombo.clear()
        if self.interpolator_manager:
            self.interpolatorCombo.addItems(self.interpolator_manager.list_interpolators())
