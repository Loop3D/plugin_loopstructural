from PyQt5.QtCore import Qt

from PyQt5.QtWidgets import (
        QWidget, QVBoxLayout, QLabel, QComboBox, QSlider, QCheckBox, QColorDialog, QPushButton, QHBoxLayout, QLineEdit, QSizePolicy
)

class ObjectPropertiesWidget(QWidget):
    def __init__(self, parent=None, *, viewer=None):
        super().__init__(parent)
        layout = QVBoxLayout()
        # Keep widgets close together and provide padding at the bottom
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 20)

        # Title / currently selected object
        self.title_label = QLabel("No object selected")
        self.title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(self.title_label)

        # Scalar Bar
        self.scalar_bar_checkbox = QCheckBox("Show Scalar Bar")
        self.scalar_bar_checkbox.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        layout.addWidget(self.scalar_bar_checkbox)

        # Colormap
        layout.addWidget(QLabel("Colormap:"))
        self.colormap_combo = QComboBox()
        self.colormap_combo.addItems(["Viridis", "Plasma", "Inferno", "Magma", "Greys"])
        self.colormap_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(self.colormap_combo)

        # Opacity
        layout.addWidget(QLabel("Opacity:"))
        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(0, 100)
        self.opacity_slider.setValue(100)
        self.opacity_slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.opacity_slider.valueChanged.connect(lambda val: self.set_opacity(val / 100.0))
        layout.addWidget(self.opacity_slider)

        # Show Edges
        self.show_edges_checkbox = QCheckBox("Show Edges")
        self.show_edges_checkbox.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        layout.addWidget(self.show_edges_checkbox)

        # Colormap Range
        range_layout = QHBoxLayout()
        range_layout.setSpacing(6)
        range_layout.addWidget(QLabel("Colormap Range:"))
        self.range_min = QLineEdit()
        self.range_min.setPlaceholderText("Min")
        self.range_min.setMaximumWidth(120)
        self.range_min.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.range_max = QLineEdit()
        self.range_max.setPlaceholderText("Max")
        self.range_max.setMaximumWidth(120)
        self.range_max.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        range_layout.addWidget(self.range_min)
        range_layout.addWidget(self.range_max)
        layout.addLayout(range_layout)

        # Surface Color
        surface_color_layout = QHBoxLayout()
        surface_color_layout.setSpacing(6)
        surface_color_layout.addWidget(QLabel("Surface Color:"))
        self.color_button = QPushButton("Choose Color")
        self.color_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        surface_color_layout.addWidget(self.color_button)
        layout.addLayout(surface_color_layout)

        # Add stretch at end so widgets stay grouped at top and bottom has padding
        layout.addStretch(1)

        self.setLayout(layout)

        # Internal state
        self.current_object_name = None
        self.current_mesh = None
        self.viewer = viewer

        # Connect color button to color dialog
        self.color_button.clicked.connect(self.choose_color)

    def choose_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.color_button.setStyleSheet(f"background-color: {color.name()}")
            actor = self.viewer.meshes[self.current_object_name]['actor']
            actor.prop.color = (color.redF(), color.greenF(), color.blueF())
            # Placeholder: store or use the selected color
            self.meshes[self.current_object_name]['color'] = (color.redF(), color.greenF(), color.blueF())
    def set_opacity(self, value: float):
        """Set the opacity of the current object.

        :param value: Opacity value between 0.0 (transparent) and 1.0 (opaque)
        """
        if self.current_object_name is None or self.viewer is None:
            return
        actor = self.viewer.meshes[self.current_object_name]['actor']
        actor.prop.opacity = value
        self.meshes[self.current_object_name]['opacity'] = value
   

    def setCurrentObject(self, object_name: str):
        """Populate the properties widget for the given object.

        :param object_name: name of the selected object
        :param mesh: optional mesh instance (pyvista.PolyData or similar)
        :param viewer: optional viewer instance for deeper control
        """
        self.current_object_name = object_name
        self.current_mesh = self.viewer.meshes[object_name]
        self.title_label.setText(f"Object: {object_name}")

        # Default values
        self.scalar_bar_checkbox.setChecked(False)
        self.range_min.clear()
        self.range_max.clear()

        # Try to infer a scalar range from mesh data (point or cell data)
        try:
            if self.current_meshmesh is not None:
                # Prefer point_data, fall back to cell_data
                pdata = getattr(self.current_mesh, 'point_data', None) or {}
                cdata = getattr(self.current_mesh, 'cell_data', None) or {}
                first = None
                if len(pdata.keys()) > 0:
                    first = next(iter(pdata.keys()))
                    vals = pdata[first]
                elif len(cdata.keys()) > 0:
                    first = next(iter(cdata.keys()))
                    vals = cdata[first]
                else:
                    first = None
                    vals = None

                if vals is not None:
                    try:
                        mn = float(getattr(vals, 'min', lambda: min(vals))()) if hasattr(vals, 'min') else float(min(vals))
                        mx = float(getattr(vals, 'max', lambda: max(vals))()) if hasattr(vals, 'max') else float(max(vals))
                        self.range_min.setText(str(mn))
                        self.range_max.setText(str(mx))
                    except Exception:
                        # best-effort only
                        self.range_min.clear()
                        self.range_max.clear()

        except Exception:
            # Keep defaults on error
            pass

        # Try to detect scalar bar visibility via viewer/actor if provided
        try:
            if self.viewer is not None and hasattr(self.viewer, 'actors') and object_name in getattr(self.viewer, 'actors', {}):
                actor = self.viewer.actors[object_name]
                # some actor wrappers expose mapper.scalar_visibility or similar
                mapper = getattr(actor, 'mapper', None)
                vis = False
                if mapper is not None and hasattr(mapper, 'scalar_visibility'):
                    vis = bool(getattr(mapper, 'scalar_visibility'))
                # update checkbox (best-effort)
                self.scalar_bar_checkbox.setChecked(vis)
        except Exception:
            # ignore failures
            pass