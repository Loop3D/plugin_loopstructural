import os

import numpy as np
from PyQt5.QtWidgets import QWidget
from qgis.core import QgsCoordinateReferenceSystem
from qgis.PyQt import uic

from loopstructural.main.data_manager import default_bounding_box


class BoundingBoxWidget(QWidget):
    def __init__(self, parent=None, data_manager=None):
        self.data_manager = data_manager
        super().__init__(parent)
        ui_path = os.path.join(os.path.dirname(__file__), "bounding_box.ui")
        uic.loadUi(ui_path, self)
        
        # Connect bounding box spinbox signals
        self.originXSpinBox.valueChanged.connect(lambda x: self.onChangeExtent({'xmin': x}))
        self.maxXSpinBox.valueChanged.connect(lambda x: self.onChangeExtent({'xmax': x}))
        self.originYSpinBox.valueChanged.connect(lambda y: self.onChangeExtent({'ymin': y}))
        self.maxYSpinBox.valueChanged.connect(lambda y: self.onChangeExtent({'ymax': y}))
        self.originZSpinBox.valueChanged.connect(lambda z: self.onChangeExtent({'zmin': z}))
        self.maxZSpinBox.valueChanged.connect(lambda z: self.onChangeExtent({'zmax': z}))
        self.useCurrentViewExtentButton.clicked.connect(self.useCurrentViewExtent)
        self.selectFromCurrentLayerButton.clicked.connect(self.selectFromCurrentLayer)
        
        # Connect CRS control signals
        self.useProjectCrsRadioButton.toggled.connect(self.onCrsSourceChanged)
        self.useCustomCrsRadioButton.toggled.connect(self.onCrsSourceChanged)
        self.crsSelector.crsChanged.connect(self.onCrsChanged)
        
        # Set up callbacks
        self.data_manager.set_bounding_box_update_callback(self.set_bounding_box)
        self.data_manager.set_model_crs_callback(self.update_crs_ui)
        
        # Initialize CRS UI
        self.initialize_crs_ui()
        self._update_bounding_box_styles()

    def initialize_crs_ui(self):
        """Initialize CRS controls with current settings."""
        # Set initial CRS selector value
        crs = self.data_manager.get_model_crs()
        if crs is not None and crs.isValid():
            self.crsSelector.setCrs(crs)
        else:
            # Default to project CRS
            self.crsSelector.setCrs(self.data_manager.project.crs())
        
        # Set radio button based on use_project_crs setting
        if self.data_manager._use_project_crs:
            self.useProjectCrsRadioButton.setChecked(True)
        else:
            self.useCustomCrsRadioButton.setChecked(True)
        
        self.validate_crs()

    def onCrsSourceChanged(self):
        """Handle change in CRS source (project vs custom)."""
        use_project_crs = self.useProjectCrsRadioButton.isChecked()
        self.crsSelector.setEnabled(not use_project_crs)
        
        if use_project_crs:
            # Use project CRS
            success, msg = self.data_manager.set_model_crs(None, use_project_crs=True)
        else:
            # Use custom CRS
            crs = self.crsSelector.crs()
            success, msg = self.data_manager.set_model_crs(crs, use_project_crs=False)
        
        self.validate_crs()

    def onCrsChanged(self):
        """Handle change in custom CRS selection."""
        if self.useCustomCrsRadioButton.isChecked():
            crs = self.crsSelector.crs()
            success, msg = self.data_manager.set_model_crs(crs, use_project_crs=False)
            self.validate_crs()

    def update_crs_ui(self, crs, use_project_crs):
        """Update UI when model CRS changes externally.
        
        Parameters
        ----------
        crs : QgsCoordinateReferenceSystem or None
            The new model CRS
        use_project_crs : bool
            Whether to use project CRS
        """
        # Block signals to avoid recursive updates
        self.useProjectCrsRadioButton.blockSignals(True)
        self.useCustomCrsRadioButton.blockSignals(True)
        self.crsSelector.blockSignals(True)
        
        try:
            if use_project_crs:
                self.useProjectCrsRadioButton.setChecked(True)
                self.crsSelector.setEnabled(False)
            else:
                self.useCustomCrsRadioButton.setChecked(True)
                self.crsSelector.setEnabled(True)
                if crs is not None and crs.isValid():
                    self.crsSelector.setCrs(crs)
            
            self.validate_crs()
        finally:
            # Unblock signals
            self.useProjectCrsRadioButton.blockSignals(False)
            self.useCustomCrsRadioButton.blockSignals(False)
            self.crsSelector.blockSignals(False)

    def validate_crs(self):
        """Validate the selected CRS and update warning label."""
        crs = self.data_manager.get_model_crs()
        
        if crs is None or not crs.isValid():
            self.crsWarningLabel.setText("⚠ Invalid CRS selected. Model cannot be initialized.")
            return False
        
        if crs.isGeographic():
            self.crsWarningLabel.setText(
                f"⚠ CRS must be projected (in meters), not geographic.\n"
                f"Selected: {crs.description()}"
            )
            return False
        
        # CRS is valid and projected
        self.crsWarningLabel.setText("")
        return True

    def set_bounding_box(self, bounding_box):
        """Populate UI controls with values from a BoundingBox object.

        Parameters
        ----------
        bounding_box : object
            BoundingBox-like object with `origin` and `maximum` sequences of length 3.
        """
        # Block spinbox signals to avoid emitting valueChanged while setting values
        spinboxes = (
            self.originXSpinBox,
            self.maxXSpinBox,
            self.originYSpinBox,
            self.maxYSpinBox,
            self.originZSpinBox,
            self.maxZSpinBox,
        )
        for sb in spinboxes:
            try:
                sb.blockSignals(True)
            except Exception:
                pass

        try:
            self.originXSpinBox.setValue(bounding_box.origin[0])
            self.maxXSpinBox.setValue(bounding_box.maximum[0])
            self.originYSpinBox.setValue(bounding_box.origin[1])
            self.maxYSpinBox.setValue(bounding_box.maximum[1])
            self.originZSpinBox.setValue(bounding_box.origin[2])
            self.maxZSpinBox.setValue(bounding_box.maximum[2])
        finally:
            # Ensure signals are unblocked even if setting values raises
            for sb in spinboxes:
                try:
                    sb.blockSignals(False)
                except Exception:
                    pass

        self._update_bounding_box_styles()

    def useCurrentViewExtent(self):
        """Set bounding box values from the current map canvas view extent."""
        if self.data_manager.map_canvas:
            extent = self.data_manager.map_canvas.extent()
            self.originXSpinBox.setValue(extent.xMinimum())
            self.originYSpinBox.setValue(extent.yMinimum())
            self.originZSpinBox.setValue(0)
            self.maxXSpinBox.setValue(extent.xMaximum())
            self.maxYSpinBox.setValue(extent.yMaximum())
            self.maxZSpinBox.setValue(1000)

    def selectFromCurrentLayer(self):
        """Set bounding box values from the currently selected layer's 3D extent."""
        layer = self.data_manager.map_canvas.currentLayer()
        if layer:
            extent = layer.extent3D()
            self.originXSpinBox.setValue(extent.xMinimum())
            self.originYSpinBox.setValue(extent.yMinimum())
            if np.isnan(extent.zMinimum()):
                self.originZSpinBox.setValue(default_bounding_box['zmin'])
            else:
                self.originZSpinBox.setValue(extent.zMinimum())

            self.maxXSpinBox.setValue(extent.xMaximum())
            self.maxYSpinBox.setValue(extent.yMaximum())
            if np.isnan(extent.zMaximum()):
                self.maxZSpinBox.setValue(default_bounding_box['zmax'])
            else:
                self.maxZSpinBox.setValue(extent.zMaximum())

    def onChangeExtent(self, value):
        self.data_manager.set_bounding_box(**value)
        try:
            self._update_bounding_box_styles()
        except Exception:
            pass

    def _update_bounding_box_styles(self):
        """Highlight spin boxes if bounding box has not been set."""
        if not hasattr(self, 'data_manager'):
            return
        try:
            is_set = self.data_manager.is_bounding_box_set()
        except Exception:
            is_set = False
        red_style = "border: 1px solid red;"
        clear_style = ""
        for sb in (
            self.originXSpinBox,
            self.originYSpinBox,
            self.originZSpinBox,
            self.maxXSpinBox,
            self.maxYSpinBox,
            self.maxZSpinBox,
        ):
            sb.setStyleSheet(clear_style if is_set else red_style)
