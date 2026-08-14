"""Widget for calculating fault topology from a fault layer."""

import os
from contextlib import nullcontext

import geopandas as gpd
from qgis.core import QgsMapLayerProxyModel
from qgis.PyQt import uic
from qgis.PyQt.QtWidgets import QDialog, QMessageBox

from ..compatibility import configure_layer_combo


class FaultTopologyWidget(QDialog):
    """Widget for calculating fault topology from a fault layer."""

    def __init__(self, parent=None, data_manager=None, debug_manager=None):
        super().__init__(parent)
        self.data_manager = data_manager
        # Load the UI file
        ui_path = os.path.join(os.path.dirname(__file__), "fault_topology_widget.ui")
        uic.loadUi(ui_path, self)
        # Set filter for fault layer selection
        configure_layer_combo(self.faultLayerComboBox, QgsMapLayerProxyModel.LineLayer)
        self.faultLayerComboBox.layerChanged.connect(self._on_fault_layer_changed)
        # react to field changes so we can update the modelling widget via the data manager
        try:
            # QgsFieldComboBox uses fieldChanged signal
            self.faultIdFieldComboBox.fieldChanged.connect(self._on_fault_field_changed)
        except Exception:
            pass

        self.runButton.clicked.connect(self._run_topology)
        # After attempting to guess, synchronise with current data manager state (if any)
        self._sync_with_data_manager()

    def _on_fault_layer_changed(self):
        layer = self.faultLayerComboBox.currentLayer()
        self.faultIdFieldComboBox.setLayer(layer)
        # Optionally auto-select a likely ID field
        if layer:
            fields = [field.name() for field in layer.fields()]
            for name in ["id", "ID", "fault_id", "FaultID", "FaultId"]:
                if name in fields:
                    self.faultIdFieldComboBox.setField(name)
                    break
        # Inform the data manager / modelling widgets about the change and preserve other settings
        self._update_data_manager_fault_layer()

    def _on_fault_field_changed(self):
        # When the selected ID field changes, update the data manager so the modelling widget updates
        self._update_data_manager_fault_layer()

    def _sync_with_data_manager(self):
        """Set the widget UI to reflect the current fault traces selection in the data manager."""
        if not hasattr(self, 'data_manager') or self.data_manager is None:
            print("No data manager to sync with")
            return
        try:
            fault_traces = self.data_manager.get_fault_traces()
        except Exception:
            fault_traces = None
        if not fault_traces:
            return
        layer = fault_traces.get('layer')
        print(f"Syncing fault topology widget with layer: {layer}")
        if layer is not None:
            try:
                self.faultLayerComboBox.setLayer(layer)
            except Exception:
                pass
        # set the name field if available
        fault_name_field = fault_traces.get('fault_name_field')
        if fault_name_field and layer is not None:
            try:
                self.faultIdFieldComboBox.setLayer(layer)
                self.faultIdFieldComboBox.setField(fault_name_field)
            except Exception:
                pass

    def _update_data_manager_fault_layer(self):
        """Update the ModellingDataManager with the layer/field chosen in this widget.

        Preserve any other fault settings already present in the data manager (dip, displacement, use_z).
        """
        if not hasattr(self, 'data_manager') or self.data_manager is None:
            return
        # Gather current selections from this widget
        layer = self.faultLayerComboBox.currentLayer()
        name_field = None
        try:
            name_field = self.faultIdFieldComboBox.currentField()
        except Exception:
            name_field = None
        # Preserve existing settings from data manager if present
        existing = self.data_manager.get_fault_traces() or {}
        fault_dip_field = existing.get('fault_dip_field')
        fault_displacement_field = existing.get('fault_displacement_field')
        use_z_coordinate = existing.get('use_z_coordinate', False)
        # Call data manager to set the fault trace layer which will notify the modelling UI
        try:
            self.data_manager.set_fault_trace_layer(
                layer,
                fault_name_field=name_field,
                fault_dip_field=fault_dip_field,
                fault_displacement_field=fault_displacement_field,
                use_z_coordinate=use_z_coordinate,
            )
        except Exception:
            # Fail silently to avoid breaking UI if data_manager is not fully initialised
            return

    def _run_topology(self):
        layer = self.faultLayerComboBox.currentLayer()
        if not layer:
            QMessageBox.warning(self, "Missing Input", "Please select a fault layer.")
            return
        id_field = self.faultIdFieldComboBox.currentField()
        if not id_field:
            QMessageBox.warning(self, "Missing Input", "Please select a fault ID field.")
            return
        # Convert to GeoDataFrame
        gdf = gpd.GeoDataFrame.from_features(layer.getFeatures())
        if gdf.empty:
            QMessageBox.warning(self, "No Data", "The selected layer has no features.")
            return
        # Rename the selected ID field to 'ID' for Topology class compatibility
        if id_field != "ID":
            gdf = gdf.rename(columns={id_field: "ID"})
        # Use map2loop Topology class
        try:
            from map2loop.topology import Topology
        except ImportError:
            QMessageBox.critical(self, "Error", "Could not import map2loop Topology class.")
            return
        topology = Topology(geology_data=None, fault_data=gdf)
        df = topology.fault_fault_relationships

        # Update the modelling FaultTopology (so the Fault Adjacency tab refreshes)
        if hasattr(self, 'data_manager') and self.data_manager is not None:
            try:
                from LoopStructural.modelling.core.fault_topology import FaultRelationshipType

                ft = self.data_manager._fault_topology
                model_manager = getattr(self.data_manager, '_model_manager', None)
                # Repopulating the whole topology fires one notification per
                # add_fault/remove_fault/update_fault_relationship call below.
                # Each notification normally triggers a full O(faults^2)
                # rescan in the model manager (see
                # `batch_fault_topology_updates`), so for a map2loop run with
                # many faults that's a lot of redundant, slow work before the
                # dialog even closes. Batch it into a single rescan.
                batch_cm = (
                    model_manager.batch_fault_topology_updates()
                    if model_manager is not None
                    else nullcontext()
                )
                with batch_cm:
                    # Remove existing fault-fault relationships (notify observers)
                    for f1, f2 in list(ft.adjacency.keys()):
                        try:
                            ft.update_fault_relationship(f1, f2, FaultRelationshipType.NONE)
                        except Exception:
                            pass

                    # Remove existing stratigraphy relationships
                    for unit, fault in list(ft.stratigraphy_fault_relationships.keys()):
                        try:
                            ft.update_fault_stratigraphy_relationship(unit, fault, False)
                        except Exception:
                            pass

                    # Determine faults from the fault layer itself (all IDs present),
                    # not just the ones map2loop found a relationship for. A fault with
                    # no detected topological relationship is still a real fault and
                    # must not be dropped from the fault topology.
                    new_faults = set(str(v) for v in gdf['ID'].unique())

                    # Add new faults; never remove existing ones here, so faults
                    # without a detected relationship (or ones the user added
                    # manually) are preserved and only updated, not deleted.
                    for f in sorted(new_faults):
                        if f not in ft.faults:
                            try:
                                ft.add_fault(f)
                            except Exception:
                                pass

                    # Add relationships from df. map2loop detects these pairs purely
                    # from spatial proximity/intersection of fault traces (see
                    # Topology._calculate_fault_fault_relationships), the same signal
                    # LoopStructural's own map2loop processor (GeologicalModel.from_processor)
                    # resolves to a splay or an ABUTTING relationship -- never a FAULTED
                    # (interpolation-chaining) one. Mark these ABUTTING here too: it's the
                    # cheap, post-hoc region crop, and matches what this data actually
                    # represents (near/intersecting faults, not a deliberate cross-cutting
                    # order). Leave FAULTED for the user to set explicitly in the Fault
                    # Adjacency tab when they really do want one fault's interpolation to
                    # depend on another -- auto-marking every detected pair FAULTED made
                    # every fault chain-build against every nearby fault, which is
                    # combinatorially expensive and freezes Initialize Model on models
                    # with more than a handful of faults.
                    if df is not None and not df.empty:
                        for _, row in df.iterrows():
                            try:
                                if 'Fault1' in row.index and 'Fault2' in row.index:
                                    f1 = str(row['Fault1'])
                                    f2 = str(row['Fault2'])
                                else:
                                    f1 = str(row.iloc[0])
                                    f2 = str(row.iloc[1])
                                ft.update_fault_relationship(
                                    f1, f2, FaultRelationshipType.ABUTTING
                                )
                            except Exception:
                                pass

                    # Update unit-fault relationships if available from topology
                    try:
                        uf = topology.unit_fault_relationships
                        if uf is not None and not uf.empty:
                            for _, r in uf.iterrows():
                                try:
                                    unit = r.get('Unit', r.iloc[0])
                                    fault = r.get('Fault', r.iloc[1])
                                    ft.update_fault_stratigraphy_relationship(
                                        unit, str(fault), True
                                    )
                                except Exception:
                                    pass
                    except Exception:
                        # unit-fault relationships not available
                        pass

            except Exception:
                # If anything fails here, still continue to show success of topology run
                pass

        QMessageBox.information(
            self,
            "Success",
            f"Calculated fault topology for {len(df) if df is not None else 0} pairs.",
        )
        self.close()
        return True
