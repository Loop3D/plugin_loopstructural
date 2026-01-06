import os

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtSvg import QGraphicsSvgItem


class TopologyNode(QtWidgets.QGraphicsItem):
    def __init__(self, name, scene: 'TopologyScene', node_type="fault"):
        super().__init__()
        self.name = name
        self.scene_ref = scene  # reference to scene
        self.node_type = node_type
        self.edges = []

        # Set shape based on node type
        if node_type == "fault":
            self.shape_item = QGraphicsSvgItem(os.path.join(os.path.dirname(__file__), "fault.svg"))
        elif node_type == "stratigraphy":
            self.shape_item = QGraphicsSvgItem(
                os.path.join(os.path.dirname(__file__), "stratigraphy.svg")
            )
        elif node_type == "unconformity":
            self.shape_item = QGraphicsSvgItem(
                os.path.join(os.path.dirname(__file__), "unconformity.svg")
            )

        self.shape_item.setParentItem(self)
        self.shape_item.setScale(0.5)  # Adjust scale if needed
        # Enable interactivity for the node and allow geometry-change notifications
        self.setFlags(
            QtWidgets.QGraphicsItem.ItemIsMovable
            | QtWidgets.QGraphicsItem.ItemIsSelectable
            | QtWidgets.QGraphicsItem.ItemSendsGeometryChanges
        )

        self.label = QtWidgets.QGraphicsTextItem(name, self)
        self.label.setDefaultTextColor(QtCore.Qt.black)
        self.label.setPos(-self.label.boundingRect().width() / 2, -30)
        self.shape_item.setAcceptedMouseButtons(QtCore.Qt.NoButton)

        # Drag state for moving multiple selected nodes
        self._dragging = False
        self._drag_origin = None
        self._drag_start_positions = {}
        self._drag_start_scene_rects = {}
        # View-related state used during dragging
        self._drag_view = None
        self._prev_viewport_mode = None

    def boundingRect(self):
        """Return a bounding rectangle that includes the shape, the label and
        any selection outline we draw in paint(). We must return a rect that
        fully contains what paint() draws so Qt can correctly refresh the
        area when the item changes.
        """
        shape_rect = self.shape_item.boundingRect()
        label_rect = self.label.boundingRect()
        combined_rect = shape_rect.united(
            label_rect.translated(0, -30)
        )  # Adjust for label position
        # Expand by the same margin used when drawing the selection outline
        margin = 8
        return combined_rect.adjusted(-margin, -margin, margin, margin)

    def mousePressEvent(self, event):
        # Support interactive edge creation: Shift + Left-Click starts/finishes a connection
        if event.button() == QtCore.Qt.LeftButton and (event.modifiers() & QtCore.Qt.ShiftModifier):
            scene = self.scene()
            # If no connection in progress, start one from this node
            if scene.connecting_from is None:
                scene.connecting_from = self
                # Start a temporary visual line
                scene.start_temporary_line(self)
            elif scene.connecting_from == self:
                # Cancel the connection
                scene.connecting_from = None
                scene.remove_temporary_line()
            else:
                # Create an edge between the nodes
                scene.add_edge_between(scene.connecting_from, self)
                scene.connecting_from = None
                scene.remove_temporary_line()
            return

        # Preserve existing selection when clicking a member of a multi-selection.
        # If the clicked item was part of the selection before the press, the
        # default QGraphicsItem behavior can clear other selected items. To
        # support dragging a group without losing selection, capture the set of
        # selected items before calling the base implementation and restore them
        # afterwards when appropriate.
        if event.button() == QtCore.Qt.LeftButton:
            scene = self.scene()
            prev_selected = set(scene.selectedItems()) if scene is not None else set()
            was_selected = self in prev_selected

            # Let the default implementation handle selection/toggle semantics
            super().mousePressEvent(event)

            # If the item was already selected before the press, restore the
            # previous selection so multi-selection is preserved for dragging.
            if was_selected:
                for item in prev_selected:
                    try:
                        item.setSelected(True)
                    except Exception:
                        pass

            # If this item is selected, prepare for a possible group drag
            if self.isSelected():
                self._dragging = True
                self._drag_origin = event.scenePos()
                # store start positions for all selected TopologyNode items
                self._drag_start_positions = {}
                self._drag_start_scene_rects = {}
                # caching and view-mode state
                self._drag_view = None
                self._prev_viewport_mode = None

                for item in self.scene().selectedItems():
                    if isinstance(item, TopologyNode):
                        self._drag_start_positions[item] = item.pos()
                        # store the scene bounding rect at the start so we can update
                        # both old and new areas during dragging to avoid trails
                        try:
                            self._drag_start_scene_rects[item] = item.sceneBoundingRect()
                        except Exception:
                            # fallback: compute from pos + boundingRect
                            br = item.boundingRect()
                            self._drag_start_scene_rects[item] = QtCore.QRectF(
                                item.pos(), br.size()
                            )

                # Switch view to full-viewport updates for the duration of the drag
                try:
                    views = self.scene().views()
                    if views:
                        self._drag_view = views[0]
                        # store previous mode if view is valid
                        if self._drag_view is not None:
                            self._prev_viewport_mode = self._drag_view.viewportUpdateMode()
                            self._drag_view.setViewportUpdateMode(
                                QtWidgets.QGraphicsView.FullViewportUpdate
                            )
                except Exception:
                    self._drag_view = None
                    self._prev_viewport_mode = None

                # Enable device-coordinate caching on moved items to avoid redraw trails
                for item in list(self._drag_start_positions.keys()):
                    try:
                        item.setCacheMode(QtWidgets.QGraphicsItem.DeviceCoordinateCache)
                    except Exception:
                        pass
            return

        # Fallback to default behavior for other buttons
        super().mousePressEvent(event)  

    def mouseMoveEvent(self, event):
        # If we're dragging a selection, move all selected nodes together
        if self._dragging and (event.buttons() & QtCore.Qt.LeftButton):
            if self._drag_origin is None:
                return
            delta = event.scenePos() - self._drag_origin
            scene = self.scene()
            for item, start_pos in self._drag_start_positions.items():
                old_scene_rect = self._drag_start_scene_rects.get(item, item.sceneBoundingRect())
                new_scene_rect = old_scene_rect.translated(delta)

                # Move the item to the new position
                item.setPos(start_pos + delta)

                # Force update of the union of old and new areas to avoid visual trails
                try:
                    scene.update(old_scene_rect.united(new_scene_rect))
                except Exception:
                    scene.update()

                # Ensure the item's visuals (including selection outline) are redrawn
                item.update()

                # Update connected edges
                for edge in item.edges:
                    edge.update_position()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._dragging and event.button() == QtCore.Qt.LeftButton:
            self._dragging = False
            self._drag_origin = None
            # disable caching and restore view update mode
            for item in list(self._drag_start_positions.keys()):
                try:
                    item.setCacheMode(QtWidgets.QGraphicsItem.NoCache)
                    item.update()
                except Exception:
                    pass
            if self._drag_view is not None and self._prev_viewport_mode is not None:
                try:
                    self._drag_view.setViewportUpdateMode(self._prev_viewport_mode)
                except Exception:
                    pass
            self._drag_start_positions = {}
            self._drag_start_scene_rects = {}
            self._drag_view = None
            self._prev_viewport_mode = None
            return
        super().mouseReleaseEvent(event)

    def paint(self, painter, option, widget=None):
        """Draw a selection highlight when selected. The SVG child handles the main rendering."""
        if self.isSelected():
            pen = QtGui.QPen(QtGui.QColor(0, 120, 215))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.setBrush(QtCore.Qt.NoBrush)
            rect = self.boundingRect()
            # Slightly expand rect for a nicer outline
            outline_rect = rect.adjusted(-6, -6, 6, 6)
            painter.drawRoundedRect(outline_rect, 6, 6)

    def add_edge(self, edge):
        self.edges.append(edge)

    def itemChange(self, change, value):
        # Update connected edges when position is changing or has changed
        if change in (
            QtWidgets.QGraphicsItem.ItemPositionChange,
            QtWidgets.QGraphicsItem.ItemPositionHasChanged,
        ):
            for edge in self.edges:
                edge.update_position()
            # Make sure the highlight redraws in the new position
            self.update()

        # Redraw when selection state changes so highlight updates
        if (
            change == QtWidgets.QGraphicsItem.ItemSelectedChange
            or change == QtWidgets.QGraphicsItem.ItemSelectedHasChanged
        ):
            self.update()

        return super().itemChange(change, value)

    def mouseDoubleClickEvent(self, event):
        """Open a simple dialog to edit the node name for fault nodes.

        Uses QInputDialog.getText to prompt for a new name. Updates the
        node's label and the scene's nodes dictionary safely (removing the
        old key and inserting the new one) so other logic that depends on
        node names keeps working.
        """
        # Only open the dialog for left-button double-clicks and fault nodes
        if event.button() == QtCore.Qt.LeftButton and self.node_type == "fault":
            # Use a simple input dialog for editing the name
            new_name, ok = QtWidgets.QInputDialog.getText(
                None, "Edit Fault", "Fault name:", QtWidgets.QLineEdit.Normal, self.name
            )
            if ok and new_name:
                new_name = str(new_name).strip()
                if new_name and new_name != self.name:
                    # Update scene registry safely
                    try:
                        if self.name in self.scene_ref.nodes:
                            del self.scene_ref.nodes[self.name]
                    except Exception:
                        pass
                    self.name = new_name
                    self.label.setPlainText(self.name)
                    # Re-center label
                    self.label.setPos(-self.label.boundingRect().width() / 2, -30)
                    try:
                        self.scene_ref.nodes[self.name] = self
                    except Exception:
                        pass
            # Consume the event so default handlers don't also process it
            return

        # Fallback to default behavior for other node types or buttons
        super().mouseDoubleClickEvent(event)


