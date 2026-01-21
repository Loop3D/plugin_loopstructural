from PyQt5.QtCore import QObject, Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import (
    QMenu,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from LoopStructural.modelling.features import FeatureType

# Import the AddFaultDialog
from .add_fault_dialog import AddFaultDialog
from .add_foliation_dialog import AddFoliationDialog
from .add_unconformity_dialog import AddUnconformityDialog
from .feature_details_panel import (
    FaultFeatureDetailsPanel,
    FoldedFeatureDetailsPanel,
    FoliationFeatureDetailsPanel,
    StructuralFrameFeatureDetailsPanel,
)


class GeologicalModelTab(QWidget):
    def __init__(self, parent=None, *, model_manager=None, data_manager=None):
        super().__init__(parent)
        self.model_manager = model_manager
        self.data_manager = data_manager
        # Register update observer using Observable API if available
        if self.model_manager is not None:
            try:
                # listen for model-level updates
                self._disp_model = self.model_manager.attach(
                    self.update_feature_list, 'model_updated'
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

        # Splitter for collapsible layout
        splitter = QSplitter(self)
        mainLayout.addWidget(splitter)

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

        # Initialize Model button
        self.initializeModelButton = QPushButton("Initialize Model")
        mainLayout.insertWidget(0, self.initializeModelButton)

        # Action buttons

        self.initializeModelButton.clicked.connect(self.initialize_model)

        # Connect feature selection to update details panel
        self.featureList.itemClicked.connect(self.on_feature_selected)

        # thread handle to keep worker alive while running
        self._model_update_thread = None
        self._model_update_worker = None

    def show_add_feature_menu(self, *args):
        menu = QMenu(self)
        add_fault = menu.addAction("Add Fault")
        add_foliaton = menu.addAction("Add Foliation")
        add_unconformity = menu.addAction("Add Unconformity")
        buttonPosition = self.sender().mapToGlobal(self.sender().rect().bottomLeft())
        action = menu.exec_(buttonPosition)

        if action == add_fault:
            self.open_add_fault_dialog()
        elif action == add_foliaton:
            self.open_add_foliation_dialog()
        elif action == add_unconformity:
            self.open_add_unconformity_dialog()

    def open_add_fault_dialog(self):
        dialog = AddFaultDialog(self)
        if dialog.exec_() == dialog.Accepted:
            fault_data = dialog.get_fault_data()
            # TODO: Add logic to use fault_data to add the fault to the model
            print("Fault data:", fault_data)

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

        # create progress dialog (indeterminate)
        progress = QProgressDialog("Updating geological model...", "Cancel", 0, 0, self)
        progress.setWindowModality(Qt.ApplicationModal)
        progress.setWindowTitle("Updating Model")
        progress.setCancelButton(None)
        progress.setMinimumDuration(0)
        progress.show()

        # worker and thread
        thread = QThread(self)
        worker = _ModelUpdateWorker(self.model_manager)
        worker.moveToThread(thread)

        # When thread starts run worker.run
        thread.started.connect(worker.run)

        # on worker finished, notify observers on main thread and cleanup
        def _on_finished():
            try:
                # notify observers now on main thread
                try:
                    self.model_manager.notify('model_updated')
                except Exception:
                    for obs in getattr(self.model_manager, 'observers', []):
                        try:
                            obs()
                        except Exception as e:
                            self._debug.log_error("Error notifying observer", e)
            finally:
                try:
                    progress.close()
                except Exception:
                    pass
                # cleanup worker/thread
                try:
                    worker.deleteLater()
                except Exception:
                    pass
                try:
                    thread.quit()
                    thread.wait(2000)
                except Exception:
                    pass

        def _on_error(tb):
            try:
                progress.close()
            except Exception:
                pass
            try:
                QMessageBox.critical(
                    self,
                    "Model update failed",
                    f"An error occurred while updating the model:\n{tb}",
                )
            except Exception:
                pass
            # ensure thread cleanup
            try:
                worker.deleteLater()
            except Exception:
                pass
            try:
                thread.quit()
                thread.wait(2000)
            except Exception:
                pass

        worker.finished.connect(_on_finished)
        worker.error.connect(_on_error)
        thread.finished.connect(thread.deleteLater)
        self._model_update_thread = thread
        self._model_update_worker = worker
        thread.start()

    def update_feature_list(self, *args, **kwargs):
        self.featureList.clear()  # Clear the feature list before populating it
        for feature in self.model_manager.features():
            if feature.name.startswith("__"):
                continue
            items = self.featureList.findItems(feature.name, Qt.MatchExactly)
            if items:
                # If the feature already exists, skip adding it again
                continue
            item = QTreeWidgetItem(self.featureList)
            item.setText(0, feature.name)
            item.setData(0, 1, feature)
            self.featureList.addTopLevelItem(item)
        # self.featureList.itemClicked.connect(self.on_feature_selected)

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
                self._progress_dialog.setWindowModality(Qt.ApplicationModal)
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
    """Worker that runs model_manager.update_model in a background thread.

    Emits finished when done and error with a string if an exception occurs.
    """

    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, model_manager):
        super().__init__()
        self.model_manager = model_manager

    @pyqtSlot()
    def run(self):
        try:
            # perform the expensive update
            # run update without notifying observers from the background thread
            try:
                self.model_manager.update_model(notify_observers=False)
            except TypeError:
                # fallback if update_model signature not available
                self.model_manager.update_model()
        except Exception as e:
            try:
                import traceback

                tb = traceback.format_exc()
            except Exception:
                tb = str(e)
            self.error.emit(tb)
        finally:
            self.finished.emit()
