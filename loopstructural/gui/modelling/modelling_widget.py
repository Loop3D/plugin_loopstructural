from qgis.PyQt.QtCore import QTimer, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from loopstructural.gui.modelling.steps import build_plan, checks
from loopstructural.gui.modelling.steps.header import DockHeader
from loopstructural.gui.modelling.steps.pages import (
    DataStep,
    FaultsStep,
    ModelStep,
    StratigraphyStep,
    ViewStep,
)
from loopstructural.gui.modelling.steps.step_bar import StepBar

# How often the checks of the steps run again, in milliseconds. Several
# widgets keep only one callback in the data manager, so the dock cannot
# listen to all changes. The checks are cheap.
CHECK_INTERVAL_MS = 750

STEPS = [
    (checks.STEP_DATA, "Data"),
    (checks.STEP_STRATIGRAPHY, "Stratigraphy"),
    (checks.STEP_FAULTS, "Faults"),
    (checks.STEP_MODEL, "Model"),
    (checks.STEP_VIEW, "View"),
]


class ModellingWidget(QWidget):
    """The modelling dock: a header, the steps, and a footer with Back and Next.

    Each step has a status. The footer shows the most important problem of the
    current step. The steps are a guide: the user can go to any step.

    Parameters
    ----------
    view_widget : QWidget, optional
        The visualisation widget, for step 5. If this is None, step 5 has a
        button that emits `open_view_requested`.
    """

    open_view_requested = pyqtSignal()

    def __init__(
        self,
        parent: QWidget = None,
        *,
        mapCanvas=None,
        logger=None,
        data_manager=None,
        model_manager=None,
        view_widget=None,
    ):

        super().__init__(parent)
        self.mapCanvas = mapCanvas
        self.logger = logger
        self.data_manager = data_manager  # ModellingDataManager(mapCanvas=mapCanvas, logger=logger)
        self.model_manager = model_manager

        managers = {'data_manager': self.data_manager, 'model_manager': self.model_manager}
        self.data_step = DataStep(self, **managers)
        self.stratigraphy_step = StratigraphyStep(self, **managers)
        self.faults_step = FaultsStep(self, **managers)
        self.model_step = ModelStep(self, **managers)
        self.view_step = ViewStep(self, view_widget=view_widget, **managers)
        self.view_step.open_view_requested.connect(self.open_view_requested)
        self.pages = [
            self.data_step,
            self.stratigraphy_step,
            self.faults_step,
            self.model_step,
            self.view_step,
        ]

        self.header = DockHeader(self, data_manager=self.data_manager)
        self.step_bar = StepBar(STEPS, self)
        self.stack = QStackedWidget(self)
        for page in self.pages:
            self.stack.addWidget(page)

        self.footer_label = QLabel(self)
        self.footer_label.setWordWrap(True)
        self.back_button = QPushButton("< Back", self)
        self.next_button = QPushButton("Next >", self)
        self.back_button.clicked.connect(lambda _checked=False: self.go_to(self._neighbour(-1)))
        self.next_button.clicked.connect(lambda _checked=False: self.go_to(self._neighbour(1)))
        footer = QHBoxLayout()
        footer.addWidget(self.footer_label, 1)
        footer.addWidget(self.back_button)
        footer.addWidget(self.next_button)

        mainLayout = QVBoxLayout(self)
        mainLayout.addWidget(self.header)
        mainLayout.addWidget(self.step_bar)
        mainLayout.addWidget(self.stack, 1)
        mainLayout.addLayout(footer)

        self.step_bar.currentChanged.connect(self.go_to)
        self._last_checks = {}
        self.model_step.tab.set_problems_provider(self.problems)
        if self.data_manager is not None:
            self.data_manager.add_workflow_mode_callback(self._apply_workflow_mode)
        self._timer = QTimer(self)
        self._timer.setInterval(CHECK_INTERVAL_MS)
        self._timer.timeout.connect(self.refresh_status)
        self._apply_workflow_mode(getattr(self.data_manager, 'workflow_mode', None))
        self.go_to(0)

    @property
    def current_index(self):
        return self.stack.currentIndex()

    def go_to(self, index):
        """Show a step. The index is limited to the steps that exist."""
        index = max(0, min(index, len(self.pages) - 1))
        if index not in self._visible_indices():
            # a hidden step: show the next visible step, or the one before it
            after = self._neighbour(1, index)
            index = after if after != index else self._neighbour(-1, index)
        self.stack.setCurrentIndex(index)
        self.step_bar.set_current_index(index)
        self.back_button.setEnabled(self._neighbour(-1, index) != index)
        self.next_button.setEnabled(self._neighbour(1, index) != index)
        self.refresh_status()

    def _visible_indices(self):
        return [i for i, page in enumerate(self.pages) if self.step_bar.is_step_visible(page.key)]

    def _neighbour(self, direction, index=None):
        """Return the index of the next visible step, or ``index`` if there is none."""
        index = self.current_index if index is None else index
        candidates = [
            i for i in self._visible_indices() if (i - index) * direction > 0
        ]
        if not candidates:
            return index
        return min(candidates, key=lambda i: abs(i - index))

    def _apply_workflow_mode(self, mode):
        """Show the steps that the start choice needs."""
        mode = mode or getattr(self.data_manager, 'workflow_mode', None)
        visible = build_plan.steps_for_mode(mode, [page.key for page in self.pages])
        for page in self.pages:
            self.step_bar.set_step_visible(page.key, page.key in visible)
        self.data_step.set_workflow_mode(mode)
        if self.stack.currentIndex() >= 0 and self.pages[self.stack.currentIndex()].key not in visible:
            self.go_to(self.stack.currentIndex())
        else:
            self.refresh_status()

    def problems(self):
        """Return the problems of the steps that show, as ``(step_key, message)`` pairs."""
        visible = self._visible_indices()
        return build_plan.collect_problems(
            (page.key, self._last_checks[page.key])
            for i, page in enumerate(self.pages)
            if i in visible and page.key in self._last_checks
        )

    def show_step(self, key):
        """Show the step with this key, for example `checks.STEP_VIEW`."""
        self.go_to([page.key for page in self.pages].index(key))

    def check_all(self):
        """Return the `StepCheck` of each step, by step key."""
        return {page.key: page.check() for page in self.pages}

    def refresh_status(self):
        """Run the checks again and show the results in the bar and the footer."""
        results = self.check_all()
        self._last_checks = results
        self.step_bar.set_checks(results)
        self.model_step.tab.refresh_primary_action()
        page = self.pages[self.current_index]
        check = results[page.key]
        if check.messages:
            self.footer_label.setText(check.summary)
            self.footer_label.setToolTip("\n".join(check.messages))
        else:
            self.footer_label.setText("This step is done.")
            self.footer_label.setToolTip("")

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh_status()
        self._timer.start()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._timer.stop()
