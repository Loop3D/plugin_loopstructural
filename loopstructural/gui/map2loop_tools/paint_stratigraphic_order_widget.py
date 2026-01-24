"""Widget for painting stratigraphic order onto geology polygons."""

import os

from PyQt5.QtWidgets import QMessageBox, QWidget
from qgis.core import QgsMapLayerProxyModel, QgsProject
from qgis.PyQt import uic

from loopstructural.toolbelt.preferences import PlgOptionsManager


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
            self.stratColumnLayerComboBox.setFilters(QgsMapLayerProxyModel.NoGeometry)
        except Exception:
            # If QGIS isn't available, skip filter setup
            pass

        # Initialize paint modes
        self.paint_modes = ["Stratigraphic Order (0=youngest)", "Cumulative Thickness"]
        self.paintModeComboBox.addItems(self.paint_modes)

        # Connect signals
        self.geologyLayerComboBox.layerChanged.connect(self._on_geology_layer_changed)
        self.stratColumnLayerComboBox.layerChanged.connect(self._on_strat_column_layer_changed)
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
        self._on_strat_column_layer_changed()

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

    def _on_strat_column_layer_changed(self):
        """Update stratigraphic column field combo boxes when layer changes."""
        strat_layer = self.stratColumnLayerComboBox.currentLayer()
        self.stratUnitFieldComboBox.setLayer(strat_layer)
        self.stratThicknessFieldComboBox.setLayer(strat_layer)

        # Try to auto-select common field names
        if strat_layer:
            field_names = [field.name() for field in strat_layer.fields()]
            
            # Unit name field
            for common_name in ['unit_name', 'name', 'UNITNAME', 'unitname']:
                if common_name in field_names:
                    self.stratUnitFieldComboBox.setField(common_name)
                    break
            
            # Thickness field
            for common_name in ['thickness', 'THICKNESS', 'thick']:
                if common_name in field_names:
                    self.stratThicknessFieldComboBox.setField(common_name)
                    break

    def _run_painter(self):
        """Run the paint stratigraphic order algorithm."""
        from qgis import processing

        self._log_params("paint_strat_order_widget_run")

        # Validate inputs
        if not self.geologyLayerComboBox.currentLayer():
            QMessageBox.warning(self, "Missing Input", "Please select a geology polygon layer.")
            return

        if not self.stratColumnLayerComboBox.currentLayer():
            QMessageBox.warning(self, "Missing Input", "Please select a stratigraphic column layer.")
            return

        if not self.unitNameFieldComboBox.currentField():
            QMessageBox.warning(self, "Missing Input", "Please select the unit name field.")
            return

        if not self.stratUnitFieldComboBox.currentField():
            QMessageBox.warning(
                self, "Missing Input", "Please select the stratigraphic column unit name field."
            )
            return

        # Run the processing algorithm
        try:
            params = {
                'INPUT_POLYGONS': self.geologyLayerComboBox.currentLayer(),
                'UNIT_NAME_FIELD': self.unitNameFieldComboBox.currentField(),
                'INPUT_STRAT_COLUMN': self.stratColumnLayerComboBox.currentLayer(),
                'STRAT_UNIT_NAME_FIELD': self.stratUnitFieldComboBox.currentField(),
                'STRAT_THICKNESS_FIELD': self.stratThicknessFieldComboBox.currentField() or '',
                'PAINT_MODE': self.paintModeComboBox.currentIndex(),
                'OUTPUT': 'TEMPORARY_OUTPUT',
            }

            if self._debug and self._debug.is_debug():
                try:
                    import json

                    params_json = json.dumps(
                        self._serialize_params_for_logging(params, "paint_strat_order"),
                        indent=2,
                    ).encode("utf-8")
                    self._debug.save_debug_file("paint_strat_order_params.json", params_json)
                except Exception as err:
                    self._debug.plugin.log(
                        message=f"[map2loop] Failed to save paint strat order params: {err}",
                        log_level=2,
                    )

            result = processing.run("plugin_map2loop:paint_stratigraphic_order", params)

            if result and 'OUTPUT' in result:
                output_layer = result['OUTPUT']
                if output_layer:
                    QgsProject.instance().addMapLayer(output_layer)
                    
                    field_name = (
                        'strat_order' if self.paintModeComboBox.currentIndex() == 0 
                        else 'cum_thickness'
                    )
                    
                    QMessageBox.information(
                        self,
                        "Success",
                        f"Stratigraphic order painted successfully!\n"
                        f"Output layer added with '{field_name}' field.",
                    )
                else:
                    QMessageBox.warning(self, "Warning", "No output layer was generated.")
            else:
                QMessageBox.warning(self, "Warning", "Algorithm did not produce expected output.")

        except Exception as e:
            if self._debug:
                self._debug.plugin.log(
                    message=f"[map2loop] Paint stratigraphic order failed: {e}",
                    log_level=2,
                )
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
            'geology_layer': self.geologyLayerComboBox.currentLayer(),
            'unit_name_field': self.unitNameFieldComboBox.currentField(),
            'strat_column_layer': self.stratColumnLayerComboBox.currentLayer(),
            'strat_unit_field': self.stratUnitFieldComboBox.currentField(),
            'strat_thickness_field': self.stratThicknessFieldComboBox.currentField(),
            'paint_mode': self.paintModeComboBox.currentIndex(),
        }

    def set_parameters(self, params):
        """Set widget parameters.

        Parameters
        ----------
        params : dict
            Dictionary of parameters to set.
        """
        if 'geology_layer' in params and params['geology_layer']:
            self.geologyLayerComboBox.setLayer(params['geology_layer'])
        if 'unit_name_field' in params and params['unit_name_field']:
            self.unitNameFieldComboBox.setField(params['unit_name_field'])
        if 'strat_column_layer' in params and params['strat_column_layer']:
            self.stratColumnLayerComboBox.setLayer(params['strat_column_layer'])
        if 'strat_unit_field' in params and params['strat_unit_field']:
            self.stratUnitFieldComboBox.setField(params['strat_unit_field'])
        if 'strat_thickness_field' in params and params['strat_thickness_field']:
            self.stratThicknessFieldComboBox.setField(params['strat_thickness_field'])
        if 'paint_mode' in params:
            self.paintModeComboBox.setCurrentIndex(params['paint_mode'])
