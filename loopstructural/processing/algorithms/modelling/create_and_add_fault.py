"""
Processing algorithm to load a geological model (pickle), add a fault using trace/orientation point layers
or explicit geometric parameters (centre, axes, orientation), and save the updated model back to a pickle file.

Inputs:
- MODEL_FILE_IN: path to an existing pickle file containing a GeologicalModel instance
- FAULT_NAME: name for the fault to create
- TRACE: optional line/point layer describing the fault trace; sampled to points
- NAME_FIELD: optional (not required) - feature id or name can be used
- DIP_FIELD / DISPLACEMENT_FIELD / PITCH_FIELD: optional fields on TRACE for dip, displacement and pitch
- CENTRE_X / CENTRE_Y / CENTRE_Z: optional numeric values defining fault centre
- MAJOR_AXIS / MINOR_AXIS / INTERMEDIATE_AXIS: optional numeric axis lengths
- STRIKE / DIP / PITCH: numeric orientation angles (degrees) for explicit geometry
- DISPLACEMENT: numeric displacement for explicit geometry
- NELEMENTS/NPW/CPW/REGULARISATION: optional numeric interpolator settings

Output:
- MODEL_FILE_OUT: path to a pickle file containing the updated model
"""

from typing import Any, Optional
import tempfile
import dill as pickle
import pandas as pd

from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingContext,
    QgsProcessingException,
    QgsProcessingFeedback,
    QgsProcessingParameterFile,
    QgsProcessingParameterFileDestination,
    QgsProcessingParameterString,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsProcessingParameterNumber,
    QgsProcessingParameterDefinition,
)

