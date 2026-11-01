from qgis.PyQt.QtCore import QTimer, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from loopstructural.gui.modelling.steps import checks
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
        self.back_button.clicked.connect(lambda _checked=False: self.go_to(self.current_index - 1))
        self.next_button.clicked.connect(lambda _checked=False: self.go_to(self.current_index + 1))
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
        self._timer = QTimer(self)
        self._timer.setInterval(CHECK_INTERVAL_MS)
        self._timer.timeout.connect(self.refresh_status)
        self.go_to(0)

    @property
    def current_index(self):
        return self.stack.currentIndex()

    def go_to(self, index):
        """Show a step. The index is limited to the steps that exist."""
        index = max(0, min(index, len(self.pages) - 1))
        self.stack.setCurrentIndex(index)
        self.step_bar.set_current_index(index)
        self.back_button.setEnabled(index > 0)
        self.next_button.setEnabled(index < len(self.pages) - 1)
        self.refresh_status()

    def show_step(self, key):
        """Show the step with this key, for example `checks.STEP_VIEW`."""
        self.go_to([page.key for page in self.pages].index(key))

    def check_all(self):
        """Return the `StepCheck` of each step, by step key."""
        return {page.key: page.check() for page in self.pages}

    def refresh_status(self):
        """Run the checks again and show the results in the bar and the footer."""
        results = self.check_all()
        self.step_bar.set_checks(results)
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
