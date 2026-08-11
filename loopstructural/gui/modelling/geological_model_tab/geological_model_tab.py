from LoopStructural.modelling.features import FeatureType
from qgis.PyQt.QtCore import QObject, Qt, QThread, pyqtSignal, pyqtSlot
from qgis.PyQt.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from qgis.PyQt.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .add_foliation_dialog import AddFoliationDialog
from .add_unconformity_dialog import AddUnconformityDialog
from .feature_details_panel import (
    FaultFeatureDetailsPanel,
    FoldedFeatureDetailsPanel,
    FoliationFeatureDetailsPanel,
    StructuralFrameFeatureDetailsPanel,
)


def _build_status_icon(color: str, *, filled: bool, mark: str = None) -> QIcon:
    """Draw a small coloured circle with an optional check/cross mark for the
    feature-list build-status indicator. `mark` is 'check', 'cross', or None.
    Drawn on the fly rather than shipped as a resource file, so the colours
    stay consistent regardless of the active icon theme.
    """
    size = 14
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    if filled:
        painter.setBrush(QColor(color))
        painter.setPen(Qt.NoPen)
    else:
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(color), 1.5))
    painter.drawEllipse(1, 1, size - 2, size - 2)
    if mark:
        pen = QPen(QColor('white'), 2)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        if mark == 'check':
            painter.drawLine(4, 7, 6, 10)
            painter.drawLine(6, 10, 10, 4)
        elif mark == 'cross':
            painter.drawLine(4, 4, 10, 10)
            painter.drawLine(10, 4, 4, 10)
    painter.end()
    return QIcon(pixmap)


_MODEL_STATE_LABELS = {
    'empty': "Model status: not initialized",
    'initialized': "Model status: initialized (not solved)",
    'solved': "Model status: solved",
    'stale': "Model status: fault topology changed — re-run Initialize Model",
}

# Solve Model only rebuilds interpolators for features that already exist; it
# can't apply a fault topology edit (that requires re-running Initialize
# Model, see GeologicalModelManager._on_fault_topology_changed), so it stays
# disabled outside these two states.
_SOLVABLE_STATES = {'initialized', 'solved'}


