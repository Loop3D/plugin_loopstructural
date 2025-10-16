import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QGridLayout,
    QLabel,
    QDoubleSpinBox,
    QVBoxLayout,
    QWidget,
)
from qgis.gui import QgsCollapsibleGroupBox

from LoopStructural import getLogger
logger = getLogger(__name__)


class BoundingBoxWidget(QWidget):
    """Standalone bounding-box widget used in the export/evaluation panel.

    Shows a compact 3-column layout for X/Y/Z nsteps and a single-row
    control for the overall element count (nelements). The widget keeps
    itself in sync with the authoritative bounding_box available from a
    provided data_manager or model_manager and will call back to update
    the model when the user changes values.
    """

    def __init__(self, parent=None, *, model_manager=None, data_manager=None):
        super().__init__(parent)
        self.model_manager = model_manager
        self.data_manager = data_manager

        # Create the inner layout that will be placed inside a collapsible group widget
        inner_layout = QVBoxLayout()
        inner_layout.setContentsMargins(0, 0, 0, 0)
        inner_layout.setSpacing(6)

        grid = QGridLayout()
        grid.setSpacing(6)

        # header row: blank, X, Y, Z
        grid.addWidget(QLabel(""), 0, 0)
        grid.addWidget(QLabel("X"), 0, 1, alignment=Qt.AlignCenter)
        grid.addWidget(QLabel("Y"), 0, 2, alignment=Qt.AlignCenter)
        grid.addWidget(QLabel("Z"), 0, 3, alignment=Qt.AlignCenter)

        # Nsteps row
        grid.addWidget(QLabel("Nsteps:"), 1, 0)
        self.nsteps_x = QDoubleSpinBox()
        self.nsteps_y = QDoubleSpinBox()
        self.nsteps_z = QDoubleSpinBox()
        for sb in (self.nsteps_x, self.nsteps_y, self.nsteps_z):
            sb.setRange(1, 1_000_000)
            sb.setDecimals(0)
            sb.setSingleStep(1)
            sb.setAlignment(Qt.AlignRight)
        grid.addWidget(self.nsteps_x, 1, 1)
        grid.addWidget(self.nsteps_y, 1, 2)
        grid.addWidget(self.nsteps_z, 1, 3)

        # Elements row (span columns)
        grid.addWidget(QLabel("Elements:"), 2, 0)
        self.nelements = QDoubleSpinBox()
        self.nelements.setRange(1, 1_000_000_000)
        self.nelements.setDecimals(0)
        self.nelements.setSingleStep(100)
        self.nelements.setAlignment(Qt.AlignRight)
        grid.addWidget(self.nelements, 2, 1, 1, 3)

        inner_layout.addLayout(grid)

        # Place the inner layout into a QGIS collapsible group box so it matches other sections
        group = QgsCollapsibleGroupBox()
        group.setTitle("Bounding Box")
        group.setLayout(inner_layout)

        # Outer layout for this widget contains the group box (so it can be treated as a single section)
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)
        outer_layout.addWidget(group)

        # initialise values from bounding box if available
        bb = self._get_bounding_box()
        if bb is not None:
            try:
                if getattr(bb, 'nsteps', None) is not None:
                    self.nsteps_x.setValue(int(bb.nsteps[0]))
                    self.nsteps_y.setValue(int(bb.nsteps[1]))
                    self.nsteps_z.setValue(int(bb.nsteps[2]))
            except Exception:
                self.nsteps_x.setValue(100)
                self.nsteps_y.setValue(100)
                self.nsteps_z.setValue(1)
            try:
                if getattr(bb, 'nelements', None) is not None:
                    self.nelements.setValue(int(getattr(bb, 'nelements')))
            except Exception:
                self.nelements.setValue(getattr(bb, 'nelements', 1000) if bb is not None else 1000)
        else:
            self.nsteps_x.setValue(100)
            self.nsteps_y.setValue(100)
            self.nsteps_z.setValue(1)
            self.nelements.setValue(1000)

        # connect signals
        self.nelements.valueChanged.connect(self._on_nelements_changed)
        self.nsteps_x.valueChanged.connect(self._on_nsteps_changed)
        self.nsteps_y.valueChanged.connect(self._on_nsteps_changed)
        self.nsteps_z.valueChanged.connect(self._on_nsteps_changed)

        # register update callback so this widget stays in sync
        if self.data_manager is not None and hasattr(self.data_manager, 'set_bounding_box_update_callback'):
            try:
                self.data_manager.set_bounding_box_update_callback(self._on_bounding_box_updated)
            except Exception:
                pass

    def _get_bounding_box(self):
        bounding_box = None
        if self.data_manager is not None:
            try:
                if hasattr(self.data_manager, 'get_bounding_box'):
                    bounding_box = self.data_manager.get_bounding_box()
                elif hasattr(self.data_manager, 'bounding_box'):
                    bounding_box = getattr(self.data_manager, 'bounding_box')
            except Exception:
                logger.debug('Failed to get bounding box from data_manager', exc_info=True)
                bounding_box = None
        if bounding_box is None and self.model_manager is not None and getattr(self.model_manager, 'model', None) is not None:
            try:
                bounding_box = getattr(self.model_manager.model, 'bounding_box', None)
            except Exception:
                logger.debug('Failed to get bounding box from model_manager', exc_info=True)
                bounding_box = None
        return bounding_box

    def _on_nelements_changed(self, val):
        bb = self._get_bounding_box()
        if bb is None:
            return
        try:
            bb.nelements = int(val)
        except Exception:
            bb.nelements = val
        if self.model_manager is not None:
            try:
                self.model_manager.update_bounding_box(bb)
            except Exception:
                logger.debug('Failed to update bounding_box on model_manager', exc_info=True)
        # refresh from authoritative source
        self._refresh_bb_ui()

    def _on_nsteps_changed(self, _):
        bb = self._get_bounding_box()
        if bb is None:
            return
        try:
            bb.nsteps = np.array([int(self.nsteps_x.value()), int(self.nsteps_y.value()), int(self.nsteps_z.value())])
        except Exception:
            try:
                bb.nsteps = [int(self.nsteps_x.value()), int(self.nsteps_y.value()), int(self.nsteps_z.value())]
            except Exception:
                pass
        if self.model_manager is not None:
            try:
                self.model_manager.update_bounding_box(bb)
            except Exception:
                logger.debug('Failed to update bounding_box on model_manager', exc_info=True)
        # refresh from authoritative source
        self._refresh_bb_ui()

    def _refresh_bb_ui(self):
        bb = self._get_bounding_box()
        if bb is not None:
            try:
                self._on_bounding_box_updated(bb)
            except Exception:
                pass

    def _on_bounding_box_updated(self, bounding_box):
        # collect spinboxes
        spinboxes = [self.nelements, self.nsteps_x, self.nsteps_y, self.nsteps_z]
        for sb in spinboxes:
            try:
                sb.blockSignals(True)
            except Exception:
                pass
        try:
            if getattr(bounding_box, 'nelements', None) is not None:
                try:
                    self.nelements.setValue(int(getattr(bounding_box, 'nelements')))
                except Exception:
                    try:
                        self.nelements.setValue(getattr(bounding_box, 'nelements'))
                    except Exception:
                        logger.debug('Could not set nelements', exc_info=True)
            if getattr(bounding_box, 'nsteps', None) is not None:
                try:
                    nsteps = list(bounding_box.nsteps)
                except Exception:
                    try:
                        nsteps = [int(bounding_box.nsteps[0]), int(bounding_box.nsteps[1]), int(bounding_box.nsteps[2])]
                    except Exception:
                        nsteps = None
                if nsteps is not None:
                    try:
                        self.nsteps_x.setValue(int(nsteps[0]))
                        self.nsteps_y.setValue(int(nsteps[1]))
                        self.nsteps_z.setValue(int(nsteps[2]))
                    except Exception:
                        logger.debug('Could not set nsteps', exc_info=True)
        finally:
            for sb in spinboxes:
                try:
                    sb.blockSignals(False)
                except Exception:
                    pass