class EdgeEditDialog(QtWidgets.QDialog):
    """Simple dialog to edit an edge's relation type and free-form properties.

    Properties are edited as plain text (JSON recommended). The dialog
    returns the chosen relation type and the properties text.
    """

    def __init__(self, parent=None, current_type="unspecified", current_props=""):
        super().__init__(parent)
        self.setWindowTitle("Edit Edge")
        self.setModal(True)
        layout = QtWidgets.QVBoxLayout(self)

        layout.addWidget(QtWidgets.QLabel("Relation type:"))
        self._combo = QtWidgets.QComboBox(self)
        # common relation types for topology graphs
        self._combo.addItems(
            [
                "unspecified",
                "stops on",
                "faults",
                "is above",
                "is below",
                "overlies",
                "contacts",
            ]
        )
        if current_type and current_type not in [
            self._combo.itemText(i) for i in range(self._combo.count())
        ]:
            self._combo.addItem(current_type)
        if current_type:
            self._combo.setCurrentText(current_type)
        layout.addWidget(self._combo)

        layout.addWidget(QtWidgets.QLabel("Properties (JSON or free text):"))
        self._props_edit = QtWidgets.QPlainTextEdit(self)
        self._props_edit.setPlainText(current_props)
        self._props_edit.setMinimumHeight(120)
        layout.addWidget(self._props_edit)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def getResult(self):
        return self._combo.currentText(), self._props_edit.toPlainText()


