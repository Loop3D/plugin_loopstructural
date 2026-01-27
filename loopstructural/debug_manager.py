#! python3

"""Debug manager handling logging and debug directory management."""

# standard
import datetime
import json
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any

# PyQGIS
from qgis.core import QgsProject

# project
import loopstructural.toolbelt.preferences as plg_prefs_hdlr


class DebugManager:
    """Manage debug mode state, logging and debug file storage."""

    def __init__(self, plugin):
        self.plugin = plugin
        self._session_dir = None
        self._session_id = uuid.uuid4().hex
        self._project_name = self._get_project_name()
        self._debug_state_logged = False
        self.logger = self.plugin.log

    def _get_settings(self):
        return plg_prefs_hdlr.PlgOptionsManager.get_plg_settings()

    def _get_project_name(self) -> str:
        try:
            proj = QgsProject.instance()
            title = proj.title()
            if title:
                return title
            stem = Path(proj.fileName() or "").stem
            return stem or "untitled_project"
        except Exception as err:
            self.plugin.log(
                message=f"[map2loop] Failed to resolve project name: {err}",
                log_level=1,
            )
            return "unknown_project"

    def is_debug(self) -> bool:
        """Return whether debug mode is enabled."""
        try:
            state = bool(self._get_settings().debug_mode)
            if not self._debug_state_logged:
                self.plugin.log(
                    message=f"[map2loop] Debug mode: {'ON' if state else 'OFF'}",
                    log_level=0,
                )
                self._debug_state_logged = True
            return state
        except Exception as err:
            self.plugin.log(
                message=f"[map2loop] Error checking debug mode: {err}",
                log_level=2,
            )
            return False

    def get_effective_debug_dir(self) -> Path:
        """Return the session debug directory, creating it if needed."""
        if self._session_dir is not None:
            return self._session_dir

        try:
            debug_dir_pref = plg_prefs_hdlr.PlgOptionsManager.get_debug_directory()
        except Exception as err:
            self.plugin.log(
                message=f"[map2loop] Reading debug_directory failed: {err}",
                log_level=1,
            )
            debug_dir_pref = ""

        base_dir = (
            Path(debug_dir_pref).expanduser()
            if str(debug_dir_pref).strip()
            else Path(tempfile.gettempdir()) / "map2loop_debug"
        )

        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        session_dir = base_dir / self._project_name / f"session_{self._session_id}_{ts}"

        try:
            session_dir.mkdir(parents=True, exist_ok=True)
        except Exception as err:
            self.plugin.log(
                message=(
                    f"[map2loop] Failed to create session dir '{session_dir}': {err}. "
                    "Falling back to system temp."
                ),
                log_level=1,
            )
            fallback = (
                Path(tempfile.gettempdir())
                / "map2loop_debug"
                / self._project_name
                / f"session_{self._session_id}_{ts}"
            )
            try:
                fallback.mkdir(parents=True, exist_ok=True)
            except Exception as err_fallback:
                self.plugin.log(
                    message=(
                        f"[map2loop] Failed to create fallback debug dir '{fallback}': "
                        f"{err_fallback}"
                    ),
                    log_level=2,
                )
                fallback = Path(tempfile.gettempdir())
            session_dir = fallback

        self._session_dir = session_dir
        self.plugin.log(
            message=f"[map2loop] Debug directory resolved: {session_dir}",
            log_level=0,
        )
        return self._session_dir

    def _sanitize_label(self, context_label: str) -> str:
        """Sanitize context label for safe filename usage."""
        return "".join(
            c if c.isalnum() or c in ("-", "_") else "_"
            for c in context_label.replace(" ", "_").lower()
        )

    def _export_gdf(self, gdf, out_path: Path) -> bool:
        """Export a GeoPandas GeoDataFrame to GeoJSON if geopandas available."""
        try:
            import geopandas as gpd

            if isinstance(gdf, gpd.GeoDataFrame):
                gdf.to_file(out_path, driver="GeoJSON")
                return True
        except Exception as err:
            # geopandas not available or export failed
            self.plugin.log(message=f"[map2loop] GeoDataFrame export failed: {err}", log_level=1)
        return False

    def _export_qgis_layer(self, qgs_layer, out_path: Path) -> bool:
        """Export a QGIS QgsVectorLayer to GeoJSON if available."""
        try:
            from qgis.core import QgsVectorFileWriter

            # In QGIS 3, writeAsVectorFormatV2 is preferred, but use writeAsVectorFormat for compatibility
            err = QgsVectorFileWriter.writeAsVectorFormat(
                qgs_layer, str(out_path), "utf-8", qgs_layer.crs(), "GeoJSON"
            )
            # writeAsVectorFormat returns 0 on success in many QGIS versions
            if err == 0:
                return True
            # Some versions return (error, msg)
            return False
        except Exception as err:
            self.plugin.log(message=f"[map2loop] QGIS layer export failed: {err}", log_level=1)
            return False

    def _prepare_value_for_export(self, safe_label: str, key: str, value):
        """If value is an exportable object, export it and return a reference dict.

        Otherwise return the original value. The reference dict has the form
        {"export_path": <path>} so the runner script can re-load exported layers.
        """
        debug_dir = self.get_effective_debug_dir()
        filename_base = f"{safe_label}_{key}"

        # GeoPandas GeoDataFrame
        try:
            import geopandas as gpd

            if isinstance(value, gpd.GeoDataFrame):
                out_path = debug_dir / f"{filename_base}.geojson"
                if self._export_gdf(value, out_path):
                    return {"export_path": str(out_path)}
        except Exception:
            pass

        # QGIS vector layer
        try:
            from qgis.core import QgsVectorLayer

            if isinstance(value, QgsVectorLayer):
                out_path = debug_dir / f"{filename_base}.geojson"
                if self._export_qgis_layer(value, out_path):
                    return {"export_path": str(out_path)}
        except Exception:
            pass

        # Not exportable: return as-is
        return value

    def _prepare_params_for_export(self, context_label: str, params: Any):
        """Walk params and export embedded spatial layers where possible.

        Returns a payload safe to JSON-serialize where exported objects are
        replaced with {"export_path": ...} references.
        """
        safe_label = self._sanitize_label(context_label)

        def _recurse(obj, prefix=""):
            # dict
            if isinstance(obj, dict):
                out = {}
                for k, v in obj.items():
                    out[k] = _recurse(v, f"{prefix}_{k}" if prefix else k)
                return out
            # list/tuple
            if isinstance(obj, (list, tuple)):
                return [_recurse(v, f"{prefix}_{i}") for i, v in enumerate(obj)]
            # try to export known types
            exported = self._prepare_value_for_export(safe_label, prefix or "item", obj)
            # If export returns same object, return raw value (may fail JSON later)
            return exported

        return _recurse(params)

    def export_file(self, filename: str, content_bytes: bytes):
        """Convenience wrapper so callers can ask DebugManager to export a file.

        This centralizes debug file persistence through DebugManager.
        """
        return self.save_debug_file(filename, content_bytes)

    def log_params(self, context_label: str, params: Any):
        """Log parameters and persist them when debug mode is enabled.

        Prior to saving params, attempt to export embedded spatial layers and
        replace them with file references so the saved JSON can be reloaded by
        the runner script.
        """
        try:
            self.plugin.log(
                message=f"[map2loop] {context_label} parameters: {str(params)}",
                log_level=0,
            )
        except Exception as err:
            self.plugin.log(
                message=(
                    f"[map2loop] {context_label} parameters (stringified due to {err}): {str(params)}"
                ),
                log_level=0,
            )

        if self.is_debug():
            try:
                # Prepare params by exporting embedded layers where applicable
                payload = params if isinstance(params, dict) else {"_payload": params}
                safe_payload = self._prepare_params_for_export(context_label, payload)

                debug_dir = self.get_effective_debug_dir()
                safe_label = self._sanitize_label(context_label)
                file_path = debug_dir / f"{safe_label}_params.json"
                with open(file_path, "w", encoding="utf-8") as file_handle:
                    json.dump(safe_payload, file_handle, ensure_ascii=False, indent=2, default=str)
                self.plugin.log(
                    message=f"[map2loop] Params saved to: {file_path}",
                    log_level=0,
                )
                self._ensure_runner_script()
            except Exception as err:
                self.plugin.log(
                    message=f"[map2loop] Failed to save params for {context_label}: {err}",
                    log_level=2,
                )

    def save_debug_file(self, filename: str, content_bytes: bytes):
        """Persist a debug file atomically and log its location."""
        try:
            debug_dir = self.get_effective_debug_dir()
            out_path = debug_dir / filename
            tmp_path = debug_dir / (filename + ".tmp")
            with open(tmp_path, "wb") as file_handle:
                file_handle.write(content_bytes)
            os.replace(tmp_path, out_path)
            self.plugin.log(
                message=f"[map2loop] Debug file saved: {out_path}",
                log_level=0,
            )
            return out_path
        except Exception as err:
            self.plugin.log(
                message=f"[map2loop] Failed to save debug file '{filename}': {err}",
                log_level=2,
            )
            return None

    def _ensure_runner_script(self):
        """Create a reusable runner script in the debug directory."""
        try:
            debug_dir = self.get_effective_debug_dir()
            script_path = debug_dir / "run_map2loop.py"
            if script_path.exists():
                return
            script_content = """#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

import geopandas as gpd

from loopstructural.main import m2l_api


def load_layer(layer_info):
    if isinstance(layer_info, dict):
        export_path = layer_info.get("export_path")
        if export_path:
            return gpd.read_file(export_path)
    return layer_info


def load_params(path):
    params = json.loads(Path(path).read_text())
    # convert exported layers to GeoDataFrames
    for key, value in list(params.items()):
        params[key] = load_layer(value)
    return params


def run(params):
    if "sampler_type" in params:
        result = m2l_api.sample_contacts(**params)
        print("Sampler result:", result)
    elif "sorting_algorithm" in params:
        result = m2l_api.sort_stratigraphic_column(**params)
        print("Sorter result:", result)
    elif "calculator_type" in params:
        result = m2l_api.calculate_thickness(**params)
        print("Thickness result:", result)
    elif "geology_layer" in params and "unit_name_field" in params:
        result = m2l_api.extract_basal_contacts(**params)
        print("Basal contacts result:", result)
    else:
        print("Unknown params shape; inspect manually:", params.keys())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "params",
        nargs="?",
        default=None,
        help="Path to params JSON (defaults to first *_params.json in this folder)",
    )
    args = parser.parse_args()
    base = Path(__file__).parent
    params_path = Path(args.params) if args.params else next(base.glob("*_params.json"))
    params = load_params(params_path)
    run(params)


if __name__ == "__main__":
    main()
"""
            script_path.write_text(script_content, encoding="utf-8")
        except Exception as err:
            self.plugin.log(
                message=f"[map2loop] Failed to create runner script: {err}",
                log_level=1,
            )

    def export_layer(self, layer, name_prefix: str):
        """Public wrapper to export a layer or GeoDataFrame via the DebugManager.

        Returns the path to the exported file (string) on success, or None on failure.
        """
        if not self.is_debug():
            return None
        safe_prefix = self._sanitize_label(name_prefix)
        debug_dir = self.get_effective_debug_dir()

        # Try GeoPandas GeoDataFrame
        try:
            import geopandas as gpd

            if isinstance(layer, gpd.GeoDataFrame):
                out_path = debug_dir / f"{safe_prefix}.geojson"
                if self._export_gdf(layer, out_path):
                    return str(out_path)
        except Exception:
            pass

        # Try QGIS vector layer
        try:
            from qgis.core import QgsVectorLayer

            if isinstance(layer, QgsVectorLayer):
                out_path = debug_dir / f"{safe_prefix}.geojson"
                if self._export_qgis_layer(layer, out_path):
                    return str(out_path)
        except Exception:
            pass

        # Unsupported type or export failed
        self.plugin.log(
            message=f"[map2loop] export_layer: Could not export object of type {type(layer)}",
            log_level=1,
        )
        return None
