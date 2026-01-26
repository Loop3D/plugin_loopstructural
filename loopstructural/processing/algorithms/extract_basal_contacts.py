"""
***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

# Python imports
from typing import Any, Optional

# QGIS imports
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingContext,
    QgsProcessingException,
    QgsProcessingFeedback,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsProcessingParameterMapLayer,
    QgsProcessingParameterMatrix,
    QgsSettings,
)

from ...main.m2l_api import extract_basal_contacts

# Internal imports
from ...main.vectorLayerWrapper import GeoDataFrameToQgsLayer


class BasalContactsAlgorithm(QgsProcessingAlgorithm):
    """Processing algorithm to create basal contacts."""

    INPUT_GEOLOGY = 'GEOLOGY'
    INPUT_FAULTS = 'FAULTS'
    INPUT_STRATI_COLUMN = 'STRATIGRAPHIC_COLUMN'
    INPUT_IGNORE_UNITS = 'IGNORE_UNITS'
    OUTPUT = "BASAL_CONTACTS"
    ALL_CONTACTS = "ALL_CONTACTS"

    def name(self) -> str:
        """Return the algorithm name."""
        return "basal_contacts"

    def displayName(self) -> str:
        """Return the algorithm display name."""
        return "Basal Contacts"

    def group(self) -> str:
        """Return the algorithm group name."""
        return "Contact Extractors"

    def groupId(self) -> str:
        """Return the algorithm group ID."""
        return "Contact_Extractors"

    def initAlgorithm(self, config: Optional[dict[str, Any]] = None) -> None:
        """Initialize the algorithm parameters."""

        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT_GEOLOGY,
                "GEOLOGY",
                [QgsProcessing.TypeVectorPolygon],
            )
        )
        self.addParameter(
            QgsProcessingParameterField(
                'UNIT_NAME_FIELD',
                'Unit Name Field',
                parentLayerParameterName=self.INPUT_GEOLOGY,
                type=QgsProcessingParameterField.String,
                defaultValue='unitname',
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT_FAULTS,
                "FAULTS",
                [QgsProcessing.TypeVectorLine],
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT_STRATI_COLUMN,
                "Stratigraphic Order",
                [QgsProcessing.TypeVector],
                defaultValue='formation',
            )
        )
        ignore_settings = QgsSettings()
        last_ignore_units = ignore_settings.value("m2l/ignore_units", "")
        self.addParameter(
            QgsProcessingParameterMatrix(
                self.INPUT_IGNORE_UNITS,
                "Unit(s) to ignore",
                headers=["Unit"],
                defaultValue=last_ignore_units,
                optional=True,
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                "Basal Contacts",
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSink(
                "ALL_CONTACTS",
                "All Contacts",
            )
        )

    def processAlgorithm(
        self,
        parameters: dict[str, Any],
        context: QgsProcessingContext,
        feedback: QgsProcessingFeedback,
    ) -> dict[str, Any]:

        feedback.pushInfo("Loading data...")
        geology = self.parameterAsVectorLayer(parameters, self.INPUT_GEOLOGY, context)
        faults = self.parameterAsVectorLayer(parameters, self.INPUT_FAULTS, context)
        strati_column = self.parameterAsSource(parameters, self.INPUT_STRATI_COLUMN, context)
        # ensure we always have a stratigraphic order list defined
        strati_order = []
        ignore_units = self.parameterAsMatrix(parameters, self.INPUT_IGNORE_UNITS, context)

        if isinstance(strati_column, QgsProcessingParameterMapLayer):
            raise QgsProcessingException("Invalid stratigraphic column layer")

        elif strati_column is not None:
            # extract unit names from strati_column
            field_name = "unit_name"
            strati_order = [f[field_name] for f in strati_column.getFeatures()]

        if not ignore_units or all(
            isinstance(unit, str) and not unit.strip() for unit in ignore_units
        ):
            feedback.pushInfo("no units to ignore specified")

        ignore_settings = QgsSettings()
        ignore_settings.setValue("m2l/ignore_units", ignore_units)

        unit_name_field = self.parameterAsString(parameters, 'UNIT_NAME_FIELD', context)

        # request all_contacts so the returned result contains both basal and all contacts
        result = extract_basal_contacts(
            geology=geology,
            stratigraphic_order=strati_order,
            faults=faults,
            ignore_units=ignore_units,
            unit_name_field=unit_name_field,
            all_contacts=True,
            updater=feedback.pushInfo,
        )
        basal_contacts = result['basal_contacts']
        all_contacts = result['all_contacts']
        feedback.pushInfo("Exporting Basal Contacts Layer...")
        basal_contacts = GeoDataFrameToQgsLayer(
            self,
            basal_contacts,
            parameters=parameters,
            context=context,
            output_key=self.OUTPUT,
            feedback=feedback,
        )
        contacts_layer = GeoDataFrameToQgsLayer(
            self,
            all_contacts,
            parameters=parameters,
            context=context,
            output_key=self.ALL_CONTACTS,
            feedback=feedback,
        )
        return {self.OUTPUT: basal_contacts, self.ALL_CONTACTS: contacts_layer}

    def createInstance(self) -> QgsProcessingAlgorithm:
        """Create a new instance of the algorithm."""
        return self.__class__()  # BasalContactsAlgorithm()
