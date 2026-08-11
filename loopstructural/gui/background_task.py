"""Generic QThread-based background task runner for long-running,
QGIS-independent work (e.g. calling into map2loop via main.m2l_api).

Mirrors the pattern already used by GeologicalModelTab's Initialize/Solve
Model buttons (see geological_model_tab.py's `_ModelUpdateWorker`/
`_run_model_task`): move work off the GUI thread via `QThread.moveToThread`,
with signals connected to *bound methods* of the calling widget, never
closures/lambdas. That distinction matters: PyQt only auto-queues a
cross-thread signal delivery when it can tell which thread the receiver
lives on, and it can only do that for a bound QObject method (via
`receiver.thread()`) -- not for a plain closure. Connecting to a closure
means the slot runs directly on the worker thread instead of being
marshalled to the GUI thread, which is what caused the freeze this pattern
was originally written to fix.

This worker differs from `_ModelUpdateWorker` in two ways, matching how the
map2loop-backed widgets (Sampler, Sorter, Basal Contacts, Thickness
Calculator, Data Conversion) actually work rather than how the model-build
buttons do:

- `main.m2l_api` functions report progress as a single message string via
  an `updater(msg)` callback, not `(msg, current, total)` -- so the
  progress dialog here is indeterminate ("busy") rather than a filled bar.
- Those functions *return a value the caller needs* (a DataFrame to turn
  into a QGIS layer) once back on the GUI thread, rather than mutating
  manager state in place -- so `finished` carries that result.

`target` must not touch any QObject that lives on the GUI thread (widgets,
layers you plan to add to a live QgsProject, etc.) -- do that in your
`on_finished` slot instead, which runs back on the GUI thread.
"""

from qgis.PyQt.QtCore import QObject, Qt, QThread, pyqtSignal, pyqtSlot
from qgis.PyQt.QtWidgets import QProgressDialog


class BackgroundTaskWorker(QObject):
    """Runs `target(progress_callback)` on a background thread.

    Emits `progress(message)` as target reports what it's doing,
    `finished(result)` with target's return value on success, or
    `error(traceback_text)` if target raised.
    """

    progress = pyqtSignal(str)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, target):
        super().__init__()
        self._target = target

    def _report_progress(self, message):
        self.progress.emit(message)

    @pyqtSlot()
    def run(self):
        try:
            result = self._target(self._report_progress)
        except Exception:
            import traceback

            self.error.emit(traceback.format_exc())
            return
        self.finished.emit(result)


def start_background_task(
    widget,
    target,
    *,
    title,
    initial_label,
    on_progress,
    on_finished,
    on_error,
):
    """Start `target(progress_callback)` on a background QThread, with a
    non-modal indeterminate QProgressDialog parented to `widget`.

    `on_progress`, `on_finished` and `on_error` MUST be bound methods of
    `widget` (e.g. `self._on_sampler_finished`), never lambdas/closures --
    see the module docstring for why. Each takes the corresponding signal's
    payload (`on_progress(message)`, `on_finished(result)`,
    `on_error(traceback_text)`).

    Returns `(thread, worker, progress_dialog)`. The caller must keep
    `thread` and `worker` alive for the duration of the run (e.g. store
    them as attributes on `widget`) -- if they're garbage collected while
    the thread is running, the thread is destroyed with it.
    """
    progress_dialog = QProgressDialog(initial_label, "Cancel", 0, 0, widget)
    progress_dialog.setWindowModality(Qt.NonModal)
    progress_dialog.setWindowTitle(title)
    progress_dialog.setCancelButton(None)
    progress_dialog.setMinimumDuration(0)
    progress_dialog.show()

    thread = QThread(widget)
    worker = BackgroundTaskWorker(target)
    worker.moveToThread(thread)

    thread.started.connect(worker.run)
    worker.progress.connect(on_progress)
    worker.finished.connect(on_finished)
    worker.error.connect(on_error)
    thread.finished.connect(thread.deleteLater)

    thread.start()
    return thread, worker, progress_dialog


def finish_background_task(thread, worker, progress_dialog):
    """Tear down a `(thread, worker, progress_dialog)` triple returned by
    `start_background_task`, once `on_finished`/`on_error` has fired.

    Safe to call defensively (e.g. from a `finally` block) -- swallows
    errors from any object that's already been torn down.
    """
    try:
        progress_dialog.close()
    except Exception:
        pass
    try:
        worker.deleteLater()
    except Exception:
        pass
    try:
        thread.quit()
        thread.wait(2000)
    except Exception:
        pass
