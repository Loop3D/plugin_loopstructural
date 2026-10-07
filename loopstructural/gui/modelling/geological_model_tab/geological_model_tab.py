import html

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

from ....main.derived_refresh import DerivedRefresh, DerivedRefreshError, names_to_refresh
from ....main.model_manager import ModelSolveCancelled
from ....main.workflow_mode import DEFAULT_WORKFLOW_MODE, WORKFLOW_MODE_CONSTRAINTS
from ...messages import push_info
from ..steps import build_plan
from .add_fault_dialog import AddFaultDialog
from .add_foliation_dialog import AddFoliationDialog
from .add_unconformity_dialog import AddUnconformityDialog
from .feature_details_panel import (
    BaseFeatureDetailsPanel,
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
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    if filled:
        painter.setBrush(QColor(color))
        painter.setPen(Qt.PenStyle.NoPen)
    else:
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(color), 1.5))
    painter.drawEllipse(1, 1, size - 2, size - 2)
    if mark:
        pen = QPen(QColor('white'), 2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
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
    'stale': (
        "Model status: faults, stratigraphic column or input data changed — "
        "rebuild the model"
    ),
}

# Solving only rebuilds interpolators for features that already exist; it
# can't apply a fault topology edit (that requires a build, see
# GeologicalModelManager._on_fault_topology_changed), so the primary button
# builds in the other states.
_SOLVABLE_STATES = {'initialized', 'solved'}


