
import pyqtgraph as pg
from qgis.PyQt.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QVBoxLayout,
)


class SPlotDialog(QDialog):
    def __init__(self, parent=None, *, data_manager=None, model_manager=None, feature_name=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.model_manager = model_manager
        self.feature_name = feature_name
        self.setWindowTitle('S-Plot')
        self.setMinimumWidth(300)
        feature = self.model_manager.model.get_feature_by_name(self.feature_name)
        layout = QVBoxLayout()

        
        fold_frame = feature.fold.fold_limb_rotation.fold_frame_coordinate
        rotation = feature.fold.fold_limb_rotation.rotation_angle 
        # Placeholder scatter plot using pyqtgraph
        self.plot_widget = pg.PlotWidget()
        
        self.plot_widget.plot(
            fold_frame,
            rotation,
            pen=None,
            symbol='o',
            symbolSize=6,
            symbolBrush=(100, 150, 255, 200),
        )
        self.plot_widget.setLabel('left', 'Fold limb rotation angle (°)')
        self.plot_widget.setLabel('bottom', 'Fold frame coordinate')
        layout.addWidget(self.plot_widget)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.setLayout(layout)
