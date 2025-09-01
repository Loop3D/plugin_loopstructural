from typing import Any, Optional
import tempfile
import dill as pickle

from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingContext,
    QgsProcessingException,
    QgsProcessingFeedback,
    QgsProcessingParameterFile,
    QgsProcessingParameterFileDestination,
    QgsProcessingParameterString,
)

try:
    from LoopStructural import FaultTopology
    from LoopStructural.modelling.core.fault_topology import FaultRelationshipType
except Exception:
    FaultTopology = None
    FaultRelationshipType = None


class AddFaultTopologyAlgorithm(QgsProcessingAlgorithm):
    """Processing algorithm to add/initialise a FaultTopology on a saved model pickle

    The user supplies a comma or newline separated list of fault pairs using '->' to
    indicate an abutting relationship. Example:
        fault1->fault2,fault2->fault3

    This will add faults (if not already present) to the topology and set the
    relationship FaultRelationshipType.ABUTTING for each pair. The resulting
    FaultTopology object is attached to the model as `fault_topology` and the
    updated model is written to the output pickle.
    """

    MODEL_FILE_IN = "MODEL_FILE_IN"
    FAULT_PAIRS = "FAULT_PAIRS"
    MODEL_FILE_OUT = "MODEL_FILE_OUT"

    def name(self) -> str:
        return "loopstructural:add_fault_topology"

    def displayName(self) -> str:
        return "Loop3d: Add Fault Topology"

    def group(self) -> str:
        return "Loop3d"

    def groupId(self) -> str:
        return "loop3d"

    def initAlgorithm(self, config: Optional[dict[str, Any]] = None) -> None:
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
                self.FAULT_PAIRS,
                "Fault pairs (use '->' between faults, comma or newline separated)",
                optional=False,
            )
        )

        self.addParameter(
            QgsProcessingParameterFileDestination(
                self.MODEL_FILE_OUT,
                "Output model file (pickle)",
                fileFilter='Pickle files (*.pkl)'
            )
        )

    def _parse_pairs(self, text: str):
        """Parse user input text into list of (f1, f2) pairs."""
        if not text:
            return []
        pairs = []
        # split on commas or newlines
        tokens = [t.strip() for t in text.replace('\n', ',').split(',') if t.strip()]
        for token in tokens:
            if '->' in token:
                a, b = token.split('->', 1)
            elif '>' in token:
                a, b = token.split('>', 1)
            elif ':' in token:
                a, b = token.split(':', 1)
            else:
                # cannot parse token
                continue
            a = a.strip()
            b = b.strip()
            if a and b:
                pairs.append((a, b))
        return pairs

    def _collect_model_fault_names(self, model):
        """Attempt to collect fault/feature names from the model in a robust way."""
        names = []
        # try feature_name_index first
        try:
            idx = getattr(model, 'feature_name_index', None)
            if isinstance(idx, dict):
                names = list(idx.keys())
                return names
        except Exception:
            pass

        # try features property
        try:
            feats = getattr(model, 'features', None)
            if feats is not None:
                for f in feats:
                    try:
                        n = getattr(f, 'name', None)
                        if callable(n):
                            n = n()
                        if n is None:
                            n = getattr(f, 'feature_name', None)
                        if n is None:
                            n = getattr(f, 'label', None)
                        if n is None:
                            # fallback to str
                            n = str(f)
                        names.append(n)
                    except Exception:
                        continue
                return names
        except Exception:
            pass

        # last resort: try iterating attributes that look like features
        try:
            for attr in dir(model):
                if attr.lower().startswith('fault') or attr.lower().endswith('_features'):
                    val = getattr(model, attr)
                    if isinstance(val, (list, tuple)):
                        for f in val:
                            try:
                                n = getattr(f, 'name', None) or getattr(f, 'feature_name', None) or str(f)
                                names.append(n)
                            except Exception:
                                continue
            return list(dict.fromkeys(names))
        except Exception:
            return []

    def processAlgorithm(
        self,
        parameters: dict[str, Any],
        context: QgsProcessingContext,
        feedback: QgsProcessingFeedback,
    ) -> dict[str, Any]:
        if FaultTopology is None or FaultRelationshipType is None:
            raise QgsProcessingException("LoopStructural FaultTopology classes are not available in the environment.")

        in_model_path = self.parameterAsString(parameters, self.MODEL_FILE_IN, context)
        if not in_model_path:
            raise QgsProcessingException("Input model file must be provided.")

        try:
            with open(in_model_path, 'rb') as fh:
                model = pickle.load(fh)
        except Exception as e:
            raise QgsProcessingException(f"Failed to load model from '{in_model_path}': {e}")

        # build fault topology using model stratigraphic column if available
        strat_col = getattr(model, 'stratigraphic_column', None)
        try:
            ft = FaultTopology(strat_col)
        except Exception:
            # try without stratigraphic column
            ft = FaultTopology(None)

        # initialise with faults found in the model
        model_faults = self._collect_model_fault_names(model)
        for fname in model_faults:
            try:
                ft.add_fault(fname)
            except Exception:
                # best effort, continue
                continue

        # parse user supplied pairs
        pairs_text = self.parameterAsString(parameters, self.FAULT_PAIRS, context)
        pairs = self._parse_pairs(pairs_text)

        for a, b in pairs:
            try:
                # ensure faults exist in topology
                if a not in ft.faults:
                    raise Exception(f"Fault '{a}' not found in model")
                if b not in ft.faults:
                    raise Exception(f"Fault '{b}' not found in model")
                # set relationship to ABUTTING
                ft.update_fault_relationship(a, b, FaultRelationshipType.ABUTTING)
            except Exception as e:
                feedback.pushInfo(f"Failed to set relationship for pair {a}->{b}: {e}")

        # attach topology to model (try common attribute names)
        try:
            setattr(model, 'fault_topology', ft)
        except Exception:
            pass
        try:
            setattr(model, '_fault_topology', ft)
        except Exception:
            pass

        # write output
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
