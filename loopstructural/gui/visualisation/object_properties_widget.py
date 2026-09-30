import matplotlib.pyplot as plt
import numpy as np

# Add plotting imports for scalar histogram
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor, QIcon, QPixmap
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from .mesh_scalar_utils import (
    apply_colormap_lut,
    filter_array_names,
    get_scalar_values,
    render_histogram,
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

        # Filter: show only the part of the object whose values are in a
        # range, or (for the unit ids of a block model, cross section or
        # topography) only the units that are checked
        self.filter_group = QGroupBox("Filter (Threshold)")
        filter_layout = QVBoxLayout(self.filter_group)
        filter_layout.addWidget(QLabel("Array:"))
        self.filter_array_combo = QComboBox()
        self.filter_array_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.filter_array_combo.currentTextChanged.connect(self._on_filter_array_changed)
        filter_layout.addWidget(self.filter_array_combo)
        self.filter_range_widget = QWidget()
        filter_range_widget_layout = QVBoxLayout(self.filter_range_widget)
        filter_range_widget_layout.setContentsMargins(0, 0, 0, 0)
        filter_range_layout = QHBoxLayout()
        filter_range_layout.setSpacing(6)
        filter_range_layout.addWidget(QLabel("Range:"))
        self.filter_min = QDoubleSpinBox()
        self.filter_max = QDoubleSpinBox()
        for box in (self.filter_min, self.filter_max):
            box.setRange(-1e12, 1e12)
            box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            filter_range_layout.addWidget(box)
        filter_range_widget_layout.addLayout(filter_range_layout)
        self.filter_invert_checkbox = QCheckBox("Invert (show values outside the range)")
        filter_range_widget_layout.addWidget(self.filter_invert_checkbox)
        filter_layout.addWidget(self.filter_range_widget)

        self.filter_units_widget = QWidget()
        filter_units_layout = QVBoxLayout(self.filter_units_widget)
        filter_units_layout.setContentsMargins(0, 0, 0, 0)
        filter_units_layout.addWidget(QLabel("Units to show:"))
        self.filter_units_list = QListWidget()
        self.filter_units_list.setMaximumHeight(160)
        self.filter_units_list.itemChanged.connect(self._on_unit_check_changed)
        filter_units_layout.addWidget(self.filter_units_list)
        filter_units_buttons_layout = QHBoxLayout()
        check_all_button = QPushButton("Check All")
        check_all_button.clicked.connect(lambda: self._set_all_units_checked(True))
        uncheck_all_button = QPushButton("Uncheck All")
        uncheck_all_button.clicked.connect(lambda: self._set_all_units_checked(False))
        filter_units_buttons_layout.addWidget(check_all_button)
        filter_units_buttons_layout.addWidget(uncheck_all_button)
        filter_units_layout.addLayout(filter_units_buttons_layout)
        self.filter_units_widget.setVisible(False)
        filter_layout.addWidget(self.filter_units_widget)
        filter_buttons_layout = QHBoxLayout()
        self.filter_apply_button = QPushButton("Apply Filter")
        self.filter_apply_button.clicked.connect(self.apply_filter)
        self.filter_clear_button = QPushButton("Clear Filter")
        self.filter_clear_button.clicked.connect(self.clear_filter)
        filter_buttons_layout.addWidget(self.filter_apply_button)
        filter_buttons_layout.addWidget(self.filter_clear_button)
        filter_layout.addLayout(filter_buttons_layout)
        self.filter_status_label = QLabel("")
        filter_layout.addWidget(self.filter_status_label)
        self.filter_group.setEnabled(False)
        layout.addWidget(self.filter_group)

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
                self.viewer.meshes[self.current_object_name]['color'] = (
                    color.redF(),
                    color.greenF(),
                    color.blueF(),
                )
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
                entry = self.viewer.meshes[self.current_object_name]
                entry['kwargs'] = {**(entry.get('kwargs') or {}), 'opacity': value}
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
                if (
                    hasattr(self.viewer, 'meshes')
                    and self.current_object_name in self.viewer.meshes
                ):
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
                if (
                    hasattr(self.viewer, 'meshes')
                    and self.current_object_name in self.viewer.meshes
                ):
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
                if f"cell:{prev_scalars}" in [
                    self.scalar_combo.itemText(i) for i in range(self.scalar_combo.count())
                ]:
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
                        import numpy as _np

                        arr = _np.asarray(vals, dtype=float)
                        finite = arr[_np.isfinite(arr)]
                        if finite.size > 0:
                            self.range_min.setText(str(float(_np.min(finite))))
                            self.range_max.setText(str(float(_np.max(finite))))
                        else:
                            self.range_min.clear()
                            self.range_max.clear()
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
                vis = bool(mapper.scalar_visibility)
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
                        show_edges = bool(prop.edge_visibility)
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
                        line_width = float(prop.line_width)
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

        self._load_filter_state(mesh_entry)

    def _load_filter_state(self, mesh_entry):
        """Show the filter of the current object, or the full value range
        of an array if the object has no filter."""
        names = filter_array_names(self.current_mesh) if self.current_mesh is not None else []
        threshold = mesh_entry.get('threshold') if isinstance(mesh_entry, dict) else None
        self.filter_array_combo.blockSignals(True)
        self.filter_array_combo.clear()
        self.filter_array_combo.addItems(names)
        self.filter_array_combo.blockSignals(False)
        self.filter_group.setEnabled(bool(names))
        if threshold and threshold.get('scalars') in names:
            self.filter_array_combo.blockSignals(True)
            self.filter_array_combo.setCurrentText(threshold['scalars'])
            self.filter_array_combo.blockSignals(False)
            self._set_filter_range_to_data(threshold['scalars'])
            if 'min' in threshold:
                self.filter_min.setValue(float(threshold['min']))
                self.filter_max.setValue(float(threshold['max']))
            self.filter_invert_checkbox.setChecked(bool(threshold.get('invert', False)))
            self._update_filter_mode(threshold['scalars'], threshold)
        elif names:
            # the unit ids of a block model or cross section are the most
            # likely array to filter on
            if 'cell:stratigraphy' in names:
                self.filter_array_combo.setCurrentText('cell:stratigraphy')
            elif 'stratigraphy' in names:
                self.filter_array_combo.setCurrentText('stratigraphy')
            self._set_filter_range_to_data(self.filter_array_combo.currentText())
            self.filter_invert_checkbox.setChecked(False)
            self._update_filter_mode(self.filter_array_combo.currentText(), None)
        self._update_filter_status()

    def _on_filter_array_changed(self, array_name: str):
        if array_name:
            self._set_filter_range_to_data(array_name)
            entry = self.viewer.meshes.get(self.current_object_name) if self.viewer else None
            threshold = entry.get('threshold') if entry else None
            self._update_filter_mode(array_name, threshold)

    @staticmethod
    def _is_unit_array(array_name: str) -> bool:
        return array_name.split(':', 1)[-1] == 'stratigraphy'

    def _update_filter_mode(self, array_name: str, threshold):
        """Show unit check boxes for a unit id array, and the range controls
        for any other array."""
        unit_mode = self._is_unit_array(array_name)
        self.filter_range_widget.setVisible(not unit_mode)
        self.filter_apply_button.setVisible(not unit_mode)
        self.filter_units_widget.setVisible(unit_mode)
        if unit_mode:
            self._populate_unit_list(array_name, threshold)

    def _populate_unit_list(self, array_name: str, threshold):
        """Fill the unit check boxes with the units that are in the array.

        The unit names and colours come from the object's metadata (stored
        when the object was coloured by the stratigraphic column), indexed
        by unit id.
        """
        from matplotlib.colors import to_hex

        entry = self.viewer.meshes.get(self.current_object_name, {}) if self.viewer else {}
        metadata = entry.get('metadata') or {}
        names = metadata.get('unit_names') or []
        colours = metadata.get('unit_colours') or []
        values = self._get_scalar_values(array_name)
        ids = [int(v) for v in np.unique(values)] if values is not None else []
        checked = None
        if threshold and threshold.get('scalars') == array_name and 'values' in threshold:
            checked = {int(v) for v in threshold['values']}

        self.filter_units_list.blockSignals(True)
        self.filter_units_list.clear()
        for unit_id in ids:
            if 0 <= unit_id < len(names):
                label = str(names[unit_id])
            elif unit_id < 0:
                label = "Outside all units"
            else:
                label = f"Unit {unit_id}"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, unit_id)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(
                Qt.Checked if checked is None or unit_id in checked else Qt.Unchecked
            )
            if 0 <= unit_id < len(colours):
                try:
                    swatch = QPixmap(12, 12)
                    swatch.fill(QColor(to_hex(colours[unit_id])))
                    item.setIcon(QIcon(swatch))
                except Exception:
                    pass
            self.filter_units_list.addItem(item)
        self.filter_units_list.blockSignals(False)

    def _checked_unit_ids(self):
        ids, total = [], self.filter_units_list.count()
        for i in range(total):
            item = self.filter_units_list.item(i)
            if item.checkState() == Qt.Checked:
                ids.append(int(item.data(Qt.UserRole)))
        return ids, total

    def _on_unit_check_changed(self, _item=None):
        ids, total = self._checked_unit_ids()
        if not ids:
            # an object with no cells cannot be shown; keep the last filter
            self.filter_status_label.setText("Check at least one unit to show")
            return
        if len(ids) == total:
            self._set_threshold(None)
        else:
            self._set_threshold({'scalars': self.filter_array_combo.currentText(), 'values': ids})

    def _set_all_units_checked(self, checked: bool):
        self.filter_units_list.blockSignals(True)
        for i in range(self.filter_units_list.count()):
            self.filter_units_list.item(i).setCheckState(Qt.Checked if checked else Qt.Unchecked)
        self.filter_units_list.blockSignals(False)
        self._on_unit_check_changed()

    def _set_filter_range_to_data(self, array_name: str):
        """Set the filter range to the full range of values of the array."""
        values = self._get_scalar_values(array_name)
        if values is None:
            return
        values = np.asarray(values)
        finite = values[np.isfinite(values)] if values.dtype.kind == 'f' else values
        if finite.size == 0:
            return
        low, high = float(finite.min()), float(finite.max())
        # show integer arrays (e.g. unit ids) without decimals
        integer = values.dtype.kind in 'iub'
        for box in (self.filter_min, self.filter_max):
            box.setDecimals(0 if integer else 4)
            box.setSingleStep(1.0 if integer else max((high - low) / 100.0, 1e-4))
        self.filter_min.setValue(low)
        self.filter_max.setValue(high)

    def apply_filter(self):
        array_name = self.filter_array_combo.currentText()
        if not array_name:
            return
        self._set_threshold(
            {
                'scalars': array_name,
                'min': self.filter_min.value(),
                'max': self.filter_max.value(),
                'invert': self.filter_invert_checkbox.isChecked(),
            }
        )

    def clear_filter(self):
        self._set_threshold(None)
        if self.filter_units_list.count():
            self.filter_units_list.blockSignals(True)
            for i in range(self.filter_units_list.count()):
                self.filter_units_list.item(i).setCheckState(Qt.Checked)
            self.filter_units_list.blockSignals(False)

    def _set_threshold(self, threshold):
        name = self.current_object_name
        if not name or self.viewer is None or name not in self.viewer.meshes:
            return
        try:
            self.viewer.replace_mesh_object(name, threshold=threshold)
        except Exception as e:
            QMessageBox.warning(self, "Filter", f"Cannot apply the filter:\n{e}")
            return
        try:
            self.viewer.render()
        except Exception:
            pass
        self._update_filter_status()

    def _update_filter_status(self):
        entry = self.viewer.meshes.get(self.current_object_name) if self.viewer else None
        if not entry or not entry.get('threshold'):
            self.filter_status_label.setText("No filter")
            return
        total = getattr(entry.get('mesh'), 'n_cells', 0)
        shown = getattr(entry.get('display_mesh'), 'n_cells', 0)
        self.filter_status_label.setText(f"Showing {shown} of {total} cells")

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
                    self.viewer.meshes[self.current_object_name].set(
                        'kwargs',
                        {
                            **self.viewer.meshes[self.current_object_name].get('kwargs', {}),
                            'scalars': None,
                        },
                    )
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

        source = self.viewer.get_source_metadata(self.current_object_name)
        try:
            self.viewer.remove_object(self.current_object_name)
        except Exception:
            pass

        try:
            self.viewer.add_mesh_object(
                mesh,
                name=self.current_object_name,
                scalars=scalars,
                cmap=cmap,
                clim=clim,
                opacity=opacity,
                show_scalar_bar=show_scalar_bar,
                **source,
            )
            self.current_mesh = self.viewer.meshes.get(self.current_object_name, {}).get('mesh')
        except Exception:
            try:
                self.viewer.add_mesh_object(mesh, name=self.current_object_name, **source)
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

            if self.current_object_name and self.current_object_name in getattr(
                self.viewer, 'meshes', {}
            ):
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
                        color = self.viewer.meshes[self.current_object_name].get(
                            'color'
                        ) or stored.get('color')
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
        Best-effort: try in-place application via _apply_scalar_to_actor, otherwise remove and re-add the mesh with the new cmap.
        """
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

            source = self.viewer.get_source_metadata(self.current_object_name)
            try:
                self.viewer.remove_object(self.current_object_name)
            except Exception:
                pass

            try:
                self.viewer.add_mesh_object(
                    mesh,
                    name=self.current_object_name,
                    scalars=scalars,
                    cmap=cmap or None,
                    clim=clim,
                    opacity=opacity,
                    show_scalar_bar=show_scalar_bar,
                    **source,
                )
                self.current_mesh = self.viewer.meshes.get(self.current_object_name, {}).get('mesh')
            except Exception:
                try:
                    self.viewer.add_mesh_object(mesh, name=self.current_object_name, **source)
                    self.current_mesh = self.viewer.meshes.get(self.current_object_name, {}).get(
                        'mesh'
                    )
                except Exception:
                    pass
        except Exception:
            pass

    def _get_scalar_values(self, scalar_name: str):
        return get_scalar_values(self.current_mesh, scalar_name)

    def _update_histogram(self, values):
        try:
            render_histogram(self.hist_ax, values)
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
                    plotter.update_scalars(
                        values,
                        mesh=mesh_entry.get('mesh'),
                        render=False,
                        name=self.current_object_name,
                    )
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

                        arr = _np.asarray(values, dtype=float) if values is not None else None
                        finite = arr[_np.isfinite(arr)] if arr is not None else None
                        if finite is not None and finite.size > 0:
                            mn = float(_np.min(finite))
                            mx = float(_np.max(finite))
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
            apply_colormap_lut(mapper, cmap, clim)

            # persist kwargs
            try:
                kwargs = mesh_entry.get('kwargs', {}) if isinstance(mesh_entry, dict) else {}
                kwargs['scalars'] = scalars
                kwargs['cmap'] = cmap or None
                if clim is not None:
                    kwargs['clim'] = (float(clim[0]), float(clim[1]))
                mesh_entry['kwargs'] = kwargs
                if (
                    hasattr(self.viewer, 'meshes')
                    and self.current_object_name in self.viewer.meshes
                ):
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
        scalars = scalar_name
        if scalar_name.startswith('cell:'):
            scalars = scalar_name.split(':', 1)[1]

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
