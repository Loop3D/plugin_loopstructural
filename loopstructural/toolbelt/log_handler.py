#!/usr/bin/env python3
"""Logging helpers that forward Python logging into QGIS messaging systems.

This module provides a convenience `PlgLogger` for emitting user-facing
messages to the QGIS message log and message bar, and `PlgLoggerHandler` that
bridges Python's `logging` into the plugin's logging facilities.
"""

# standard library
import logging
from functools import partial
from typing import Callable, Literal, Optional, Union

# PyQGIS
from qgis.core import Qgis, QgsMessageLog, QgsMessageOutput
from qgis.gui import QgsMessageBar
from qgis.PyQt.QtWidgets import QPushButton, QWidget
from qgis.utils import iface

import loopstructural.toolbelt.preferences as plg_prefs_hdlr

# project package
from loopstructural.__about__ import __title__

# ############################################################################
# ########## Classes ###############
# ##################################


class PlgLogger(logging.Handler):
    """Python logging handler supercharged with QGIS useful methods."""

    @staticmethod
    def log(
        message: str,
        application: str = __title__,
        log_level: int = 0,
        push: bool = False,
        duration: int = None,
        # widget
        button: bool = False,
        button_text: str = None,
        button_connect: Callable = None,
        # parent
        parent_location: QWidget = None,
    ):
        """Send messages to QGIS messages windows and to the user as a message bar.

        Plugin name is used as title. If debug mode is disabled, only warnings
        and errors (or messages with `push=True`) are shown.

        Parameters
        ----------
        message : str
            Message to display.
        application : str, optional
            Name of the application sending the message. Defaults to plugin title.
        log_level : int, optional
            Message level. Possible values: 0 (info), 1 (warning), 2 (critical),
            3 (success), 4 (none/grey). Defaults to 0 (info).
        push : bool, optional
            If True, also display the message in the QGIS message bar.
        duration : int or None, optional
            Duration in seconds for the message. If None, a duration is computed
            from the log level. If 0 the message must be dismissed manually.
        button : bool, optional
            Display a button in the message bar (defaults to False).
        button_text : str or None, optional
            Text label for the optional button.
        button_connect : Callable or None, optional
            Callable invoked when the optional button is pressed.
        parent_location : QWidget or None, optional
            Parent widget in which to search for a `QgsMessageBar`. If not
            provided, the QGIS main message bar is used.

        Returns
        -------
        None
        """
        # if not debug mode and not push, let's ignore INFO, SUCCESS and TEST
        debug_mode = plg_prefs_hdlr.PlgOptionsManager.get_plg_settings().debug_mode
        if not debug_mode and not push and (log_level < 1 or log_level > 2):
            return

        # ensure message is a string
        if not isinstance(message, str):
            try:
                message = str(message)
            except Exception as err:
                err_msg = "Log message must be a string, not: {}. Trace: {}".format(
                    type(message), err
                )
                logging.error(err_msg)
                message = err_msg

        # send it to QGIS messages panel
        QgsMessageLog.logMessage(message=message, tag=application, notifyUser=push, level=log_level)

        # optionally, display message on QGIS Message bar (above the map canvas)
        if push and iface is not None:
            msg_bar = None

            # QGIS or custom dialog
            if parent_location and isinstance(parent_location, QWidget):
                msg_bar = parent_location.findChild(QgsMessageBar)

            if not msg_bar:
                msg_bar = iface.messageBar()

            # calc duration
            if duration is None:
                duration = (log_level + 1) * 3

            # create message with/out a widget
            if button:
                # create output message
                notification = iface.messageBar().createMessage(title=application, text=message)
                widget_button = QPushButton(button_text or "More...")
                if button_connect:
                    widget_button.clicked.connect(button_connect)
                else:
                    mini_dlg = QgsMessageOutput.createMessageOutput()
                    mini_dlg.setTitle(application)
                    mini_dlg.setMessage(message, QgsMessageOutput.MessageText)
                    widget_button.clicked.connect(partial(mini_dlg.showMessage, False))

                notification.layout().addWidget(widget_button)
                msg_bar.pushWidget(widget=notification, level=log_level, duration=duration)

            else:
                # send simple message
                msg_bar.pushMessage(
                    title=application,
                    text=message,
                    level=log_level,
                    duration=duration,
                )


class PlgLoggerHandler(logging.Handler):
    """Handler that forwards Python log records to the plugin logger.

    The handler calls the provided `plg_logger_class.log()` static method to
    forward formatted log messages to QGIS messaging systems.
    """

    def __init__(self, plg_logger_class, level=logging.NOTSET, push=False, duration=None):
        """Initialize the log handler.

        Parameters
        ----------
        plg_logger_class : class
            Class providing a static `log()` method (like PlgLogger).
        level : int, optional
            The logging level to handle. Defaults to logging.NOTSET.
        push : bool, optional
            Whether to push messages to the QGIS message bar.
        duration : int, optional
            Optional fixed duration for messages.
        """
        super().__init__(level)
        self.plg_logger_class = plg_logger_class
        self.push = push
        self.duration = duration

    def emit(self, record):
        """Emit a logging record by forwarding it to the plugin logger.

        This formats the record, maps the Python logging level to QGIS levels
        and calls `plg_logger_class.log()` with the resulting message.
        """
        try:
            msg = self.format(record)
            qgis_level = self._map_log_level(record.levelno)
            self.plg_logger_class.log(
                message=msg,
                log_level=qgis_level,
                push=self.push,
                duration=self.duration,
                application='LoopStructural',
            )
        except Exception:
            self.handleError(record)

    @staticmethod
    def _map_log_level(py_level):
        if py_level >= logging.CRITICAL:
            return 2
        elif py_level >= logging.ERROR:
            return 2
        elif py_level >= logging.WARNING:
            return 1
        elif py_level >= logging.INFO:
            return 0
        else:
            return 4  # "none" / debug / custom