class TopologyEdge(QtWidgets.QGraphicsLineItem):
    def __init__(self, source, target):
        super().__init__()
        self.source = source
        self.target = target
        self.setPen(QtGui.QPen(QtCore.Qt.darkRed, 2))
        self.setFlags(
            QtWidgets.QGraphicsItem.ItemIsSelectable | QtWidgets.QGraphicsItem.ItemIsFocusable
        )
        self.setAcceptHoverEvents(True)

        # user-editable metadata
        self.relation_type = "unspecified"
        self.properties = {}

        self.source.add_edge(self)
        self.target.add_edge(self)
        self.update_position()

    def update_position(self):
        line = QtCore.QLineF(self.source.pos(), self.target.pos())
        self.setLine(line)

    def contextMenuEvent(self, event):
        menu = QtWidgets.QMenu()
        edit_action = menu.addAction("Edit Edge")
        delete_action = menu.addAction("Delete Edge")
        selected_action = menu.exec_(event.screenPos())

        if selected_action == edit_action:
            self.edit_edge()
        elif selected_action == delete_action:
            self.delete_edge()

    def edit_edge(self):
        QtWidgets.QMessageBox.information(
            None, "Edit", f"Editing relationship between {self.source.name} and {self.target.name}"
        )

    def delete_edge(self):
        # Remove from the scene
        self.source.edges.remove(self)
        self.target.edges.remove(self)
        # Remove from the scene's edge list
        if self in self.scene().edges:
            self.scene().edges.remove(self)

        self.scene().removeItem(self)

    def hoverEnterEvent(self, event):
        self.setPen(QtGui.QPen(QtCore.Qt.blue, 3))
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.setPen(QtGui.QPen(QtCore.Qt.darkRed, 2))
        super().hoverLeaveEvent(event)

    def mouseDoubleClickEvent(self, event):
        # Open the edit dialog when the edge is double-clicked
        if event.button() == QtCore.Qt.LeftButton:
            # Show current properties as pretty-printed JSON if possible
            current_props_text = ""
            try:
                import json

                if isinstance(self.properties, dict):
                    current_props_text = json.dumps(self.properties, indent=2)
                else:
                    current_props_text = str(self.properties)
            except Exception:
                current_props_text = str(self.properties)

            dlg = EdgeEditDialog(
                None,
                current_type=getattr(self, "relation_type", "unspecified"),
                current_props=current_props_text,
            )
            if dlg.exec_() == QtWidgets.QDialog.Accepted:
                rel_type, props_text = dlg.getResult()
                self.relation_type = rel_type
                # Try to interpret properties as JSON, otherwise store raw text
                try:
                    import json

                    parsed = json.loads(props_text) if props_text and props_text.strip() else {}
                    self.properties = parsed
                except Exception:
                    self.properties = {"text": props_text}

                # Update tooltip and visual style based on relation type
                try:
                    self.setToolTip(f"{self.relation_type}: {self.properties}")
                except Exception:
                    pass

                # Simple visual cue: change color for some types
                color = QtCore.Qt.darkRed
                rt = (self.relation_type or "").lower()
                if "stops" in rt or "above" in rt or "overlies" in rt:
                    color = QtCore.Qt.darkBlue
                elif "fault" in rt:
                    color = QtCore.Qt.darkRed
                else:
                    color = QtCore.Qt.darkGray

                self.setPen(QtGui.QPen(color, 2))
            return

        super().mouseDoubleClickEvent(event)


