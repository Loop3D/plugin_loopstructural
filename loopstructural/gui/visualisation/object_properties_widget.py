from PyQt5.QtCore import Qt

from PyQt5.QtWidgets import (
        QWidget, QVBoxLayout, QLabel, QComboBox, QSlider, QCheckBox, QColorDialog, QPushButton, QHBoxLayout, QLineEdit, QSizePolicy
)

# Add plotting imports for scalar histogram
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt
import numpy as np

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

        # Scalar selection
        layout.addWidget(QLabel("Active Scalar:"))
        self.scalar_combo = QComboBox()
        self.scalar_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.scalar_combo.addItem("<none>")
        self.scalar_combo.currentTextChanged.connect(self._on_scalar_changed)
        layout.addWidget(self.scalar_combo)

        # Color with Scalar checkbox (new)
        self.color_with_scalar_checkbox = QCheckBox("Color with Scalar")
        self.color_with_scalar_checkbox.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.color_with_scalar_checkbox.toggled.connect(self._on_color_with_scalar_toggled)
        layout.addWidget(self.color_with_scalar_checkbox)

        # Scalar Bar
        self.scalar_bar_checkbox = QCheckBox("Show Scalar Bar")
        self.scalar_bar_checkbox.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        layout.addWidget(self.scalar_bar_checkbox)

        # Colormap
        layout.addWidget(QLabel("Colormap:"))
        self.colormap_combo = QComboBox()
        self.colormap_combo.addItems(["viridis", "plasma", "inferno", "magma", "greys"])
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

        # Scalar Histogram (matplotlib canvas)
        layout.addWidget(QLabel("Scalar Histogram:"))
        self.hist_fig = plt.Figure(figsize=(4, 2))
        self.hist_canvas = FigureCanvas(self.hist_fig)
        self.hist_ax = self.hist_fig.subplots()
        self.hist_canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(self.hist_canvas)

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

        # Initialize UI state: default to not coloring by scalar until an object is selected
        self.color_with_scalar_checkbox.setChecked(False)
        # Ensure controls reflect the initial state
        self._on_color_with_scalar_toggled(False)

    def choose_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.color_button.setStyleSheet(f"background-color: {color.name()}")
            try:
                actor = self.viewer.meshes[self.current_object_name]['actor']
                # pyvista/VTK actor property access may vary; try common attributes
                if hasattr(actor, 'prop'):
                    actor.prop.color = (color.redF(), color.greenF(), color.blueF())
                elif hasattr(actor, 'GetProperty'):
                    prop = actor.GetProperty()
                    prop.SetColor(color.redF(), color.greenF(), color.blueF())
                # store color in metadata if present
                if self.current_object_name in getattr(self.viewer, 'meshes', {}):
                    self.viewer.meshes[self.current_object_name].set('color', (color.redF(), color.greenF(), color.blueF()))
            except Exception:
                pass

    def set_opacity(self, value: float):
        """Set the opacity of the current object.

        :param value: Opacity value between 0.0 (transparent) and 1.0 (opaque)
        """
        if self.current_object_name is None or self.viewer is None:
            return
        try:
            actor = self.viewer.meshes[self.current_object_name]['actor']
            if hasattr(actor, 'prop'):
                actor.prop.opacity = value
            elif hasattr(actor, 'GetProperty'):
                prop = actor.GetProperty()
                prop.SetOpacity(value)
            # store in metadata
            if self.current_object_name in getattr(self.viewer, 'meshes', {}):
                self.viewer.meshes[self.current_object_name].set('kwargs', {**self.viewer.meshes[self.current_object_name].get('kwargs', {}), 'opacity': value})
        except Exception:
            pass
   

    def setCurrentObject(self, object_name: str):
        """Populate the properties widget for the given object.

        :param object_name: name of the selected object
        """
        self.current_object_name = object_name
        # viewer.meshes stores a dict with keys 'mesh', 'actor', 'kwargs'
        mesh_entry = self.viewer.meshes.get(object_name, None)
        if mesh_entry is None:
            self.current_mesh = None
            self.title_label.setText(f"Object: {object_name} (not found)")
            # clear histogram
            self._update_histogram(None)
            return
        self.current_mesh = mesh_entry.get('mesh', None)
        self.title_label.setText(f"Object: {object_name}")

        # Default values
        self.scalar_bar_checkbox.setChecked(False)
        self.range_min.clear()
        self.range_max.clear()

        # Populate scalar combo with available arrays
        self.scalar_combo.blockSignals(True)
        self.scalar_combo.clear()
        self.scalar_combo.addItem("<none>")
        try:
            pdata = getattr(self.current_mesh, 'point_data', None) or {}
            cdata = getattr(self.current_mesh, 'cell_data', None) or {}
            for k in sorted(pdata.keys()):
                self.scalar_combo.addItem(k)
            for k in sorted(cdata.keys()):
                # prefix cell_ to help user know where it comes from
                self.scalar_combo.addItem(f"cell:{k}")
        except Exception:
            pass

        # If kwargs indicate a previously-used scalar, select it
        try:
            kwargs = mesh_entry.get('kwargs', {}) if isinstance(mesh_entry, dict) else {}
            prev_scalars = kwargs.get('scalars')
            if prev_scalars:
                # if scalar came from cell data, it may be stored as 'cell:NAME' or just NAME
                sel_name = prev_scalars
                # prefer 'cell:...' if that exists in the combo
                if f"cell:{prev_scalars}" in [self.scalar_combo.itemText(i) for i in range(self.scalar_combo.count())]:
                    sel_name = f"cell:{prev_scalars}"
                # set selection without emitting signals
                idx = self.scalar_combo.findText(sel_name)
                if idx >= 0:
                    self.scalar_combo.setCurrentIndex(idx)
            else:
                # ensure default selection is <none>
                idx = self.scalar_combo.findText("<none>")
                if idx >= 0:
                    self.scalar_combo.setCurrentIndex(idx)
        except Exception:
            pass

        self.scalar_combo.blockSignals(False)

        # Try to infer a scalar range from mesh data (point or cell data)
        try:
            if self.current_mesh is not None:
                # Prefer point_data, fall back to cell_data
                pdata = getattr(self.current_mesh, 'point_data', None) or {}
                cdata = getattr(self.current_mesh, 'cell_data', None) or {}
                first = None
                vals = None
                if len(pdata.keys()) > 0:
                    first = next(iter(pdata.keys()))
                    vals = pdata[first]
                elif len(cdata.keys()) > 0:
                    first = next(iter(cdata.keys()))
                    vals = cdata[first]

                if vals is not None:
                    try:
                        # attempt numpy-like min/max or python min/max
                        mn = float(getattr(vals, 'min', lambda: min(vals))()) if hasattr(vals, 'min') else float(min(vals))
                        mx = float(getattr(vals, 'max', lambda: max(vals))()) if hasattr(vals, 'max') else float(max(vals))
                        self.range_min.setText(str(mn))
                        self.range_max.setText(str(mx))
                    except Exception:
                        self.range_min.clear()
                        self.range_max.clear()

        except Exception:
            # Keep defaults on error
            pass

        # Try to detect scalar bar visibility via viewer/actor if provided
        try:
            if self.viewer is not None and hasattr(self.viewer, 'mesh' or 'meshes') and object_name in getattr(self.viewer, 'meshes', {}):
                actor = self.viewer.meshes[object_name].get('actor', None)
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

        # Determine initial 'color with scalar' state from stored kwargs if available
        try:
            kwargs = mesh_entry.get('kwargs', {}) if isinstance(mesh_entry, dict) else {}
            # If scalars or cmap were provided when the mesh was added, default to coloring with scalar
            default_color_with_scalar = bool(kwargs.get('scalars') or kwargs.get('cmap'))
            # set without emitting signal to avoid immediate re-add
            self.color_with_scalar_checkbox.blockSignals(True)
            self.color_with_scalar_checkbox.setChecked(default_color_with_scalar)
            self.color_with_scalar_checkbox.blockSignals(False)
            # update controls to reflect this choice
            self._on_color_with_scalar_toggled(default_color_with_scalar)
        except Exception:
            # ignore any failure and leave the previously set state
            pass

        # Update histogram for the currently selected scalar (if any and if enabled)
        try:
            current_scalar = self.scalar_combo.currentText()
            vals = self._get_scalar_values(current_scalar)
            self._update_histogram(vals if self.color_with_scalar_checkbox.isChecked() else None)
        except Exception:
            self._update_histogram(None)

    def choose_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.color_button.setStyleSheet(f"background-color: {color.name()}")
            try:
                actor = self.viewer.meshes[self.current_object_name]['actor']
                # pyvista/VTK actor property access may vary; try common attributes
                if hasattr(actor, 'prop'):
                    actor.prop.color = (color.redF(), color.greenF(), color.blueF())
                elif hasattr(actor, 'GetProperty'):
                    prop = actor.GetProperty()
                    prop.SetColor(color.redF(), color.greenF(), color.blueF())
                # store color in metadata if present
                if self.current_object_name in getattr(self.viewer, 'meshes', {}):
                    self.viewer.meshes[self.current_object_name].set('color', (color.redF(), color.greenF(), color.blueF()))
            except Exception:
                pass

    def set_opacity(self, value: float):
        """Set the opacity of the current object.

        :param value: Opacity value between 0.0 (transparent) and 1.0 (opaque)
        """
        if self.current_object_name is None or self.viewer is None:
            return
        try:
            actor = self.viewer.meshes[self.current_object_name]['actor']
            if hasattr(actor, 'prop'):
                actor.prop.opacity = value
            elif hasattr(actor, 'GetProperty'):
                prop = actor.GetProperty()
                prop.SetOpacity(value)
            # store in metadata
            if self.current_object_name in getattr(self.viewer, 'meshes', {}):
                self.viewer.meshes[self.current_object_name].set('kwargs', {**self.viewer.meshes[self.current_object_name].get('kwargs', {}), 'opacity': value})
        except Exception:
            pass
   

    def setCurrentObject(self, object_name: str):
        """Populate the properties widget for the given object.

        :param object_name: name of the selected object
        """
        self.current_object_name = object_name
        # viewer.meshes stores a dict with keys 'mesh', 'actor', 'kwargs'
        mesh_entry = self.viewer.meshes.get(object_name, None)
        if mesh_entry is None:
            self.current_mesh = None
            self.title_label.setText(f"Object: {object_name} (not found)")
            # clear histogram
            self._update_histogram(None)
            return
        self.current_mesh = mesh_entry.get('mesh', None)
        self.title_label.setText(f"Object: {object_name}")

        # Default values
        self.scalar_bar_checkbox.setChecked(False)
        self.range_min.clear()
        self.range_max.clear()

        # Populate scalar combo with available arrays
        self.scalar_combo.blockSignals(True)
        self.scalar_combo.clear()
        self.scalar_combo.addItem("<none>")
        try:
            pdata = getattr(self.current_mesh, 'point_data', None) or {}
            cdata = getattr(self.current_mesh, 'cell_data', None) or {}
            for k in sorted(pdata.keys()):
                self.scalar_combo.addItem(k)
            for k in sorted(cdata.keys()):
                # prefix cell_ to help user know where it comes from
                self.scalar_combo.addItem(f"cell:{k}")
        except Exception:
            pass

        # If kwargs indicate a previously-used scalar, select it
        try:
            kwargs = mesh_entry.get('kwargs', {}) if isinstance(mesh_entry, dict) else {}
            prev_scalars = kwargs.get('scalars')
            if prev_scalars:
                # if scalar came from cell data, it may be stored as 'cell:NAME' or just NAME
                sel_name = prev_scalars
                # prefer 'cell:...' if that exists in the combo
                if f"cell:{prev_scalars}" in [self.scalar_combo.itemText(i) for i in range(self.scalar_combo.count())]:
                    sel_name = f"cell:{prev_scalars}"
                # set selection without emitting signals
                idx = self.scalar_combo.findText(sel_name)
                if idx >= 0:
                    self.scalar_combo.setCurrentIndex(idx)
            else:
                # ensure default selection is <none>
                idx = self.scalar_combo.findText("<none>")
                if idx >= 0:
                    self.scalar_combo.setCurrentIndex(idx)
        except Exception:
            pass

        self.scalar_combo.blockSignals(False)

        # Try to infer a scalar range from mesh data (point or cell data)
        try:
            if self.current_mesh is not None:
                # Prefer point_data, fall back to cell_data
                pdata = getattr(self.current_mesh, 'point_data', None) or {}
                cdata = getattr(self.current_mesh, 'cell_data', None) or {}
                first = None
                vals = None
                if len(pdata.keys()) > 0:
                    first = next(iter(pdata.keys()))
                    vals = pdata[first]
                elif len(cdata.keys()) > 0:
                    first = next(iter(cdata.keys()))
                    vals = cdata[first]

                if vals is not None:
                    try:
                        # attempt numpy-like min/max or python min/max
                        mn = float(getattr(vals, 'min', lambda: min(vals))()) if hasattr(vals, 'min') else float(min(vals))
                        mx = float(getattr(vals, 'max', lambda: max(vals))()) if hasattr(vals, 'max') else float(max(vals))
                        self.range_min.setText(str(mn))
                        self.range_max.setText(str(mx))
                    except Exception:
                        self.range_min.clear()
                        self.range_max.clear()

        except Exception:
            # Keep defaults on error
            pass

        # Try to detect scalar bar visibility via viewer/actor if provided
        try:
            if self.viewer is not None and hasattr(self.viewer, 'mesh' or 'meshes') and object_name in getattr(self.viewer, 'meshes', {}):
                actor = self.viewer.meshes[object_name].get('actor', None)
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

        # Determine initial 'color with scalar' state from stored kwargs if available
        try:
            kwargs = mesh_entry.get('kwargs', {}) if isinstance(mesh_entry, dict) else {}
            # If scalars or cmap were provided when the mesh was added, default to coloring with scalar
            default_color_with_scalar = bool(kwargs.get('scalars') or kwargs.get('cmap'))
            # set without emitting signal to avoid immediate re-add
            self.color_with_scalar_checkbox.blockSignals(True)
            self.color_with_scalar_checkbox.setChecked(default_color_with_scalar)
            self.color_with_scalar_checkbox.blockSignals(False)
            # update controls to reflect this choice
            self._on_color_with_scalar_toggled(default_color_with_scalar)
        except Exception:
            # ignore any failure and leave the previously set state
            pass

        # Update histogram for the currently selected scalar (if any and if enabled)
        try:
            current_scalar = self.scalar_combo.currentText()
            vals = self._get_scalar_values(current_scalar)
            self._update_histogram(vals if self.color_with_scalar_checkbox.isChecked() else None)
        except Exception:
            self._update_histogram(None)

    def _on_scalar_changed(self, scalar_name: str):
        """Handler when the user selects a different active scalar.

        Approach: remove the existing actor/object and re-add it passing the
        chosen scalar name to the viewer. This keeps the viewer in control of
        actor creation and colormap handling.
        """
        # update histogram preview first (don't require re-add to preview)
        try:
            vals = self._get_scalar_values(scalar_name)
            self._update_histogram(vals)
        except Exception:
            self._update_histogram(None)

        if not self.current_object_name or self.viewer is None:
            return

        mesh_entry = self.viewer.meshes.get(self.current_object_name, None)
        if mesh_entry is None:
            return
        mesh = mesh_entry.get('mesh')
        old_kwargs = mesh_entry.get('kwargs', {}) if isinstance(mesh_entry, dict) else {}

        # Determine scalars parameter and whether it's point or cell data
        scalars = None
        if scalar_name and scalar_name != "<none>":
            if scalar_name.startswith('cell:'):
                scalars = scalar_name.split(':', 1)[1]
            else:
                scalars = scalar_name

        # Determine cmap and clim from widgets
        cmap = self.colormap_combo.currentText() or None
        clim = None
        try:
            if self.range_min.text() and self.range_max.text():
                clim = (float(self.range_min.text()), float(self.range_max.text()))
        except Exception:
            clim = None

        opacity = old_kwargs.get('opacity', None)
        show_scalar_bar = self.scalar_bar_checkbox.isChecked()

        # Remove existing object and re-add with new scalars
        try:
            # preserve name: remove_object removes metadata so re-adding keeps same name
            self.viewer.remove_object(self.current_object_name)
        except Exception:
            # if remove fails, continue and try to add anyway (may create duplicate names)
            pass

        try:
            self.viewer.add_mesh_object(mesh, name=self.current_object_name, scalars=scalars, cmap=cmap, clim=clim, opacity=opacity, show_scalar_bar=show_scalar_bar)
            # refresh local pointers
            self.current_mesh = self.viewer.meshes.get(self.current_object_name, {}).get('mesh')
        except Exception:
            # on failure, try to add without scalars
            try:
                self.viewer.add_mesh_object(mesh, name=self.current_object_name)
                self.current_mesh = self.viewer.meshes.get(self.current_object_name, {}).get('mesh')
            except Exception:
                pass

    def _on_color_with_scalar_toggled(self, checked: bool):
        """Enable/disable scalar/colormap controls vs solid color selector.

        When checked: enable scalar selection, colormap and colormap range and scalar bar.
        When unchecked: enable surface color chooser and disable scalar-related controls.
        """
        try:
            # scalar-related controls
            self.scalar_combo.setEnabled(checked)
            self.colormap_combo.setEnabled(checked)
            self.range_min.setEnabled(checked)
            self.range_max.setEnabled(checked)
            self.scalar_bar_checkbox.setEnabled(checked)
            # color chooser is enabled only when not coloring by scalar
            self.color_button.setEnabled(not checked)
            # histogram visibility follows scalar-mode
            self.hist_canvas.setVisible(checked)
        except Exception:
            pass

    # New helper methods for histogram
    def _get_scalar_values(self, scalar_name: str):
        """Return a numpy array of scalar values for the current mesh and scalar_name.

        scalar_name can be '<none>', 'name' (point data) or 'cell:name'.
        Returns None if values cannot be retrieved.
        """
        if not scalar_name or scalar_name == "<none>" or self.current_mesh is None:
            return None
        try:
            if scalar_name.startswith('cell:'):
                name = scalar_name.split(':', 1)[1]
                cdata = getattr(self.current_mesh, 'cell_data', None) or {}
                vals = cdata.get(name, None)
            else:
                name = scalar_name
                pdata = getattr(self.current_mesh, 'point_data', None) or {}
                vals = pdata.get(name, None)
            if vals is None:
                return None
            arr = np.asarray(vals)
            if arr.size == 0:
                return None
            return arr
        except Exception:
            return None

    def _update_histogram(self, values):
        """Draw the histogram of the provided scalar values. If values is None,
        clear the axes and show a placeholder message.
        """
        try:
            self.hist_ax.clear()
            if values is None:
                # show placeholder
                self.hist_ax.text(0.5, 0.5, 'No scalar selected', ha='center', va='center', transform=self.hist_ax.transAxes)
                self.hist_ax.set_xticks([])
                self.hist_ax.set_yticks([])
            else:
                self.hist_ax.hist(values.flatten(), bins=40, color='C0', alpha=0.8)
                self.hist_ax.set_xlabel('Value')
                self.hist_ax.set_ylabel('Count')
            self.hist_canvas.draw_idle()
        except Exception:
            # swallow plotting errors
            pass