"""Paint stratigraphic order onto geology polygons.

This algorithm allows the user to paint stratigraphic order (0-N where 0 is youngest)
or cumulative thickness onto polygon features based on a stratigraphic column.
"""

from typing import Any, Optional

from PyQt5.QtCore import QVariant
from qgis.core import (
    QgsFeature,
    QgsFeatureSink,
    QgsField,
    QgsFields,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingContext,
    QgsProcessingException,
    QgsProcessingFeedback,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsWkbTypes,
)


class PaintStratigraphicOrderAlgorithm(QgsProcessingAlgorithm):
    """Algorithm to paint stratigraphic order or cumulative thickness onto geology polygons.
    
    This algorithm takes a polygon layer with unit names and a stratigraphic column,
    then adds fields for:
    - Stratigraphic order (0 = youngest, N = oldest)
    - Cumulative thickness (from bottom unit)
    - Group index (for handling unconformities)
    """

    # Parameter names
    INPUT_POLYGONS = "INPUT_POLYGONS"
    UNIT_NAME_FIELD = "UNIT_NAME_FIELD"
    INPUT_STRAT_COLUMN = "INPUT_STRAT_COLUMN"
    STRAT_UNIT_NAME_FIELD = "STRAT_UNIT_NAME_FIELD"
    STRAT_THICKNESS_FIELD = "STRAT_THICKNESS_FIELD"
    PAINT_MODE = "PAINT_MODE"
    OUTPUT = "OUTPUT"

    def name(self) -> str:
        """Algorithm name."""
        return "paint_stratigraphic_order"

    def displayName(self) -> str:
        """Display name for the algorithm."""
        return "Paint Stratigraphic Order"

    def group(self) -> str:
        """Group name."""
        return "Stratigraphy"

    def groupId(self) -> str:
        """Group ID."""
        return "stratigraphy"

    def shortHelpString(self) -> str:
        """Short help string."""
        return """
        Paint stratigraphic order or cumulative thickness onto geology polygons.
        
        This tool matches unit names from a polygon layer with a stratigraphic column
        and adds fields for:
        - Stratigraphic order (0 = youngest, N = oldest)
        - Cumulative thickness (starting from the bottom unit)
        - Group index (breaks at unconformities)
        
        Parameters:
        - Input Polygons: Polygon layer with geological units
        - Unit Name Field: Field in the polygon layer containing unit names
        - Stratigraphic Column: Table/layer with ordered stratigraphic units
        - Strat Unit Name Field: Field in the stratigraphic column with unit names
        - Strat Thickness Field: Field in the stratigraphic column with thickness values
        - Paint Mode: Choose between painting order or cumulative thickness
        """

    def initAlgorithm(self, config: Optional[dict[str, Any]] = None) -> None:
        """Initialize algorithm parameters."""
        
        # Input polygon layer
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT_POLYGONS,
                "Input Polygons (Geology)",
                [QgsProcessing.TypeVectorPolygon],
            )
        )

        # Unit name field in polygon layer
        self.addParameter(
            QgsProcessingParameterField(
                self.UNIT_NAME_FIELD,
                "Unit Name Field",
                parentLayerParameterName=self.INPUT_POLYGONS,
                type=QgsProcessingParameterField.String,
                defaultValue="UNITNAME",
            )
        )

        # Stratigraphic column table/layer
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT_STRAT_COLUMN,
                "Stratigraphic Column",
                [QgsProcessing.TypeVector],
            )
        )

        # Unit name field in stratigraphic column
        self.addParameter(
            QgsProcessingParameterField(
                self.STRAT_UNIT_NAME_FIELD,
                "Stratigraphic Column Unit Name Field",
                parentLayerParameterName=self.INPUT_STRAT_COLUMN,
                type=QgsProcessingParameterField.String,
                defaultValue="unit_name",
            )
        )

        # Thickness field in stratigraphic column
        self.addParameter(
            QgsProcessingParameterField(
                self.STRAT_THICKNESS_FIELD,
                "Stratigraphic Column Thickness Field",
                parentLayerParameterName=self.INPUT_STRAT_COLUMN,
                type=QgsProcessingParameterField.Numeric,
                defaultValue="thickness",
                optional=True,
            )
        )

        # Paint mode: order or cumulative thickness
        self.addParameter(
            QgsProcessingParameterEnum(
                self.PAINT_MODE,
                "Paint Mode",
                options=["Stratigraphic Order (0=youngest)", "Cumulative Thickness"],
                defaultValue=0,
            )
        )

        # Output layer
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                "Output Layer",
            )
        )

    def processAlgorithm(
        self,
        parameters: dict[str, Any],
        context: QgsProcessingContext,
        feedback: QgsProcessingFeedback,
    ) -> dict[str, Any]:
        """Process the algorithm."""
        
        # Get parameters
        polygon_source = self.parameterAsSource(parameters, self.INPUT_POLYGONS, context)
        unit_name_field = self.parameterAsString(parameters, self.UNIT_NAME_FIELD, context)
        
        strat_column_source = self.parameterAsSource(parameters, self.INPUT_STRAT_COLUMN, context)
        strat_unit_field = self.parameterAsString(parameters, self.STRAT_UNIT_NAME_FIELD, context)
        strat_thickness_field = self.parameterAsString(parameters, self.STRAT_THICKNESS_FIELD, context)
        
        paint_mode = self.parameterAsEnum(parameters, self.PAINT_MODE, context)

        if not polygon_source:
            raise QgsProcessingException("Invalid input polygon layer")
        
        if not strat_column_source:
            raise QgsProcessingException("Invalid stratigraphic column layer")

        # Read stratigraphic column and build lookup
        feedback.pushInfo("Reading stratigraphic column...")
        strat_order = []
        strat_thickness_map = {}
        
        for feature in strat_column_source.getFeatures():
            unit_name = feature[strat_unit_field]
            if unit_name:
                strat_order.append(unit_name)
                if strat_thickness_field:
                    thickness = feature[strat_thickness_field]
                    try:
                        strat_thickness_map[unit_name] = float(thickness) if thickness is not None else 0.0
                    except (ValueError, TypeError):
                        strat_thickness_map[unit_name] = 0.0
                else:
                    strat_thickness_map[unit_name] = 0.0

        if not strat_order:
            raise QgsProcessingException("Stratigraphic column is empty")

        feedback.pushInfo(f"Found {len(strat_order)} units in stratigraphic column")

        # Build order lookup (0 = youngest, which is at the top of the list)
        # In stratigraphic column, youngest is typically first
        order_lookup = {name: idx for idx, name in enumerate(strat_order)}
        
        # Calculate cumulative thickness from bottom (oldest) to top (youngest)
        # Reverse the order for thickness calculation
        cumulative_thickness = {}
        total_thickness = 0.0
        for unit_name in reversed(strat_order):
            cumulative_thickness[unit_name] = total_thickness
            total_thickness += strat_thickness_map.get(unit_name, 0.0)

        feedback.pushInfo(f"Total stratigraphic thickness: {total_thickness}")

        # Prepare output fields
        output_fields = QgsFields(polygon_source.fields())
        
        if paint_mode == 0:  # Stratigraphic Order
            output_fields.append(QgsField("strat_order", QVariant.Int))
        else:  # Cumulative Thickness
            output_fields.append(QgsField("cum_thickness", QVariant.Double))

        # Create sink
        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            output_fields,
            polygon_source.wkbType(),
            polygon_source.sourceCrs(),
        )

        if sink is None:
            raise QgsProcessingException("Could not create output layer")

        # Process features
        total = 100.0 / polygon_source.featureCount() if polygon_source.featureCount() else 0
        matched_count = 0
        unmatched_count = 0
        
        feedback.pushInfo("Processing polygons...")
        
        for current, feature in enumerate(polygon_source.getFeatures()):
            if feedback.isCanceled():
                break

            # Create output feature
            out_feature = QgsFeature(output_fields)
            out_feature.setGeometry(feature.geometry())
            
            # Copy existing attributes
            for i, field in enumerate(polygon_source.fields()):
                out_feature.setAttribute(field.name(), feature.attribute(field.name()))

            # Get unit name from polygon
            unit_name = feature[unit_name_field]
            
            if unit_name in order_lookup:
                matched_count += 1
                if paint_mode == 0:  # Paint stratigraphic order
                    out_feature.setAttribute("strat_order", order_lookup[unit_name])
                else:  # Paint cumulative thickness
                    out_feature.setAttribute("cum_thickness", cumulative_thickness[unit_name])
            else:
                unmatched_count += 1
                # Set null/default value for unmatched units
                if paint_mode == 0:
                    out_feature.setAttribute("strat_order", None)
                else:
                    out_feature.setAttribute("cum_thickness", None)
                    
                if unmatched_count <= 10:  # Only show first 10 warnings
                    feedback.pushWarning(f"Unit '{unit_name}' not found in stratigraphic column")

            sink.addFeature(out_feature, QgsFeatureSink.FastInsert)
            feedback.setProgress(int(current * total))

        feedback.pushInfo(f"\nProcessing complete:")
        feedback.pushInfo(f"  Matched units: {matched_count}")
        feedback.pushInfo(f"  Unmatched units: {unmatched_count}")

        return {self.OUTPUT: dest_id}

    def createInstance(self) -> QgsProcessingAlgorithm:
        """Create a new instance of the algorithm."""
        return PaintStratigraphicOrderAlgorithm()