class TopologyScene(QtWidgets.QGraphicsScene):
    def __init__(self):
        super().__init__()
        self.setSceneRect(0, 0, 600, 400)
        self.nodes = {}
        self.edges = []
        self.connecting_from = None  # <-- store selected node for connecting
        self.temp_line = None  # Temporary line for visual feedback

        # Rubber-band selection state
        self._rubber_origin = None
        self._rubber_rect_item = None
        self._rubber_selecting = False

        # self._create_static_graph()
        self.finalize_layout()

    # def _create_static_graph(self):
    #     positions = {
    #         "fault_1": (100, 100),
    #         "fault_2": (200, 150),
    #         "fault_3": (100, 300),
    #         "fault_4": (300, 250),
    #         "fault_5": (400, 150),
    #     }

    #     for name, pos in positions.items():
    #         node = TopologyNode(name, self)
    #         self.addItem(node)
    #         node.setPos(*pos)
    #         self.nodes[name] = node

    # for src, tgt in edge_defs:
    #     self.add_edge_between(self.nodes[src], self.nodes[tgt])

    def finalize_layout(self):
        for edge in self.edges:
            edge.update_position()

    def add_edge_between(self, source, target):
        # Avoid duplicate edges
        print(f"Adding edge between {source.name} and {target.name}")
        if any(
            (e.source == source and e.target == target)
            or (e.source == target and e.target == source)
            for e in self.edges
        ):
            print(f"Edge already exists between {source.name} and {target.name}")
            return
        edge = TopologyEdge(source, target)
        self.addItem(edge)
        self.edges.append(edge)

    def mouseMoveEvent(self, event):
        # Update connecting temporary line if active
        if self.connecting_from and self.temp_line:
            # Update the temporary line to follow the cursor
            line = QtCore.QLineF(self.connecting_from.pos(), event.scenePos())
            self.temp_line.setLine(line)

        # Update rubber-band rectangle if we're selecting
        if self._rubber_selecting and self._rubber_rect_item is not None:
            rect = QtCore.QRectF(self._rubber_origin, event.scenePos()).normalized()
            self._rubber_rect_item.setRect(rect)
            return  # Don't pass to super while drawing rubber band

        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        # Start rubber-band selection when left-clicking empty space
        if event.button() == QtCore.Qt.LeftButton:
            if not self.itemAt(event.scenePos(), QtGui.QTransform()):
                # Optionally clear existing selection unless Ctrl is held
                if not (event.modifiers() & QtCore.Qt.ControlModifier):
                    for item in self.selectedItems():
                        item.setSelected(False)

                # Create the rubber-band rectangle
                self._rubber_origin = event.scenePos()
                self._rubber_rect_item = QtWidgets.QGraphicsRectItem()
                pen = QtGui.QPen(QtGui.QColor(0, 120, 215))
                pen.setStyle(QtCore.Qt.DashLine)
                pen.setWidth(1)
                self._rubber_rect_item.setPen(pen)
                self._rubber_rect_item.setBrush(QtGui.QBrush(QtGui.QColor(0, 120, 215, 40)))
                self._rubber_rect_item.setZValue(1000)  # on top
                self.addItem(self._rubber_rect_item)
                self._rubber_selecting = True
                return

        # Otherwise default behavior (e.g., clicking on nodes)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        # Finish rubber-band selection
        if event.button() == QtCore.Qt.LeftButton and self._rubber_selecting:
            rect = QtCore.QRectF(self._rubber_origin, event.scenePos()).normalized()

            # Select nodes that intersect the rectangle
            items_in_rect = self.items(rect)
            for item in items_in_rect:
                if isinstance(item, TopologyNode):
                    item.setSelected(True)

            # Clean up rubber-band rectangle
            if self._rubber_rect_item:
                self.removeItem(self._rubber_rect_item)
                self._rubber_rect_item = None
            self._rubber_origin = None
            self._rubber_selecting = False
            return

        super().mouseReleaseEvent(event)

    def start_temporary_line(self, source):
        """Start drawing a temporary line from the source node."""
        self.temp_line = QtWidgets.QGraphicsLineItem()
        self.temp_line.setPen(QtGui.QPen(QtCore.Qt.DotLine))
        self.addItem(self.temp_line)

    def remove_temporary_line(self):
        """Remove the temporary line from the scene."""
        if self.temp_line:
            self.removeItem(self.temp_line)
            self.temp_line = None

    def keyPressEvent(self, event):
        """Handle key press events for deleting nodes or edges.

        When deleting, collect items first then remove them so iteration
        isn't invalidated. Clear selection and update the scene to ensure
        highlights are refreshed/removed immediately.
        """
        if event.key() == QtCore.Qt.Key_Delete:
            # Snapshot items to delete
            to_delete = list(self.selectedItems())
            for item in to_delete:
                if isinstance(item, TopologyNode):
                    # Remove all edges connected to the node
                    for edge in item.edges[:]:
                        edge.delete_edge()
                    # Remove the node itself
                    if item in self.items():
                        self.removeItem(item)
                    if item.name in self.nodes:
                        try:
                            del self.nodes[item.name]
                        except Exception:
                            pass
                elif isinstance(item, TopologyEdge):
                    # Remove the edge
                    item.delete_edge()

            # Clear selection and refresh the scene/view
            self.clearSelection()
            self.update()
            return
        elif event.key() == QtCore.Qt.Key_Escape:
            # Deselect all selected items
            for item in self.selectedItems():
                item.setSelected(False)
        else:
            super().keyPressEvent(event)

    def mouseDoubleClickEvent(self, event):
        """Handle double-click events to create a new node."""
        if not self.itemAt(event.scenePos(), QtGui.QTransform()):
            # Create a new node at the double-click position
            node_name = f"fault_{len(self.nodes) + 1}"
            new_node = TopologyNode(node_name, self)
            self.addItem(new_node)
            new_node.setPos(event.scenePos())
            self.nodes[node_name] = new_node
        else:
            super().mouseDoubleClickEvent(event)


