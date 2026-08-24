import os

import numpy as np
from qgis.core import (
    QgsApplication,
    QgsCoordinateTransform,
    QgsGeometry,
    QgsProject,
    QgsRectangle,
    QgsWkbTypes,
)
from qgis.gui import QgsMapToolExtent, QgsRubberBand
from qgis.PyQt import uic
from qgis.PyQt.QtCore import QSize
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import QWidget

from loopstructural.main.data_manager import default_bounding_box


class BoundingBoxWidget(QWidget):
    def __init__(self, parent=None, data_manager=None):
        self.data_manager = data_manager
        super().__init__(parent)
        ui_path = os.path.join(os.path.dirname(__file__), "bounding_box.ui")
        uic.loadUi(ui_path, self)

        # The three extent-setting actions are icon-only tool buttons (styled
        # here rather than in the .ui, to match the icon buttons used
        # elsewhere in the plugin); their tooltips carry the old label text.
        self._style_tool_button(
            self.selectFromCurrentLayerButton, "mActionZoomToLayer.svg", "Select from Current Layer"
        )
        self._style_tool_button(
            self.useCurrentViewExtentButton,
            "mActionSetToCanvasExtent.svg",
            "Use Current View Extent",
        )
        self._style_tool_button(self.drawOnMapButton, "mActionAddBasicRectangle.svg", "Draw on Map")
        self.drawOnMapButton.setCheckable(True)
        self.drawOnMapButton.clicked.connect(self.drawOnMap)
        self._draw_extent_tool = None
        self._previous_map_tool = None

        self._style_tool_button(
            self.showBoundingBoxButton, "mActionShowAllLayers.svg", "Show Bounding Box on Map"
        )
        self.showBoundingBoxButton.setCheckable(True)
        self.showBoundingBoxButton.toggled.connect(self._on_show_bounding_box_toggled)
        self._bounding_box_rubber_band = None

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

        # Connect to project CRS changes so the widget updates when the project's CRS changes
        try:
            project = getattr(self.data_manager, 'project', None) or QgsProject.instance()
            project.crsChanged.connect(self._onProjectCrsChanged)
        except Exception:
            # If the signal isn't available or connection fails, ignore to keep widget functional
            pass

        # Keep the bounding box outline (when shown) aligned with the canvas
        # if its own CRS ever changes independently of the project's.
        try:
            if self.data_manager.map_canvas is not None:
                self.data_manager.map_canvas.destinationCrsChanged.connect(
                    self._update_bounding_box_rubber_band
                )
        except Exception:
            pass

    @staticmethod
    def _style_tool_button(button, theme_icon_name, tooltip):
        """Configure a .ui-declared QToolButton with an icon and tooltip,
        since icons aren't set from the .ui file (see the other icon-only
        toolbars in the visualisation sidebar and stratigraphic column).
        """
        button.setIcon(QgsApplication.getThemeIcon(theme_icon_name))
        button.setIconSize(QSize(22, 22))
        button.setToolTip(tooltip)
        button.setAutoRaise(True)

    def _transform_rect(self, rect, source_crs, dest_crs):
        """Reproject a QgsRectangle's X/Y coordinates from source_crs to
        dest_crs. Falls back to the original rectangle unchanged if either
        CRS is missing/invalid, they already match, or the transform fails
        (e.g. no known path between the two CRSs) -- Z is never touched
        here, since horizontal reprojection says nothing about elevation.
        """
        if source_crs is None or not source_crs.isValid():
            return rect
        if dest_crs is None or not dest_crs.isValid():
            return rect
        if source_crs == dest_crs:
            return rect
        try:
            project = getattr(self.data_manager, 'project', None) or QgsProject.instance()
            transform = QgsCoordinateTransform(source_crs, dest_crs, project)
            return transform.transformBoundingBox(rect)
        except Exception:
            return rect

    def _rect_to_model_crs(self, rect, source_crs):
        """Reproject a rectangle from source_crs into the model's chosen CRS
        (see the CRS controls above the extent actions).
        """
        return self._transform_rect(rect, source_crs, self.data_manager.get_model_crs())

    def _rect_from_model_crs(self, rect, dest_crs):
        """Reproject a rectangle from the model's chosen CRS into dest_crs."""
        return self._transform_rect(rect, self.data_manager.get_model_crs(), dest_crs)

    def _on_show_bounding_box_toggled(self, checked):
        """Show or hide the bounding box outline on the map canvas."""
        if checked:
            self._update_bounding_box_rubber_band()
        elif self._bounding_box_rubber_band is not None:
            self._bounding_box_rubber_band.hide()

    def _update_bounding_box_rubber_band(self):
        """Redraw the bounding box outline on the canvas from the current
        X/Y extent fields, reprojected into the canvas's own CRS. A no-op
        while the "Show Bounding Box on Map" button isn't checked.
        """
        if not self.showBoundingBoxButton.isChecked():
            return
        canvas = self.data_manager.map_canvas
        if canvas is None:
            return

        if self._bounding_box_rubber_band is None:
            rubber_band = QgsRubberBand(canvas, QgsWkbTypes.PolygonGeometry)
            rubber_band.setColor(QColor(255, 0, 0, 60))
            rubber_band.setStrokeColor(QColor(255, 0, 0, 200))
            rubber_band.setWidth(2)
            self._bounding_box_rubber_band = rubber_band

        rect = QgsRectangle(
            self.originXSpinBox.value(),
            self.originYSpinBox.value(),
            self.maxXSpinBox.value(),
            self.maxYSpinBox.value(),
        )
        rect = self._rect_from_model_crs(rect, canvas.mapSettings().destinationCrs())
        self._bounding_box_rubber_band.setToGeometry(QgsGeometry.fromRect(rect), None)
        self._bounding_box_rubber_band.show()

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
                self.crsSelector.setCrs(crs)

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

        self._update_bounding_box_rubber_band()

    def _onProjectCrsChanged(self, crs=None):
        """Handle project CRS changes and update UI when the widget is using the project CRS.

        Accept an optional `crs` argument because different QGIS versions may emit the
        new CRS or emit no arguments when the project's CRS changes.
        """
        # If the signal didn't provide a CRS, try to obtain it from the project's current CRS
        if crs is None:
            try:
                project = getattr(self.data_manager, 'project', None) or QgsProject.instance()
                crs = project.crs()
            except Exception:
                crs = None

        # Only update the UI if the model is configured to use the project CRS
        try:
            if getattr(self.data_manager, '_use_project_crs', False):
                # Update the UI to reflect the new project CRS
                self.update_crs_ui(crs, use_project_crs=True)
        except Exception:
            pass

    def validate_crs(self):
        """Validate the selected CRS and update warning label."""
        crs = self.data_manager.get_model_crs()

        if crs is None or not crs.isValid():
            self.crsWarningLabel.setText("⚠ Invalid CRS selected. Model cannot be initialized.")
            return False

        if crs.isGeographic():
            # Safely get CRS description
            try:
                crs_desc = crs.description() or crs.authid() or "Unknown"
            except Exception:
                crs_desc = crs.authid() if hasattr(crs, 'authid') else "Unknown"

            self.crsWarningLabel.setText(
                f"⚠ CRS must be projected (in meters), not geographic.\n" f"Selected: {crs_desc}"
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
        self._update_bounding_box_rubber_band()

    def useCurrentViewExtent(self):
        """Set bounding box values from the current map canvas view extent."""
        if self.data_manager.map_canvas:
            canvas = self.data_manager.map_canvas
            extent = self._rect_to_model_crs(canvas.extent(), canvas.mapSettings().destinationCrs())
            self.originXSpinBox.setValue(extent.xMinimum())
            self.originYSpinBox.setValue(extent.yMinimum())
            self.originZSpinBox.setValue(0)
            self.maxXSpinBox.setValue(extent.xMaximum())
            self.maxYSpinBox.setValue(extent.yMaximum())
            self.maxZSpinBox.setValue(1000)

    def drawOnMap(self, checked):
        """Toggle an interactive rubber-band rectangle tool on the map canvas.

        While active, the button stays pressed and the user's next
        click-drag on the canvas sets the X/Y extent (Z is left at the same
        defaults as `useCurrentViewExtent`, since a 2D canvas drag carries no
        Z information). Clicking the button again, pressing Escape, or
        picking any other map tool cancels the draw.
        """
        canvas = self.data_manager.map_canvas
        if canvas is None:
            self.drawOnMapButton.setChecked(False)
            return

        if checked:
            # `QgsMapCanvas.unsetMapTool` does not reliably restore whatever
            # tool was active before ours (it can leave the canvas with no
            # tool at all), so remember it ourselves and restore explicitly.
            self._previous_map_tool = canvas.mapTool()
            tool = QgsMapToolExtent(canvas)
            tool.extentChanged.connect(self._on_draw_on_map_extent_changed)
            tool.deactivated.connect(self._on_draw_on_map_tool_deactivated)
            self._draw_extent_tool = tool
            canvas.setMapTool(tool)
        else:
            self._restore_previous_map_tool()

    def _on_draw_on_map_extent_changed(self, rectangle):
        """Apply the rectangle drawn on the canvas to the X/Y extent fields."""
        canvas = self.data_manager.map_canvas
        source_crs = canvas.mapSettings().destinationCrs() if canvas is not None else None
        rectangle = self._rect_to_model_crs(rectangle, source_crs)
        self.originXSpinBox.setValue(rectangle.xMinimum())
        self.originYSpinBox.setValue(rectangle.yMinimum())
        self.originZSpinBox.setValue(0)
        self.maxXSpinBox.setValue(rectangle.xMaximum())
        self.maxYSpinBox.setValue(rectangle.yMaximum())
        self.maxZSpinBox.setValue(1000)
        self._restore_previous_map_tool()

    def _restore_previous_map_tool(self):
        """Put the canvas back into whatever tool was active before the draw
        started (falling back to just clearing our tool if there wasn't one).
        """
        canvas = self.data_manager.map_canvas
        if canvas is not None:
            if self._previous_map_tool is not None:
                canvas.setMapTool(self._previous_map_tool)
            elif self._draw_extent_tool is not None:
                canvas.unsetMapTool(self._draw_extent_tool)
        self._previous_map_tool = None

    def _on_draw_on_map_tool_deactivated(self):
        """Reset the button whenever the draw tool stops being active, be it
        because we just finished a draw, or the user cancelled by pressing
        Escape or switching to a different map tool mid-draw.
        """
        self.drawOnMapButton.setChecked(False)
        self._draw_extent_tool = None

    def selectFromCurrentLayer(self):
        """Set bounding box values from the currently selected layer's 3D extent."""
        layer = self.data_manager.map_canvas.currentLayer()
        if layer:
            box3d = layer.extent3D()
            extent = self._rect_to_model_crs(box3d.toRectangle(), layer.crs())
            self.originXSpinBox.setValue(extent.xMinimum())
            self.originYSpinBox.setValue(extent.yMinimum())
            if np.isnan(box3d.zMinimum()):
                self.originZSpinBox.setValue(default_bounding_box['zmin'])
            else:
                self.originZSpinBox.setValue(box3d.zMinimum())

            self.maxXSpinBox.setValue(extent.xMaximum())
            self.maxYSpinBox.setValue(extent.yMaximum())
            if np.isnan(box3d.zMaximum()):
                self.maxZSpinBox.setValue(default_bounding_box['zmax'])
            else:
                self.maxZSpinBox.setValue(box3d.zMaximum())

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
