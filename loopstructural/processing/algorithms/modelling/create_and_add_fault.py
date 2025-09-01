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

    CENTRE_X = "CENTRE_X"
    CENTRE_Y = "CENTRE_Y"
    CENTRE_Z = "CENTRE_Z"
    MAJOR_AXIS = "MAJOR_AXIS"
    MINOR_AXIS = "MINOR_AXIS"
    INTERMEDIATE_AXIS = "INTERMEDIATE_AXIS"
    STRIKE = "STRIKE"
    DIP = "DIP"
    PITCH = "PITCH"
    DISPLACEMENT = "DISPLACEMENT"

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
        self.addParameter(
            QgsProcessingParameterFile(
                self.MODEL_FILE_IN,
                "Input model file (pickle)",
                behavior=QgsProcessingParameterFile.File,
                fileFilter='Pickle files (*.pkl)'
            )
        )

        self.addParameter(
            QgsProcessingParameterString(
                self.FAULT_NAME,
                "Fault name",
                defaultValue="Fault",
            )
        )

        # trace / trace attributes
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.TRACE,
                "Fault trace (line or point layer)",
                [QgsProcessing.TypeVectorAnyGeometry],
                optional=True,
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

        # explicit geometry parameters
        self.addParameter(QgsProcessingParameterNumber(self.CENTRE_X, "Centre X", type=QgsProcessingParameterNumber.Double, optional=True))
        self.addParameter(QgsProcessingParameterNumber(self.CENTRE_Y, "Centre Y", type=QgsProcessingParameterNumber.Double, optional=True))
        self.addParameter(QgsProcessingParameterNumber(self.CENTRE_Z, "Centre Z", type=QgsProcessingParameterNumber.Double, optional=True))
        self.addParameter(QgsProcessingParameterNumber(self.MAJOR_AXIS, "Major axis length", type=QgsProcessingParameterNumber.Double, optional=True))
        self.addParameter(QgsProcessingParameterNumber(self.MINOR_AXIS, "Minor axis length", type=QgsProcessingParameterNumber.Double, optional=True))
        self.addParameter(QgsProcessingParameterNumber(self.INTERMEDIATE_AXIS, "Intermediate axis length", type=QgsProcessingParameterNumber.Double, optional=True))
        self.addParameter(QgsProcessingParameterNumber(self.STRIKE, "Strike (degrees)", type=QgsProcessingParameterNumber.Double, optional=True))
        self.addParameter(QgsProcessingParameterNumber(self.DIP, "Dip (degrees)", type=QgsProcessingParameterNumber.Double, optional=True))
        self.addParameter(QgsProcessingParameterNumber(self.PITCH, "Pitch (degrees)", type=QgsProcessingParameterNumber.Double, optional=True))
        self.addParameter(QgsProcessingParameterNumber(self.DISPLACEMENT, "Displacement", type=QgsProcessingParameterNumber.Double, optional=True))

        # make numeric interpolator parameters advanced
        param_ne = QgsProcessingParameterNumber(self.NELEMENTS, "nelements", type=QgsProcessingParameterNumber.Integer, optional=True)
        param_ne.setFlags(QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param_ne)

        param_npw = QgsProcessingParameterNumber(self.NPW, "npw", type=QgsProcessingParameterNumber.Integer, optional=True)
        param_npw.setFlags(QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param_npw)

        param_cpw = QgsProcessingParameterNumber(self.CPW, "cpw", type=QgsProcessingParameterNumber.Integer, optional=True)
        param_cpw.setFlags(QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param_cpw)

        param_reg = QgsProcessingParameterNumber(self.REGULARISATION, "regularisation", type=QgsProcessingParameterNumber.Double, optional=True)
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

    def _iterate_point_source(self, source):
        """Yield tuples (x,y,z,attributes,fields) for each point feature in the QgsFeatureSource."""
        for feat in source.getFeatures():
            geom = feat.geometry()
            if geom is None or geom.isEmpty():
                continue
            try:
                if geom.type() == 0:  # point
                    pts = geom.asMultiPoint() if geom.isMultipart() else [geom.asPoint()]
                else:
                    # for linestrings take vertices
                    if geom.isMultipart():
                        lines = geom.asMultiPolyline()
                    else:
                        try:
                            lines = [geom.asPolyline()]
                        except Exception:
                            lines = []
                    pts = []
                    for line in lines:
                        for coord in line:
                            # coord may be QgsPoint or tuple
                            try:
                                x = coord.x()
                                y = coord.y()
                                z = coord.z() if hasattr(coord, 'z') else 0.0
                                pts.append(type('P', (), {'x': lambda self=x: x, 'y': lambda self=y: y, 'z': lambda self=z: z})())
                            except Exception:
                                try:
                                    x, y = coord[0], coord[1]
                                    z = coord[2] if len(coord) > 2 else 0.0
                                    pts.append(type('P', (), {'x': lambda self=x: x, 'y': lambda self=y: y, 'z': lambda self=z: z})())
                                except Exception:
                                    continue
            except Exception:
                # fallback
                try:
                    pts = [geom.asPoint()]
                except Exception:
                    continue

            for p in pts:
                try:
                    x = p.x()
                    y = p.y()
                    z = p.z() if hasattr(p, 'z') else 0.0
                except Exception:
                    try:
                        x, y = p[0], p[1]
                        z = p[2] if len(p) > 2 else 0.0
                    except Exception:
                        continue
                yield x, y, z, feat.attributes(), feat.fields()

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

        fault_name = self.parameterAsString(parameters, self.FAULT_NAME, context)
        if not fault_name:
            fault_name = "Fault"

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

        # explicit numeric params
        cx = self.parameterAsDouble(parameters, self.CENTRE_X, context) if parameters.get(self.CENTRE_X) is not None else None
        cy = self.parameterAsDouble(parameters, self.CENTRE_Y, context) if parameters.get(self.CENTRE_Y) is not None else None
        cz = self.parameterAsDouble(parameters, self.CENTRE_Z, context) if parameters.get(self.CENTRE_Z) is not None else None
        major = self.parameterAsDouble(parameters, self.MAJOR_AXIS, context) if parameters.get(self.MAJOR_AXIS) is not None else None
        minor = self.parameterAsDouble(parameters, self.MINOR_AXIS, context) if parameters.get(self.MINOR_AXIS) is not None else None
        inter = self.parameterAsDouble(parameters, self.INTERMEDIATE_AXIS, context) if parameters.get(self.INTERMEDIATE_AXIS) is not None else None
        strike = self.parameterAsDouble(parameters, self.STRIKE, context) if parameters.get(self.STRIKE) is not None else None
        dip = self.parameterAsDouble(parameters, self.DIP, context) if parameters.get(self.DIP) is not None else None
        pitch = self.parameterAsDouble(parameters, self.PITCH, context) if parameters.get(self.PITCH) is not None else None
        displacement = self.parameterAsDouble(parameters, self.DISPLACEMENT, context) if parameters.get(self.DISPLACEMENT) is not None else None

        nelements = self.parameterAsInt(parameters, self.NELEMENTS, context) if parameters.get(self.NELEMENTS) is not None else None
        npw = self.parameterAsInt(parameters, self.NPW, context) if parameters.get(self.NPW) is not None else None
        cpw = self.parameterAsInt(parameters, self.CPW, context) if parameters.get(self.CPW) is not None else None
        regularisation = self.parameterAsDouble(parameters, self.REGULARISATION, context) if parameters.get(self.REGULARISATION) is not None else None

        data = None

        # build data from trace if provided
        if trace_src is not None:
            rows = []
            for x, y, z, attrs, fields in self._iterate_point_source(trace_src):
                row = {"X": x, "Y": y, "Z": z}
                # attempt to retrieve attributes by field name
                try:
                    if name_field is not None:
                        row['fault_name'] = attrs[fields.indexOf(name_field)] if fields.indexOf(name_field) >= 0 else None
                except Exception:
                    # best-effort: ignore
                    row['fault_name'] = fault_name
                try:
                    if dip_field is not None:
                        row['dip'] = attrs[fields.indexOf(dip_field)] if fields.indexOf(dip_field) >= 0 else None
                except Exception:
                    pass
                try:
                    if disp_field is not None:
                        row['displacement'] = attrs[fields.indexOf(disp_field)] if fields.indexOf(disp_field) >= 0 else None
                except Exception:
                    pass
                try:
                    if pitch_field is not None:
                        row['pitch'] = attrs[fields.indexOf(pitch_field)] if fields.indexOf(pitch_field) >= 0 else None
                except Exception:
                    pass
                row['feature_name'] = fault_name
                rows.append(row)
            if len(rows) == 0:
                raise QgsProcessingException("No valid input points found in trace for fault creation.")
            data = pd.DataFrame(rows)

        # if no trace data, try explicit geometry
        if data is None:
            if cx is None or cy is None or cz is None or major is None or minor is None:
                raise QgsProcessingException("Either a fault trace must be provided or explicit geometry (centre XYZ and at least major and minor axes) must be supplied.")

        # call model.create_and_add_fault
        try:
            kwargs = {}
            if data is not None:
                kwargs['data'] = data
            if displacement is not None:
                kwargs['displacement'] = displacement
            # model_manager sometimes passed 'fault_dip'/'fault_pitch' names
            if dip is not None:
                kwargs['fault_dip'] = dip
            if pitch is not None:
                kwargs['fault_pitch'] = pitch

            # explicit geometry
            if cx is not None and cy is not None and cz is not None:
                kwargs['centre'] = (cx, cy, cz)
            if major is not None:
                kwargs['major_axis'] = major
            if minor is not None:
                kwargs['minor_axis'] = minor
            if inter is not None:
                kwargs['intermediate_axis'] = inter
            if strike is not None:
                kwargs['strike'] = strike

            if nelements is not None:
                kwargs['nelements'] = nelements
            if npw is not None:
                kwargs['npw'] = npw
            if cpw is not None:
                kwargs['cpw'] = cpw
            if regularisation is not None:
                kwargs['regularisation'] = regularisation

            # try calling
            model.create_and_add_fault(fault_name, **kwargs)
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