class FaultGraph(QtWidgets.QWidget):
    def __init__(self, parent=None, data_manager=None):
        super().__init__()
        layout = QtWidgets.QVBoxLayout(self)
        self.view = QtWidgets.QGraphicsView()
        # Use a smarter viewport update mode to reduce painting artifacts
        try:
            self.view.setViewportUpdateMode(QtWidgets.QGraphicsView.SmartViewportUpdate)
        except Exception:
            # Fallback if the enum isn't available
            self.view.setViewportUpdateMode(QtWidgets.QGraphicsView.FullViewportUpdate)
        self.scene = TopologyScene()
        self.view.setScene(self.scene)
        layout.addWidget(self.view)

        # Add a "big plus button" in the top-right corner
        self.add_button = QtWidgets.QPushButton("+")
        self.add_button.setFixedSize(50, 50)
        self.add_button.setStyleSheet("font-size: 24px; font-weight: bold;")
        self.add_button.clicked.connect(self.show_add_node_menu)

        # Create a layout for the button
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.add_button)
        layout.addLayout(button_layout)

        self.setWindowTitle("Stratigraphic Topology Viewer")
        self.resize(640, 480)

    def show_add_node_menu(self):
        """Show a menu to add different types of nodes."""
        menu = QtWidgets.QMenu(self)

        # Add options for different node types
        fault_action = menu.addAction("Add Fault Node")
        stratigraphy_action = menu.addAction("Add Stratigraphy Node")
        unconformity_action = menu.addAction("Add Unconformity Node")

        # Connect actions to methods
        fault_action.triggered.connect(lambda: self.add_node("fault"))
        stratigraphy_action.triggered.connect(lambda: self.add_node("stratigraphy"))
        unconformity_action.triggered.connect(lambda: self.add_node("unconformity"))

        # Show the menu below the button
        menu.exec_(self.add_button.mapToGlobal(QtCore.QPoint(0, self.add_button.height())))

    def add_node(self, node_type):
        """Add a new node of the specified type to the scene."""
        node_name = f"{node_type}_{len(self.scene.nodes) + 1}"
        new_node = TopologyNode(node_name, self.scene, node_type=node_type)
        self.scene.addItem(new_node)
        new_node.setPos(300, 200)  # Default position for new nodes
        self.scene.nodes[node_name] = new_node
