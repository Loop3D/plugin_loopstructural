"""Data conversion widgets and dialog for LoopStructural."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from qgis.core import QgsMapLayerProxyModel, QgsProject, QgsVectorLayer
from qgis.gui import QgsMapLayerComboBox

from ...main.helpers import ColumnMatcher
from ...main.vectorLayerWrapper import QgsLayerFromDataFrame, QgsLayerFromGeoDataFrame
from LoopDataConverter import Datatype, InputData, LoopConverter, SurveyName

try:
    from geopandas import GeoDataFrame
except Exception:  # pragma: no cover - geopandas may be unavailable in tests
    GeoDataFrame = None

try:
    from pandas import DataFrame
except Exception:  # pragma: no cover - pandas may be unavailable in tests
    DataFrame = None


def _is_tabular_payload(value: Any) -> bool:
    if GeoDataFrame is not None and isinstance(value, GeoDataFrame):
        return True
    if DataFrame is not None and isinstance(value, DataFrame):
        return True
    return False


def _build_input_data(
    formatted_sources: Mapping[str, str],
    config_map: Optional[Mapping[str, Mapping[str, Any]]],
) -> Tuple[InputData, bool]:
    if config_map is None:
        return InputData(**formatted_sources), False

    for key in ("config_map", "config", "configuration"):
        try:
            return InputData(**formatted_sources, **{key: config_map}), True
        except TypeError:
            continue

    return InputData(**formatted_sources), False


def _build_loop_converter(
    survey_name: SurveyName,
    input_data: InputData,
    config_map: Optional[Mapping[str, Mapping[str, Any]]],
) -> Tuple[LoopConverter, bool]:
    if config_map is None:
        return LoopConverter(survey_name=survey_name, data=input_data), False

    for key in ("config_map", "config", "configuration"):
        try:
            return (
                LoopConverter(survey_name=survey_name, data=input_data, **{key: config_map}),
                True,
            )
        except TypeError:
            continue

    converter = LoopConverter(survey_name=survey_name, data=input_data)
    for method_name in ("set_config_map", "set_config", "set_configuration"):
        method = getattr(converter, method_name, None)
        if callable(method):
            method(config_map)
            return converter, True

    for attr_name in ("config_map", "config", "configuration"):
        if hasattr(converter, attr_name):
            try:
                setattr(converter, attr_name, config_map)
                return converter, True
            except Exception:
                continue

    return converter, False


def _run_loop_conversion(
    survey_name: SurveyName,
    data_sources: Mapping[Datatype | str, str],
    *,
    config_map: Optional[Mapping[str, Mapping[str, Any]]] = None,
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

    input_data, input_has_config = _build_input_data(formatted_sources, config_map)
    converter, converter_has_config = _build_loop_converter(survey_name, input_data, config_map)
    if config_map is not None and not (input_has_config or converter_has_config):
        raise ValueError("Conversion configuration could not be applied to the converter.")
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

    if isinstance(converters, (str, bytes)):
        converters = [converters]

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
        if self.project is not None:
            try:
                self.project.layersAdded.connect(self._guess_layers)
            except Exception:
                pass

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
        available = self._default_converter_options() if converters is None else converters
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
            if self.project is not None:
                try:
                    combo.setProject(self.project)
                except Exception:
                    pass
            combo.setFilters(self._layer_filter_for_data_type(data_type))
            combo.setAllowEmptyLayer(True)
            combo.setObjectName(f"automaticSource_{self._format_identifier_label(data_type)}")
            self.sources_layout.addRow(self._format_identifier_label(data_type), combo)
            self.layer_selectors[data_type] = combo
        self._schedule_guess_layers()

    def _schedule_guess_layers(self) -> None:
        QTimer.singleShot(0, self._guess_layers)

    def _guess_layers(self) -> None:
        """Attempt to auto-select layers based on common naming conventions."""
        if self.project is None and QgsProject.instance() is None:
            return

        for data_type, combo in self.layer_selectors.items():
            if combo.currentLayer() is not None:
                continue
            candidates = self._build_layer_candidate_map(combo)
            if not candidates:
                continue
            matcher = ColumnMatcher(list(candidates.keys()))
            match = None
            for target in self._target_keys_for_data_type(data_type):
                match = matcher.find_match(target)
                if match is not None:
                    break
            if match is None:
                match = matcher.find_match(self._format_identifier_label(data_type))
            if match is None and isinstance(data_type, Datatype):
                value = getattr(data_type, "value", None)
                if isinstance(value, str) and value.strip():
                    match = matcher.find_match(value)
            if match:
                layer = candidates.get(match)
                if layer is not None:
                    combo.setLayer(layer)

    def _build_layer_candidate_map(
        self, combo: QgsMapLayerComboBox
    ) -> Dict[str, QgsVectorLayer]:
        candidates: Dict[str, QgsVectorLayer] = {}
        for layer in self._layers_for_combo(combo):
            if not isinstance(layer, QgsVectorLayer) or not layer.isValid():
                continue
            for candidate in self._layer_candidates(layer):
                if candidate and candidate not in candidates:
                    candidates[candidate] = layer
                upper_candidate = candidate.upper() if isinstance(candidate, str) else None
                if upper_candidate and upper_candidate not in candidates:
                    candidates[upper_candidate] = layer
        return candidates

    def _layers_for_combo(self, combo: QgsMapLayerComboBox) -> List[QgsVectorLayer]:
        layers: List[QgsVectorLayer] = []
        for index in range(combo.count()):
            layer = combo.layer(index)
            if isinstance(layer, QgsVectorLayer):
                layers.append(layer)
        if layers:
            return layers
        project = self.project or QgsProject.instance()
        if project is None:
            return layers
        for layer in project.mapLayers().values():
            if isinstance(layer, QgsVectorLayer) and layer.isValid():
                layers.append(layer)
        return layers

    def _layer_candidates(self, layer: QgsVectorLayer) -> List[str]:
        names: List[str] = []
        if layer is None:
            return names
        layer_name = layer.name()
        if layer_name:
            names.append(layer_name)
        try:
            source = layer.source()
        except Exception:
            source = ""
        names.extend(self._names_from_source(source))
        return names

    def _names_from_source(self, source: str) -> List[str]:
        if not source:
            return []

        names: List[str] = []
        parts = source.split("|")
        base = parts[0].strip()
        if base:
            names.append(base)
            basename = os.path.basename(base)
            if basename:
                names.append(basename)
                stem, _ = os.path.splitext(basename)
                if stem:
                    names.append(stem)

        for part in parts[1:]:
            key, _, value = part.partition("=")
            if not value:
                continue
            key = key.strip().lower()
            if key in ("layername", "table"):
                cleaned = value.strip().strip("\"'").strip()
                if cleaned:
                    names.append(cleaned)

        for pattern in (r"\blayername\s*=\s*([^|;]+)", r"\btable\s*=\s*([^|;]+)"):
            match = re.search(pattern, source, re.IGNORECASE)
            if match:
                cleaned = match.group(1).strip().strip("\"'").strip()
                if cleaned:
                    names.append(cleaned)

        return names

    def _target_key_for_data_type(self, data_type: Datatype | str) -> str:
        if isinstance(data_type, Datatype):
            return data_type.name
        return str(data_type)

    def _target_keys_for_data_type(self, data_type: Datatype | str) -> List[str]:
        key = self._target_key_for_data_type(data_type).upper()
        if key == "GEOLOGY":
            return ["GEOLOGY", "LITH", "LITHOLOGY", "OUTCROP"]
        if key == "FOLD":
            return ["FOLD", "FOLDS"]
        if key == "FAULT":
            return ["FAULT", "FAULTS"]
        if key == "STRUCTURE":
            return ["STRUCTURE", "STRUCTURES"]
        return [key]

    def _layer_filter_for_data_type(self, data_type: Datatype | str) -> int:
        key = self._target_key_for_data_type(data_type).upper()
        if key == "GEOLOGY":
            return QgsMapLayerProxyModel.PolygonLayer
        if key == "FAULT":
            return QgsMapLayerProxyModel.LineLayer
        if key == "STRUCTURE":
            return QgsMapLayerProxyModel.PointLayer
        if key == "FOLD":
            return QgsMapLayerProxyModel.LineLayer
        return QgsMapLayerProxyModel.VectorLayer

    def _collect_data_sources(self) -> Dict[Datatype | str, str]:
        data_sources: Dict[Datatype | str, str] = {}
        for data_type, combo in self.layer_selectors.items():
            layer = combo.currentLayer()
            if layer and isinstance(layer, QgsVectorLayer) and layer.isValid():
                path = layer.source()
                if path:
                    data_sources[data_type] = path
        return data_sources

    def _handle_run_conversion(self) -> bool:
        converter_option = self.current_converter()
        if converter_option is None:
            self._update_status("Please select a converter before running.", error=True)
            return False

        sources = self._collect_data_sources()
        if not sources:
            self._update_status("Select at least one data source layer before running.", error=True)
            return False

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
            return False

        if added_layers:
            message = (
                f"Conversion completed: {added_layers} layer(s) added to '{self.OUTPUT_GROUP_NAME}'."
            )
        elif result not in (None, True):
            message = f"Conversion completed: {result}"
        else:
            message = "Conversion completed successfully."
        self._update_status(message)
        return True

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
        if _is_tabular_payload(payload):
            layer = self._vector_layer_from_value(prefix, payload)
            if layer is not None and layer.isValid():
                layers.append(layer)
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


class AutomaticConversionDialog(QDialog):
    """Dialog wrapper for the automatic conversion workflow."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        converters: Optional[Iterable[Any]] = None,
        project: Optional[QgsProject] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Data Converter")
        self.project = project or QgsProject.instance()

        layout = QVBoxLayout(self)
        description = QLabel("Convert geological datasets for use within LoopStructural.")
        description.setWordWrap(True)
        layout.addWidget(description)

        self.widget = AutomaticConversionWidget(self, converters=converters, project=self.project)
        layout.addWidget(self.widget)
        self.widget.run_button.hide()

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.button_box.accepted.connect(self._run_and_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _run_and_accept(self) -> None:
        if self.widget._handle_run_conversion():
            self.accept()

    def set_converters(self, converters: Iterable[Any]) -> None:
        """Update the converter options displayed in the dialog."""
        self.widget.set_converters(converters)
