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

    def log_params(self, context_label: str, params: Any):
        """Log parameters and persist them when debug mode is enabled."""
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
                debug_dir = self.get_effective_debug_dir()
                safe_label = self._sanitize_label(context_label)
                file_path = debug_dir / f"{safe_label}_params.json"
                payload = params if isinstance(params, dict) else {"_payload": params}
                with open(file_path, "w", encoding="utf-8") as file_handle:
                    json.dump(payload, file_handle, ensure_ascii=False, indent=2, default=str)
                self.plugin.log(
                    message=f"[map2loop] Params saved to: {file_path}",
                    log_level=0,
                )
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
