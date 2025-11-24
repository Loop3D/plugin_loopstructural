"""Data conversion widget displayed inside the LoopStructural dock."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QComboBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from qgis.core import QgsMapLayer, QgsMapLayerProxyModel, QgsProject, QgsVectorLayer
from qgis.gui import QgsFieldComboBox, QgsMapLayerComboBox

from .configuration import NtgsConfigurationModel


@dataclass
class ConverterOption:
    """Simple data container describing an available converter."""

    identifier: str
    label: str
    description: str = ""

    def to_dict(self) -> Dict[str, str]:
        """Return a serialisable representation of the option."""
        return {
            "id": self.identifier,
            "label": self.label,
            "description": self.description,
        }


def _normalise_converters(converters: Optional[Iterable[Any]]) -> List[ConverterOption]:
    normalised: List[ConverterOption] = []
    if not converters:
        return normalised

    for raw in converters:
        if isinstance(raw, ConverterOption):
            normalised.append(raw)
            continue

        if isinstance(raw, Mapping):
            identifier = str(
                raw.get("id")
                or raw.get("identifier")
                or raw.get("name")
                or raw.get("label")
                or "converter"
            )
            label = str(raw.get("label") or raw.get("name") or identifier)
            description = str(raw.get("description") or "")
            normalised.append(ConverterOption(identifier=identifier, label=label, description=description))
            continue

        text = str(raw)
        normalised.append(ConverterOption(identifier=text, label=text, description=""))
    return normalised


class AutomaticConversionWidget(QWidget):
    """Widget showing the automatic conversion workflow."""

    def __init__(self, parent: Optional[QWidget] = None, *, converters: Optional[Iterable[Any]] = None):
        super().__init__(parent)
        self._options: List[ConverterOption] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        description = QLabel(
            "Automatically run one of the available converters on the selected data sources."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        self.converter_combo = QComboBox()
        self.converter_combo.setToolTip("Select the converter implementation to run.")
        layout.addWidget(self.converter_combo)

        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setMinimumHeight(80)
        layout.addWidget(self.summary_text)

        self.set_converters(converters)
        self.converter_combo.currentIndexChanged.connect(self._update_summary_text)

    def set_converters(self, converters: Optional[Iterable[Any]]) -> None:
        """Populate the dropdown with the converters supplied by the backend."""
        self._options = _normalise_converters(converters)
        self.converter_combo.clear()
        for option in self._options:
            self.converter_combo.addItem(option.label, option.identifier)
        if not self._options:
            self.converter_combo.addItem("No converters available")
            self.converter_combo.setEnabled(False)
        else:
            self.converter_combo.setEnabled(True)
        self._update_summary_text()

    def current_converter(self) -> Optional[ConverterOption]:
        """Return the active converter option, if any."""
        index = self.converter_combo.currentIndex()
        if index < 0 or index >= len(self._options):
            return None
        return self._options[index]

    def _update_summary_text(self) -> None:
        option = self.current_converter()
        if option is None:
            self.summary_text.setPlainText(
                "No converter selected. Please configure converters in the plugin settings."
            )
        else:
            description = option.description or "No description provided for this converter."
            self.summary_text.setPlainText(description)


class ManualConversionWidget(QWidget):
    """Widget that lets the user map table columns to the NTGS configuration."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        config_model: Optional[NtgsConfigurationModel] = None,
        project: Optional[QgsProject] = None,
    ):
        super().__init__(parent)
        self.project = project or QgsProject.instance()
        self.model = config_model or NtgsConfigurationModel()
        self.data_types = list(self.model.data_types())
        if not self.data_types:
            raise ValueError("Configuration model does not provide any data types.")
        self.current_data_type = self.data_types[0]
        self.layer_selections: Dict[str, Optional[Dict[str, str]]] = {
            dtype: None for dtype in self.data_types
        }
        self.field_widgets: Dict[str, QWidget] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        instructions = QLabel(
            "Manually map QGIS table columns to the fields expected by the NTGS configuration."
            " Select a data type, choose the source table and assign each field."
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        self.data_type_combo = QComboBox()
        for dtype in self.data_types:
            self.data_type_combo.addItem(dtype.title(), dtype)
        layout.addWidget(self.data_type_combo)

        self.layer_combo = QgsMapLayerComboBox()
        self.layer_combo.setFilters(QgsMapLayerProxyModel.VectorLayer)
        self.layer_combo.setAllowEmptyLayer(True)
        layout.addWidget(self.layer_combo)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        layout.addWidget(self.scroll_area, stretch=1)

        self.form_widget = QWidget()
        self.form_layout = QFormLayout(self.form_widget)
        self.form_layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.scroll_area.setWidget(self.form_widget)

        self.data_type_combo.currentIndexChanged.connect(self._handle_data_type_changed)
        self.layer_combo.layerChanged.connect(self._handle_layer_changed)

        self._apply_layer_selection_for_current_type()
        self._build_form()

    def _handle_data_type_changed(self, index: int) -> None:
        next_data_type = self.data_type_combo.itemData(index)
        if not next_data_type or next_data_type == self.current_data_type:
            return
        self._persist_current_values()
        self.current_data_type = next_data_type
        self._apply_layer_selection_for_current_type()
        self._build_form()

    def _apply_layer_selection_for_current_type(self) -> None:
        selection = self.layer_selections.get(self.current_data_type)
        if not selection:
            self.layer_combo.setCurrentIndex(-1)
            return
        layer = self._layer_from_selection(selection)
        if layer is None:
            self.layer_combo.setCurrentIndex(-1)
            return
        self.layer_combo.setLayer(layer)

    def _layer_from_selection(self, selection: Dict[str, str]) -> Optional[QgsMapLayer]:
        if not selection:
            return None
        layer_id = selection.get("layer_id")
        if not layer_id or self.project is None:
            return None
        return self.project.mapLayer(layer_id)

    def _handle_layer_changed(self, layer: Optional[QgsMapLayer]) -> None:
        if layer and isinstance(layer, QgsVectorLayer):
            self.layer_selections[self.current_data_type] = {
                "layer_id": layer.id(),
                "layer_name": layer.name(),
            }
        else:
            self.layer_selections[self.current_data_type] = None

        for key, widget in self.field_widgets.items():
            if isinstance(widget, QgsFieldComboBox):
                widget.setLayer(layer)
                stored_value = self.model.get_value(self.current_data_type, key)
                if stored_value:
                    widget.setField(stored_value)
                else:
                    widget.setCurrentIndex(-1)

    def _build_form(self) -> None:
        while self.form_layout.count():
            item = self.form_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.field_widgets.clear()

        config = self.model.get_config_for_type(self.current_data_type)
        for key, default_value in config.items():
            widget = self._create_widget_for_entry(key, default_value)
            self.form_layout.addRow(self._format_label(key), widget)
            self.field_widgets[key] = widget

    def _create_widget_for_entry(self, key: str, value: Any) -> QWidget:
        if key.endswith("_column"):
            field_combo = QgsFieldComboBox()
            field_combo.setLayer(self.layer_combo.currentLayer())
            if hasattr(field_combo, "setAllowEmptyFieldName"):
                field_combo.setAllowEmptyFieldName(True)
            stored = self.model.get_value(self.current_data_type, key)
            if stored:
                field_combo.setField(stored)
            return field_combo

        line_edit = QLineEdit()
        line_edit.setText(self._stringify_value(value))
        line_edit.setClearButtonEnabled(True)
        return line_edit

    def _format_label(self, key: str) -> str:
        parts = key.replace("_", " ").split()
        return " ".join(part.capitalize() for part in parts)

    def _stringify_value(self, value: Any) -> str:
        if isinstance(value, list):
            return ", ".join(str(item) for item in value)
        if value is None:
            return ""
        return str(value)

    def _persist_current_values(self) -> None:
        if not self.field_widgets:
            return

        updates: Dict[str, Any] = {}
        for key, widget in self.field_widgets.items():
            if isinstance(widget, QgsFieldComboBox):
                updates[key] = widget.currentField() or ""
            elif isinstance(widget, QLineEdit):
                updates[key] = widget.text()
        self.model.update_values(self.current_data_type, updates)

        layer = self.layer_combo.currentLayer()
        if layer and isinstance(layer, QgsVectorLayer):
            self.layer_selections[self.current_data_type] = {
                "layer_id": layer.id(),
                "layer_name": layer.name(),
            }
        else:
            self.layer_selections[self.current_data_type] = None

    def get_configuration(self) -> Dict[str, Dict[str, Any]]:
        """Return the configuration map built from the user selections."""
        self._persist_current_values()
        return self.model.as_dict()

    def get_layer_selections(self) -> Dict[str, Optional[Dict[str, str]]]:
        """Return the per-data-type layer selections."""
        self._persist_current_values()
        return {key: (value.copy() if value else None) for key, value in self.layer_selections.items()}


class DataConversionWidget(QWidget):
    """High level widget that exposes tabs for automatic and manual conversion."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        data_manager: Any = None,
        converters: Optional[Iterable[Any]] = None,
        project: Optional[QgsProject] = None,
    ):
        super().__init__(parent)
        self.data_manager = data_manager
        self.project = project or QgsProject.instance()

        layout = QVBoxLayout(self)
        description = QLabel("Convert geological datasets for use within LoopStructural.")
        description.setWordWrap(True)
        layout.addWidget(description)

        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        self.automatic_widget = AutomaticConversionWidget(self, converters=converters)
        self.manual_widget = ManualConversionWidget(self, config_model=NtgsConfigurationModel(), project=self.project)

        self.tab_widget.addTab(self.automatic_widget, "Automatic")
        self.tab_widget.addTab(self.manual_widget, "Manual")

    def set_converters(self, converters: Iterable[Any]) -> None:
        """Update the converter options displayed in the automatic tab."""
        self.automatic_widget.set_converters(converters)

    def get_active_configuration(self) -> Dict[str, Any]:
        """Return a serialisable summary of the current tab selection."""
        if self.tab_widget.currentWidget() is self.automatic_widget:
            converter = self.automatic_widget.current_converter()
            return {
                "mode": "automatic",
                "converter": converter.to_dict() if converter else None,
            }

        return {
            "mode": "manual",
            "layers": self.manual_widget.get_layer_selections(),
            "config_map": self.manual_widget.get_configuration(),
        }