class GeologicalModelTab(QWidget):
    def __init__(self, parent=None, *, model_manager=None, data_manager=None):
        super().__init__(parent)
        self.model_manager = model_manager
        self.data_manager = data_manager
        # Build-status icons for the feature list, created once and reused.
        self._built_icon = _build_status_icon('#2e8b40', filled=True, mark='check')
        self._unbuilt_icon = _build_status_icon('#c0392b', filled=True, mark='cross')
        self._unknown_icon = _build_status_icon('#9a9a9a', filled=False, mark=None)

        # Register update observer using Observable API if available
        if self.model_manager is not None:
            try:
                # listen for model-level updates, plus per-feature/whole-model
                # solve events so build-status ticks stay current
                self._disp_model = self.model_manager.attach(
                    self.update_feature_list, 'model_updated'
                )
                self._disp_feature_updated = self.model_manager.attach(
                    self.update_feature_list, 'feature_updated'
                )
                self._disp_all_features_updated = self.model_manager.attach(
                    self.update_feature_list, 'all_features_updated'
                )
                # show progress when model updates start/finish (covers indirect calls)
                self._disp_update_start = self.model_manager.attach(
                    lambda _obs, _ev, *a, **k: self._on_model_update_started(),
                    'model_update_started',
                )
                self._disp_update_finish = self.model_manager.attach(
                    lambda _obs, _ev, *a, **k: self._on_model_update_finished(),
                    'model_update_finished',
                )
            except Exception:
                # fallback to legacy list
                try:
                    self.model_manager.observers.append(self.update_feature_list)
                except Exception:
                    raise RuntimeError("Failed to register model update observer")
        # Main layout
        mainLayout = QVBoxLayout(self)

        # Splitter for collapsible layout. Given all the stretch so the
        # button/status row above it never competes for space.
        splitter = QSplitter(self)
        mainLayout.addWidget(splitter, 1)

        # Feature list panel

        self.featureList = QTreeWidget()
        self.featureList.setHeaderLabel("Geological Features")
        # Enable right-click context menu on feature items
        self.featureList.setContextMenuPolicy(Qt.CustomContextMenu)
        self.featureList.customContextMenuRequested.connect(self.show_feature_context_menu)
        side_panel = QVBoxLayout()
        side_panel.addWidget(self.featureList)
        add_feature_button = QPushButton("Add Feature")

        add_feature_button.setContextMenuPolicy(Qt.CustomContextMenu)
        add_feature_button.customContextMenuRequested.connect(self.show_add_feature_menu)
        add_feature_button.clicked.connect(self.show_add_feature_menu)
        side_panel.addWidget(add_feature_button)
        side_panel_widget = QWidget()
        side_panel_widget.setLayout(side_panel)
        splitter.addWidget(side_panel_widget)
        # self.splitter.addWidget(QWidget())  # Placeholder for the feature list panel
        # Feature details panel
        self.featureDetailsPanel = QWidget()
        splitter.addWidget(self.featureDetailsPanel)

        # Limit feature details panel expansion
        splitter.setStretchFactor(0, 1)  # Feature list panel
        splitter.setStretchFactor(1, 0)  # Feature details panel
        splitter.setOrientation(Qt.Horizontal)  # Add horizontal slider

        # Initialize / Solve Model buttons + a status summary of where the
        # model currently is: empty -> initialized (unsolved) -> solved.
        self.initializeModelButton = QPushButton("Initialize Model")
        self.solveModelButton = QPushButton("Solve Model")
        self.solveModelButton.setEnabled(False)  # nothing to solve until initialized
        self.modelStatusLabel = QLabel(_MODEL_STATE_LABELS['empty'])

        buttonRow = QHBoxLayout()
        buttonRow.setContentsMargins(0, 0, 0, 0)
        buttonRow.addWidget(self.initializeModelButton)
        buttonRow.addWidget(self.solveModelButton)
        buttonRow.addStretch(1)
        buttonRow.addWidget(self.modelStatusLabel)
        buttonRowWidget = QWidget()
        buttonRowWidget.setLayout(buttonRow)
        # Fixed vertical size policy so this row only ever takes the height
        # its contents need, leaving the rest of the tab to the feature list.
        buttonRowWidget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        mainLayout.insertWidget(0, buttonRowWidget, 0)

        # Action buttons

        self.initializeModelButton.clicked.connect(self.initialize_model)
        self.solveModelButton.clicked.connect(self.solve_model)

        # Connect feature selection to update details panel
        self.featureList.itemClicked.connect(self.on_feature_selected)

        # thread handle to keep worker alive while running
        self._model_update_thread = None
        self._model_update_worker = None

        # populate immediately in case a model already exists (e.g. tab
        # re-created after a model was loaded)
        if self.model_manager is not None:
            self.update_feature_list()

    def show_add_feature_menu(self, *args):
        menu = QMenu(self)
        add_fault = menu.addAction("Add Fault (not yet implemented)")
        # Unlike Add Foliation/Add Unconformity, there's no model_manager entry
        # point yet for a parametric (strike/dip/centre) fault -- faults are
        # currently only created from trace data via update_fault_points. Keep
        # the menu entry visible (so it's discoverable) but disabled, rather
        # than silently accepting input and doing nothing with it.
        add_fault.setEnabled(False)
        add_fault.setToolTip("Adding a fault from parameters isn't implemented yet.")
        add_foliaton = menu.addAction("Add Foliation")
        add_unconformity = menu.addAction("Add Unconformity")
        buttonPosition = self.sender().mapToGlobal(self.sender().rect().bottomLeft())
        action = menu.exec_(buttonPosition)

        if action == add_foliaton:
            self.open_add_foliation_dialog()
        elif action == add_unconformity:
            self.open_add_unconformity_dialog()

    def open_add_foliation_dialog(self):
        dialog = AddFoliationDialog(
            self, data_manager=self.data_manager, model_manager=self.model_manager
        )
        if dialog.exec_() == dialog.Accepted:
            pass

    def open_add_unconformity_dialog(self):
        dialog = AddUnconformityDialog(
            self, data_manager=self.data_manager, model_manager=self.model_manager
        )
        if dialog.exec_() == dialog.Accepted:
            pass

    def initialize_model(self):
        # Run update_model in a background thread to avoid blocking the UI.
        if not self.model_manager:
            return
        if self.data_manager is not None:
            if not self.data_manager.is_bounding_box_set():
                QMessageBox.critical(
                    self,
                    "Bounding box required",
                    "Please set the bounding box before initializing the model.",
                )
                return

            # Validate model CRS
            if not self.data_manager.is_model_crs_valid():
                crs = self.data_manager.get_model_crs()
                if crs is None or not crs.isValid():
                    msg = "Model CRS is not set or invalid. Please select a valid projected CRS in the Model Definition tab."
                else:
                    # Safely get CRS description
                    try:
                        crs_desc = crs.description() or crs.authid() or "Unknown"
                    except Exception:
                        crs_desc = crs.authid() if hasattr(crs, 'authid') else "Unknown"
                    msg = f"Model CRS must be projected (in meters), not geographic.\nSelected CRS: {crs_desc}\n\nPlease select a valid projected CRS in the Model Definition tab."

                QMessageBox.critical(
                    self,
                    "Invalid Model CRS",
                    msg,
                )
                return

        self._run_model_task(
            lambda progress_callback: self.model_manager.update_model(
                notify_observers=False, progress_callback=progress_callback
            ),
            title="Updating Model",
            initial_label="Updating geological model...",
        )

    def solve_model(self):
        # Build/interpolate every feature already added to the model. Only
        # meaningful once Initialize Model has created some features, and not
        # while a fault topology edit is pending re-Initialize.
        if not self.model_manager or self.model_manager.model_state not in _SOLVABLE_STATES:
            return
        self._run_model_task(
            lambda progress_callback: self.model_manager.update_all_features(
                progress_callback=progress_callback, notify_observers=False
            ),
            title="Solving Model",
            initial_label="Solving geological model...",
        )

    def _run_model_task(self, target, *, title, initial_label):
        """Run `target(progress_callback)` on a background QThread with a
        non-modal progress dialog, so the rest of QGIS stays usable. Both
        Initialize Model and Solve Model share this: they disable each other
        while either is running so only one model update runs at a time.

        The worker's signals are connected to *bound methods of this widget*
        (`_on_task_progress` etc.) rather than local closures. That matters:
        PyQt only auto-queues a cross-thread signal delivery when it can tell
        which thread the receiver lives in, and it can only do that for a
        bound QObject method (via `receiver.thread()`) -- not for a plain
        closure. Connecting to closures meant the progress/finished handlers
        could run directly on the worker thread instead of being marshalled
        to the GUI thread, which is what made "Solve Model" freeze QGIS
        despite the work already being on a background QThread.
        """
        progress = QProgressDialog(initial_label, "Cancel", 0, 0, self)
        progress.setWindowModality(Qt.NonModal)
        progress.setWindowTitle(title)
        progress.setCancelButton(None)
        progress.setMinimumDuration(0)
        progress.show()

        self.initializeModelButton.setEnabled(False)
        self.solveModelButton.setEnabled(False)

        # Only one task runs at a time (buttons are disabled above for the
        # duration), so it's safe to stash the per-run state needed by the
        # bound slot methods below directly on self.
        self._task_title = title
        self._task_progress_dialog = progress

        thread = QThread(self)
        worker = _ModelUpdateWorker(target)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.progress.connect(self._on_task_progress)
        worker.finished.connect(self._on_task_finished)
        worker.error.connect(self._on_task_error)
        thread.finished.connect(thread.deleteLater)

        self._model_update_thread = thread
        self._model_update_worker = worker
        thread.start()

    @pyqtSlot(str, int, int)
    def _on_task_progress(self, message, current, total):
        progress = self._task_progress_dialog
        try:
            if total > 0:
                if progress.maximum() != total:
                    progress.setMaximum(total)
                progress.setValue(current)
            progress.setLabelText(message)
        except Exception:
            pass

    @pyqtSlot()
    def _on_task_finished(self):
        try:
            # notify observers now on the GUI thread
            try:
                self.model_manager.notify('model_updated')
            except Exception:
                for obs in getattr(self.model_manager, 'observers', []):
                    try:
                        obs()
                    except Exception as e:
                        self._debug.log_error("Error notifying observer", e)
        finally:
            self._finish_task()

    @pyqtSlot(str)
    def _on_task_error(self, tb):
        try:
            QMessageBox.critical(
                self,
                f"{self._task_title} failed",
                f"An error occurred while updating the model:\n{tb}",
            )
        except Exception:
            pass
        self._finish_task()

    def _finish_task(self):
        self.initializeModelButton.setEnabled(True)
        self.solveModelButton.setEnabled(self.model_manager.model_state in _SOLVABLE_STATES)
        try:
            self._task_progress_dialog.close()
        except Exception:
            pass
        try:
            self._model_update_worker.deleteLater()
        except Exception:
            pass
        try:
            self._model_update_thread.quit()
            self._model_update_thread.wait(2000)
        except Exception:
            pass

    def update_feature_list(self, *args, **kwargs):
        self.featureList.clear()  # Clear the feature list before populating it
        for feature in self.model_manager.features():
            if feature.name.startswith("__"):
                continue
            item = QTreeWidgetItem(self.featureList)
            item.setText(0, feature.name)
            item.setData(0, 1, feature)
            item.setIcon(0, self._status_icon(self.model_manager.is_feature_built(feature)))
            self.featureList.addTopLevelItem(item)
        self._refresh_model_status()

    def _status_icon(self, built):
        if built is True:
            return self._built_icon
        if built is False:
            return self._unbuilt_icon
        return self._unknown_icon

    def _refresh_model_status(self):
        state = self.model_manager.model_state if self.model_manager is not None else 'empty'
        self.modelStatusLabel.setText(_MODEL_STATE_LABELS.get(state, "Model status: unknown"))
        self.solveModelButton.setEnabled(state in _SOLVABLE_STATES)

    def on_feature_selected(self, item):
        feature_name = item.text(0)
        feature = self.model_manager.model.get_feature_by_name(feature_name)
        if feature.type == FeatureType.FAULT:
            self.featureDetailsPanel = FaultFeatureDetailsPanel(
                fault=feature, model_manager=self.model_manager, data_manager=self.data_manager
            )
        elif feature.type == FeatureType.INTERPOLATED:
            self.featureDetailsPanel = FoliationFeatureDetailsPanel(
                feature=feature, model_manager=self.model_manager, data_manager=self.data_manager
            )
        elif feature.type == FeatureType.STRUCTURALFRAME:
            self.featureDetailsPanel = StructuralFrameFeatureDetailsPanel(
                feature=feature, model_manager=self.model_manager, data_manager=self.data_manager
            )
        elif feature.type == FeatureType.FOLDED:
            self.featureDetailsPanel = FoldedFeatureDetailsPanel(
                feature=feature, model_manager=self.model_manager, data_manager=self.data_manager
            )
        else:
            self.featureDetailsPanel = QWidget()  # Default empty panel

        # Dynamically replace the featureDetailsPanel widget
        splitter = self.layout().itemAt(1).widget()
        splitter.widget(1).deleteLater()  # Remove the existing widget
        splitter.addWidget(self.featureDetailsPanel)  # Add the new widget

    def _on_model_update_started(self):
        """Show a non-blocking indeterminate progress dialog for model updates.

        This method is invoked via the Observable notifications and ensures the
        user sees that a background or foreground update is in progress.
        """
        print("Model update started - showing progress dialog")
        try:
            if getattr(self, '_progress_dialog', None) is None:
                self._progress_dialog = QProgressDialog(
                    "Updating geological model...", None, 0, 0, self
                )
                self._progress_dialog.setWindowTitle("Updating Model")
                self._progress_dialog.setWindowModality(Qt.NonModal)
                self._progress_dialog.setCancelButton(None)
                self._progress_dialog.setMinimumDuration(0)
            self._progress_dialog.show()
        except Exception:
            pass

    def _on_model_update_finished(self):
        """Close the progress dialog shown for model updates."""
        try:
            if getattr(self, '_progress_dialog', None) is not None:
                try:
                    self._progress_dialog.close()
                except Exception:
                    pass
                try:
                    self._progress_dialog.deleteLater()
                except Exception:
                    pass
                self._progress_dialog = None
        except Exception:
            pass

    def show_feature_context_menu(self, pos):
        # Show context menu only for items
        item = self.featureList.itemAt(pos)
        if item is None:
            return
        menu = QMenu(self)
        delete_action = menu.addAction("Delete Feature")
        action = menu.exec_(self.featureList.mapToGlobal(pos))
        if action == delete_action:
            self.delete_feature(item)

    def delete_feature(self, item):
        feature_name = item.text(0)
        # Attempt to remove from the underlying model in a few ways
        try:
            # Try model's __delitem__ if supported
            try:
                del self.model_manager.model[feature_name]
                del self.data_manager.feature_data[feature_name]
            except Exception:
                # Fallback: remove object from features list and feature index if present
                feature = self.model_manager.model.get_feature_by_name(feature_name)
                if feature and hasattr(self.model_manager.model, 'features'):
                    try:
                        self.model_manager.model.features.remove(feature)
                    except Exception:
                        pass
                if hasattr(self.model_manager.model, 'feature_name_index'):
                    try:
                        self.model_manager.model.feature_name_index.pop(feature_name, None)
                    except Exception:
                        pass
        except Exception as e:
            print(f"Failed to remove feature from model: {e}")

        # Remove from the tree widget
        try:
            self.featureList.takeTopLevelItem(self.featureList.indexOfTopLevelItem(item))
        except Exception:
            # Fallback: just clear and refresh
            pass

        # Notify observers to refresh UI
        try:
            # Prefer notify API
            try:
                self.model_manager.notify('model_updated')
            except Exception:
                # fallback to legacy observers list
                for obs in getattr(self.model_manager, 'observers', []):
                    try:
                        obs()
                    except Exception:
                        pass
        except Exception:
            pass


class _ModelUpdateWorker(QObject):
    """Runs an arbitrary long-running model update in a background thread.

    `target` is called as `target(progress_callback)`, where `progress_callback`
    forwards to the `progress` signal below -- used for both "Initialize Model"
    (model_manager.update_model) and "Solve Model" (model_manager.update_all_features).

    Emits finished when done and error with a string if an exception occurs.
    Emits progress(message, current, total) as each fault/stratigraphic
    group/feature is built, so the GUI can show what's currently happening.
    `progress.emit` is safe to call from this worker thread: Qt automatically
    queues the delivery to slots living on the main thread.
    """

    finished = pyqtSignal()
    error = pyqtSignal(str)
    progress = pyqtSignal(str, int, int)

    def __init__(self, target):
        super().__init__()
        self._target = target

    def _report_progress(self, message, current, total):
        self.progress.emit(message, current, total)

    @pyqtSlot()
    def run(self):
        try:
            self._target(self._report_progress)
        except Exception as e:
            try:
                import traceback

                tb = traceback.format_exc()
            except Exception:
                tb = str(e)
            self.error.emit(tb)
        finally:
            self.finished.emit()
