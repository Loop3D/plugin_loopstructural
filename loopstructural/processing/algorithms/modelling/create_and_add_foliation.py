"""
Processing algorithm to load a geological model (pickle), add a foliation using value and gradient point layers,
and save the updated model back to a pickle file.

Inputs:
- MODEL_FILE_IN: path to an existing pickle file containing a GeologicalModel instance
- FOLIATION_NAME: name for the foliation to create
- VALUE: point layer containing value points (optional)
- VALUE_FIELD: field name in VALUE layer containing numeric values
- GRADIENT: point layer containing orientation points (optional)
- STRIKE_FIELD: strike field name in GRADIENT layer
- DIP_FIELD: dip field name in GRADIENT layer
- FORCE_CONSTRAINED: whether to force constrained interpolation (boolean)
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
    QgsProcessingParameterBoolean,
    QgsProcessingParameterNumber,
    QgsProcessingParameterDefinition,
)
from loopstructural.toolbelt.preferences import PlgOptionsManager

class CreateAndAddFoliationAlgorithm(QgsProcessingAlgorithm):
    """Load model from pickle, add foliation from supplied layers, save updated model."""

    MODEL_FILE_IN = "MODEL_FILE_IN"
    FOLIATION_NAME = "FOLIATION_NAME"
    VALUE = "VALUE"
    VALUE_FIELD = "VALUE_FIELD"
    GRADIENT = "GRADIENT"
    STRIKE_FIELD = "STRIKE_FIELD"
    DIP_FIELD = "DIP_FIELD"
    FORCE_CONSTRAINED = "FORCE_CONSTRAINED"
    NELEMENTS = "NELEMENTS"
    NPW = "NPW"
    CPW = "CPW"
    REGULARISATION = "REGULARISATION"
    MODEL_FILE_OUT = "MODEL_FILE_OUT"

    def name(self) -> str:
        return "loopstructural:create_and_add_foliation"

    def displayName(self) -> str:
        return "Loop3d: Create and Add Foliation"

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

        self.addParameter(
            QgsProcessingParameterString(
                self.FOLIATION_NAME,
                "Foliation name",
                defaultValue="Foliation",
            )
        )

        # value points
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.VALUE,
                "Value points (point layer)",
                [QgsProcessing.TypeVectorPoint],
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterField(
                self.VALUE_FIELD,
                "Value field",
                parentLayerParameterName=self.VALUE,
                type=QgsProcessingParameterField.DataType.Numeric,
                optional=True,
            )
        )

        # gradient / orientation points
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.GRADIENT,
                "Gradient points (point layer)",
                [QgsProcessing.TypeVectorPoint],
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterField(
                self.STRIKE_FIELD,
                "Strike field",
                parentLayerParameterName=self.GRADIENT,
                type=QgsProcessingParameterField.DataType.Numeric,
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterField(
                self.DIP_FIELD,
                "Dip field",
                parentLayerParameterName=self.GRADIENT,
                type=QgsProcessingParameterField.DataType.Numeric,
                optional=True,
            )
        )

        # options
        
        # make numeric interpolator parameters advanced
        param_ne = QgsProcessingParameterNumber(self.NELEMENTS, "nelements", type=QgsProcessingParameterNumber.Integer, optional=True, defaultValue=opts.interpolator_nelements)
        param_ne.setFlags(QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param_ne)

        param_npw = QgsProcessingParameterNumber(self.NPW, "npw", type=QgsProcessingParameterNumber.Integer, optional=True, defaultValue=opts.interpolator_npw  )
        param_npw.setFlags(QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param_npw)

        param_cpw = QgsProcessingParameterNumber(self.CPW, "cpw", type=QgsProcessingParameterNumber.Integer, optional=True,defaultValue=opts.interpolator_cpw )
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

    def _iterate_point_source(self, source, x_attr="X"):
        """Yield tuples (x,y,z,attrs) for each point feature in the QgsFeatureSource."""
        for feat in source.getFeatures():
            geom = feat.geometry()
            if geom is None:
                continue
            # handle Point / MultiPoint
            if geom.isEmpty():
                continue
            try:
                if geom.type() == 0:  # point
                    if geom.isMultipart():
                        pts = geom.asMultiPoint()
                    else:
                        pts = [geom.asPoint()]
                else:
                    # skip non-point geometry
                    continue
            except Exception:
                # fallback: try asPoint
                try:
                    pts = [geom.asPoint()]
                except Exception:
                    continue

            for p in pts:
                # p may be QgsPointXY or QgsPoint with z
                try:
                    x = p.x()
                    y = p.y()
                    z = p.z() if hasattr(p, 'z') else 0.0
                except Exception:
                    # p could be a tuple
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

        foliation_name = self.parameterAsString(parameters, self.FOLIATION_NAME, context)
        if not foliation_name:
            foliation_name = "Foliation"

        value_src = self.parameterAsSource(parameters, self.VALUE, context)
        value_field = None
        vf = self.parameterAsFields(parameters, self.VALUE_FIELD, context)
        if vf:
            # parameterAsFields returns list or tuple
            value_field = vf[0] if isinstance(vf, (list, tuple)) and len(vf) > 0 else vf

        grad_src = self.parameterAsSource(parameters, self.GRADIENT, context)
        strike_field = None
        dip_field = None
        sf = self.parameterAsFields(parameters, self.STRIKE_FIELD, context)
        if sf:
            strike_field = sf[0] if isinstance(sf, (list, tuple)) and len(sf) > 0 else sf
        df = self.parameterAsFields(parameters, self.DIP_FIELD, context)
        if df:
            dip_field = df[0] if isinstance(df, (list, tuple)) and len(df) > 0 else df

        force_constrained = self.parameterAsBool(parameters, self.FORCE_CONSTRAINED, context)
        nelements = self.parameterAsInt(parameters, self.NELEMENTS, context) if parameters.get(self.NELEMENTS) is not None else None
        npw = self.parameterAsInt(parameters, self.NPW, context) if parameters.get(self.NPW) is not None else None
        cpw = self.parameterAsInt(parameters, self.CPW, context) if parameters.get(self.CPW) is not None else None
        regularisation = self.parameterAsDouble(parameters, self.REGULARISATION, context) if parameters.get(self.REGULARISATION) is not None else None

        dfs = []

        # build value dataframe
        if value_src is not None and value_field:
            cols = ['X', 'Y', 'Z', 'val']
            rows = []
            for feat in value_src.getFeatures():
                geom = feat.geometry()
                if geom is None or geom.isEmpty():
                    continue
                if geom.isMultipart():
                    points = geom.asMultiPoint()
                else:
                    try:
                        points = [geom.asPoint()]
                    except Exception:
                        continue
                for p in points:
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
                    try:
                        val = feat.attribute(value_field)
                    except Exception:
                        val = None
                    rows.append({'X': x, 'Y': y, 'Z': z, 'val': val, 'feature_name': foliation_name})
            if rows:
                dfs.append(pd.DataFrame(rows))

        # build gradient / orientation dataframe
        if grad_src is not None and strike_field and dip_field:
            rows = []
            for feat in grad_src.getFeatures():
                geom = feat.geometry()
                if geom is None or geom.isEmpty():
                    continue
                if geom.isMultipart():
                    points = geom.asMultiPoint()
                else:
                    try:
                        points = [geom.asPoint()]
                    except Exception:
                        continue
                for p in points:
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
                    try:
                        strike = feat.attribute(strike_field)
                    except Exception:
                        strike = None
                    try:
                        dip = feat.attribute(dip_field)
                    except Exception:
                        dip = None
                    rows.append({'X': x, 'Y': y, 'Z': z, 'strike': strike, 'dip': dip, 'feature_name': foliation_name})
            if rows:
                dfs.append(pd.DataFrame(rows))

        if len(dfs) == 0:
            raise QgsProcessingException("No valid input points found for foliation creation.")

        data = pd.concat(dfs, ignore_index=True)

        # call model.create_and_add_foliation
        try:
            # only pass optional args if provided
            kwargs = {'force_constrained': force_constrained}
            if nelements is not None:
                kwargs['nelements'] = nelements
            if npw is not None:
                kwargs['npw'] = npw
            if cpw is not None:
                kwargs['cpw'] = cpw
            if regularisation is not None:
                kwargs['regularisation'] = regularisation

            model.create_and_add_foliation(foliation_name, data=data, **kwargs)
        except Exception as e:
            raise QgsProcessingException(f"Failed to create and add foliation: {e}")

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