from loopstructural.toolbelt.preferences import PlgOptionsManager
from loopstructural.main.vectorLayerWrapper import qgsLayerToGeoDataFrame
from loopstructural.main.samplers import AllSampler
from loopstructural.main.utils import process_gdf_for_faults
class CreateAndAddFaultAlgorithm(QgsProcessingAlgorithm):
    """Load model from pickle, add fault from supplied trace/orientation layers or explicit geometry, save updated model.
    """

    MODEL_FILE_IN = "MODEL_FILE_IN"
    FAULT_NAME = "FAULT_NAME"
    TRACE = "TRACE"
    NAME_FIELD = "NAME_FIELD"
    DIP_FIELD = "DIP_FIELD"
    DISPLACEMENT_FIELD = "DISPLACEMENT_FIELD"
    PITCH_FIELD = "PITCH_FIELD"



    NELEMENTS = "NELEMENTS"
    NPW = "NPW"
    CPW = "CPW"
    REGULARISATION = "REGULARISATION"

    MODEL_FILE_OUT = "MODEL_FILE_OUT"

    def name(self) -> str:
        return "loopstructural:create_and_add_fault"

    def displayName(self) -> str:
        return "Loop3d: Create and Add Fault"

    def group(self) -> str:
        return "Loop3d"

    def groupId(self) -> str:
        return "loop3d"

    def initAlgorithm(self, config: Optional[dict[str, Any]] = None) -> None:
        # input model pickle
        opts = PlgOptionsManager.get_plg_settings()

        self.addParameter(
            QgsProcessingParameterFile(
                self.MODEL_FILE_IN,
                "Input model file (pickle)",
                behavior=QgsProcessingParameterFile.File,
                fileFilter='Pickle files (*.pkl)'
            )
        )

        # trace / trace attributes
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.TRACE,
                "Fault trace (line or point layer)",
                [QgsProcessing.TypeVectorAnyGeometry],
            )
        )

        self.addParameter(
            QgsProcessingParameterField(
                self.NAME_FIELD,
                "Name / id field (optional)",
                parentLayerParameterName=self.TRACE,
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterField(
                self.DIP_FIELD,
                "Dip field (degrees)",
                parentLayerParameterName=self.TRACE,
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterField(
                self.DISPLACEMENT_FIELD,
                "Displacement field",
                parentLayerParameterName=self.TRACE,
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterField(
                self.PITCH_FIELD,
                "Pitch field (degrees)",
                parentLayerParameterName=self.TRACE,
                optional=True,
            )
        )

        
        # make numeric interpolator parameters advanced
        param_ne = QgsProcessingParameterNumber(self.NELEMENTS, "nelements", type=QgsProcessingParameterNumber.Integer, optional=True, defaultValue=opts.interpolator_nelements)
        param_ne.setFlags(QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param_ne)

        param_npw = QgsProcessingParameterNumber(self.NPW, "npw", type=QgsProcessingParameterNumber.Integer, optional=True, defaultValue=opts.interpolator_npw)
        param_npw.setFlags(QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param_npw)

        param_cpw = QgsProcessingParameterNumber(self.CPW, "cpw", type=QgsProcessingParameterNumber.Integer, optional=True, defaultValue=opts.interpolator_cpw)
        param_cpw.setFlags(QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param_cpw)

        param_reg = QgsProcessingParameterNumber(self.REGULARISATION, "regularisation", type=QgsProcessingParameterNumber.Double, optional=True, defaultValue=opts.interpolator_regularisation)
        param_reg.setFlags(QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param_reg)

        # output model pickle
        self.addParameter(
            QgsProcessingParameterFileDestination(
                self.MODEL_FILE_OUT,
                "Output model file (pickle)",
                fileFilter='Pickle files (*.pkl)'
            )
        )

 

    def processAlgorithm(
        self,
        parameters: dict[str, Any],
        context: QgsProcessingContext,
        feedback: QgsProcessingFeedback,
    ) -> dict[str, Any]:
        # load input model
        in_model_path = self.parameterAsString(parameters, self.MODEL_FILE_IN, context)
        if not in_model_path:
            raise QgsProcessingException("Input model file must be provided.")
        try:
            with open(in_model_path, "rb") as fh:
                model = pickle.load(fh)
        except Exception as e:
            raise QgsProcessingException(f"Failed to load model from '{in_model_path}': {e}")

        

        trace_src = self.parameterAsSource(parameters, self.TRACE, context)
        # get field selections
        name_field = None
        nf = self.parameterAsFields(parameters, self.NAME_FIELD, context)
        if nf:
            name_field = nf[0] if isinstance(nf, (list, tuple)) and len(nf) > 0 else nf
        dip_field = None
        df = self.parameterAsFields(parameters, self.DIP_FIELD, context)
        if df:
            dip_field = df[0] if isinstance(df, (list, tuple)) and len(df) > 0 else df
        disp_field = None
        dpf = self.parameterAsFields(parameters, self.DISPLACEMENT_FIELD, context)
        if dpf:
            disp_field = dpf[0] if isinstance(dpf, (list, tuple)) and len(dpf) > 0 else dpf
        pitch_field = None
        pf = self.parameterAsFields(parameters, self.PITCH_FIELD, context)
        if pf:
            pitch_field = pf[0] if isinstance(pf, (list, tuple)) and len(pf) > 0 else pf

        

        nelements = self.parameterAsInt(parameters, self.NELEMENTS, context) if parameters.get(self.NELEMENTS) is not None else None
        npw = self.parameterAsInt(parameters, self.NPW, context) if parameters.get(self.NPW) is not None else None
        cpw = self.parameterAsInt(parameters, self.CPW, context) if parameters.get(self.CPW) is not None else None
        regularisation = self.parameterAsDouble(parameters, self.REGULARISATION, context) if parameters.get(self.REGULARISATION) is not None else None

        data = None
        geodataframe = qgsLayerToGeoDataFrame(trace_src) if trace_src is not None else None
        if geodataframe is not None:
            geodataframe, cols = process_gdf_for_faults(
                fault_trace=geodataframe,
                sampler=AllSampler(),
                dem_function=lambda x,y: 0,
                use_z_coordinate=False,
                fault_name_field=name_field,
                fault_dip_field=dip_field,
                fault_displacement_field=disp_field,
                fault_pitch_field=pitch_field,
            )
            print(f"Extracted {len(geodataframe)} fault points from trace layer")

    
        # call model.create_and_add_fault
        try:
            kwargs = {}
            
            if nelements is not None:
                kwargs['nelements'] = nelements
            if npw is not None:
                kwargs['npw'] = npw
            if cpw is not None:
                kwargs['cpw'] = cpw
            if regularisation is not None:
                kwargs['regularisation'] = regularisation
            for fname in geodataframe['fault_name'].unique():
                kwargs['data'] = geodataframe.loc[geodataframe['fault_name'] == fname,cols]
                kwargs['fault_name'] = fname
                if 'displacement' not in kwargs:
                    kwargs['displacement'] = 1.
                print(f"Creating fault '{fname}' with parameters: {kwargs}")

                # model.create_and_add_fault(**kwargs)

                print(f"Finished creating faults for {fname}")  
        except TypeError as e:
            # pass through a helpful message if the underlying function signature doesn't match
            raise QgsProcessingException(f"Failed to create and add fault (signature mismatch): {e}")
        except Exception as e:
            raise QgsProcessingException(f"Failed to create and add fault: {e}")

        # determine output path
        out_path = self.parameterAsString(parameters, self.MODEL_FILE_OUT, context)
        if not out_path:
            tmp = tempfile.NamedTemporaryFile(suffix='.pkl', delete=False)
            out_path = tmp.name
            tmp.close()

        try:
            with open(out_path, 'wb') as fh:
                pickle.dump(model, fh)
        except Exception as e:
            raise QgsProcessingException(f"Failed to save updated model to '{out_path}': {e}")

        return {self.MODEL_FILE_OUT: out_path}

    def createInstance(self) -> QgsProcessingAlgorithm:
        return self.__class__()
