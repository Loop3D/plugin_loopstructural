from calendar import c
import os
import random
import json
from PyQt5.QtCore import QVariant
import numpy as np
from qgis.PyQt import uic
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QLabel,
    QListWidgetItem,
    QPushButton,
    QWidget,
    QLineEdit,
)
from qgis.core import (
    QgsEllipse,
    QgsFeature,
    QgsField,
    QgsMapLayerProxyModel,
    QgsFieldProxyModel,
    QgsPoint,
    QgsProject,
    QgsVectorLayer,
)

from pyvistaqt import QtInteractor
import pyvista as pv
from LoopStructural.utils import random_hex_colour

from ...main import QgsProcessInputData
from ...main.geometry.calculateLineAzimuth import calculateAverageAzimuth
from ...main.rasterFromModel import callableToRaster
from ...main.callableToLayer import callableToLayer


# from .feature_widget import FeatureWidget
# from LoopStructural.visualisation import Loop3DView
# from loopstructural.gui.modelling.stratigraphic_column import StratigraphicColumnWidget
__title__ = "LoopStructural"
class ModellingWidget(QWidget):
    def __init__(self, parent: QWidget = None, mapCanvas=None, logger=None):
        super().__init__(parent)
        uic.loadUi(os.path.join(os.path.dirname(__file__), "modelling_widget.ui"), self)
        self.project = QgsProject.instance()
        self.mapCanvas = mapCanvas
        self.rotationDoubleSpinBox.setValue(mapCanvas.rotation())
        self._set_layer_filters()
        # self.unitNameField.setLayer(self.basalContactsLayer.currentLayer())
        self.logger = logger
        self._basalContacts = None
        self._units = {}
        self._faults = {}
        self._connectSignals()
        self.view = None
        self.model = None
        self.outputPath = ""
        self.activeFeature = None
        self.groups = []
        self.plotter = QtInteractor(parent)
        self.plotter.add_axes()
        self.pyvista_layout.addWidget(self.plotter)
        self.loadFromProject()
    def setLayerComboBoxFromProject(self, comboBox: QComboBox, layerKey: str):
        layerName, flag = self.project.readEntry(__title__, layerKey)
        if flag:

            layers = self.project.mapLayersByName(layerName)
            print(layerName,layers)
            if len(layers) == 0:
                self.logger(
                    message=f"Layer {layerName} not found in project",
                    log_level=2,
                    push=True,
                )
                return
            comboBox.setLayer(None)
            comboBox.setLayer(layers[0])
    def setLayerFieldComboBoxFromProject(self, comboBox: QComboBox, fieldKey: str, layer: QgsVectorLayer):
        if layer is None:
            self.logger(message="Layer is None", log_level=2, push=True)
            return
        fieldName, flag = self.project.readEntry(__title__, fieldKey)
        if not flag or not fieldName:
            self.logger(message=f"Field {fieldKey} not found in project", log_level=0, push=True)
            return
        field_names = [field.name() for field in layer.fields()]
        if fieldName not in field_names:
            self.logger(
                message=f"Field {fieldName} not found in layer {layer.name()}",
                log_level=0,
                push=True,
            )
            return
        comboBox.setField(fieldName)
    
        
        
    def loadFromProject(self):
        # Load settings from project    
        self.setLayerComboBoxFromProject(self.basalContactsLayer, "basal_contacts_layer")
        self.setLayerFieldComboBoxFromProject(self.unitNameField, "unitname_field", self.basalContactsLayer.currentLayer())
        self.setLayerComboBoxFromProject(self.structuralDataLayer, "structural_data_layer")
        self.setLayerFieldComboBoxFromProject(self.dipField, "dip_field", self.structuralDataLayer.currentLayer())
        self.setLayerFieldComboBoxFromProject(self.orientationField, "orientation_field", self.structuralDataLayer.currentLayer())
        self.setLayerFieldComboBoxFromProject(self.structuralDataUnitName, "structuraldata_unitname_field", self.structuralDataLayer.currentLayer())
        self.setLayerComboBoxFromProject(self.faultTraceLayer, "fault_trace_layer")
        self.setLayerFieldComboBoxFromProject(self.faultNameField, "faultname_field", self.faultTraceLayer.currentLayer())
        self.setLayerFieldComboBoxFromProject(self.faultDipField, "fault_dip_field", self.faultTraceLayer.currentLayer())
        self.setLayerFieldComboBoxFromProject(self.faultDisplacementField, "fault_displacement_field", self.faultTraceLayer.currentLayer())
        self.setLayerFieldComboBoxFromProject(self.faultPitchField, "fault_pitch_field", self.faultTraceLayer.currentLayer())
        self.setLayerComboBoxFromProject(self.DtmLayer, "dtm_layer")
        self.setLayerComboBoxFromProject(self.roiLayer, "roi_layer")
        label, flag = self.project.readEntry(__title__, "orientation_label", "Strike")
        if flag:
            self.orientationType.setCurrentText(label)
        resp, flag = self.project.readEntry(__title__,"units","")
        if flag:
            self._units = json.loads(resp)
            if len(self._units) > 0:
                self._initialiseStratigraphicColumn()
        resp, flag = self.project.readEntry(__title__,"faults","")
        if flag:
            # try:
            self._faults = json.loads(resp)
            self.initFaultNetwork()
            # except:
                # self.logger(message="Faults not loaded", log_level=2, push=True)


        
    def _set_layer_filters(self):
        # Set filters for the layer selection comboboxes
        # basal contacts can be line or points
        self.basalContactsLayer.setFilters(
            QgsMapLayerProxyModel.LineLayer | QgsMapLayerProxyModel.PointLayer
        )
        self.basalContactsLayer.setAllowEmptyLayer(True)
        # Structural data can only be points
        self.structuralDataLayer.setFilters(QgsMapLayerProxyModel.PointLayer)
        self.basalContactsLayer.setAllowEmptyLayer(True)
        # fault traces can be lines or points
        self.faultTraceLayer.setFilters(
            QgsMapLayerProxyModel.LineLayer | QgsMapLayerProxyModel.PointLayer
        )
        self.faultTraceLayer.setAllowEmptyLayer(True)
        # dtm can only be a raster
        self.DtmLayer.setFilters(QgsMapLayerProxyModel.RasterLayer)
        self.DtmLayer.setAllowEmptyLayer(True)

        # evaluate on model layer
        self.evaluateModelOnLayerSelector.setFilters(QgsMapLayerProxyModel.PointLayer)
        self.evaluateModelOnLayerSelector.setAllowEmptyLayer(True)
        # evaluate on feature layer
        self.evaluateFeatureLayerSelector.setFilters(QgsMapLayerProxyModel.PointLayer)
        self.evaluateFeatureLayerSelector.setAllowEmptyLayer(True)
        # orientation field can only be double or int
        self.orientationField.setFilters(QgsFieldProxyModel.Numeric)
        self.dipField.setFilters(QgsFieldProxyModel.Numeric)
        # fault dip field can only be double or int
        self.faultDipField.setFilters(QgsFieldProxyModel.Numeric)
        # fault displacement field can only be double or int
        self.faultDisplacementField.setFilters(QgsFieldProxyModel.Numeric)
    def saveLayerComboBoxState(self, comboBox: QComboBox, layerKey: str):
        layer = comboBox.currentLayer()
        if layer is not None:
            self.project.writeEntry(__title__, layerKey, layer.name())
        
    def saveLayerFieldComboBoxState(self, comboBox: QComboBox, fieldKey: str):
        field = comboBox.currentField()
        if field is not None:
            self.project.writeEntry(__title__, fieldKey, field)
    def saveSettingToProject(self,key:str,value:str):
        self.project.writeEntry(__title__, key, value)
    
    def _connectSignals(self):
        self.basalContactsLayer.layerChanged.connect(self.onBasalContactsChanged)
        self.structuralDataLayer.layerChanged.connect(self.onStructuralDataLayerChanged)
        self.unitNameField.fieldChanged.connect(self.onUnitFieldChanged)
        self.faultTraceLayer.layerChanged.connect(self.onFaultTraceLayerChanged)
        self.faultNameField.fieldChanged.connect(self.onFaultFieldChanged)
        self.faultDipField.fieldChanged.connect(self.onFaultFieldChanged)
        self.faultDisplacementField.fieldChanged.connect(self.onFaultFieldChanged)
        self.orientationType.currentIndexChanged.connect(self.onOrientationTypeChanged)
        self.orientationField.fieldChanged.connect(self.onOrientationFieldChanged)
        self.initModel.clicked.connect(self.onInitialiseModel)
        self.rotationDoubleSpinBox.valueChanged.connect(self.onRotationChanged)
        self.runModelButton.clicked.connect(self.onRunModel)
        self.pathButton.clicked.connect(self.onClickPath)
        self.saveButton.clicked.connect(self.onSaveModel)
        self.path.textChanged.connect(self.onPathTextChanged)
        self.faultSelection.currentIndexChanged.connect(self.onSelectedFaultChanged)
        
        self.basalContactsLayer.layerChanged.connect(lambda: self.saveLayerComboBoxState(self.basalContactsLayer,'basal_contacts_layer'))
        self.unitNameField.fieldChanged.connect(lambda: self.saveLayerFieldComboBoxState(self.unitNameField,'unitname_field'))
        self.structuralDataLayer.layerChanged.connect(lambda: self.saveLayerComboBoxState(self.structuralDataLayer,'structural_data_layer'))
        self.orientationField.fieldChanged.connect(lambda: self.saveLayerFieldComboBoxState(self.orientationField,'orientation_field'))

        self.dipField.fieldChanged.connect(lambda: self.saveLayerFieldComboBoxState(self.dipField,'dip_field'))
        self.roiLayer.layerChanged.connect(lambda: self.saveLayerComboBoxState(self.roiLayer,'roi_layer'))
        self.faultTraceLayer.layerChanged.connect(lambda: self.saveLayerComboBoxState(self.faultTraceLayer,'fault_trace_layer'))
        self.faultNameField.fieldChanged.connect(lambda: self.saveLayerFieldComboBoxState(self.faultNameField,'faultname_field'))
        self.faultDipField.fieldChanged.connect(lambda: self.saveLayerFieldComboBoxState(self.faultDipField,'fault_dip_field'))
        self.faultDisplacementField.fieldChanged.connect(lambda: self.saveLayerFieldComboBoxState(self.faultDisplacementField,'fault_displacement_field'))
        self.faultPitchField.fieldChanged.connect(lambda: self.saveLayerFieldComboBoxState(self.faultPitchField,'fault_pitch_field'))
        self.faultDipValue.valueChanged.connect(
            lambda value: self.updateFaultProperty('fault_dip', value)
        )
        
        
        self.structuralDataUnitName.fieldChanged.connect(
            lambda: self.saveLayerFieldComboBoxState(self.structuralDataUnitName,'structuraldata_unitname_field')
        )
        self.faultPitchValue.valueChanged.connect(
            lambda value: self.updateFaultProperty('fault_pitch', value)
        )
        self.faultDisplacementValue.valueChanged.connect(
            lambda value: self.updateFaultProperty('displacement', value)
        )
        self.faultActiveCheckBox.stateChanged.connect(
            lambda value: self.updateFaultProperty('active', value)
        )
        self.faultMajorAxisLength.valueChanged.connect(
            lambda value: self.updateFaultProperty('major_axis', value)
        )
        self.faultIntermediateAxisLength.valueChanged.connect(
            lambda value: self.updateFaultProperty('intermediate_axis', value)
        )
        self.faultMinorAxisLength.valueChanged.connect(
            lambda value: self.updateFaultProperty('minor_axis', value)
        )
       
        self.orientationType.currentIndexChanged.connect(lambda value: self.saveSettingToProject('orientation_type', self.orientationLabel.text()))
            
        # self.faultCentreX.valueChanged.connect(lambda value: self.updateFaultProperty('centre', value))
        # self.faultCentreY.valueChanged.connect(lambda value: self.updateFaultProperty('centre', value))
        # self.faultCentreZ.valueChanged.connect(lambda value: self.updateFaultProperty('centre', value))
        self.addFaultElipseToMap.clicked.connect(self.drawFaultElipse)
        self.addModelContactsToProject.clicked.connect(self.onAddModelContactsToProject)
        self.addFaultDisplacementsToProject.clicked.connect(self.onAddFaultDisplacmentsToProject)
        self.evaluateModelOnLayer.clicked.connect(self.onEvaluateModelOnLayer)
        self.evaluateFeatureOnLayer.clicked.connect(self.onEvaluateFeatureOnLayer)
        self.addMappedLithologiesToProject.clicked.connect(self.onAddModelledLithologiesToProject)
        self.addFaultTracesToProject.clicked.connect(self.onAddFaultTracesToProject)
        self.addScalarFieldToProject.clicked.connect(self.onAddScalarFieldToProject)
        # self.saveThicknessOrderButton.clicked.connect(self.saveThicknessOrder)
        self.addUnitButton.clicked.connect(self.addUnitToStratigraphicColumn)
        self.addBlockModelToPyvistaButton.clicked.connect(self.addBlockModelToPyvista)
        self.clearPyvistaButton.clicked.connect(self.clearPyvista)
        self.addSurfacesToPyvistaButton.clicked.connect(self.addModelSurfacesToPyvista)
        self.addDataToPyvistaButton.clicked.connect(self.addDataToPyvista)
        QgsProject.instance().readProject.connect(self.loadFromProject)      
    def onModelListItemClicked(self, feature):
        self.activeFeature = self.model[feature.text()]
        self.numberOfElementsSpinBox.setValue(
            self.activeFeature.builder.build_arguments['nelements']
        )
        self.numberOfElementsSpinBox.valueChanged.connect(
            lambda nelements: self.activeFeature.builder.update_build_arguments(
                {'nelements': nelements}
            )
        )
        self.regularisationSpin.setValue(
            self.activeFeature.builder.build_arguments['regularisation']
        )
        self.regularisationSpin.valueChanged.connect(
            lambda regularisation: self.activeFeature.builder.update_builupdate_build_argumentsd_args(
                {'regularisation': regularisation}
            )
        )
        self.npwSpin.setValue(self.activeFeature.builder.build_arguments['npw'])
        self.npwSpin.valueChanged.connect(
            lambda npw: self.activeFeature.builder.update_build_arguments({'npw': npw})
        )
        self.cpwSpin.setValue(self.activeFeature.builder.build_arguments['cpw'])
        self.cpwSpin.valueChanged.connect(
            lambda cpw: self.activeFeature.builder.update_build_arguments({'cpw': cpw})
        )
        # self.updateButton.clicked.connect(lambda : feature.builder.update())

    def onInitialiseModel(self):

        columnmap = {
            'unitname': self.unitNameField.currentField(),
            'faultname': self.faultNameField.currentField(),
            'dip': self.dipField.currentField(),
            'orientation': self.orientationField.currentField(),
            'structure_unitname': self.structuralDataUnitName.currentField(),
            # 'pitch': self.faultPitchField.currentField()
        }
        faultNetwork = np.zeros((len(self._faults), len(self._faults)))
        for i in range(len(self._faults)):
            for j in range(len(self._faults)):
                if i != j:
                    item = self.faultNetworkTable.cellWidget(i, j)
                    if item.currentText() == 'Abuts':
                        faultNetwork[i, j] = 1
                    elif item.currentText() == 'Cuts':
                        faultNetwork[i, j] = -1
        faultStratigraphy = np.zeros((len(self._faults), len(self.groups)))
        for i in range(len(self._faults)):
            for j in range(len(self.groups)):
                item = self.faultStratigraphyTable.cellWidget(i, j)
                faultStratigraphy[i, j] = item.isChecked()

        processor = QgsProcessInputData(
            basal_contacts=self.basalContactsLayer.currentLayer(),
            groups=self.groups,
            fault_trace=self.faultTraceLayer.currentLayer(),
            fault_properties=self._faults,
            structural_data=self.structuralDataLayer.currentLayer(),
            dtm=self.DtmLayer.currentLayer(),
            columnmap=columnmap,
            roi=self.roiLayer.currentLayer(),
            top=self.heightSpinBox.value(),
            bottom=self.depthSpinBox.value(),
            dip_direction=self.orientationType.currentIndex() == 1,
            rotation=self.rotationDoubleSpinBox.value(),
            faultNetwork=faultNetwork,
            faultStratigraphy=faultStratigraphy,
            faultlist=list(self._faults.keys()),
        )
        self.processor = processor
        self.model = processor.get_model()
        self.logger(message="Model initialised", log_level=0, push=True)
        self.modelList.clear()
        for feature in self.model.features:
            if feature.name[0] == '_':
                continue
            item = QListWidgetItem()
            item.setText(feature.name)
            item.setBackground(
                QColor(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
            )

            self.modelList.addItem(item)
        self.modelList.itemClicked.connect(self.onModelListItemClicked)
        self.plotter.add_mesh(self.model.bounding_box.vtk().outline())
    def onOrientationTypeChanged(self, index):
        if index == 0:
            self.orientationLabel.setText("Strike")
        else:
            self.orientationLabel.setText("Dip Direction")

    def onRotationChanged(self, rotation):
        self.mapCanvas.setRotation(rotation)

    def onOrientationFieldChanged(self, field):
        pass

    def onStructuralDataLayerChanged(self, layer):
        self.orientationField.setLayer(layer)
        self.dipField.setLayer(layer)
        self.structuralDataUnitName.setLayer(layer)
        # self.saveLayersToProject()
        # self.dipField.setValidator(QDoubleValidator(0.0, 360.0, 2))
        # self.orientationField.setValidator(QDoubleValidator(0.0, 360.0, 2))

    def onRunModel(self):
        try:
            self.model.update(progressbar=False)
            self._model_updated()
            self.logger(message="Model run", log_level=0, push=True)

        except Exception as e:
            self.logger(
                message=str(e),
                log_level=2,
                push=True,
            )

    def _model_updated(self):
        self.addScalarFieldComboBox.clear()
        self.evaluateFeatureFeatureSelector.clear()
        for feature in self.model.features:
            ## make sure that private features are not added to the list
            if feature.name[0] != "_":
                self.addScalarFieldComboBox.addItem(feature.name)
                self.evaluateFeatureFeatureSelector.addItem(feature.name)
        self.addScalarFieldComboBox.setCurrentIndex(0)
        self.evaluateFeatureFeatureSelector.setCurrentIndex(0)

    def onAddModelContactsToProject(self):
        pass

    def onAddFaultDisplacmentsToProject(self):
        pass
    def addBlockModelToPyvista(self):
        if self.model is None:
            self.logger(message="Model not initialised", log_level=2, push=True)
            return
        self.plotter.add_mesh(self.model.get_block_model()[0].vtk(),show_scalar_bar=False)
    def addModelSurfacesToPyvista(self):
        if self.model is None:
            self.logger(message="Model not initialised", log_level=2, push=True)
            return
        surfaces = self.model.get_stratigraphic_surfaces()
        for surface in surfaces:
            self.plotter.add_mesh(surface.vtk(),show_scalar_bar=False,color=surface.colour) 
        fault_surfaces = self.model.get_fault_surfaces()
        for surface in fault_surfaces:
            self.plotter.add_mesh(surface.vtk(),show_scalar_bar=False,color='black')
    def addDataToPyvista(self):
        if self.model is None:
            self.logger(message="Model not initialised", log_level=2, push=True)
            return
        for f in self.model.features:
            if f.name[0] != "_":
                for d in f.get_data():
                    self.plotter.add_mesh(d.vtk(), show_scalar_bar=False)
    def clearPyvista(self):
        self.plotter.clear()
        if self.model is not None:
            self.plotter.add_mesh(self.model.bounding_box.vtk().outline())
    def onEvaluateModelOnLayer(self):
        layer = self.evaluateModelOnLayerSelector.currentLayer()

        callableToLayer(
            lambda xyz: self.model.evaluate_model(xyz),
            layer,
            self.DtmLayer.currentLayer(),
            'unit_id',
        )

    def onEvaluateFeatureOnLayer(self):
        feature_name = self.evaluateFeatureFeatureSelector.currentText()
        layer = self.evaluateFeatureLayerSelector.currentLayer()
        callableToLayer(
            lambda xyz: self.model.evaluate_feature_value(feature_name, xyz),
            layer,
            self.DtmLayer.currentLayer(),
            feature_name,
        )
        pass

    def onAddModelledLithologiesToProject(self):
        if self.model is None:
            self.logger(message="Model not initialised", log_level=2, push=True)
            return
        bounding_box = self.model.bounding_box
        feature_layer = callableToRaster(
            lambda xyz: self.model.evaluate_model(xyz),
            dtm=self.DtmLayer.currentLayer(),
            bounding_box=bounding_box,
            crs=QgsProject.instance().crs(),
            layer_name='modelled_lithologies',
        )
        if feature_layer.isValid():
            QgsProject.instance().addMapLayer(feature_layer)
        else:
            self.logger(message="Failed to add scalar field to project", log_level=2, push=True)
        pass

    def onAddFaultTracesToProject(self):
        pass

    def onAddScalarFieldToProject(self):
        feature_name = self.addScalarFieldComboBox.currentText()
        if self.model is None:
            self.logger(message="Model not initialised", log_level=2, push=True)
            return
        bounding_box = self.model.bounding_box
        feature_layer = callableToRaster(
            lambda xyz: self.model.evaluate_feature_value(feature_name, xyz),
            dtm=self.DtmLayer.currentLayer(),
            bounding_box=bounding_box,
            crs=QgsProject.instance().crs(),
            layer_name=f'{feature_name}_scalar_field',
        )
        if feature_layer.isValid():
            QgsProject.instance().addMapLayer(feature_layer)
        else:
            self.logger(message="Failed to add scalar field to project", log_level=2, push=True)

    def onBasalContactsChanged(self, layer):
        self.unitNameField.setLayer(layer)
        # self.saveLayersToProject()
    def onFaultTraceLayerChanged(self, layer):
        self.faultNameField.setLayer(layer)
        self.faultDipField.setLayer(layer)
        self.faultDisplacementField.setLayer(layer)
        self._faults = {}  # reset faults
        self.onSelectedFaultChanged(-1)
        self.initFaultSelector()
        self.initFaultNetwork()
        # self.saveLayersToProject()

    def onUnitFieldChanged(self, field):
        if len(self._units) == 0:

            unique_values = set()
            attributes = {}
            layer = self.unitNameField.layer()
            if layer:
                fields = {}
                fields['unitname'] = layer.fields().indexFromName(field)
                if '_ls_th' in [field.name() for field in layer.fields()]:
                    fields['thickness'] = layer.fields().indexFromName('_ls_th')
                if '_ls_or' in [field.name() for field in layer.fields()]:
                    fields['order'] = layer.fields().indexFromName('_ls_or')
                if '_ls_col' in [field.name() for field in layer.fields()]:
                    fields['colour'] = layer.fields().indexFromName('_ls_col')
                field_index = layer.fields().indexFromName(field)

                for feature in layer.getFeatures():
                    unique_values.add(str(feature[field_index]))
                    attributes[str(feature[field_index])] = {}
                    for k in fields:
                        if feature[fields[k]] is not None:
                            attributes[str(feature[field_index])][k] = feature[fields[k]]
        
            colours = random_hex_colour(n=len(unique_values))
            self._units = dict(
                zip(
                    list(unique_values),
                    [
                        {
                            'thickness': (
                                attributes[u]['thickness'] if 'thickness' in attributes[u] else 10.0
                            ),
                            'order': int(attributes[u]['order']) if 'order' in attributes[u] else i,
                            'name': u,
                            'colour': (
                                str(attributes[u]['colour'])
                                if 'colour' in attributes[u]
                                else colours[i]
                            ),
                            'contact': (
                                str(attributes[u]['contact'])
                                if 'contact' in attributes[u]
                                else 'Conformable'
                            ),
                        }
                        for i, u in enumerate(unique_values)
                    ],
                )
            )
            self._initialiseStratigraphicColumn()

    def initFaultSelector(self):
        self.faultSelection.clear()
        self.resetFaultField()
        if self._faults:
            faults = list(self._faults.keys())
            self.faultSelection.addItems(faults)

    def initFaultNetwork(self):
        # faultNetwork
        self.faultNetworkTable.clear()
        self.faultNetworkTable.setRowCount(0)
        self.faultNetworkTable.setColumnCount(0)
        self.faultStratigraphyTable.clear()
        self.faultStratigraphyTable.setRowCount(0)
        self.faultStratigraphyTable.setColumnCount(0)
        if not self._faults:
            return

        faults = list(self._faults.keys())
        self.faultNetworkTable.setRowCount(len(faults))
        self.faultNetworkTable.setColumnCount(len(faults))

        # Set headers
        self.faultNetworkTable.setHorizontalHeaderLabels(faults)
        self.faultNetworkTable.setVerticalHeaderLabels(faults)

        # Fill table with empty items
        for i in range(len(faults)):
            for j in range(len(faults)):
                if i == j:
                    flag = QLabel()
                    flag.setText('')
                else:
                    flag = QComboBox()
                    flag.addItem('')
                    flag.addItem('Abuts')
                    flag.addItem('Cuts')
                # item = QTableWidgetItem(flag)
                self.faultNetworkTable.setCellWidget(i, j, flag)

        # Make cells more visible
        self.faultNetworkTable.setShowGrid(True)
        self.faultNetworkTable.resizeColumnsToContents()
        self.faultNetworkTable.resizeRowsToContents()

        self.faultStratigraphyTable.clear()

        faults = list(self._faults.keys())
        groups = [g['name'] for g in self.groups]
        self.faultStratigraphyTable.setRowCount(len(faults))
        self.faultStratigraphyTable.setColumnCount(len(groups))

        # Set headers
        self.faultStratigraphyTable.setHorizontalHeaderLabels(groups)
        self.faultStratigraphyTable.setVerticalHeaderLabels(faults)

        # Fill table with empty items
        for j in range(len(groups)):
            for i in range(len(faults)):
                flag = QCheckBox()
                flag.setChecked(True)
                self.faultStratigraphyTable.setCellWidget(i, j, flag)

        # Make cells more visible
        self.faultStratigraphyTable.setShowGrid(True)
        self.faultStratigraphyTable.resizeColumnsToContents()
        self.faultStratigraphyTable.resizeRowsToContents()

    def onFaultFieldChanged(self, field):
        name_field = self.faultNameField.currentField()
        dip_field = self.faultDipField.currentField()
        displacement_field = self.faultDisplacementField.currentField()
        layer = self.faultNameField.layer()

        if name_field and layer:
            self._faults = {}
            for feature in layer.getFeatures():
                self._faults[str(feature[name_field])] = {
                    'fault_dip': feature.attributeMap().get(dip_field, 90),
                    'displacement': feature.attributeMap().get(displacement_field, 0.1*feature.geometry().length()),
                    'fault_centre': {'x':feature.geometry().centroid().asPoint().x(), 'y':feature.geometry().centroid().asPoint().y()},
                    'major_axis': feature.geometry().length(),
                    'intermediate_axis': feature.geometry().length(),
                    'minor_axis': feature.geometry().length() / 3,
                    'active': True,
                    "azimuth": calculateAverageAzimuth(feature.geometry()),
                    "fault_pitch": feature.attributeMap().get('pitch', 90),
                    "crs": layer.crs().authid(),
                }
        self.initFaultSelector()
        self.initFaultNetwork()
        # self.saveLayersToProject()
    
    def saveLayersToProject(self):
        if self.basalContactsLayer.currentLayer() is not None:
            self.project.writeEntry(
                __title__, "basal_contacts_layer", self.basalContactsLayer.currentLayer().name()
            )
        if self.structuralDataLayer.currentLayer() is not None:
            self.project.writeEntry(
                __title__, "structural_data_layer", self.structuralDataLayer.currentLayer().name()
            )
        if self.faultTraceLayer.currentLayer() is not None:
            self.project.writeEntry(
                __title__, "fault_trace_layer", self.faultTraceLayer.currentLayer().name()
            )
        if self.DtmLayer.currentLayer() is not None:
            self.project.writeEntry(__title__, "dtm_layer", self.DtmLayer.currentLayer().name())
        if self.roiLayer.currentLayer() is not None:
            self.project.writeEntry(__title__, "roi_layer", self.roiLayer.currentLayer().name())
        if self.unitNameField.currentField() is not None:
            self.project.writeEntry(
                __title__, "unitname_field", self.unitNameField.currentField()
            )
        if self.dipField.currentField() is not None:
            self.project.writeEntry(__title__, "dip_field", self.dipField.currentField())
        if self.orientationField.currentField() is not None:
            self.project.writeEntry(
                __title__, "orientation_field", self.orientationField.currentField()
            )
        if self.faultNameField.currentField() is not None:
            self.project.writeEntry(
                __title__, "faultname_field", self.faultNameField.currentField()
            )
        if self.faultDipField.currentField() is not None:
            self.project.writeEntry(
                __title__, "fault_dip_field", self.faultDipField.currentField()
            )
        if self.faultDisplacementField.currentField() is not None:
            self.project.writeEntry(
                __title__, "fault_displacement_field", self.faultDisplacementField.currentField()
            )
        if self.faultPitchField.currentField() is not None:
            self.project.writeEntry(
                __title__, "fault_pitch_field", self.faultPitchField.currentField()
            )
        if self._units:
            self.project.writeEntry(__title__, "units", json.dumps(self._units))
        if self._faults:
            self.project.writeEntry(__title__, "faults", json.dumps(self._faults))
        
    def onSelectedFaultChanged(self, index):
        if index >= 0:
            fault = self.faultSelection.currentText()
            self.faultDipValue.setValue(self._faults[fault]['fault_dip'])
            self.faultPitchValue.setValue(self._faults[fault]['fault_pitch'])
            self.faultDisplacementValue.setValue(self._faults[fault]['displacement'])
            self.faultActiveCheckBox.setChecked(self._faults[fault]['active'])
            self.faultMajorAxisLength.setValue(self._faults[fault]['major_axis'])
            self.faultIntermediateAxisLength.setValue(self._faults[fault]['intermediate_axis'])
            self.faultMinorAxisLength.setValue(self._faults[fault]['minor_axis'])
            self.faultCentreX.setValue(self._faults[fault]['fault_centre']['x'])
            self.faultCentreY.setValue(self._faults[fault]['fault_centre']['y'])
            # self.faultCentreZ.setValue(self._faults[fault]['centre'].z())
            self._onActiveFaultChanged(self._faults[fault]['active'])
    def saveFaultsToProject(self):
        if self._faults:
            self.project.writeEntry(__title__, "faults", json.dumps(self._faults))
    def saveUnitsToProject(self):
        if self._units:
            self.project.writeEntry(__title__, "units", json.dumps(self._units))
    
    def resetFaultField(self):
        self.faultDipValue.setValue(0)
        self.faultPitchValue.setValue(0)
        self.faultDisplacementValue.setValue(0)
        self.faultActiveCheckBox.setChecked(0)
        self.faultMajorAxisLength.setValue(0)
        self.faultIntermediateAxisLength.setValue(0)
        self.faultMinorAxisLength.setValue(0)
        self.faultCentreX.setValue(0)
        self.faultCentreY.setValue(0)
        # self.faultCentreZ.setValue(self._faults[fault]['centre'].z())
        self._onActiveFaultChanged(False)

    def _onActiveFaultChanged(self, value):
        self.faultDipValue.setEnabled(value)
        self.faultPitchValue.setEnabled(value)
        self.faultDisplacementValue.setEnabled(value)
        self.faultMajorAxisLength.setEnabled(value)
        self.faultIntermediateAxisLength.setEnabled(value)
        self.faultMinorAxisLength.setEnabled(value)
        self.faultCentreX.setEnabled(value)
        self.faultCentreY.setEnabled(value)
        # self.faultCentreZ.setEnabled(value)

    def updateFaultProperty(self, prop, value):
        fault = self.faultSelection.currentText()
        if fault not in self._faults:
            return
        self._faults[fault][prop] = value
        if prop == 'active':
            self._onActiveFaultChanged(value)
        self.saveFaultsToProject()
    def drawFaultElipse(self):
        fault = self.faultSelection.currentText()
        if fault:
            centre = self._faults[fault]['centre']
            major_axis = self._faults[fault]['major_axis']

            minor_axis = self._faults[fault]['minor_axis']
            azimuth = self._faults[fault].get('azimuth', 0)
            crs = self._faults[fault].get('crs', 'EPSG:4326')
            # Create an ellipsoid centered at the fault center
            ellipsoid = QgsEllipse(
                QgsPoint(centre.x(), centre.y()), major_axis / 2, minor_axis / 2, azimuth
            )

            # Add the ellipsoid to the map canvas
            ellipsoid_layer = QgsVectorLayer(f"Polygon?crs={crs}", f"{fault}:  Ellipsoid", "memory")
            ellipsoid_layer_provider = ellipsoid_layer.dataProvider()
            ellipsoid_feature = QgsFeature()
            ellipsoid_feature.setGeometry(ellipsoid.toPolygon())
            ellipsoid_layer_provider.addFeatures([ellipsoid_feature])

            QgsProject.instance().addMapLayer(ellipsoid_layer)

    def _getSortedStratigraphicColumn(self):

        return sorted(self._units.items(), key=lambda x: x[1]['order'])

    def _initialiseStratigraphicColumn(self):
        while self.stratigraphicColumnContainer.count():
            child = self.stratigraphicColumnContainer.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        def create_lambda(i, direction):
            return lambda: self.onOrderChanged(i, i + direction)

        def create_color_picker(unit):
            def pick_color():
                color = QColorDialog.getColor()
                if color.isValid():
                    self._units[unit]['colour'] = color.name()
                    self._initialiseStratigraphicColumn()

            return pick_color

        for i, (unit, value) in enumerate(self._getSortedStratigraphicColumn()):
            # Add stretch factor to first column
            

            label = QLineEdit(unit)
            label.editingFinished.connect(lambda unit=unit, label=label: self.stratigraphicColumnUnitNameChanged(unit, label.text()))
            spin_box = QDoubleSpinBox(maximum=100000, minimum=0)
            spin_box.setValue(value['thickness'])
            order = QLabel()
            order.setText(str(value['order']))
            up = QPushButton("↑")
            down = QPushButton("↓")
            color_picker = QPushButton("Pick Colour")
            # Set background color for the row
            background_color = value.get('colour', "#ffffff")
            label.setStyleSheet(f"background-color: {background_color};")
            spin_box.setStyleSheet(f"background-color: {background_color};")
            order.setStyleSheet(f"background-color: {background_color};")
            up.setStyleSheet(f"background-color: {background_color};")
            down.setStyleSheet(f"background-color: {background_color};")
            color_picker.setStyleSheet(f"background-color: {background_color};")
            self.stratigraphicColumnContainer.addWidget(label, i, 0)
            self.stratigraphicColumnContainer.addWidget(spin_box, i, 1)
            self.stratigraphicColumnContainer.addWidget(up, i, 2)
            self.stratigraphicColumnContainer.addWidget(down, i, 3)
            self.stratigraphicColumnContainer.addWidget(color_picker, i, 4)
            unconformity = QComboBox()
            unconformity.addItem('Conformable')
            unconformity.addItem('Erode')
            unconformity.addItem('Onlap')
            if 'contact' in value:
                unconformity.setCurrentText(value['contact'])

            unconformity.currentTextChanged.connect(
                lambda text, unit=unit: self.stratigraphicColumnChanged(text, unit)
            )

            self.stratigraphicColumnContainer.addWidget(unconformity, i, 5)
            up.clicked.connect(create_lambda(i, -1))
            down.clicked.connect(create_lambda(i, 1))
            color_picker.clicked.connect(create_color_picker(unit))
            spin_box.valueChanged.connect(
                lambda value, unit=unit: self.onThicknessChanged(unit, value)
            )
            remove_button = QPushButton("Remove")
            remove_button.setStyleSheet(f"background-color: {background_color};")
            remove_button.clicked.connect(
                lambda value, unit=unit: self.stratigraphicColumnRemoveClicked(unit)
            )
            self.stratigraphicColumnContainer.addWidget(remove_button, i, 6)
        
        self.updateGroups()
    def stratigraphicColumnChanged(self, text, unit):
        self._units[unit]['contact'] = text
        self.updateGroups()
        self.saveUnitsToProject()
    def stratigraphicColumnRemoveClicked(self, unit):
        if unit in self._units:
            del self._units[unit]
        self._initialiseStratigraphicColumn()
        self.saveUnitsToProject()
    def addUnitToStratigraphicColumn(self):
        name = 'New Unit'
        if len(self._units) > 0:
            name = f'New Unit {len(self._units) + 1}'
        colour = random_hex_colour(n=1)[0]
        self._units[name] = {
            'thickness': 10.0,
            'order': len(self._units),
            'name': name,
            'colour': colour,
            'contact': 'Conformable',
        }
        self._initialiseStratigraphicColumn()
        self.saveUnitsToProject()
        
    def stratigraphicColumnUnitNameChanged(self, unit, name):
        
        old_name = unit
        if unit == name:
            return  
        if unit not in self._units:
            return
        if name in self._units and name != unit:
            self.logger(message="Cannot rename, unit name already exists", log_level=2, push=True)
            return
        unit = self._units[unit]
        unit['name'] = name
        self._units[name] = unit
        del self._units[old_name]
        self._initialiseStratigraphicColumn()
        self.saveUnitsToProject()
    def updateGroups(self):
        columns = self._getSortedStratigraphicColumn()

        self.groups = []
        group = []
        ii = 0
        for _i, (_unit, value) in enumerate(columns):
            group.append(value)
            if value['contact'] != 'Conformable':
                self.groups.append({'name': f'group_{ii}', 'units': group})
                ii += 1
                group = []

        self.groups.append({'name': f'group_{ii}', 'units': group})
        self.initFaultNetwork()

    def onOrderChanged(self, old_index, new_index):
        if new_index < 0 or new_index >= len(self._units):
            return
        units = dict(self._units)  # update a copy
        for unit, value in self._units.items():
            if value['order'] == old_index:
                units[unit]['order'] = new_index
            elif value['order'] == new_index:
                units[unit]['order'] = old_index
        self._units = units  # set to copy
        self._initialiseStratigraphicColumn()
        self.saveUnitsToProject()
    def onThicknessChanged(self, unit, value):
        self._units[unit]['thickness'] = value
        self.saveUnitsToProject()
    def onSaveModel(self):
        if self.model is None:
            self.logger(message="Cannot save model, model not initialised", log_level=2, push=True)
            return
        try:

            fileFormat = self.fileFormatCombo.currentText()
            path = self.path.text()  #
            name = self.modelNameLineEdit.text()
            if fileFormat == 'python':
                fileFormat = 'pkl'
                self.model.to_file(os.path.join(path, name + "." + fileFormat))
                with open(os.path.join(path, name + "." + 'py'), 'w') as f:
                    f.write(f"from loopstructural import GeologicalModel\n")
                    f.write(f"model = GeologicalModel.from_file('{name + '.' + fileFormat}')\n")
                return

            self.model.save(
                filename=os.path.join(path, name + "." + fileFormat),
                block_model=self.blockModelCheckBox.isChecked(),
                stratigraphic_surfaces=self.stratigraphicSurfacesCheckBox.isChecked(),
                fault_surfaces=self.faultSurfacesCheckBox.isChecked(),
                stratigraphic_data=self.stratigraphicDataCheckBox.isChecked(),
                fault_data=self.faultDataCheckBox.isChecked(),
            )
            self.logger(message=f"Model saved to {path}", log_level=0, push=True)
        except Exception as e:
            self.logger(
                message=str(e),
                log_level=2,
                push=True,
            )

    def saveThicknessOrder(self):
        pass
        # if self._units is None:
        #     self.logger(message="No units found", log_level=2, push=True)
        #     return
        # self.project.writeEntry(
        #     "LoopStructural", "units", json.dumps(self._units)
        # )
        # layer = self.basalContactsLayer.currentLayer()
        # layer.startEditing()
        # field_names = ["_ls_th", "_ls_or", "_ls_col"]
        # field_types = [QVariant.Double, QVariant.Int, QVariant.String]
        # for field_name, field_type in zip(field_names, field_types):

        #     if field_name not in [field.name() for field in layer.fields()]:
        #         layer.dataProvider().addAttributes([QgsField(field_name, field_type)])
        #         layer.updateFields()
        # for unit, value in self._units.items():
        #     for feature in layer.getFeatures():
        #         if feature.attributeMap().get(self.unitNameField.currentField()) == unit:
        #             feature[field_names[0]] = value['thickness']
        #             feature[field_names[1]] = value['order']
        #             feature[field_names[2]] = value['colour']
        #             layer.updateFeature(feature)
        # layer.commitChanges()
        # layer.updateFields()
        # self.logger(
        #     message=f"Thickness, colour and order saved to {layer.name()}", log_level=0, push=True
        # )

    def onPathTextChanged(self, text):
        self.outputPath = text

    def onClickPath(self):
        self.outputPath = QFileDialog.getExistingDirectory(None, "Select output path for model")

        self.path.setText(self.outputPath)
        # if self.path:
        #     if os.path.exists(self.gridDirectory):
        #         self.output_directory = os.path.split(
        #             self.dlg.lineEdit_gridOutputDir.text()
        #         )[-1]
