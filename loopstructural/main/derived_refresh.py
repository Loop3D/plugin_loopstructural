"""Calculate the out-of-date derived data again before a model build.

A model build must not use out-of-date basal contacts or thicknesses. This
module finds the results to calculate, reads their inputs on the GUI thread,
calculates them (on a background thread) and records the new inputs (on the
GUI thread).

The order is fixed: the basal contacts first, then the thicknesses, because
the thickness calculation reads the contacts.

With "Calculate from geology polygons", the contacts go directly to the model.
The project layer of the contacts is updated afterwards, for display only.
"""

from typing import Callable, List, Optional

from . import derived_data, layer_roles

BASAL_CONTACT_UNIT_FIELD = 'basal_unit'


class DerivedRefreshError(RuntimeError):
    """A derived result could not be calculated. The build must stop."""


def names_to_refresh(data_manager) -> List[str]:
    """Return the derived results that a build calculates, in the order of calculation.

    - Basal contacts: with "Calculate from geology polygons", when they are
      out of date, or never calculated. With "Use a contacts layer", never,
      because the layer is an input of the user.
    - Thickness: only when it is out of date. A thickness that was never
      calculated can be typed, so the build does not calculate it.

    With no units in the column (a model of faults only), nothing comes from
    the column, so the list is empty.
    """
    derived = data_manager.derived
    names = []
    if not data_manager.get_stratigraphic_unit_names():
        return names
    if (
        data_manager.layer_roles.contacts_source == layer_roles.CONTACTS_FROM_GEOLOGY
        and data_manager.get_stratigraphic_unit_names()
        and data_manager.get_layer_role(layer_roles.GEOLOGY) is not None
        and data_manager.get_layer_role(layer_roles.GEOLOGY_UNIT_FIELD)
        and derived.status(derived_data.BASAL_CONTACTS) != derived_data.CURRENT
    ):
        names.append(derived_data.BASAL_CONTACTS)
    if derived.is_out_of_date(derived_data.THICKNESS):
        names.append(derived_data.THICKNESS)
    return names


def _check_contacts_inputs(inputs):
    if not inputs.get('geology') or not inputs.get('unit_field'):
        raise DerivedRefreshError(
            "The basal contacts cannot be calculated: select the geology layer and the "
            "unit name field in step 2."
        )


