"""
Processing algorithm to create a LoopStructural geological model from a bounding box JSON.

Inputs:
- BBOX_JSON: a JSON string describing the bounding box. Accepts either:
  - {'origin': [xmin, ymin, zmin], 'maximum': [xmax, ymax, zmax]}
  - or {'xmin':..., 'xmax':..., 'ymin':..., 'ymax':..., 'zmin':..., 'zmax':...}

Output:
- MODEL_FILE: path to a temporary pickle file containing the created GeologicalModel instance.

The saved pickle file can be used by downstream processing tools which expect a serialized model.
"""

from typing import Any, Optional
import json
import tempfile
import dill as pickle

from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingContext,
    QgsProcessingException,
    QgsProcessingFeedback,
    QgsProcessingParameterString,
    QgsProcessingParameterFileDestination,
)

# LoopStructural / plugin imports
from LoopStructural.datatypes import BoundingBox
from LoopStructural import GeologicalModel


class CreateModelAlgorithm(QgsProcessingAlgorithm):
    """Create a LoopStructural geological model from a bounding box JSON."""

    BBOX_JSON = "BBOX_JSON"
    MODEL_FILE = "MODEL_FILE"

    def name(self) -> str:
        return "loopstructural:create_model"

    def displayName(self) -> str:
        return "Loop3d: Create Geological Model"

    def group(self) -> str:
        return "Loop3d"

    def groupId(self) -> str:
        return "loop3d"

    def initAlgorithm(self, config: Optional[dict[str, Any]] = None) -> None:
        # bounding box json input (string)
        self.addParameter(
            QgsProcessingParameterString(
                self.BBOX_JSON,
                "Bounding Box (JSON)",
                defaultValue="",
                optional=False,
            )
        )

        # output: path to pickle file containing the created model
        self.addParameter(
            QgsProcessingParameterFileDestination(
                self.MODEL_FILE,
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
        bbox_json = self.parameterAsString(parameters, self.BBOX_JSON, context)

        if not bbox_json:
            raise QgsProcessingException("Bounding box JSON must be provided.")

        try:
            bbox_obj = json.loads(bbox_json)
        except Exception as e:
            raise QgsProcessingException(f"Failed to parse bounding box JSON: {e}")

        # Accept either {'origin': [...], 'maximum': [...]} or xmin/xmax style dict
        origin = None
        maximum = None
        if isinstance(bbox_obj, dict):
            if "origin" in bbox_obj and "maximum" in bbox_obj:
                origin = bbox_obj["origin"]
                maximum = bbox_obj["maximum"]
            elif all(k in bbox_obj for k in ("xmin", "xmax", "ymin", "ymax", "zmin", "zmax")):
                origin = [bbox_obj["xmin"], bbox_obj["ymin"], bbox_obj["zmin"]]
                maximum = [bbox_obj["xmax"], bbox_obj["ymax"], bbox_obj["zmax"]]
            else:
                raise QgsProcessingException(
                    "Bounding box JSON must contain either 'origin' and 'maximum' arrays or xmin/xmax/ymin/ymax/zmin/zmax keys"
                )
        else:
            raise QgsProcessingException("Bounding box JSON must be a JSON object/dict.")

        try:
            bbox = BoundingBox(origin=origin, maximum=maximum)
        except Exception as e:
            raise QgsProcessingException(f"Failed to create BoundingBox: {e}")

        # create model manager and update bounding box
        try:
            model = GeologicalModel(bbox)
            print(model.bounding_box)
        except Exception as e:
            raise QgsProcessingException(f"Failed to create geological model: {e}")

        # determine output path: use user-provided destination if given, otherwise create a temp file
        out_path = self.parameterAsString(parameters, self.MODEL_FILE, context)
        if not out_path:
            tmp = tempfile.NamedTemporaryFile(suffix=".pkl", delete=False)
            out_path = tmp.name
            tmp.close()

        try:
            with open(out_path, "wb") as fh:
                pickle.dump(model, fh)
        except Exception as e:
            raise QgsProcessingException(f"Failed to save model to file '{out_path}': {e}")

        return {self.MODEL_FILE: out_path}

    def createInstance(self) -> QgsProcessingAlgorithm:
        return self.__class__()