class GeologicalModelTab(QWidget):
    # Emitted when a solve finished without an error. The dock offers the 3D view.
    model_solved = pyqtSignal()

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
        splitter = self._splitter = QSplitter(self)
        mainLayout.addWidget(splitter, 1)

        # Feature list panel

        self.featureList = QTreeWidget()
        self.featureList.setHeaderLabel("Geological Features")
        # Enable right-click context menu on feature items
        self.featureList.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.featureList.customContextMenuRequested.connect(self.show_feature_context_menu)
        side_panel = QVBoxLayout()
        side_panel.addWidget(self.featureList)
        add_feature_button = QPushButton("Add Feature")

        add_feature_button.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
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
        splitter.setOrientation(Qt.Orientation.Horizontal)  # Add horizontal slider

        # One primary button. Its text and action come from the model state
        # (see build_plan.choose_primary_action). The status label shows where
        # the model is: empty -> initialized (unsolved) -> solved.
        self.primaryButton = QPushButton("Build model")
        self.primaryButton.clicked.connect(self.on_primary_clicked)
        self._primary_action = build_plan.PrimaryAction(build_plan.ACTION_BUILD, "Build model")
        self._task_running = False
        self.modelStatusLabel = QLabel(_MODEL_STATE_LABELS['empty'])

        buttonRow = QHBoxLayout()
        buttonRow.setContentsMargins(0, 0, 0, 0)
        buttonRow.addWidget(self.primaryButton)
        buttonRow.addStretch(1)
        buttonRow.addWidget(self.modelStatusLabel)
        buttonRowWidget = QWidget()
        buttonRowWidget.setLayout(buttonRow)
        # Fixed vertical size policy so this row only ever takes the height
        # its contents need, leaving the rest of the tab to the feature list.
        buttonRowWidget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        mainLayout.insertWidget(0, buttonRowWidget, 0)

        # The problems of all steps. They show before the build, so the user
        # sees why a build can fail or can give a poor model.
        self.problemsLabel = QLabel()
        self.problemsLabel.setWordWrap(True)
        self.problemsLabel.setTextFormat(Qt.TextFormat.RichText)
        self.problemsLabel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        mainLayout.insertWidget(1, self.problemsLabel, 0)
        self.problemsLabel.hide()
        self._problems_provider = None
        if self.data_manager is not None:
            self.data_manager.add_layer_data_changed_callback(self.refresh_primary_action)

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
        add_fault = menu.addAction("Add Fault")
        add_fault.setToolTip(
            "Add a fault from a centre, a strike, a dip and a size. "
            "Faults from a trace layer are in step 3."
        )
        add_foliaton = menu.addAction("Add Foliation")
        add_unconformity = menu.addAction("Add Unconformity")
        buttonPosition = self.sender().mapToGlobal(self.sender().rect().bottomLeft())
        action = menu.exec(buttonPosition)

        if action == add_fault:
            self.open_add_fault_dialog()
        elif action == add_foliaton:
            self.open_add_foliation_dialog()
        elif action == add_unconformity:
            self.open_add_unconformity_dialog()

    def open_add_fault_dialog(self):
        dialog = AddFaultDialog(self, model_manager=self.model_manager)
        if dialog.exec() != dialog.Accepted:
            return
        try:
            self.model_manager.add_parametric_fault(dialog.get_fault_data())
        except ValueError as err:
            QMessageBox.critical(self, "Cannot add the fault", str(err))
            return
        push_info(
            "Fault", f"'{dialog.get_fault_data()['name']}' is added. Rebuild the model to use it."
        )
        self.refresh_primary_action()

    def open_add_foliation_dialog(self):
        dialog = AddFoliationDialog(
            self, data_manager=self.data_manager, model_manager=self.model_manager
        )
        if dialog.exec() == dialog.Accepted:
            pass

    def open_add_unconformity_dialog(self):
        dialog = AddUnconformityDialog(
            self, data_manager=self.data_manager, model_manager=self.model_manager
        )
        if dialog.exec() == dialog.Accepted:
            pass

    def set_problems_provider(self, provider):
        """Set the function that gives the problems of all steps.

        ``provider()`` returns ``(step_key, message)`` pairs. The dock sets it,
        because the tab does not know the other steps.
        """
        self._problems_provider = provider
        self.refresh_primary_action()

    def _blocked_reason(self):
        """Return why no build can start now, or None."""
        if self.model_manager is None or self.data_manager is None:
            return None
        if not self.data_manager.is_bounding_box_set():
            return "Set the bounding box in step 1."
        if not self.data_manager.is_model_crs_valid():
            return "Select a projected model CRS in step 1."
        return None

    def _workflow_mode(self):
        return getattr(self.data_manager, 'workflow_mode', DEFAULT_WORKFLOW_MODE)

    def _derived_to_refresh(self):
        """Return the derived results that the build calculates again.

        With "Interpolate surfaces from constraints", there is no column, so
        there is nothing to calculate.
        """
        if self.data_manager is None or self._workflow_mode() == WORKFLOW_MODE_CONSTRAINTS:
            return []
        return names_to_refresh(self.data_manager)

    def refresh_primary_action(self, *args, **kwargs):
        """Show the action of the primary button and the problems of the steps."""
        if self.model_manager is None:
            return
        changed = self.data_manager.get_changed_layers() if self.data_manager else []
        self._primary_action = build_plan.choose_primary_action(
            self.model_manager.model_state,
            derived_out_of_date=self._derived_to_refresh(),
            layers_changed=bool(changed),
            blocked_reason=self._blocked_reason(),
        )
        action = self._primary_action
        self.primaryButton.setText(action.text)
        self.primaryButton.setToolTip(action.tooltip)
        if not self._task_running:
            self.primaryButton.setEnabled(action.enabled)

        problems = self._problems_provider() if self._problems_provider is not None else []
        if problems:
            lines = "".join(f"<li>{html.escape(message)}</li>" for _key, message in problems)
            self.problemsLabel.setText(
                f"<b>Check before the build:</b><ul style='margin:0'>{lines}</ul>"
            )
            self.problemsLabel.show()
        else:
            self.problemsLabel.hide()

    def on_primary_clicked(self):
        """Do the action of the primary button."""
        if self.model_manager is None or self._task_running:
            return
        self.refresh_primary_action()
        action = self._primary_action
        if action.action == build_plan.ACTION_BUILD:
            self.build_model()
        elif action.action == build_plan.ACTION_SOLVE:
            self.solve_model()

    def build_model(self):
        """Calculate the out-of-date derived data, make the features, and solve them.

        The derived data is calculated first, because a build must not use
        out-of-date contacts or thicknesses. If a calculation fails, the build
        stops.
        """
        if not self.model_manager or not self._validate_before_build():
            return
        if not self._confirm_bounding_box_contains_data():
            return

        if self.data_manager is not None:
            # build from the current layer data, not the data read before
            # the layers changed
            self.data_manager.reload_changed_layers()
            # the rows that the user added to generated features
            self.data_manager.sync_extra_constraints()

        refresh = None
        names = self._derived_to_refresh()
        if names:
            try:
                refresh = DerivedRefresh(self.data_manager, self.model_manager, names)
            except DerivedRefreshError as err:
                QMessageBox.critical(self, "Cannot build the model", str(err))
                return

        if refresh is not None:
            self._run_model_task(
                lambda progress_callback: refresh.run(progress_callback),
                title="Updating derived data",
                initial_label="Calculating the data that comes from the column...",
                cancellable=False,
                on_success=lambda: self._after_derived_refresh(refresh),
            )
        else:
            self._run_build_task()

    def _after_derived_refresh(self, refresh):
        """Put the new derived data in place, then make the features."""
        try:
            skipped = refresh.finish()
        except Exception as err:
            QMessageBox.critical(self, "Cannot build the model", f"{type(err).__name__}: {err}")
            return
        if skipped:
            push_info(
                "Thickness",
                "These units keep the thickness that you typed: " + ", ".join(skipped) + ".",
            )
        self._run_build_task()

    def _run_build_task(self):
        def target(progress_callback):
            self.model_manager.update_model(
                notify_observers=False, progress_callback=progress_callback
            )
            self.model_manager.update_all_features(
                progress_callback=progress_callback, notify_observers=False
            )

        self._run_model_task(
            target,
            title="Building Model",
            initial_label="Building geological model...",
        )

    def _validate_before_build(self):
        if self.data_manager is None:
            return True
        if not self.data_manager.is_bounding_box_set():
            QMessageBox.critical(
                self,
                "Bounding box required",
                "Please set the bounding box before building the model.",
            )
            return False
        if not self.data_manager.is_model_crs_valid():
            crs = self.data_manager.get_model_crs()
            if crs is None or not crs.isValid():
                msg = (
                    "Model CRS is not set or invalid. "
                    "Please select a valid projected CRS in step 1."
                )
            else:
                # Safely get CRS description
                try:
                    crs_desc = crs.description() or crs.authid() or "Unknown"
                except Exception:
                    crs_desc = crs.authid() if hasattr(crs, 'authid') else "Unknown"
                msg = (
                    "Model CRS must be projected (in meters), not geographic.\n"
                    f"Selected CRS: {crs_desc}\n\nPlease select a valid projected CRS in step 1."
                )
            QMessageBox.critical(self, "Invalid Model CRS", msg)
            return False
        return True

    def _update_model_data(self):
        """Put the data of the changed input layers into the current
        features, without a build. Returns False if the caller must not solve now."""
        try:
            result = self.data_manager.refresh_model_data()
        except Exception as e:
            QMessageBox.critical(self, "Update model data failed", str(e))
            return False
        self.refresh_primary_action()
        if not result['needs_initialize']:
            return True
        names = "\n".join(f"  - {name}" for name in result['needs_initialize'])
        reply = QMessageBox.question(
            self,
            "Rebuild needed",
            "The new data for these features cannot be put into the current "
            f"model:\n{names}\n\n"
            "Rebuild the model to use it? A rebuild makes all features again.",
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.build_model()
        return False

    def solve_model(self):
        # Solve every feature already added to the model. Only meaningful
        # once a build has created some features, and not while a fault
        # topology edit is pending a build.
        if not self.model_manager or self.model_manager.model_state not in _SOLVABLE_STATES:
            return
        if not self._confirm_bounding_box_contains_data():
            return
        if self.data_manager is not None and self.data_manager.get_changed_layers():
            if not self._update_model_data():
                return
        self._run_model_task(
            lambda progress_callback: self.model_manager.update_all_features(
                progress_callback=progress_callback, notify_observers=False
            ),
            title="Solving Model",
            initial_label="Solving geological model...",
        )

    def _confirm_bounding_box_contains_data(self):
        """Warn the user if none of the input layers overlap the bounding
        box. The model still solves in that case, but no surfaces appear, so
        this is usually a bounding box that was never set correctly.
        Returns True if the task should continue.
        """
        if self.data_manager is None:
            return True
        try:
            inside, outside = self.data_manager.get_layers_outside_bounding_box()
        except Exception:
            return True
        if inside or not outside:
            return True
        bb = self.data_manager.get_bounding_box()
        layer_list = "\n".join(f"  - {name}" for name in outside)
        reply = QMessageBox.warning(
            self,
            "Check bounding box",
            "None of the input layers overlap the model bounding box:\n"
            f"{layer_list}\n\n"
            f"Bounding box X: {bb.origin[0]:g} to {bb.maximum[0]:g}, "
            f"Y: {bb.origin[1]:g} to {bb.maximum[1]:g}\n\n"
            "The model will solve, but no surfaces will appear. Check that the "
            "bounding box in the Model Definition tab is correct.\n\n"
            "Do you want to continue anyway?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return reply == QMessageBox.StandardButton.Yes

    def _run_model_task(
        self, target, *, title, initial_label, cancellable=True, on_success=None
    ):
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
        progress.setWindowModality(Qt.WindowModality.NonModal)
        progress.setWindowTitle(title)
        progress.setMinimumDuration(0)
        if cancellable:
            progress.canceled.connect(self._on_task_cancel_requested)
        else:
            # the calculation of derived data cannot stop part way
            progress.setCancelButton(None)
        progress.show()

        self._task_running = True
        self._task_failed = False
        self._task_on_success = on_success
        self._task_cancellable = cancellable
        self.primaryButton.setEnabled(False)

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
        worker.cancelled.connect(self._on_task_cancelled)
        thread.finished.connect(thread.deleteLater)

        self._model_update_thread = thread
        self._model_update_worker = worker
        thread.start()

    def _on_task_cancel_requested(self):
        """Handle the progress dialog's Cancel button.

        Clicking Cancel asks the model manager to stop at the next
        fault/feature build boundary (see `ModelManager.request_cancel`) --
        the build already running when Cancel is clicked can't be
        interrupted, so there can be a short delay before the worker
        actually stops. `QProgressDialog.cancel()` hides the dialog before
        emitting `canceled`, so it's re-shown here (without a Cancel button,
        since a second click has nothing new to do) to keep the user informed
        while the worker winds down.
        """
        if self.model_manager is not None:
            self.model_manager.request_cancel()
        progress = self._task_progress_dialog
        try:
            progress.setLabelText("Cancelling... finishing the current step")
            progress.setCancelButton(None)
            progress.show()
        except Exception:
            pass

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
        failed = self._task_failed
        solving = self._task_title in ("Solving Model", "Building Model")
        on_success = None if failed else self._task_on_success
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
        if on_success is not None:
            on_success()
        if not failed and solving and self.model_manager.model_state == 'solved':
            self.model_solved.emit()

    @pyqtSlot(str)
    def _on_task_cancelled(self, message):
        # Nothing to do here beyond letting `_on_task_finished` (emitted
        # right after this, from the worker's `finally`) run its normal
        # cleanup/refresh -- the feature list will reflect whatever was
        # actually built before the cancellation took effect.
        self._task_failed = True
        print(f"{self._task_title} cancelled: {message}")

    @pyqtSlot(str, str)
    def _on_task_error(self, reason, tb):
        self._task_failed = True
        try:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Critical)
            box.setWindowTitle(f"{self._task_title} failed")
            box.setText(f"Model update stopped: {reason}")
            box.setInformativeText("Click 'Show Details...' for the full error trace.")
            box.setDetailedText(tb)
            box.exec()
        except Exception:
            pass
        self._finish_task()

    def _finish_task(self):
        self._task_running = False
        self.refresh_primary_action()
        try:
            # QProgressDialog.close() emits canceled() itself (same as
            # clicking the Cancel button), so disconnect first -- otherwise
            # closing the dialog after a normal finish/error would call
            # request_cancel() and arm cancellation for the *next* run.
            self._task_progress_dialog.canceled.disconnect(self._on_task_cancel_requested)
        except Exception:
            pass
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
        selected_name = getattr(self, '_displayed_feature_name', None)
        self.featureList.clear()  # Clear the feature list before populating it
        selected_item = None
        for feature in self.model_manager.features():
            if feature.name.startswith("__"):
                continue
            item = QTreeWidgetItem(self.featureList)
            item.setText(0, feature.name)
            item.setData(0, 1, feature)
            item.setIcon(0, self._status_icon(self.model_manager.is_feature_built(feature)))
            self.featureList.addTopLevelItem(item)
            if feature.name == selected_name:
                selected_item = item
        self._refresh_model_status()
        self._restore_selection(selected_item)

    def _restore_selection(self, item):
        """Keep the displayed feature selected after the list is rebuilt.

        Converting a feature to a structural frame or adding a fold replaces
        the feature object in the model under the same name, so the details
        panel is rebuilt when the object it shows is no longer the one in the
        model. Otherwise the panel is kept, so edits in it are not lost.
        """
        if item is None:
            if getattr(self, '_displayed_feature_name', None) is not None:
                # the displayed feature was removed from the model
                self._set_details_panel(QWidget(), None, None)
            return
        self.featureList.setCurrentItem(item)
        feature = self.model_manager.model.get_feature_by_name(item.text(0))
        if feature is not getattr(self, '_displayed_feature', None):
            self.on_feature_selected(item)

    def _status_icon(self, built):
        if built is True:
            return self._built_icon
        if built is False:
            return self._unbuilt_icon
        return self._unknown_icon

    def _refresh_model_status(self):
        state = self.model_manager.model_state if self.model_manager is not None else 'empty'
        self.modelStatusLabel.setText(_MODEL_STATE_LABELS.get(state, "Model status: unknown"))
        self.refresh_primary_action()

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
        elif feature.type == FeatureType.DOMAINFAULT:
            # A domain fault is built by the same GeologicalFeatureBuilder
            # as a foliation (see create_and_add_domain_fault), just with a
            # different .type tag -- the generic base panel (interpolator
            # settings, data layers, export/evaluate) already applies to it
            # unchanged. Skip FoliationFeatureDetailsPanel's fold-frame
            # attachment controls, which don't make sense for a domain
            # boundary.
            self.featureDetailsPanel = BaseFeatureDetailsPanel(
                feature=feature, model_manager=self.model_manager, data_manager=self.data_manager
            )
        else:
            self.featureDetailsPanel = QWidget()  # Default empty panel

        self._set_details_panel(self.featureDetailsPanel, feature_name, feature)

    def _set_details_panel(self, panel, feature_name, feature):
        self.featureDetailsPanel = panel
        self._displayed_feature_name = feature_name
        self._displayed_feature = feature
        # Dynamically replace the featureDetailsPanel widget
        splitter = self._splitter
        splitter.widget(1).deleteLater()  # Remove the existing widget
        splitter.addWidget(panel)  # Add the new widget

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
                self._progress_dialog.setWindowModality(Qt.WindowModality.NonModal)
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
        action = menu.exec(self.featureList.mapToGlobal(pos))
        if action == delete_action:
            self.delete_feature(item)

    def delete_feature(self, item):
        feature_name = item.text(0)
        # so that Initialize Model does not build it again
        self.model_manager.remove_manual_foliation(feature_name)
        self.model_manager.remove_parametric_fault(feature_name)
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

    Emits finished when done. Emits error(reason, traceback) if an unexpected
    exception occurs, or cancelled(message) if the run stopped because
    `ModelManager.request_cancel()` was called. Emits
    progress(message, current, total) as each fault/stratigraphic
    group/feature is built, so the GUI can show what's currently happening.
    `progress.emit` is safe to call from this worker thread: Qt automatically
    queues the delivery to slots living on the main thread.
    """

    finished = pyqtSignal()
    error = pyqtSignal(str, str)
    cancelled = pyqtSignal(str)
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
        except ModelSolveCancelled as e:
            self.cancelled.emit(str(e))
        except Exception as e:
            try:
                import traceback

                tb = traceback.format_exc()
            except Exception:
                tb = str(e)
            # Short, human-facing headline: exception type + message (e.g.
            # "ValueError: could not build fault 'F1': ..."), with the full
            # traceback available separately for anyone who needs it.
            reason = f"{type(e).__name__}: {e}" if str(e) else type(e).__name__
            self.error.emit(reason, tb)
        finally:
            self.finished.emit()
