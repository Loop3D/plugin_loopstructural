#! python3

"""Preferences manager helpers for the plugin.

This module exposes `PlgOptionsManager` which centralises access to plugin
settings used across the UI and background services.
"""

# standard
import logging
from dataclasses import asdict, dataclass, fields

# PyQGIS
from qgis.core import QgsSettings

# package
import loopstructural.toolbelt.log_handler as log_hdlr
from loopstructural.__about__ import __title__, __version__

# ############################################################################
# ########## Classes ###############
# ##################################


@dataclass
class PlgSettingsStructure:
    """Plugin settings structure and defaults values."""

    # global
    debug_mode: bool = False
    debug_directory: str = ""
    version: str = __version__
    interpolator_type: str = 'FDI'
    interpolator_nelements: int = 10000
    interpolator_regularisation: float = 1.0
    interpolator_cpw: float = 1.0
    interpolator_npw: float = 1.0
    separate_dock_widgets: bool = False


class PlgOptionsManager:
    """Manager for accessing and updating plugin configuration values.

    Provides convenience helpers around QGIS settings storage used by the
    plugin to persist user preferences such as debug mode and UI options.
    """

    @staticmethod
    def _configure_logging(debug_mode: bool):
        """Configure Python logging level according to plugin debug setting.

        When debug_mode is True the root logger level is set to DEBUG so that
        any logger.debug(...) calls in the plugin will be emitted. When False
        the level is set to INFO to reduce verbosity.
        """
        try:
            root = logging.getLogger()
            root.setLevel(logging.DEBUG if bool(debug_mode) else logging.INFO)
        except Exception:
            # Best-effort: do not raise from logging configuration issues
            pass

    @staticmethod
    def get_plg_settings() -> PlgSettingsStructure:
        """Load and return plugin settings as a PlgSettingsStructure instance.

        Useful to get user preferences across plugin logic.

        Returns
        -------
        PlgSettingsStructure
            Plugin settings dataclass populated from QGIS settings.
        """
        # get dataclass fields definition
        settings_fields = fields(PlgSettingsStructure)

        # retrieve settings from QGIS/Qt
        settings = QgsSettings()
        settings.beginGroup(__title__)

        # map settings values to preferences object
        li_settings_values = []
        for i in settings_fields:
            li_settings_values.append(
                settings.value(key=i.name, defaultValue=i.default, type=i.type)
            )

        # instanciate new settings object
        options = PlgSettingsStructure(*li_settings_values)

        settings.endGroup()

        # Ensure logging level matches the loaded debug_mode preference
        PlgOptionsManager._configure_logging(options.debug_mode)

        return options

    @staticmethod
    def get_value_from_key(key: str, default=None, exp_type=None):
        """Load a single plugin setting value by key.

        Parameters
        ----------
        key : str
            Settings key to retrieve (must match a field on `PlgSettingsStructure`).
        default : any, optional
            Default value to return if the key is not set.
        exp_type : type, optional
            Expected type for the value retrieval.

        Returns
        -------
        any
            The stored setting value or None if an error occurs or the key is invalid.
        """
        if not hasattr(PlgSettingsStructure, key):
            log_hdlr.PlgLogger.log(
                message="Bad settings key. Must be one of: {}".format(
                    ",".join(PlgSettingsStructure._fields)
                ),
                log_level=1,
            )
            return None

        settings = QgsSettings()
        settings.beginGroup(__title__)

        try:
            out_value = settings.value(key=key, defaultValue=default, type=exp_type)
        except Exception as err:
            log_hdlr.PlgLogger.log(
                message="Error occurred trying to get settings: {}.Trace: {}".format(key, err)
            )
            out_value = None

        settings.endGroup()

        return out_value

    @classmethod
    def get_debug_mode(cls) -> bool:
        """Get the current debug mode setting.

        Returns
        -------
        bool
            True if debug mode is enabled, False otherwise.
        """
        return cls.get_value_from_key("debug_mode", default=False, exp_type=bool)

    @classmethod
    def get_debug_directory(cls) -> str:
        """Get the configured debug directory path."""
        value = cls.get_value_from_key("debug_directory", default="", exp_type=str)
        return value if value is not None else ""

    @classmethod
    def set_debug_directory(cls, path: str) -> bool:
        """Set the debug directory path."""
        return cls.set_value_from_key("debug_directory", path or "")

    @classmethod
    def set_value_from_key(cls, key: str, value) -> bool:
        """Set a plugin setting value in QGIS settings.

        Parameters
        ----------
        key : str
            Settings key to set (must match a field on `PlgSettingsStructure`).
        value : any
            Value to store for the given key.

        Returns
        -------
        bool
            True if the operation succeeded, False otherwise.
        """
        if not hasattr(PlgSettingsStructure, key):
            log_hdlr.PlgLogger.log(
                message="Bad settings key. Must be one of: {}".format(
                    ",".join(PlgSettingsStructure._fields)
                ),
                log_level=2,
            )
            return False

        settings = QgsSettings()
        settings.beginGroup(__title__)

        try:
            settings.setValue(key, value)
            out_value = True

            # If debug mode was toggled, immediately apply logging configuration
            if key == "debug_mode":
                try:
                    PlgOptionsManager._configure_logging(value)
                except Exception:
                    pass
        except Exception as err:
            log_hdlr.PlgLogger.log(
                message="Error occurred trying to set settings: {}.Trace: {}".format(key, err)
            )
            out_value = False

        settings.endGroup()

        return out_value

    @classmethod
    def save_from_object(cls, plugin_settings_obj: PlgSettingsStructure):
        """Persist a settings dataclass to QGIS settings.

        Parameters
        ----------
        plugin_settings_obj : PlgSettingsStructure
            Dataclass instance containing settings to save.

        Returns
        -------
        None
        """
        settings = QgsSettings()
        settings.beginGroup(__title__)

        for k, v in asdict(plugin_settings_obj).items():
            cls.set_value_from_key(k, v)

        settings.endGroup()
