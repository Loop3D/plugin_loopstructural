import matplotlib.pyplot as plt
import numpy as np

# Add plotting imports for scalar histogram
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from qgis.PyQt.QtCore import Qt, pyqtSignal
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
    """The properties of the selected viewer object.

    The widget reads and changes the object only through `viewer.registry`.
    Which controls it shows depends on the source type of the object (see
    `_update_visible_controls`).
    """

    # (object name, new value): the owner builds the isosurface again
    isovalueChangeRequested = pyqtSignal(str, float)

    def __init__(self, parent=None, *, viewer=None):
        super().__init__(parent)
        layout = QVBoxLayout()
        # Keep widgets close together and provide padding at the bottom
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 20)

        # Title / currently selected object
        self.title_label = QLabel("No object selected")
        self.title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.title_label)

        # Isosurface value (only for isosurfaces of a model feature)
        self.isovalue_group = QGroupBox("Isosurface")
        isovalue_layout = QHBoxLayout(self.isovalue_group)
        isovalue_layout.addWidget(QLabel("Value:"))
        self.isovalue_spinbox = QDoubleSpinBox()
        self.isovalue_spinbox.setRange(-1e12, 1e12)
        self.isovalue_spinbox.setDecimals(4)
        self.isovalue_spinbox.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        isovalue_layout.addWidget(self.isovalue_spinbox)
        self.isovalue_apply_button = QPushButton("Apply")
        self.isovalue_apply_button.clicked.connect(self._on_isovalue_apply)
        isovalue_layout.addWidget(self.isovalue_apply_button)
        self.isovalue_group.setVisible(False)
        layout.addWidget(self.isovalue_group)

        # Scalar selection
        self.scalar_label = QLabel("Active Scalar:")
        layout.addWidget(self.scalar_label)
        self.scalar_combo = QComboBox()
        self.scalar_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.scalar_combo.currentTextChanged.connect(self._on_scalar_changed)
        layout.addWidget(self.scalar_combo)

        # Color with Scalar checkbox
        self.color_with_scalar_checkbox = QCheckBox("Color with Scalar")
        self.color_with_scalar_checkbox.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )
        self.color_with_scalar_checkbox.toggled.connect(self._on_color_with_scalar_toggled)
        layout.addWidget(self.color_with_scalar_checkbox)

        # Scalar Bar
        self.scalar_bar_checkbox = QCheckBox("Show Scalar Bar")
        self.scalar_bar_checkbox.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )
        layout.addWidget(self.scalar_bar_checkbox)

        # Colormap
        self.colormap_label = QLabel("Colormap:")
        layout.addWidget(self.colormap_label)
        self.colormap_combo = QComboBox()
        self.colormap_combo.addItems(["viridis", "plasma", "inferno", "magma", "greys"])
        self.colormap_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        # apply colormap changes when user selects a different cmap
        self.colormap_combo.currentTextChanged.connect(self._on_colormap_changed)
        layout.addWidget(self.colormap_combo)

        # Opacity
        layout.addWidget(QLabel("Opacity:"))
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(0, 100)
        self.opacity_slider.setValue(100)
        self.opacity_slider.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.opacity_slider.valueChanged.connect(lambda val: self.set_opacity(val / 100.0))
        layout.addWidget(self.opacity_slider)

        # Show Edges
        self.show_edges_checkbox = QCheckBox("Show Edges")
        self.show_edges_checkbox.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )
        # call set_show_edges when toggled
        self.show_edges_checkbox.toggled.connect(self.set_show_edges)
        layout.addWidget(self.show_edges_checkbox)

        # Line Width
        layout.addWidget(QLabel("Line Width:"))
        self.line_width_slider = QSlider(Qt.Orientation.Horizontal)
        # allow 0..20, interpreted as float line width
        self.line_width_slider.setRange(0, 20)
        self.line_width_slider.setValue(1)
        self.line_width_slider.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.line_width_slider.valueChanged.connect(lambda val: self.set_line_width(val))
        layout.addWidget(self.line_width_slider)

        # Colormap Range
        range_layout = QHBoxLayout()
        range_layout.setSpacing(6)
        self.range_label = QLabel("Colormap Range:")
        range_layout.addWidget(self.range_label)
        self.range_min = QLineEdit()
        self.range_min.setPlaceholderText("Min")
        self.range_min.setMaximumWidth(120)
        self.range_min.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.range_max = QLineEdit()
        self.range_max.setPlaceholderText("Max")
        self.range_max.setMaximumWidth(120)
        self.range_max.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        range_layout.addWidget(self.range_min)
        range_layout.addWidget(self.range_max)
        layout.addLayout(range_layout)

        # Scalar Histogram (matplotlib canvas)
        self.hist_label = QLabel("Scalar Histogram:")
        layout.addWidget(self.hist_label)
        self.hist_fig = plt.Figure(figsize=(4, 2))
        self.hist_canvas = FigureCanvas(self.hist_fig)
        self.hist_ax = self.hist_fig.subplots()
        self.hist_canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.hist_canvas)

        # Filter: show only the part of the object whose values are in a
        # range, or (for the unit ids of a block model, cross section or
        # topography) only the units that are checked
        self.filter_group = QGroupBox("Filter (Threshold)")
        filter_layout = QVBoxLayout(self.filter_group)
        filter_layout.addWidget(QLabel("Array:"))
        self.filter_array_combo = QComboBox()
        self.filter_array_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
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
            box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
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
        self.color_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
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

    # -- the selected object ---------------------------------------------

    def _object(self):
        """The selected object in the registry of the viewer, or None."""
        if self.viewer is None:
            return None
        return self.viewer.registry.get(self.current_object_name)

    def _render(self):
        if self.viewer is None:
            return
        try:
            self.viewer.render()
        except Exception:
            pass

    def _actor_prop(self):
        """The property of the actor of the selected object, or None."""
        obj = self._object()
        return getattr(obj.actor, 'prop', None) if obj else None

    def choose_color(self):
        color = QColorDialog.getColor()
        if not color.isValid():
            return
        self.color_button.setStyleSheet(f"background-color: {color.name()}")
        obj = self._object()
        if obj is None:
            return
        rgb = (color.redF(), color.greenF(), color.blueF())
        prop = self._actor_prop()
        if prop is not None:
            try:
                prop.color = rgb
            except Exception:
                pass
        obj.color = rgb
        self._render()

    def set_opacity(self, value: float):
        obj = self._object()
        if obj is None:
            return
        prop = self._actor_prop()
        if prop is not None:
            try:
                prop.opacity = value
            except Exception:
                pass
        obj.update_kwargs(opacity=value)
        self._render()

    def set_show_edges(self, show: bool):
        """Enable or disable edge display for the current object."""
        obj = self._object()
        if obj is None:
            return
        prop = self._actor_prop()
        if prop is not None:
            try:
                prop.edge_visibility = bool(show)
            except Exception:
                pass
        obj.update_kwargs(show_edges=bool(show))
        self._render()

    def set_line_width(self, value):
        """Set the line width for edge rendering. Value is an integer slider value; interpreted as float width."""
        obj = self._object()
        if obj is None:
            return
        width = float(value)
        prop = self._actor_prop()
        if prop is not None:
            try:
                prop.line_width = width
            except Exception:
                pass
        obj.update_kwargs(line_width=width)
        self._render()

    def setCurrentObject(self, object_name: str):
        self.current_object_name = object_name
        obj = self._object()
        if obj is None:
            self.current_mesh = None
            self.title_label.setText(f"Object: {object_name} (not found)")
            self._update_histogram(None)
            return
        self.current_mesh = obj.mesh
        self.title_label.setText(f"Object: {object_name}")

        self._populate_scalar_combo(obj)
        self._show_data_range()
        self._restore_display_state(obj)

        # update histogram display
        vals = self._get_scalar_values(self.scalar_combo.currentText())
        self._update_histogram(vals if self.color_with_scalar_checkbox.isChecked() else None)

        self._load_filter_state(obj)
        self._update_visible_controls(obj)

    def _populate_scalar_combo(self, obj):
        """List the arrays of the mesh, and select the one that is used."""
        self.scalar_combo.blockSignals(True)
        self.scalar_combo.clear()
        pdata = getattr(self.current_mesh, 'point_data', None) or {}
        cdata = getattr(self.current_mesh, 'cell_data', None) or {}
        for k in sorted(pdata.keys()):
            self.scalar_combo.addItem(k)
        for k in sorted(cdata.keys()):
            self.scalar_combo.addItem(f"cell:{k}")
        used = obj.kwargs.get('scalars')
        if used:
            idx = self.scalar_combo.findText(used)
            if idx < 0:
                idx = self.scalar_combo.findText(f"cell:{used}")
            if idx >= 0:
                self.scalar_combo.setCurrentIndex(idx)
        self.scalar_combo.blockSignals(False)

    def _show_data_range(self):
        """Show the range of values of the first array in the colormap range."""
        self.range_min.clear()
        self.range_max.clear()
        mesh = self.current_mesh
        if mesh is None:
            return
        pdata = getattr(mesh, 'point_data', None) or {}
        cdata = getattr(mesh, 'cell_data', None) or {}
        values = None
        if len(pdata.keys()) > 0:
            values = next(iter(pdata.values()))
        elif len(cdata.keys()) > 0:
            values = next(iter(cdata.values()))
        if values is None:
            return
        try:
            arr = np.asarray(values, dtype=float)
        except (TypeError, ValueError):
            return
        finite = arr[np.isfinite(arr)]
        if finite.size > 0:
            self.range_min.setText(str(float(finite.min())))
            self.range_max.setText(str(float(finite.max())))

    def _restore_display_state(self, obj):
        """Set the controls from the stored settings, or from the actor."""
        mapper = getattr(obj.actor, 'mapper', None)
        self.scalar_bar_checkbox.setChecked(bool(getattr(mapper, 'scalar_visibility', False)))

        prop = self._actor_prop()
        show_edges = obj.kwargs.get('show_edges')
        if show_edges is None:
            show_edges = bool(getattr(prop, 'edge_visibility', False))
        line_width = obj.kwargs.get('line_width')
        if line_width is None:
            line_width = getattr(prop, 'line_width', 1.0)
        self.show_edges_checkbox.blockSignals(True)
        self.show_edges_checkbox.setChecked(bool(show_edges))
        self.show_edges_checkbox.blockSignals(False)
        self.line_width_slider.blockSignals(True)
        self.line_width_slider.setValue(int(round(float(line_width))))
        self.line_width_slider.blockSignals(False)

        color_with_scalar = bool(obj.kwargs.get('scalars') or obj.kwargs.get('cmap'))
        self.color_with_scalar_checkbox.blockSignals(True)
        self.color_with_scalar_checkbox.setChecked(color_with_scalar)
        self.color_with_scalar_checkbox.blockSignals(False)
        self._on_color_with_scalar_toggled(color_with_scalar)

        self.isovalue_spinbox.setValue(float(obj.isovalue) if obj.isovalue is not None else 0.0)

    def _update_visible_controls(self, obj):
        """Show the controls that fit the source type of the object.

        - The value control is for an isosurface of a model feature only.
        - The scalar controls need at least one array on the mesh.
        - The filter needs an array to filter on.
        """
        self.isovalue_group.setVisible(obj.is_isosurface)
        has_arrays = self.scalar_combo.count() > 0
        for widget in (
            self.scalar_label,
            self.scalar_combo,
            self.color_with_scalar_checkbox,
            self.scalar_bar_checkbox,
            self.colormap_label,
            self.colormap_combo,
            self.range_label,
            self.range_min,
            self.range_max,
            self.hist_label,
        ):
            widget.setVisible(has_arrays)
        self.hist_canvas.setVisible(has_arrays and self.color_with_scalar_checkbox.isChecked())
        self.filter_group.setVisible(self.filter_array_combo.count() > 0)

    def _on_isovalue_apply(self):
        obj = self._object()
        if obj is None or not obj.is_isosurface:
            return
        value = self.isovalue_spinbox.value()
        if obj.isovalue is not None and np.isclose(value, obj.isovalue):
            return
        self.isovalueChangeRequested.emit(obj.name, float(value))

    def _load_filter_state(self, obj):
        """Show the filter of the current object, or the full value range
        of an array if the object has no filter."""
        names = filter_array_names(self.current_mesh) if self.current_mesh is not None else []
        threshold = obj.threshold
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
            obj = self._object()
            threshold = obj.threshold if obj else None
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

        obj = self._object()
        metadata = obj.metadata if obj else {}
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
            item.setData(Qt.ItemDataRole.UserRole, unit_id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked
                if checked is None or unit_id in checked
                else Qt.CheckState.Unchecked
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
            if item.checkState() == Qt.CheckState.Checked:
                ids.append(int(item.data(Qt.ItemDataRole.UserRole)))
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
            self.filter_units_list.item(i).setCheckState(
                Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
            )
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
                self.filter_units_list.item(i).setCheckState(Qt.CheckState.Checked)
            self.filter_units_list.blockSignals(False)

    def _set_threshold(self, threshold):
        name = self.current_object_name
        if self._object() is None:
            return
        try:
            self.viewer.replace_mesh_object(name, threshold=threshold)
        except Exception as e:
            QMessageBox.warning(self, "Filter", f"Cannot apply the filter:\n{e}")
            return
        self._render()
        self._update_filter_status()

    def _update_filter_status(self):
        obj = self._object()
        if obj is None or not obj.threshold:
            self.filter_status_label.setText("No filter")
            return
        total = getattr(obj.mesh, 'n_cells', 0)
        shown = getattr(obj.display_mesh, 'n_cells', 0)
        self.filter_status_label.setText(f"Showing {shown} of {total} cells")

    @staticmethod
    def _array_name(scalar_name: str):
        """The array name of a combo box entry, or None for no array."""
        if not scalar_name or scalar_name == "<none>":
            return None
        return scalar_name.split(':', 1)[1] if scalar_name.startswith('cell:') else scalar_name

    def _colormap_range(self):
        """The colormap range from the two text boxes, or None."""
        try:
            if self.range_min.text() and self.range_max.text():
                return (float(self.range_min.text()), float(self.range_max.text()))
        except ValueError:
            pass
        return None

    def _on_scalar_changed(self, scalar_name: str):
        vals = self._get_scalar_values(scalar_name)
        self._update_histogram(vals if self.color_with_scalar_checkbox.isChecked() else None)
        obj = self._object()
        if obj is None:
            return

        # if not coloring by scalar, only update metadata
        if not self.color_with_scalar_checkbox.isChecked():
            obj.update_kwargs(scalars=None)
            return
        self._color_by_array(obj, scalar_name, self.colormap_combo.currentText() or None)

    def _color_by_array(self, obj, scalar_name: str, cmap):
        """Colour the object with an array: try an in-place update of the
        actor, and add the object again if that fails."""
        try:
            self._apply_scalar_to_actor(obj, scalar_name)
            return
        except Exception:
            pass
        scalars = self._array_name(scalar_name)
        source = self.viewer.get_source_metadata(obj.name)
        old_kwargs = dict(obj.kwargs)
        self.viewer.remove_object(obj.name)
        try:
            self.viewer.add_mesh_object(
                obj.mesh,
                name=obj.name,
                scalars=scalars,
                cmap=cmap,
                clim=self._colormap_range(),
                opacity=old_kwargs.get('opacity'),
                show_scalar_bar=self.scalar_bar_checkbox.isChecked(),
                **source,
            )
        except Exception:
            self.viewer.add_mesh_object(obj.mesh, name=obj.name, **source)
        new_obj = self._object()
        self.current_mesh = new_obj.mesh if new_obj else None

    def _on_color_with_scalar_toggled(self, checked: bool):
        self.scalar_combo.setEnabled(checked)
        self.colormap_combo.setEnabled(checked)
        self.range_min.setEnabled(checked)
        self.range_max.setEnabled(checked)
        self.scalar_bar_checkbox.setEnabled(checked)
        self.color_button.setEnabled(not checked)
        self.hist_canvas.setVisible(checked and self.scalar_combo.count() > 0)

        obj = self._object()
        if obj is None:
            return
        if checked:
            try:
                self._apply_scalar_to_actor(obj, self.scalar_combo.currentText())
            except Exception:
                pass
            return
        mapper = getattr(obj.actor, 'mapper', None)
        if mapper is not None:
            try:
                mapper.scalar_visibility = False
            except Exception:
                pass
        color = obj.color or obj.kwargs.get('color')
        prop = self._actor_prop()
        if color is not None and prop is not None:
            try:
                prop.color = color
            except Exception:
                pass
        self._render()

    def _on_colormap_changed(self, cmap: str):
        """Apply or persist selected colormap for the current object."""
        obj = self._object()
        if obj is None:
            return
        # persist cmap in metadata even when not coloring by scalar
        obj.update_kwargs(cmap=cmap or None)
        # only need to change rendering if we're coloring by scalar
        if not self.color_with_scalar_checkbox.isChecked():
            return
        scalar_name = self.scalar_combo.currentText()
        if self._array_name(scalar_name) is None:
            return
        self._color_by_array(obj, scalar_name, cmap or None)

    def _get_scalar_values(self, scalar_name: str):
        return get_scalar_values(self.current_mesh, scalar_name)

    def _update_histogram(self, values):
        try:
            render_histogram(self.hist_ax, values)
            self.hist_canvas.draw_idle()
        except Exception:
            pass

    def _apply_scalar_to_actor(self, obj, scalar_name: str):
        """Colour the actor of an object with an array, without adding the
        object again. Raises if the array is not on the mesh."""
        scalars = self._array_name(scalar_name)
        if scalars is None:
            # no array: switch the mapping off
            mapper = getattr(obj.actor, 'mapper', None)
            if mapper is not None:
                mapper.scalar_visibility = False
            obj.update_kwargs(scalars=None)
            return

        values = self._get_scalar_values(scalar_name)
        if values is None:
            raise RuntimeError('Failed to retrieve scalar values')
        self._update_actor_mapper(
            obj,
            scalars,
            self.colormap_combo.currentText() or None,
            self._colormap_range(),
            values,
        )

    def _update_actor_mapper(self, obj, scalars, cmap, clim, values):
        """Select the array, set the scalar range, assign a LUT from a
        matplotlib colormap, and store the settings."""
        mapper = getattr(obj.actor, 'mapper', None)
        if mapper is None:
            return
        mapper.SelectColorArray(scalars)
        mapper.scalar_visibility = True
        if clim:
            low, high = float(clim[0]), float(clim[1])
        else:
            finite = np.asarray(values, dtype=float)
            finite = finite[np.isfinite(finite)]
            low, high = (float(finite.min()), float(finite.max())) if finite.size else (None, None)
        if low is not None:
            mapper.SetScalarRange(low, high)
        apply_colormap_lut(mapper, cmap, clim)

        settings = {'scalars': scalars, 'cmap': cmap or None}
        if clim is not None:
            settings['clim'] = (float(clim[0]), float(clim[1]))
        obj.update_kwargs(**settings)
        self._render()
