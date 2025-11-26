"""Data conversion widget displayed inside the LoopStructural dock."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from qgis.core import QgsMapLayer, QgsMapLayerProxyModel, QgsProject, QgsVectorLayer
from qgis.gui import QgsFieldComboBox, QgsMapLayerComboBox

from ...main.vectorLayerWrapper import QgsLayerFromDataFrame, QgsLayerFromGeoDataFrame
from .configuration import ConfigurationState
from LoopDataConverter import Datatype, InputData, LoopConverter, SurveyName

try:
    from geopandas import GeoDataFrame
except Exception:  # pragma: no cover - geopandas may be unavailable in tests
    GeoDataFrame = None

try:
    from pandas import DataFrame
except Exception:  # pragma: no cover - pandas may be unavailable in tests
    DataFrame = None


def _run_loop_conversion(
    survey_name: SurveyName, data_sources: Mapping[Datatype | str, str]
) -> Tuple[Any, Any]:
    """Execute the LoopDataConverter workflow for the supplied survey and data."""
    if not data_sources:
        raise ValueError("At least one data source is required for conversion.")

    formatted_sources: Dict[str, str] = {}
    for data_type, dataset in data_sources.items():
        if not dataset:
            continue
        key = data_type.name if isinstance(data_type, Datatype) else str(data_type)
        formatted_sources[key.split(".")[-1].upper()] = dataset

    if not formatted_sources:
        raise ValueError("Unable to run conversion without valid data sources.")

    input_data = InputData(**formatted_sources)
    converter = LoopConverter(survey_name=survey_name, data=input_data)
    conversion_result = converter.convert()
    return converter, conversion_result


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

    SUPPORTED_DATA_TYPES: Tuple[str, ...] = ("GEOLOGY", "STRUCTURE", "FAULT", "FOLD")
    OUTPUT_DATA_TYPES: Tuple[str, ...] = ("GEOLOGY", "STRUCTURE", "FAULT", "FOLD", "FAULT_ORIENTATION")
    OUTPUT_GROUP_NAME = "Loop-Ready Data"

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        converters: Optional[Iterable[Any]] = None,
        project: Optional[QgsProject] = None,
    ):
        super().__init__(parent)
        self.project = project or QgsProject.instance()
        self._options: List[ConverterOption] = []
        self._data_types: List[Datatype | str] = self._discover_data_types()
        self.layer_selectors: Dict[Datatype | str, QgsMapLayerComboBox] = {}
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

        source_description = QLabel("Select the layers that correspond to each dataset required by the converter.")
        source_description.setWordWrap(True)
        layout.addWidget(source_description)

        self.sources_widget = QWidget()
        self.sources_layout = QFormLayout(self.sources_widget)
        self.sources_layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignTop)
        layout.addWidget(self.sources_widget)
        self._build_data_source_inputs()

        actions_widget = QWidget()
        actions_layout = QHBoxLayout(actions_widget)
        actions_layout.setContentsMargins(0, 0, 0, 0)

        self.run_button = QPushButton("Run Conversion")
        self.run_button.clicked.connect(self._handle_run_conversion)
        actions_layout.addWidget(self.run_button)
        actions_layout.addStretch()

        self.status_label = QLabel("")
        self.status_label.setObjectName("automaticConversionStatus")
        actions_layout.addWidget(self.status_label)

        layout.addWidget(actions_widget)

        self.set_converters(converters)
        self.converter_combo.currentIndexChanged.connect(self._update_summary_text)

    def set_converters(self, converters: Optional[Iterable[Any]]) -> None:
        """Populate the dropdown with the converters supplied by the backend."""
        available = converters if converters else self._default_converter_options()
        self._options = _normalise_converters(available)
        self.converter_combo.clear()
        for option in self._options:
            self.converter_combo.addItem(option.label, option.identifier)
        if not self._options:
            self.converter_combo.addItem("No converters available")
            self.converter_combo.setEnabled(False)
            self.run_button.setEnabled(False)
        else:
            self.converter_combo.setEnabled(True)
            self.run_button.setEnabled(True)
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

    def _build_data_source_inputs(self) -> None:
        while self.sources_layout.count():
            item = self.sources_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.layer_selectors.clear()

        for data_type in self._data_types:
            combo = QgsMapLayerComboBox()
            combo.setFilters(QgsMapLayerProxyModel.VectorLayer)
            combo.setAllowEmptyLayer(True)
            combo.setObjectName(f"automaticSource_{self._format_identifier_label(data_type)}")
            self.sources_layout.addRow(self._format_identifier_label(data_type), combo)
            self.layer_selectors[data_type] = combo

    def _collect_data_sources(self) -> Dict[Datatype | str, str]:
        data_sources: Dict[Datatype | str, str] = {}
        for data_type, combo in self.layer_selectors.items():
            layer = combo.currentLayer()
            if layer and isinstance(layer, QgsVectorLayer) and layer.isValid():
                path = layer.source()
                if path:
                    data_sources[data_type] = path
        return data_sources

    def _handle_run_conversion(self) -> None:
        converter_option = self.current_converter()
        if converter_option is None:
            self._update_status("Please select a converter before running.", error=True)
            return

        sources = self._collect_data_sources()
        if not sources:
            self._update_status("Select at least one data source layer before running.", error=True)
            return

        loop_converter: Any = None
        result: Any = None
        added_layers = 0
        try:
            survey = self._normalise_survey_name(converter_option.identifier)
            loop_converter, result = self.run_conversion(survey, sources)
            layers = self._build_layers_from_converter(loop_converter)
            if not layers:
                layers = self._materialise_layers_from_result(result)
            if layers:
                added_layers = self._add_layers_to_project_group(layers)
        except Exception as exc:  # pragma: no cover - UI feedback
            self._update_status(f"Conversion failed: {exc}", error=True)
            return

        if added_layers:
            message = (
                f"Conversion completed: {added_layers} layer(s) added to '{self.OUTPUT_GROUP_NAME}'."
            )
        elif result not in (None, True):
            message = f"Conversion completed: {result}"
        else:
            message = "Conversion completed successfully."
        self._update_status(message)

    def _update_status(self, message: str, *, error: bool = False) -> None:
        color = "#c00000" if error else "#006400"
        self.status_label.setStyleSheet(f"color: {color};")
        self.status_label.setText(message)

    def run_conversion(
        self, survey_name: SurveyName | str, data_sources: Mapping[Datatype | str, str]
    ) -> Tuple[Any, Any]:
        """Execute the LoopConverter against the supplied dataset."""
        survey = self._normalise_survey_name(survey_name)
        return _run_loop_conversion(survey, data_sources)

    @staticmethod
    def _normalise_survey_name(value: SurveyName | str) -> SurveyName:
        """Convert user-provided identifiers into a SurveyName enum."""
        if isinstance(value, SurveyName):
            return value
        key = str(value).strip()
        if "." in key:
            key = key.split(".", 1)[1]
        try:
            return SurveyName[key]
        except KeyError:
            pass
        try:
            return SurveyName[key.upper()]
        except KeyError as exc:
            raise ValueError(f"Unknown survey name '{value}'.") from exc

    def _build_layers_from_converter(self, converter: Any) -> List[QgsVectorLayer]:
        if converter is None:
            return []
        data_store = getattr(converter, "data", None)
        if not data_store:
            return []

        layers: List[QgsVectorLayer] = []
        for identifier in self.OUTPUT_DATA_TYPES:
            dtype = self._datatype_for_name(identifier)
            dataset = self._extract_dataset(data_store, dtype)
            if dataset is None:
                continue
            layer = self._vector_layer_from_value(dtype, dataset)
            if layer is not None and layer.isValid():
                layers.append(layer)
        return layers

    def _datatype_for_name(self, identifier: str | Datatype) -> Datatype | str:
        if isinstance(identifier, Datatype):
            return identifier
        try:
            return Datatype[str(identifier)]
        except Exception:
            return str(identifier)

    def _extract_dataset(self, data_store: Any, key: Datatype | str) -> Any:
        if data_store is None:
            return None

        candidates: List[Any] = []
        if isinstance(key, Datatype):
            candidates.append(key)
            candidates.append(key.name)
            value = getattr(key, "value", None)
            if value is not None:
                candidates.append(value)
        else:
            candidates.append(key)

        text_key = str(key)
        if "." in text_key:
            text_key = text_key.split(".", 1)[-1]
        candidates.extend(
            [
                text_key,
                text_key.upper(),
                text_key.lower(),
            ]
        )

        for candidate in candidates:
            if candidate is None:
                continue
            if isinstance(data_store, Mapping) and candidate in data_store:
                return data_store[candidate]
            getter = getattr(data_store, "__getitem__", None)
            if callable(getter):
                try:
                    return getter(candidate)
                except Exception:
                    pass
            attr_name = str(candidate).lower()
            if hasattr(data_store, attr_name):
                return getattr(data_store, attr_name)
        return None

    def _materialise_layers_from_result(self, result: Any) -> List[QgsVectorLayer]:
        layers: List[QgsVectorLayer] = []
        self._collect_layers_from_result(result, layers, prefix="output")
        return layers

    def _collect_layers_from_result(
        self, payload: Any, layers: List[QgsVectorLayer], *, prefix: str
    ) -> None:
        if payload is None:
            return
        if isinstance(payload, Mapping):
            for key, value in payload.items():
                label = str(key)
                self._collect_layers_from_result(value, layers, prefix=label or prefix)
            return
        if isinstance(payload, (list, tuple, set)):
            for index, value in enumerate(payload, start=1):
                self._collect_layers_from_result(value, layers, prefix=f"{prefix}_{index}")
            return
        layer = self._vector_layer_from_value(prefix, payload)
        if layer is not None and layer.isValid():
            layers.append(layer)

    def _vector_layer_from_value(self, name: Any, value: Any) -> Optional[QgsVectorLayer]:
        label = self._format_identifier_label(str(name))
        if isinstance(value, QgsVectorLayer):
            value.setName(label)
            return value
        if GeoDataFrame is not None and isinstance(value, GeoDataFrame):
            try:
                return QgsLayerFromGeoDataFrame(value, layer_name=label)
            except ValueError:
                # fall back to attribute-only table if geometry is missing
                return QgsLayerFromDataFrame(value, layer_name=label)
        if DataFrame is not None and isinstance(value, DataFrame):
            return QgsLayerFromDataFrame(value, layer_name=label)
        if (
            DataFrame is not None
            and isinstance(value, list)
            and value
            and all(isinstance(item, Mapping) for item in value)
        ):
            try:
                dataframe = DataFrame(value)
            except Exception:
                dataframe = None
            if dataframe is not None:
                return QgsLayerFromDataFrame(dataframe, layer_name=label)
        if isinstance(value, str):
            layer = QgsVectorLayer(value, label, "ogr")
            return layer if layer.isValid() else None
        if isinstance(value, Mapping):
            provider = str(value.get("provider") or "ogr")
            nested_layer = value.get("layer")
            if isinstance(nested_layer, QgsVectorLayer):
                nested_layer.setName(str(value.get("name") or label))
                return nested_layer if nested_layer.isValid() else None
            for key in ("path", "source", "file"):
                path = value.get(key)
                if isinstance(path, str):
                    layer_name = str(value.get("name") or label)
                    layer = QgsVectorLayer(path, layer_name, provider)
                    return layer if layer.isValid() else None
        return None

    def _add_layers_to_project_group(self, layers: Iterable[QgsVectorLayer]) -> int:
        project = self.project or QgsProject.instance()
        if project is None:
            return 0
        root = project.layerTreeRoot()
        if root is None:
            return 0
        group = root.findGroup(self.OUTPUT_GROUP_NAME)
        if group is None:
            group = root.insertGroup(0, self.OUTPUT_GROUP_NAME)
        added = 0
        for layer in layers:
            if project.mapLayer(layer.id()) is None:
                project.addMapLayer(layer, False)
            group.addLayer(layer)
            added += 1
        return added

    def _discover_data_types(self) -> List[Datatype | str]:
        members = getattr(Datatype, "__members__", None)
        if isinstance(members, Mapping):
            selected = [members[name] for name in self.SUPPORTED_DATA_TYPES if name in members]
            if selected:
                return selected

        try:
            enum_values = list(Datatype)
        except TypeError:
            enum_values = []
        data_types: List[Datatype | str] = []
        for candidate in enum_values:
            name = getattr(candidate, "name", str(candidate)).upper()
            if name in self.SUPPORTED_DATA_TYPES:
                data_types.append(candidate)
        if data_types:
            return data_types
        return list(self.SUPPORTED_DATA_TYPES)

    def _format_identifier_label(self, identifier: Datatype | str) -> str:
        member: Optional[Datatype] = identifier if isinstance(identifier, Datatype) else None
        text_value = None if isinstance(identifier, Datatype) else str(identifier).strip()

        if member is None and text_value:
            # Try exact member name
            candidates = getattr(Datatype, "__members__", {})
            key = text_value.split(".", 1)[-1].upper()
            member = candidates.get(key)

        if member is None and text_value:
            # Try matching the enum value
            lowered = text_value.lower()
            for enum_member in getattr(Datatype, "__members__", {}).values():
                if str(getattr(enum_member, "value", "")).lower() == lowered:
                    member = enum_member
                    break

        if member is not None:
            name = member.name
        else:
            name = text_value or "Data"
            if "." in name:
                name = name.split(".")[-1]

        parts = name.replace("_", " ").split()
        return " ".join(part.capitalize() for part in parts) or "Data"

    def _default_converter_options(self) -> List[ConverterOption]:
        members = getattr(SurveyName, "__members__", None)
        if not isinstance(members, Mapping):
            return []
        options: List[ConverterOption] = []
        for name, survey in members.items():
            label = getattr(survey, "value", None)
            if not isinstance(label, str) or not label.strip():
                label = self._format_identifier_label(name)
            description = getattr(survey, "description", "")
            options.append(ConverterOption(identifier=name, label=label, description=description))
        return options


class ManualConversionWidget(QWidget):
    """Widget that lets the user map table columns to the NTGS configuration."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        config_model: Optional[ConfigurationState] = None,
        project: Optional[QgsProject] = None,
    ):
        super().__init__(parent)
        self.project = project or QgsProject.instance()
        self.model = config_model or ConfigurationState()
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

        self.automatic_widget = AutomaticConversionWidget(self, converters=converters, project=self.project)
        self.manual_widget = ManualConversionWidget(self, config_model=ConfigurationState(), project=self.project)

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