class DerivedRefresh:
    """One refresh of the out-of-date derived data.

    Make the object on the GUI thread (it reads the layers and the settings).
    Call `run` on the background thread. Call `finish` on the GUI thread.
    """

    def __init__(self, data_manager, model_manager, names=None):
        self.data_manager = data_manager
        self.model_manager = model_manager
        self.names = list(names if names is not None else names_to_refresh(data_manager))
        self._contacts = None
        self._thickness = None
        self._contacts_result = None
        self._thickness_result = None
        if derived_data.BASAL_CONTACTS in self.names:
            self._contacts = self._read_contacts_job()
        if derived_data.THICKNESS in self.names:
            self._thickness = self._read_thickness_job()

    def __bool__(self):
        return bool(self.names)

    # -- the reads on the GUI thread -------------------------------------

    def _read_contacts_job(self):
        dm = self.data_manager
        settings = dm.get_widget_settings('basal_contacts_widget', {}) or {}
        geology = dm.get_layer_role(layer_roles.GEOLOGY)
        faults = (
            dm.find_layer_by_name(settings['faults_layer'])
            if settings.get('faults_layer')
            else dm.get_layer_role(layer_roles.FAULT_TRACES)
        )
        unit_field = dm.get_layer_role(layer_roles.GEOLOGY_UNIT_FIELD)
        inputs = dm.basal_contacts_inputs(
            geology=geology,
            unit_field=unit_field,
            faults=faults,
            ignore_units=settings.get('ignore_units', []),
            override_units=settings.get('basal_override_units', []),
        )
        _check_contacts_inputs(inputs)
        target_crs = dm.get_model_crs()
        if target_crs is None or not target_crs.isValid():
            target_crs = geology.crs()
        return {
            'inputs': inputs,
            'params': dict(
                geology=geology,
                stratigraphic_order=dm.get_stratigraphic_unit_names(),
                faults=faults,
                ignore_units=list(settings.get('ignore_units', [])),
                unit_name_field=unit_field,
                target_crs=target_crs,
                unit_colours=dm.get_stratigraphic_unit_colours(),
                basal_override_units=list(settings.get('basal_override_units', [])),
                debug_manager=getattr(dm, 'debug_manager', None),
            ),
        }

    def _read_thickness_job(self):
        dm = self.data_manager
        settings = dm.get_widget_settings('thickness_calculator_widget', {}) or {}
        calculator_type = settings.get('calculator_type')
        if not calculator_type:
            raise DerivedRefreshError(
                "The thicknesses are out of date, but the thickness calculator has no settings. "
                "Run Calculate thickness in step 2 one time."
            )

        def layer(key, role=None):
            name = settings.get(key)
            if name:
                return dm.find_layer_by_name(name)
            return dm.get_layer_role(role) if role else None

        geology = layer('geology_layer', layer_roles.GEOLOGY)
        structure = layer('structure_layer', layer_roles.STRUCTURE)
        cross_sections = layer('cross_sections_layer')
        unit_field = settings.get('unit_name_field') or dm.get_layer_role(
            layer_roles.GEOLOGY_UNIT_FIELD
        )
        if geology is None or not unit_field:
            raise DerivedRefreshError(
                "The thicknesses cannot be calculated: select the geology layer and the "
                "unit name field in step 2."
            )
        if calculator_type == 'StructuralPoint' and structure is None:
            raise DerivedRefreshError(
                "The thicknesses cannot be calculated: select the structure layer in step 2."
            )
        if calculator_type == 'AlongSection' and cross_sections is None:
            raise DerivedRefreshError(
                "The thicknesses cannot be calculated: select the cross-sections layer in "
                "the thickness calculator."
            )
        contacts_layer = None
        if dm.layer_roles.contacts_source == layer_roles.CONTACTS_FROM_LAYER:
            contacts_layer = dm.get_layer_role(layer_roles.BASAL_CONTACTS)
        elif settings.get('basal_contacts_layer'):
            contacts_layer = dm.find_layer_by_name(settings['basal_contacts_layer'])
        inputs = dm.thickness_inputs(
            geology=geology,
            unit_field=unit_field,
            contacts_layer=contacts_layer,
            calculator_type=calculator_type,
            structure=structure,
            cross_sections=cross_sections,
        )
        orientation_types = ("Dip Direction", "Strike")
        index = settings.get('orientation_type_index', 0)
        orientation_type = orientation_types[index] if 0 <= index < len(orientation_types) else None
        params = dict(
            calculator_type=calculator_type,
            dtm=layer('dtm_layer', layer_roles.DEM),
            geology=geology,
            basal_contacts=contacts_layer,
            sampling_frequency=settings.get('sampling_frequency', 200),
            structure=structure,
            cross_sections=cross_sections,
            unit_name_field=unit_field,
            dip_field=settings.get('dip_field') or 'DIP',
            dipdir_field=settings.get('dipdir_field') or 'DIPDIR',
            basal_contacts_unit_name=settings.get('basal_unit_field'),
            max_line_length=(
                settings.get('max_line_length')
                if calculator_type in ("StructuralPoint", "InterpolatedStructure")
                else None
            ),
            stratigraphic_order=dm.get_stratigraphic_unit_names(),
            debug_manager=getattr(dm, 'debug_manager', None),
        )
        if orientation_type is not None:
            params['orientation_type'] = orientation_type
        return {'inputs': inputs, 'params': params}

    # -- the calculation on the background thread ------------------------

    def run(self, progress: Optional[Callable[[str, int, int], None]] = None):
        """Calculate the results. Raise `DerivedRefreshError` if one fails."""
        total = len(self.names)

        def report(message, current):
            if progress is not None:
                progress(message, current, total)

        for index, name in enumerate(self.names):
            label = derived_data.DESCRIPTIONS[name].lower()
            report(f"Calculating the {label} ({index + 1} of {total})...", index)

            def updater(message, _label=label, _index=index):
                report(f"Calculating the {_label}: {message}", _index)

            try:
                if name == derived_data.BASAL_CONTACTS:
                    self._run_contacts(updater)
                elif name == derived_data.THICKNESS:
                    self._run_thickness(updater)
            except DerivedRefreshError:
                raise
            except Exception as err:
                raise DerivedRefreshError(
                    f"The {label} could not be calculated: {type(err).__name__}: {err}"
                ) from err
        report("Derived data is up to date.", total)

    def _run_contacts(self, updater):
        from .m2l_api import extract_basal_contacts

        job = self._contacts
        result = extract_basal_contacts(updater=updater, **job['params'])
        contacts = result['basal_contacts']
        if contacts is None or contacts.empty:
            raise DerivedRefreshError(
                "No basal contacts were found with the geology layer and the stratigraphic "
                "column. Check the unit name field and the order of the column."
            )
        self._contacts_result = contacts
        # The model reads the contacts directly. The project layer is only for display.
        self.data_manager.update_stratigraphy(
            basal_contacts=contacts, unit_name_field=BASAL_CONTACT_UNIT_FIELD
        )

    def _run_thickness(self, updater):
        from .m2l_api import calculate_thickness

        result = calculate_thickness(updater=updater, **self._thickness['params'])
        if not isinstance(result, dict) or result.get('thicknesses') is None:
            raise DerivedRefreshError("The thickness calculation gave no result.")
        self._thickness_result = result

    # -- the changes on the GUI thread ----------------------------------

    def finish(self):
        """Put the results into the data manager and record their inputs.

        Returns
        -------
        list of str
            The names of the units that keep a thickness that the user typed.
        """
        dm = self.data_manager
        skipped = []
        if self._contacts_result is not None:
            self._update_contacts_layer(self._contacts_result)
            dm.derived.record(derived_data.BASAL_CONTACTS, inputs=self._contacts['inputs'])
        if self._thickness_result is not None:
            values = thickness_values(self._thickness_result['thicknesses'])
            _, skipped = dm.apply_calculated_thicknesses(values)
            dm.derived.record(derived_data.THICKNESS, inputs=self._thickness['inputs'])
        return skipped

    def _update_contacts_layer(self, contacts):
        """Show the contacts in the project. The model does not read this layer."""
        from qgis.core import QgsProject

        from .vectorLayerWrapper import addGeoDataFrameToproject

        dm = self.data_manager
        old = dm.get_layer_role(layer_roles.BASAL_CONTACTS)
        layer = addGeoDataFrameToproject(contacts, "Basal contacts")
        dm.apply_stratigraphic_colours_to_layer(layer, BASAL_CONTACT_UNIT_FIELD)
        dm.set_basal_contacts(layer, unitname_field=BASAL_CONTACT_UNIT_FIELD)
        # An earlier layer of the plugin is replaced. A layer of the user is not removed.
        try:
            if (
                old is not None
                and old.id() != layer.id()
                and old.dataProvider().name() == 'memory'
                and old.name() == "Basal contacts"
            ):
                QgsProject.instance().removeMapLayer(old.id())
        except RuntimeError:
            pass


def thickness_values(thicknesses):
    """Return unit name -> thickness from the table of the thickness calculator.

    The median is used if it is there, then the mean. A unit with no result
    (map2loop uses -1) is left out.
    """
    columns = getattr(thicknesses, 'columns', [])
    if 'ThicknessMedian' in columns:
        column = 'ThicknessMedian'
    elif 'ThicknessMean' in columns:
        column = 'ThicknessMean'
    else:
        return {}
    values = {}
    for _, row in thicknesses.iterrows():
        name = row.get('name') or row.get('UNITNAME')
        if not name:
            continue
        value = row.get(column)
        if derived_data.thickness_is_set(value):
            values[name] = float(value)
    return values
