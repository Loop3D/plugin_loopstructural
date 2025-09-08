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
        self.scalar_combo.currentTextChanged.connect(self._on_scalar_changed)
        layout.addWidget(self.scalar_combo)

        # Color with Scalar checkbox
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
        # apply colormap changes when user selects a different cmap
        self.colormap_combo.currentTextChanged.connect(self._on_colormap_changed)
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
        # call set_show_edges when toggled
        self.show_edges_checkbox.toggled.connect(self.set_show_edges)
        layout.addWidget(self.show_edges_checkbox)

        # Line Width
        layout.addWidget(QLabel("Line Width:"))
        self.line_width_slider = QSlider(Qt.Horizontal)
        # allow 0..20, interpreted as float line width
        self.line_width_slider.setRange(0, 20)
        self.line_width_slider.setValue(1)
        self.line_width_slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.line_width_slider.valueChanged.connect(lambda val: self.set_line_width(val))
        layout.addWidget(self.line_width_slider)

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

        # Initialize UI state
        self.color_with_scalar_checkbox.setChecked(False)
        self._on_color_with_scalar_toggled(False)

    def choose_color(self):
        color = QColorDialog.getColor()
        if not color.isValid():
            return
        self.color_button.setStyleSheet(f"background-color: {color.name()}")
        try:
            if not self.current_object_name:
                return
            actor = self.viewer.meshes[self.current_object_name]['actor']
            if hasattr(actor, 'prop'):
                try:
                    actor.prop.color = (color.redF(), color.greenF(), color.blueF())
                except Exception:
                    pass
            elif hasattr(actor, 'GetProperty'):
                try:
                    prop = actor.GetProperty()
                    prop.SetColor(color.redF(), color.greenF(), color.blueF())
                except Exception:
                    pass
            # store color in metadata
            if self.current_object_name in getattr(self.viewer, 'meshes', {}):
                self.viewer.meshes[self.current_object_name]['color'] = (color.redF(), color.greenF(), color.blueF())
        except Exception:
            pass

    def set_opacity(self, value: float):
        if self.current_object_name is None or self.viewer is None:
            return
        try:
            actor = self.viewer.meshes[self.current_object_name]['actor']
            if hasattr(actor, 'prop'):
                try:
                    actor.prop.opacity = value
                except Exception:
                    pass
            elif hasattr(actor, 'GetProperty'):
                try:
                    prop = actor.GetProperty()
                    prop.SetOpacity(value)
                except Exception:
                    pass
            # store in metadata
            if self.current_object_name in getattr(self.viewer, 'meshes', {}):
                self.viewer.meshes[self.current_object_name].set('kwargs', {**self.viewer.meshes[self.current_object_name].get('kwargs', {}), 'opacity': value})
        except Exception:
            pass

    def set_show_edges(self, show: bool):
        """Enable or disable edge display for the current object.
        Best-effort support for both pyvista actor wrappers and raw VTK actors.
        """
        if self.current_object_name is None or self.viewer is None:
            return
        try:
            mesh_entry = self.viewer.meshes.get(self.current_object_name, {})
            actor = mesh_entry.get('actor')
            if actor is None:
                return
            # pyvista-style
            if hasattr(actor, 'prop'):
                try:
                    actor.prop.edge_visibility = bool(show)
                except Exception:
                    pass
                try:
                    # some wrappers expose setter methods on prop
                    actor.prop.SetEdgeVisibility(bool(show))
                except Exception:
                    pass
            # raw VTK actor
            elif hasattr(actor, 'GetProperty'):
                try:
                    prop = actor.GetProperty()
                    if hasattr(prop, 'SetEdgeVisibility'):
                        prop.SetEdgeVisibility(bool(show))
                    else:
                        # fall back to On/Off style methods
                        if bool(show) and hasattr(prop, 'EdgeVisibilityOn'):
                            prop.EdgeVisibilityOn()
                        elif not bool(show) and hasattr(prop, 'EdgeVisibilityOff'):
                            prop.EdgeVisibilityOff()
                except Exception:
                    pass
            # update metadata
            try:
                kwargs = mesh_entry.get('kwargs', {}) if isinstance(mesh_entry, dict) else {}
                kwargs['show_edges'] = bool(show)
                mesh_entry['kwargs'] = kwargs
                # persist back to viewer.meshes
                if hasattr(self.viewer, 'meshes') and self.current_object_name in self.viewer.meshes:
                    self.viewer.meshes[self.current_object_name] = mesh_entry
            except Exception:
                pass
            # request render
            plotter = getattr(self.viewer, 'plotter', None)
            if plotter is not None and hasattr(plotter, 'render'):
                try:
                    plotter.render()
                except Exception:
                    pass
        except Exception:
            pass

    def set_line_width(self, value):
        """Set the line width for edge rendering. Value is an integer slider value; interpreted as float width."""
        try:
            width = float(value)
        except Exception:
            return
        if self.current_object_name is None or self.viewer is None:
            return
        try:
            mesh_entry = self.viewer.meshes.get(self.current_object_name, {})
            actor = mesh_entry.get('actor')
            if actor is None:
                return
            if hasattr(actor, 'prop'):
                try:
                    actor.prop.line_width = width
                except Exception:
                    pass
                try:
                    actor.prop.SetLineWidth(width)
                except Exception:
                    pass
            elif hasattr(actor, 'GetProperty'):
                try:
                    prop = actor.GetProperty()
                    if hasattr(prop, 'SetLineWidth'):
                        prop.SetLineWidth(width)
                except Exception:
                    pass
            # update metadata
            try:
                kwargs = mesh_entry.get('kwargs', {}) if isinstance(mesh_entry, dict) else {}
                kwargs['line_width'] = width
                mesh_entry['kwargs'] = kwargs
                if hasattr(self.viewer, 'meshes') and self.current_object_name in self.viewer.meshes:
                    self.viewer.meshes[self.current_object_name] = mesh_entry
            except Exception:
                pass
            # request render
            plotter = getattr(self.viewer, 'plotter', None)
            if plotter is not None and hasattr(plotter, 'render'):
                try:
                    plotter.render()
                except Exception:
                    pass
        except Exception:
            pass

    def setCurrentObject(self, object_name: str):
        self.current_object_name = object_name
        mesh_entry = self.viewer.meshes.get(object_name, None)
        if mesh_entry is None:
            self.current_mesh = None
            self.title_label.setText(f"Object: {object_name} (not found)")
            self._update_histogram(None)
            return
        self.current_mesh = mesh_entry.get('mesh', None)
        self.title_label.setText(f"Object: {object_name}")

        # reset small things
        self.scalar_bar_checkbox.setChecked(False)
        self.range_min.clear()
        self.range_max.clear()

        # populate scalar combo
        self.scalar_combo.blockSignals(True)
        self.scalar_combo.clear()
        
        try:
            pdata = getattr(self.current_mesh, 'point_data', None) or {}
            cdata = getattr(self.current_mesh, 'cell_data', None) or {}
            for k in sorted(pdata.keys()):
                self.scalar_combo.addItem(k)
            for k in sorted(cdata.keys()):
                self.scalar_combo.addItem(f"cell:{k}")
        except Exception:
            pass

        # restore previous scalar selection if available
        try:
            kwargs = mesh_entry.get('kwargs', {}) if isinstance(mesh_entry, dict) else {}
            prev_scalars = kwargs.get('scalars')
            if prev_scalars:
                sel_name = prev_scalars
                if f"cell:{prev_scalars}" in [self.scalar_combo.itemText(i) for i in range(self.scalar_combo.count())]:
                    sel_name = f"cell:{prev_scalars}"
                idx = self.scalar_combo.findText(sel_name)
                if idx >= 0:
                    self.scalar_combo.setCurrentIndex(idx)
            else:
                idx = self.scalar_combo.findText("<none>")
                if idx >= 0:
                    self.scalar_combo.setCurrentIndex(idx)
        except Exception:
            pass
        self.scalar_combo.blockSignals(False)

        # infer scalar range for display
        try:
            if self.current_mesh is not None:
                pdata = getattr(self.current_mesh, 'point_data', None) or {}
                cdata = getattr(self.current_mesh, 'cell_data', None) or {}
                vals = None
                if len(pdata.keys()) > 0:
                    vals = next(iter(pdata.values()))
                elif len(cdata.keys()) > 0:
                    vals = next(iter(cdata.values()))
                if vals is not None:
                    try:
                        mn = float(getattr(vals, 'min', lambda: min(vals))()) if hasattr(vals, 'min') else float(min(vals))
                        mx = float(getattr(vals, 'max', lambda: max(vals))()) if hasattr(vals, 'max') else float(max(vals))
                        self.range_min.setText(str(mn))
                        self.range_max.setText(str(mx))
                    except Exception:
                        self.range_min.clear()
                        self.range_max.clear()
        except Exception:
            pass

        # detect scalar bar visibility
        try:
            actor = mesh_entry.get('actor', None)
            mapper = getattr(actor, 'mapper', None)
            vis = False
            if mapper is not None and hasattr(mapper, 'scalar_visibility'):
                vis = bool(getattr(mapper, 'scalar_visibility'))
            self.scalar_bar_checkbox.setChecked(vis)
        except Exception:
            pass

        # restore edge and line width from metadata or actor
        try:
            kwargs = mesh_entry.get('kwargs', {}) if isinstance(mesh_entry, dict) else {}
            show_edges = kwargs.get('show_edges', None)
            line_width = kwargs.get('line_width', None)
            actor = mesh_entry.get('actor', None)
            if show_edges is None and actor is not None:
                try:
                    prop = getattr(actor, 'prop', None)
                    if prop is not None and hasattr(prop, 'edge_visibility'):
                        show_edges = bool(getattr(prop, 'edge_visibility'))
                    elif hasattr(actor, 'GetProperty'):
                        p = actor.GetProperty()
                        if hasattr(p, 'GetEdgeVisibility'):
                            show_edges = bool(p.GetEdgeVisibility())
                except Exception:
                    show_edges = False
            if line_width is None and actor is not None:
                try:
                    prop = getattr(actor, 'prop', None)
                    if prop is not None and hasattr(prop, 'line_width'):
                        line_width = float(getattr(prop, 'line_width'))
                    elif hasattr(actor, 'GetProperty'):
                        p = actor.GetProperty()
                        if hasattr(p, 'GetLineWidth'):
                            line_width = float(p.GetLineWidth())
                except Exception:
                    line_width = 1.0
            if show_edges is None:
                show_edges = False
            if line_width is None:
                line_width = 1.0
            self.show_edges_checkbox.blockSignals(True)
            self.show_edges_checkbox.setChecked(bool(show_edges))
            self.show_edges_checkbox.blockSignals(False)
            self.line_width_slider.blockSignals(True)
            try:
                self.line_width_slider.setValue(int(round(float(line_width))))
            except Exception:
                self.line_width_slider.setValue(1)
            self.line_width_slider.blockSignals(False)
        except Exception:
            pass

        # determine initial color-with-scalar
        try:
            kwargs = mesh_entry.get('kwargs', {}) if isinstance(mesh_entry, dict) else {}
            default_color_with_scalar = bool(kwargs.get('scalars') or kwargs.get('cmap'))
            self.color_with_scalar_checkbox.blockSignals(True)
            self.color_with_scalar_checkbox.setChecked(default_color_with_scalar)
            self.color_with_scalar_checkbox.blockSignals(False)
            self._on_color_with_scalar_toggled(default_color_with_scalar)
        except Exception:
            pass

        # update histogram display
        try:
            current_scalar = self.scalar_combo.currentText()
            vals = self._get_scalar_values(current_scalar)
            self._update_histogram(vals if self.color_with_scalar_checkbox.isChecked() else None)
        except Exception:
            self._update_histogram(None)

    def _on_scalar_changed(self, scalar_name: str):
        # update histogram preview immediately
        try:
            vals = self._get_scalar_values(scalar_name)
            self._update_histogram(vals if self.color_with_scalar_checkbox.isChecked() else None)
        except Exception:
            self._update_histogram(None)

        # if not coloring by scalar, only update metadata
        if not self.color_with_scalar_checkbox.isChecked():
            try:
                if self.current_object_name in getattr(self.viewer, 'meshes', {}):
                    self.viewer.meshes[self.current_object_name].set('kwargs', {**self.viewer.meshes[self.current_object_name].get('kwargs', {}), 'scalars': None})
            except Exception:
                pass
            return

        # try in-place update
        try:
            self._apply_scalar_to_actor(self.current_object_name, scalar_name)
            return
        except Exception:
            pass

        # fallback to remove/add
        if not self.current_object_name or self.viewer is None:
            return
        mesh_entry = self.viewer.meshes.get(self.current_object_name, None)
        if mesh_entry is None:
            return
        mesh = mesh_entry.get('mesh')
        old_kwargs = mesh_entry.get('kwargs', {}) if isinstance(mesh_entry, dict) else {}

        scalars = None
        if scalar_name and scalar_name != "<none>":
            if scalar_name.startswith('cell:'):
                scalars = scalar_name.split(':', 1)[1]
            else:
                scalars = scalar_name

        cmap = self.colormap_combo.currentText() or None
        clim = None
        try:
            if self.range_min.text() and self.range_max.text():
                clim = (float(self.range_min.text()), float(self.range_max.text()))
        except Exception:
            clim = None

        opacity = old_kwargs.get('opacity', None)
        show_scalar_bar = self.scalar_bar_checkbox.isChecked()

        try:
            self.viewer.remove_object(self.current_object_name)
        except Exception:
            pass

        try:
            self.viewer.add_mesh_object(mesh, name=self.current_object_name, scalars=scalars, cmap=cmap, clim=clim, opacity=opacity, show_scalar_bar=show_scalar_bar)
            self.current_mesh = self.viewer.meshes.get(self.current_object_name, {}).get('mesh')
        except Exception:
            try:
                self.viewer.add_mesh_object(mesh, name=self.current_object_name)
                self.current_mesh = self.viewer.meshes.get(self.current_object_name, {}).get('mesh')
            except Exception:
                pass

    def _on_color_with_scalar_toggled(self, checked: bool):
        try:
            self.scalar_combo.setEnabled(checked)
            self.colormap_combo.setEnabled(checked)
            self.range_min.setEnabled(checked)
            self.range_max.setEnabled(checked)
            self.scalar_bar_checkbox.setEnabled(checked)
            self.color_button.setEnabled(not checked)
            self.hist_canvas.setVisible(checked)

            if self.current_object_name and self.current_object_name in getattr(self.viewer, 'meshes', {}):
                current_scalar = self.scalar_combo.currentText()
                if checked:
                    try:
                        self._apply_scalar_to_actor(self.current_object_name, current_scalar)
                    except Exception:
                        pass
                else:
                    try:
                        actor = self.viewer.meshes[self.current_object_name].get('actor')
                        mapper = getattr(actor, 'mapper', None)
                        if mapper is not None:
                            try:
                                if hasattr(mapper, 'scalar_visibility'):
                                    mapper.scalar_visibility = False
                            except Exception:
                                pass
                            try:
                                if hasattr(mapper, 'ScalarVisibilityOff'):
                                    mapper.ScalarVisibilityOff()
                            except Exception:
                                pass
                        stored = self.viewer.meshes[self.current_object_name].get('kwargs', {})
                        color = self.viewer.meshes[self.current_object_name].get('color') or stored.get('color')
                        if color is not None and hasattr(actor, 'prop'):
                            try:
                                actor.prop.color = color
                            except Exception:
                                pass
                    except Exception:
                        pass
        except Exception:
            pass

    def _on_colormap_changed(self, cmap: str):
        """Apply or persist selected colormap for the current object.
        Best-effort: try in-place application via _apply_scalar_to_actor, otherwise remove and re-add the mesh with the new cmap."""
        try:
            if not self.current_object_name or self.viewer is None:
                return

            # persist cmap in metadata even when not coloring by scalar
            try:
                if self.current_object_name in getattr(self.viewer, 'meshes', {}):
                    mesh_entry = self.viewer.meshes[self.current_object_name]
                    kwargs = mesh_entry.get('kwargs', {}) if isinstance(mesh_entry, dict) else {}
                    kwargs['cmap'] = cmap or None
                    mesh_entry['kwargs'] = kwargs
                    # write back
                    if hasattr(self.viewer, 'meshes'):
                        self.viewer.meshes[self.current_object_name] = mesh_entry
            except Exception:
                pass

            # only need to change rendering if we're coloring by scalar
            if not self.color_with_scalar_checkbox.isChecked():
                return

            scalar_name = self.scalar_combo.currentText()
            if not scalar_name or scalar_name == "<none>":
                return

            # try in-place update first
            try:
                self._apply_scalar_to_actor(self.current_object_name, scalar_name)
                return
            except Exception:
                pass

            # fallback: remove and re-add mesh with new cmap
            mesh_entry = self.viewer.meshes.get(self.current_object_name, None)
            if mesh_entry is None:
                return
            mesh = mesh_entry.get('mesh')
            old_kwargs = mesh_entry.get('kwargs', {}) if isinstance(mesh_entry, dict) else {}

            scalars = None
            if scalar_name and scalar_name != "<none>":
                if scalar_name.startswith('cell:'):
                    scalars = scalar_name.split(':', 1)[1]
                else:
                    scalars = scalar_name

            clim = None
            try:
                if self.range_min.text() and self.range_max.text():
                    clim = (float(self.range_min.text()), float(self.range_max.text()))
            except Exception:
                clim = None

            opacity = old_kwargs.get('opacity', None)
            show_scalar_bar = self.scalar_bar_checkbox.isChecked()

            try:
                self.viewer.remove_object(self.current_object_name)
            except Exception:
                pass

            try:
                self.viewer.add_mesh_object(mesh, name=self.current_object_name, scalars=scalars, cmap=cmap or None, clim=clim, opacity=opacity, show_scalar_bar=show_scalar_bar)
                self.current_mesh = self.viewer.meshes.get(self.current_object_name, {}).get('mesh')
            except Exception:
                try:
                    self.viewer.add_mesh_object(mesh, name=self.current_object_name)
                    self.current_mesh = self.viewer.meshes.get(self.current_object_name, {}).get('mesh')
                except Exception:
                    pass
        except Exception:
            pass

    def _get_scalar_values(self, scalar_name: str):
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
        try:
            self.hist_ax.clear()
            if values is None:
                self.hist_ax.text(0.5, 0.5, 'No scalar selected', ha='center', va='center', transform=self.hist_ax.transAxes)
                self.hist_ax.set_xticks([])
                self.hist_ax.set_yticks([])
            else:
                self.hist_ax.hist(values.flatten(), bins=40, color='C0', alpha=0.8)
                self.hist_ax.set_xlabel('Value')
                self.hist_ax.set_ylabel('Count')
            self.hist_canvas.draw_idle()
        except Exception:
            pass

    def _update_actor_mapper(self, mesh_entry, scalars, cmap, clim, values, actor, plotter):
        """Centralized actor/mapper update:
        - select/enable scalar array
        - set scalar range
        - build and assign a LUT from matplotlib cmap when possible
        - persist kwargs and trigger render
        """
        try:
            mapper = getattr(actor, 'mapper', None)
            # if plotter can update scalars more directly, prefer that
            if plotter is not None and hasattr(plotter, 'update_scalars') and values is not None:
                try:
                    plotter.update_scalars(values, mesh=mesh_entry.get('mesh'), render=False, name=self.current_object_name)
                except Exception:
                    pass

            if mapper is None:
                return

            # select color array
            try:
                if scalars and hasattr(mapper, 'SelectColorArray'):
                    try:
                        mapper.SelectColorArray(scalars)
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                if scalars and hasattr(mapper, 'SetArrayName'):
                    try:
                        mapper.SetArrayName(scalars)
                    except Exception:
                        pass
            except Exception:
                pass

            # enable scalar visibility
            try:
                if hasattr(mapper, 'scalar_visibility'):
                    try:
                        mapper.scalar_visibility = True
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                if hasattr(mapper, 'ScalarVisibilityOn'):
                    try:
                        mapper.ScalarVisibilityOn()
                    except Exception:
                        pass
            except Exception:
                pass

            # set scalar range
            try:
                mn = mx = None
                if clim:
                    mn, mx = float(clim[0]), float(clim[1])
                else:
                    try:
                        import numpy as _np
                        arr = _np.asarray(values) if values is not None else None
                        if arr is not None and arr.size > 0:
                            mn = float(_np.nanmin(arr))
                            mx = float(_np.nanmax(arr))
                    except Exception:
                        pass
                if mn is not None and mx is not None:
                    try:
                        if hasattr(mapper, 'SetScalarRange'):
                            mapper.SetScalarRange(mn, mx)
                    except Exception:
                        pass
            except Exception:
                pass

            # build and assign LUT from matplotlib cmap
            try:
                if cmap:
                    vtkLookupTable = None
                    try:
                        from vtk import vtkLookupTable as _vtkLookupTable  # type: ignore
                        vtkLookupTable = _vtkLookupTable
                    except Exception:
                        try:
                            from vtkmodules.vtkCommonCore import vtkLookupTable as _vtkLookupTable  # type: ignore
                            vtkLookupTable = _vtkLookupTable
                        except Exception:
                            vtkLookupTable = None
                    if vtkLookupTable is not None:
                        lut = vtkLookupTable()
                        lut.SetNumberOfTableValues(256)
                        lut.Build()
                        try:
                            import matplotlib.cm as mcm
                            cm = mcm.get_cmap(cmap)
                            for i in range(256):
                                r, g, b, a = cm(i / 255.0)
                                try:
                                    lut.SetTableValue(i, float(r), float(g), float(b), float(a))
                                except Exception:
                                    try:
                                        lut.SetTableValue(i, r, g, b, a)
                                    except Exception:
                                        pass
                        except Exception:
                            pass

                        # set LUT range if we know clim
                        try:
                            if clim is not None and len(clim) == 2:
                                try:
                                    lut.SetRange(float(clim[0]), float(clim[1]))
                                except Exception:
                                    pass
                        except Exception:
                            pass

                        # assign to mapper
                        try:
                            if hasattr(mapper, 'SetLookupTable'):
                                try:
                                    mapper.SetLookupTable(lut)
                                except Exception:
                                    pass
                            if hasattr(mapper, 'SetUseLookupTableScalarRange'):
                                try:
                                    mapper.SetUseLookupTableScalarRange(True)
                                except Exception:
                                    pass
                        except Exception:
                            pass
            except Exception:
                pass

            # persist kwargs
            try:
                kwargs = mesh_entry.get('kwargs', {}) if isinstance(mesh_entry, dict) else {}
                kwargs['scalars'] = scalars
                kwargs['cmap'] = cmap or None
                if clim is not None:
                    kwargs['clim'] = (float(clim[0]), float(clim[1]))
                mesh_entry['kwargs'] = kwargs
                if hasattr(self.viewer, 'meshes') and self.current_object_name in self.viewer.meshes:
                    self.viewer.meshes[self.current_object_name] = mesh_entry
            except Exception:
                pass

            # request render
            try:
                if plotter is not None and hasattr(plotter, 'render'):
                    plotter.render()
            except Exception:
                pass
        except Exception:
            pass

    def _apply_scalar_to_actor(self, object_name: str, scalar_name: str):
        if not object_name or self.viewer is None:
            raise RuntimeError("No viewer or object specified")
        mesh_entry = self.viewer.meshes.get(object_name)
        if mesh_entry is None:
            raise RuntimeError("Object not found in viewer.meshes")
        mesh = mesh_entry.get('mesh')
        actor = mesh_entry.get('actor')

        # disable mapping if requested
        if not scalar_name or scalar_name == "<none>":
            mapper = getattr(actor, 'mapper', None)
            if mapper is not None:
                if hasattr(mapper, 'scalar_visibility'):
                    mapper.scalar_visibility = False
                if hasattr(mapper, 'ScalarVisibilityOff'):
                    mapper.ScalarVisibilityOff()
            mesh_entry.setdefault('kwargs', {})['scalars'] = None
            return

        # resolve scalar name
        use_cell = False
        scalars = scalar_name
        if scalar_name.startswith('cell:'):
            scalars = scalar_name.split(':', 1)[1]
            use_cell = True

        values = self._get_scalar_values(scalar_name)
        if values is None:
            raise RuntimeError('Failed to retrieve scalar values')

        plotter = getattr(self.viewer, 'plotter', None)
        applied = False
        if plotter is not None and hasattr(plotter, 'update_scalars'):
            try:
                plotter.update_scalars(values, mesh=mesh, render=True, name=object_name)
                applied = True
            except Exception:
                applied = False

        # If we didn't use plotter.update_scalars, use the centralized mapper update helper
        if not applied:
            try:
                cmap = self.colormap_combo.currentText() or None
                clim = None
                try:
                    if self.range_min.text() and self.range_max.text():
                        clim = (float(self.range_min.text()), float(self.range_max.text()))
                except Exception:
                    clim = None
                self._update_actor_mapper(mesh_entry, scalars, cmap, clim, values, actor, plotter)
                return
            except Exception:
                pass
