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
        # Enable interactivity for the node
        self.setFlags(
            QtWidgets.QGraphicsItem.ItemIsMovable
            | QtWidgets.QGraphicsItem.ItemIsSelectable
            | QtWidgets.QGraphicsItem.ItemSendsGeometryChanges
        )
        self.label = QtWidgets.QGraphicsTextItem(name, self)
        self.label.setDefaultTextColor(QtCore.Qt.black)
        self.label.setPos(-self.label.boundingRect().width() / 2, -30)
        self.shape_item.setAcceptedMouseButtons(QtCore.Qt.NoButton)

    def boundingRect(self):
        """Return a bounding rectangle that includes the shape and the label."""
        shape_rect = self.shape_item.boundingRect()
        label_rect = self.label.boundingRect()
        combined_rect = shape_rect.united(
            label_rect.translated(0, -30)
        )  # Adjust for label position
        return combined_rect

    def mousePressEvent(self, event):
        scene = self.scene_ref
        if event.button() == QtCore.Qt.LeftButton:
            if scene.connecting_from is None:
                scene.connecting_from = self
                self.setBrush(QtGui.QBrush(QtCore.Qt.yellow))  # highlight source
            elif scene.connecting_from == self:
                # cancel connection
                scene.connecting_from = None
                self.setBrush(QtGui.QBrush(QtCore.Qt.lightGray))
            else:
                # create edge
                scene.add_edge_between(scene.connecting_from, self)
                scene.connecting_from.setBrush(QtGui.QBrush(QtCore.Qt.lightGray))
                scene.connecting_from = None
        else:
            super().mousePressEvent(event)

    def paint(self, painter, option, widget=None):
        """Delegate paint to the shape_item."""
        # No custom painting is needed since the shape_item handles rendering.
        pass

    def add_edge(self, edge):
        self.edges.append(edge)

    def itemChange(self, change, value):
        if change == QtWidgets.QGraphicsItem.ItemPositionChange:
            for edge in self.edges:
                edge.update_position()
        return super().itemChange(change, value)


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


class TopologyScene(QtWidgets.QGraphicsScene):
    def __init__(self):
        super().__init__()
        self.setSceneRect(0, 0, 600, 400)
        self.nodes = {}
        self.edges = []
        self.connecting_from = None  # <-- store selected node for connecting
        self.temp_line = None  # Temporary line for visual feedback

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
        if self.connecting_from and self.temp_line:
            # Update the temporary line to follow the cursor
            line = QtCore.QLineF(self.connecting_from.pos(), event.scenePos())
            self.temp_line.setLine(line)
        super().mouseMoveEvent(event)

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
        """Handle key press events for deleting nodes or edges."""
        if event.key() == QtCore.Qt.Key_Delete:
            for item in self.selectedItems():
                if isinstance(item, TopologyNode):
                    # Remove all edges connected to the node
                    for edge in item.edges[:]:
                        edge.delete_edge()
                    # Remove the node itself
                    self.removeItem(item)
                    del self.nodes[item.name]
                elif isinstance(item, TopologyEdge):
                    # Remove the edge
                    item.delete_edge()
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
