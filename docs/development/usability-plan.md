# Usability plan: guided modelling workflow

## Purpose

This plan makes the plugin easier to use. It changes the plugin from a set of
separate tools into one guided workflow. It also adds a second entry, so that
users can interpolate surfaces directly from their own constraints.

Do the work in phases. Each phase is a separate pull request. Each phase must
leave the plugin in a usable state.

## Current problems

### Entry points

- The plugin has three separate entry points: the toolbar, the Plugins menu,
  and the dock. None of them shows the order of the workflow.
- The toolbar has approximately 10 actions. Many actions have no icon, so the
  toolbar shows long text labels.
- `action_fault_topology` is added to the toolbar two times
  (`plugin_main.py`, `initGui`).
- `initProcessing()` is called two times in `initGui`.
- The Modelling and Visualisation tabs are at the bottom of the dock
  (`TabPosition.South`). Users can easily miss them.

### Workflow order

The real dependency order is:

```
Convert data -> Define column -> Extract basal contacts -> Calculate thickness
  -> Sample -> Area / DEM / layers -> Fault topology -> Fault adjacency
  -> Initialise -> Solve -> View in 3D -> Export
```

The UI does not follow this order:

- "Load Data" is the first tab. It asks for a basal contacts layer, but that
  layer does not exist until the user defines the column and runs a dialog.
- The map2loop tools are modal dialogs outside the dock. Each tool adds its
  output to the project as a new layer. The user must then go back to
  "Load Data" and select that layer.
- Each dialog has its own geology, fault and structure layer pickers. The user
  selects the same layers many times.
- There are five ways to build the stratigraphic column, in three places:
  - the dock buttons "Initialise from map" and "Initialise from Layer Field"
  - the Automatic Sorter dialog
  - the User-Defined Stratigraphic Column dialog
  - Paint Stratigraphic Order
- The Fault Topology Calculator is a dialog, but Fault Adjacency is a tab.
- Save, Load and Reset State are on the "Load Data" tab, but they apply to all
  of the plugin.
- Only the Geological Model tab shows a status. The user cannot see which
  earlier steps are done.

### Feedback and consistency

- Many actions show a modal `QMessageBox` for a successful result.
- Basal Contacts shows "No Contacts Found" and then also "Successfully
  extracted" for the same run (`basal_contacts_widget.py`,
  `_on_extractor_finished`).
- The Fault Adjacency instruction labels are created, but they are never added
  to a layout. Users do not see the colour key.
- The Fault Adjacency tables use red and green only. This is a problem for
  colour-blind users.
- `BaseTab(scrollable=True)` puts lists that scroll inside a scroll area.
- Rows use emoji (🗑️) as icons, but toolbars use QGIS theme icons.
- `export_tab.ui`, `topology_tab.ui`, `viewer_tab.ui` and
  `geological_history_tab.ui` are not used.

### Derived data becomes out of date

- `extract_basal_contacts` gives each contact the name of the younger unit in
  the column at the time of the run (see `get_stratigraphic_unit_names` in
  `data_manager.py`). Thus the `basal_unit` values record the column order of
  that run.
- When the user changes the column order, the model is marked stale
  (`GeologicalModelManager._on_stratigraphic_column_changed`). But the next
  initialisation reads the old contacts layer. Some contacts then have the
  wrong unit name. The plugin gives no warning.
- The calculated thicknesses come from the contacts. They can also become
  incorrect, with no warning.
- The `strat_order` and `strat_thickness` fields that are written onto a map
  layer also become out of date.

### Direct interpolation

- "Add Feature -> Add Foliation" already lets the user add Value, Form Line,
  Orientation and Inequality constraints from layers
  (`layer_selection_table.py`). But it is at the end of the stratigraphic
  workflow, so users do not easily find it.
- "Add Fault" in the Geological Model tab is "not yet implemented".

## Target design

### One dock with steps

```
+ LoopStructural ---------------------------- [Save][Open][...] +
| (1) Data ok   (2) Stratigraphy !   (3) Faults ok   (4) Model -   (5) View - |
+-------------------------------------------------------------+
|  contents of the current step                               |
+-------------------------------------------------------------+
| ! 2 units have no basal contacts.            [Back] [Next >] |
+-------------------------------------------------------------+
```

- Each step has a status: done, problem, or not started.
- The footer shows the most important problem and the next action.
- Save, Open, Reset and Settings go in the dock header.

### Steps

| Step | Contents | Moves in from |
|---|---|---|
| 1 Data | Bounding box, CRS, DEM. Source layer roles: geology, fault traces, structural points, contacts. Link to "Convert data". | Load Data tab, Data Conversion dialog |
| 2 Stratigraphy | Column list. "Build column" menu. "Derive from map" menu: basal contacts, thickness, sampler. | Stratigraphic Column tab, Sorter, User-Defined Sorter, Paint Order, Basal Contacts, Thickness, Sampler dialogs |
| 3 Faults | Fault list and fault properties. "Calculate topology". Adjacency tables. | Load Data -> Fault Layers, Fault Topology dialog, Fault Adjacency tab |
| 4 Model | Feature list, constraints for each feature, interpolator settings, one primary build button, list of problems. | Geological Model tab |
| 5 View and export | "Open 3D view". Export of surfaces, block model, cross-sections. | Visualisation dock, unused `export_tab.ui` |

### Two entries, one structure

At the start, the user selects one of:

- **Build from a geological map.** All steps are visible.
- **Interpolate surfaces from constraints.** Steps 2 and 3 are hidden. The
  checks for unit names, thickness and adjacency do not apply.

The user can show the hidden steps later. Steps 2 and 3 are generators: they
make features and constraints for step 4. In step 4, generated constraints are
read-only rows ("from stratigraphic column"). The user can add constraints to a
generated feature, or detach it and edit it.

Thus both entries use the same area setup, the same build path and the same
viewer. A user can mix the two methods in one model, for example a column-based
model with one more surface for a dyke.

### Derived data

Some data is calculated from other inputs. The plugin must keep this data
correct when the inputs change.

**Contacts source.** In step 1, the user selects one of:

- **Calculate from geology polygons** (default). The plugin extracts the basal
  contacts from the geology layer and the stratigraphic column when it needs
  them. A layer is added to the project only so that the user can see or
  export the contacts. The model does not read that layer.
- **Use a contacts layer.** The user's own layer is an input. The plugin does
  not change it.

The thickness calculator can already make basal contacts from the geology
layer and the column when no contacts layer is selected. Use the same code.

**Recorded inputs.** For each derived result, keep the inputs of the run:

| Derived result | Inputs to record |
|---|---|
| Basal contacts | Column unit order, geology layer, unit name field, override and ignored units |
| Calculated thickness | Basal contacts inputs, calculator type, structure layer, cross-section layer |
| `strat_order` / `strat_thickness` fields on a map layer | Column unit order, thickness values |

When one of these inputs changes, mark the result as out of date. Use a hash
of the inputs, so that a change and its undo (for example, two reorders) do not
mark the result as out of date.

**When to calculate again.**

- Do not calculate again after each change in the column list. Extraction is
  too slow, and the user often moves many rows.
- In step 2, show the out-of-date results, for example "Basal contacts are out
  of date (the column changed)", with an **Update** button.
- In step 4, the build button calculates all out-of-date derived data before it
  initialises the model. A build cannot use out-of-date contacts.

**Thickness values.** Record the source of each unit thickness: "typed" or
"calculated". Do not overwrite a typed value. Mark a calculated value as out
of date with its contacts, and update it at build time.

### Toolbar and menu

- Toolbar: LoopStructural (opens the dock), 3D View, Help.
- Plugins menu: the same actions, plus a "Tools" submenu with the map2loop
  dialogs for advanced users.
- The Processing algorithms do not change.

### General rules

1. Select a layer one time. All tools read the layer roles from the data
   manager.
2. Use `iface.messageBar()` for results. Use `QMessageBox` only for errors that
   stop an action, and for confirmations before destructive actions.
3. Each step has a check function. The step header shows its result.
4. Use QGIS widgets and theme icons: `QgsColorButton`, `QgsCollapsibleGroupBox`,
   `QgsApplication.getThemeIcon`. Do not use emoji as icons.
5. Do not put a scroll area around a widget that scrolls.
6. Derived data records its inputs. The UI shows when it is out of date. A
   model build never uses out-of-date derived data.

## Phases

### Phase 0: Quick fixes

No change to the layout.

- [x] Remove the second `toolbar.addAction(self.action_fault_topology)`.
- [x] Remove the second `initProcessing()` call.
- [x] Add the Fault Adjacency instruction labels to their group layouts.
- [x] Basal Contacts: show one message only. Do not show "Success" after "No
      Contacts Found".
- [x] Replace success `QMessageBox.information` calls with message bar
      messages. Start with the stratigraphic column, basal contacts, thickness
      and save state.
- [x] Ask for confirmation before "Clear Stratigraphic Column".
- [x] Delete the unused `.ui` files, or keep `export_tab.ui` for phase 5.

Files: `plugin_main.py`, `fault_adjacency_tab.py`, `basal_contacts_widget.py`,
`stratigraphic_column.py`, `model_definition_tab.py`.

Acceptance: the toolbar shows each action one time. The adjacency legend is
visible. No modal dialog opens for a successful action.

### Phase 1: Shared layer roles

- [x] Add layer roles to the data manager: `geology`, `geology_unit_field`,
      `fault_traces`, `structure`, `basal_contacts`, `dem`. Save them with the
      application state.
- [x] Add a signal or observer event when a role changes.
- [x] Make the "Load Data" widgets write to the roles.
- [x] Make each map2loop dialog read the roles as its default values. The user
      can still change the value in the dialog.
- [x] When Basal Contacts makes a new layer, set it as the `basal_contacts`
      role.
- [x] The stratigraphic column "geology layer" pickers use the `geology` role.
- [x] Add the contacts source setting: "Calculate from geology polygons" or
      "Use a contacts layer". Save it with the application state.
- [x] Add a derived-data record to the data manager. For each result (basal
      contacts, calculated thickness, styled fields), keep a hash of its inputs
      and a status: current or out of date.
- [x] Compare the hash when the column, a layer role or a tool setting changes.
      Send an event when a status changes.
- [x] Record the source of each unit thickness: "typed" or "calculated". A
      thickness that the user types in the column list is "typed".
- [x] In step 2 (until phase 3, in the Stratigraphic Column tab), show the
      out-of-date results and an **Update** button.

Files: `main/data_manager.py`,
`model_definition/*.py`, `map2loop_tools/*_widget.py`, `stratigraphic_column.py`.

Acceptance: the user selects the geology layer one time. All dialogs show it.
After Basal Contacts runs, the model uses the new contacts layer without more
selections. After the user changes the column order, the UI shows that the
basal contacts and the calculated thicknesses are out of date. If the user
moves a unit and then moves it back, the contacts stay current.

Tests: unit tests for the role storage, the save/load of roles, and the change
event. Unit tests for the input hash: a reorder marks the contacts out of date;
a change to a unit colour does not; a reorder and its undo give the same hash.
A typed thickness is not overwritten by a calculated thickness.

### Phase 2: Stratigraphic column changes

Depends on: the `feat/highlight-strat-unit` branch (map highlight, thickness
styling) is merged.

- [x] Put the geology layer group at the top, with labels. Show a summary of
      the unit names that have no match.
- [x] Toolbar: "+ Unit" and "+ Unconformity" as text buttons. A "Build column"
      menu for the import actions. An overflow menu for Reverse and Clear.
- [x] Add "Youngest" and "Oldest" labels above and below the list.
- [x] Replace the three apply buttons with one "Style map layer" group: a
      "Style by" combo (unit colour, stratigraphic order, thickness), a ramp
      combo and one Apply button.
- [x] Rows: use `QgsColorButton`, a theme delete icon, and no repeated
      "Thickness:" label. Give unconformity rows a different style.
- [x] Show text in the empty list.
- [x] Remove the outer scroll area from the tab.

Files: `stratigraphic_column/*.py`, `stratigraphic_column/*.ui`,
`geological_history_tab.py`.

### Phase 3: Step-based dock

- [x] Add a step navigation widget with a status for each step.
- [x] Add a `check()` function for each step. It returns a status and a list of
      problems.
- [x] Move the existing tabs into the steps, in the order of the target design.
- [x] Move Save, Open, Reset and Settings into the dock header.
- [x] Move the dialogs into their steps as buttons or menus. Keep the dialogs.
      Do not rewrite them in this phase.
- [x] Move the Fault Topology Calculator into step 3.
- [x] Reduce the toolbar to three actions. Put the dialogs in a "Tools"
      submenu.
- [x] Keep the `separate_dock_widgets` setting.

Files: `loop_widget.py`, `modelling/modelling_widget.py`, `plugin_main.py`,
new `gui/modelling/steps/` module.

Acceptance: a new user can go from an empty project to a solved model with the
"Next" button only. Each step shows why it is not done.

### Phase 4: Model step and direct interpolation

- [x] Replace "Initialize Model", "Solve Model" and "Update Model Data" with one
      primary button. Its text and action come from the model state.
- [x] Show the problems from all steps before the build.
- [x] Before the build, calculate all out-of-date derived data again: basal
      contacts first, then calculated thicknesses. Run this in a background
      task with progress. If the calculation fails, stop the build and show
      the error.
- [x] With "Calculate from geology polygons", give the extracted contacts
      directly to the model. Update the project contacts layer for display
      only.
- [x] Add the start choice: "Build from a geological map" or "Interpolate
      surfaces from constraints". Save the choice with the state.
- [x] Constraint list for each feature: source layer, constraint type, field
      mapping, weight, Z source (layer Z, DEM or constant).
- [x] Add the constraint types: value, interface, gradient/normal, tangent,
      inequality, pairwise inequality.
- [x] Show generated constraints as read-only rows. Add "Detach" to make a
      generated feature editable.
- [x] Build and preview one feature: an isoline on the map canvas, or a surface
      in the 3D view.
- [x] Implement "Add Fault" in the model step.

Files: `geological_model_tab/*.py`, `layer_selection_table.py`,
`feature_details_panel/*.py`, `main/model_manager.py`.

Acceptance: a user can make a model from constraint layers only, without a
stratigraphic column. A user can add a direct-constraint feature to a
column-based model. After the user changes the column order and builds the
model, the model uses basal contacts and thicknesses that match the new order.

### Phase 5: View and export

- [x] Show "Open 3D view" as the next action after a successful build.
- [x] Add export of surfaces, block model and cross-sections to step 5.

Files: `gui/modelling/steps/export_panel.py`, `main/model_export.py`,
`gui/modelling/modelling_widget.py`.

Acceptance: after a successful build, the dock tells the user to open the 3D
view. From step 5, a user can write the surfaces, the block model and a
cross-section to files without the 3D view.

### Phase 6: Follow-up changes

Nine changes that come from use of phases 3 to 5. Do them in this order. Each
one is a separate pull request.

#### 6.1 Two separate workflows

Problem: with "Interpolate surfaces from constraints", the build still uses the
data of the map workflow. The build reads the basal contacts, the structural
orientations, the fault traces and the stratigraphic column that the user set
in the other steps. The "constraints" choice only hides steps 2 and 3. It does
not stop the model from using their data.

Rules:

- With "Interpolate surfaces from constraints", the model has only the features
  that the user adds in step 4 (foliations, unconformities, parametric faults).
  It has no feature from the column, and no fault from a trace layer.
- With "Build from a geological map", the model has the generated features, and
  the features that the user adds.
- The data of one workflow is kept when the user changes the choice. It is not
  used, and it is not deleted.

Tasks:

- [x] Give the model manager the workflow mode. `update_model` skips
      `update_fault_features` (trace faults only), `update_foliation_features`
      and the generated-feature data in the "constraints" mode. It still builds
      the parametric faults and the manual foliations.
- [x] `refresh_feature_data` and `model_state` ignore the column, the contacts
      and the fault traces in the "constraints" mode. A change to the column
      does not make the model stale.
- [x] The data manager does not watch, reload or check the map input layers
      (contacts, structure, fault traces) in the "constraints" mode. This stops
      "Update data and solve" and the "Input layers changed" problem for layers
      that the model does not use. `get_layers_outside_bounding_box` uses the
      same rule.
- [x] `sync_extra_constraints` and the read-only "processed" rows are empty in
      the "constraints" mode.
- [x] Step checks: `check_data` does not ask for the geology and structure
      layers in the "constraints" mode. Move these two items to
      `check_stratigraphy` (see 6.2).
- [x] The primary button text and tooltip name the workflow ("Build model from
      constraints").
- [x] Save the choice with the state (done in phase 4). Load old state files
      with the "map" mode.

Acceptance: a user has a map project with a column, contacts and faults. The
user changes the choice to "constraints" and adds one foliation. The build gives
one feature. The solved model does not change when the user edits the column or
the contacts layer. When the user changes back to "map", the generated features
are made again from the same data.

Tests: unit tests of the model manager with a fake column and fake contacts: the
"constraints" mode builds only the manual features; the "map" mode builds both.
Unit tests for the checks and for `choose_primary_action` in each mode.

#### 6.2 Stratigraphic layers move to step 2

Problem: the "Stratigraphic Layers" group (basal contacts and structural
orientations) is in step 1. It belongs to the column workflow. Its layer picker
shows only line and point layers. With "Calculate from geology polygons", the
input is the polygon geology layer, so the user cannot select it there.

Tasks:

- [x] Remove `StratigraphicLayersWidget` from `ModelDefinitionTab`. Step 1 has
      only the bounding box, the CRS and the DEM.
- [x] Add the widget to `StratigraphyStep`, as a collapsible group (see 6.3).
- [x] The first layer picker depends on the contacts source:
  - "Calculate from geology polygons": the picker shows polygon layers. It
    reads and writes the `geology` and `geology_unit_field` roles. It does not
    call `set_basal_contacts`. The Z-coordinate check box is hidden.
  - "Use a contacts layer": the picker shows line and point layers, as now. It
    reads and writes the `basal_contacts` role.
  - Change the group title and the label to match ("Geology layer" or
    "Contacts layer").
- [x] When the user changes the source, do not write the old selection to the
      other role. Keep one selection for each source.
- [x] The `set_basal_contacts` callback (a tool or a build made a new contacts
      layer) does not change the picker in the "geology" source. The layer is for
      display.
- [x] Keep the geology picker of the column group in sync with the new picker
      (both use the same roles). Decide in the review if one of them must be
      removed (see the open questions).
- [x] Move the "Select the geology layer" and "Select the structure layer"
      items from `check_data` to `check_stratigraphy`.
- [x] Update the text that says "in step 1" for these layers
      (`derived_refresh.py`, `checks.py`, `pages.py`, the docs).
- [x] Keep the saved widget settings key `stratigraphic_layers_widget`, so old
      state files load.

Acceptance: with "Calculate from geology polygons", the user selects the
polygon layer in the group in step 2, and the unit name field list shows the
fields of that layer. After the user changes to "Use a contacts layer", the
picker shows only line and point layers. The selection of each source is kept.

Tests: unit tests for the role writes of each source. A Qt test of the picker
filter for each source (QGIS test job).

#### 6.3 Limit the vertical stack of widgets

Problem: the pages put many widgets one above the other. Step 2 has the
geology group, the button row, the column list, the style group, the derived
data panel and the "Derive from map" row. Adding the stratigraphic layers (6.2)
makes it worse. The group boxes, the feature details panel (its own scroll
area) and the dock header, step bar and footer use the height. On a laptop
screen the part with the content is very small.

Rules:

- A page has at most one scroll area, at the page level. A widget inside a page
  does not make its own scroll area.
- A page shows at most two expanded sections at one time. When the user
  expands a third section, the section that was expanded first collapses.
- The main widget of a page (the column list, the feature list) is not in a
  collapsible section. Its minimum height is 120 px. It gets the extra height.
- Do not nest a group box in a group box more than one level.
- A section that the user needs only sometimes starts collapsed ("Style map
  layer", "Derived data", "Stratigraphic layers" after the first setup).

Tasks:

- [x] Add a small `SectionStack` widget in `gui/modelling/steps/`. It holds
      collapsible sections, the maximum number of open sections, and the
      collapsed state of each section. It saves the state in the widget
      settings.
- [x] Use it in steps 1, 2, 3 and in the feature details panel of step 4
      (`Data Layers`, `Interpolator Settings`, `Preview`, `Export Feature`).
- [x] Remove the scroll areas that are inside other scroll areas
      (`BaseTab(scrollable=True)`, the scroll area of
      `feature_details_panel/_base.py`).
- [x] Give the page a header summary for each collapsed section, for example
      "Geology layer: Geology, UNITNAME", so the user does not need to expand
      it to read the value.
- [x] Reduce the vertical use of the dock: the header and the footer use one
      row each. The footer text is one line with a tooltip.
- [x] In step 4, the problems list is collapsed to one line ("3 problems") with
      the list in a tooltip or a popup.

Acceptance: at a window height of 700 px, the main widget of each step has at
least 200 px. No page has a scroll area inside a scroll area.

Tests: unit test of the open-section limit (it does not need QGIS if the logic
is in a plain class). Manual check at 700 px and 1080 px.

#### 6.4 Choose the number of elements from the data

Problem: each interpolator has the fixed number of elements of the settings
(default 50 000). A feature with 10 points and a feature with 10 000 points
get the same number. A small number gives a coarse surface. A large number
makes the solve slow. In addition, the model manager reads the default value
of `PlgSettingsStructure` (the class), not the value that the user saved. The
setting of the user has no effect on a build. User-added foliations do not set
the number at all.

Design:

- Add a pure function `suggest_nelements(summary)` in
  `main/interpolation_size.py` (no QGIS import). The `summary` has the number
  of value constraints, the number of orientation constraints, the number of
  different values (surfaces) and a measure of the spread of the orientations
  (0 for parallel planes, 1 for all directions).
- Rule of thumb: elements = equations x 25 x surface factor x spread factor,
  where an orientation counts as two equations, the surface factor is
  1 + 0.1 for each surface after the first (at most 10 surfaces), and the
  spread factor is 1 + spread. Round to 1 000. Limit to 5 000 .. 250 000. A
  feature with no data gets the minimum. These numbers are a first guess: check
  them with real models (see the open questions).
- Add the setting `interpolator_nelements_auto` (default: on). With it on,
  the settings page shows the number as "Automatic" and the spin box is
  disabled. With it off, the fixed number is used.
- Add one method in the model manager that gives the interpolator arguments
  (`nelements`, `npw`, `cpw`, `regularisation`) for a data frame. It reads the
  saved settings, not the class defaults. Use it for the generated features,
  the faults, the domain faults, the parametric faults and the foliations that
  the user added.
- Show the number that was used in the feature details panel ("Elements: 24 000
  (automatic)"). If the user changes it there, the feature keeps the number of
  the user until the user selects "Automatic" again.

Tasks:

- [x] `main/interpolation_size.py` with `summarise_data` and `suggest_nelements`.
- [x] Setting, settings page and preference test.
- [x] Model manager: one method for the interpolator arguments, used in all
      build paths. Fix the use of the class defaults.
- [x] Feature panel: show the number, and an "Automatic" check box.
- [x] Docs: say how the number is chosen, and what the user can change.

Acceptance: a model with 20 contact points and a model with 5 000 points get
different numbers of elements, both inside the limits. A saved fixed number is
used when "Automatic" is off. A user-added foliation gets a number.

Tests: unit tests for the function: more data gives more or equal elements; the
limits; no data; parallel and spread orientations; orientation signs do not
matter.

#### 6.5 Build a model with only faults

Problem: the "map" workflow needs a stratigraphic column and basal contacts. A
user who has only fault traces (for example, to model the faults alone) cannot
build a model. The build asks for contacts, and the contacts extraction stops
with "No basal contacts were found".

Rules:

- In the "map" workflow, the stratigraphic column and the basal contacts are
  optional. A model with fault traces only builds the faults.
- With no units in the column, the build does not calculate the basal contacts
  and the thicknesses, and it makes no stratigraphic feature.
- With units in the column but no contacts for a unit, the build gives the
  current message. Only an empty column skips the contacts.

Tasks:

- [x] `names_to_refresh` returns no result that comes from the column when the
      column has no units. `DerivedRefresh` does not raise when there are no
      units.
- [x] `update_model` builds the faults when the column has no groups.
      `update_foliation_features` does nothing for an empty column. Check that
      `model.stratigraphic_column` is safe to leave unset.
- [x] `check_stratigraphy` does not ask for the geology layer, the structure
      layer or the contacts when the column is empty. The text says that the
      step is optional if the user models only faults.
- [x] `model_state`, `valid` and the primary action accept a model that has
      faults and no groups.
- [x] Step 5 (view and export) works with fault features only. The block model
      and the stratigraphic surfaces are not offered when there are no units.

Acceptance: a project has a fault trace layer and an empty column. The user
sets the bounding box and the fault layer, and builds the model. The model has
the fault features, and the user can view and export the fault surfaces.

Tests: unit tests for `names_to_refresh` and for the checks with an empty
column. A QGIS test of `update_model` with faults and no column.

#### 6.6 Fault topology as a button, not a dialog

Problem: "Calculate topology..." in step 3 opens a dialog
(`FaultTopologyWidget`). The dialog asks again for the fault layer and the fault
ID field. The user already chose these in the "Fault layer" section of the same
page. The dialog also closes by itself and shows a second message box.

Rules:

- The button runs the calculation at once. It uses the fault layer and the name
  field that are set in the data manager.
- The button is disabled until a fault layer and a name field are set. The
  tooltip says why it is disabled.
- No dialog opens. The result shows in the step message bar (for example,
  "Calculated fault topology for 12 pairs."), not in a message box. Errors use
  the same message bar.
- The label is "Calculate topology", with no ellipsis, because no dialog opens.

Tasks:

- [x] Move the calculation from `FaultTopologyWidget._run_topology` to a
      function that does not use Qt widgets. It takes the layer, the ID field
      and the data manager, and it returns the number of pairs or raises an
      error with a clear message.
- [x] `FaultsStep` calls this function from the button. It reads the layer and
      the field from `data_manager.get_fault_traces()`. It updates the enabled
      state when the fault layer or the field changes.
- [x] Show the result and the errors in the message bar of the step page.
- [x] Remove `FaultTopologyWidget`, `fault_topology_widget.ui` and
      `launchers.FAULT_TOPOLOGY`. Keep the toolbar action only if it still has
      a use: if it stays, it calls the same function with the fault layer from
      the data manager.

Acceptance: the user sets the fault layer in step 3 and presses "Calculate
topology". The Fault Adjacency tables fill with no dialog and no second choice
of layer.

Tests: unit tests for the function (a missing layer, a missing field, an empty
layer, and a normal result). A QGIS test that the button is disabled with no
fault layer.

#### 6.7 Fault topology sets the relationship order wrongly

Problem: the topology calculation writes the fault pairs in the wrong order.
`FaultTopologyWidget._run_topology` reads `Fault1` and `Fault2` from the
map2loop table and calls `update_fault_relationship(Fault1, Fault2, ABUTTING)`.
In `FaultTopology` the pair `(a, b)` is directional. In
`apply_fault_abutting_relationships`, `(a, b)` ABUTTING means that fault `a` is
cropped by fault `b`. The map2loop pair has no such direction. The code takes
the table order, so the abutting fault and the fault that it abuts can be the
wrong way round. The crop then removes the wrong part of the model.

Other places that use order, to check at the same time:

- `new_faults` is `sorted(...)` on strings, so the fault list order is
  alphabetical ("10" before "2"), not the order in the layer.
- The code first removes all pairs with `NONE`, and then adds the new pairs.
  Pairs that the user set to FAULTED are lost when the user calculates again.

Status: I read the LoopStructural and plugin code. I did not read map2loop's
table (the package is not installed here), so the cause in the table must be
confirmed first.

Rules:

- For each detected pair, decide which fault ends at the other, from the
  geometry of the traces (the fault whose end point lies on the other trace is
  the abutting fault). Write the pair as `(abutting fault, other fault)`.
- If the geometry does not give a direction, do not guess. Leave the pair as
  `NONE` and list it in the message bar, so the user sets it in the Fault
  Adjacency tab.
- Keep the layer order for the fault list.
- A new calculation does not delete a relationship that the user set by hand.

Tasks:

- [x] Confirm the columns and the order of the map2loop table. Confirmed in
      `map2loop/topology.py`: the columns are `Fault1`, `Fault2`, `Type`,
      `Angle`. The pairs come from the lower triangle of a buffer adjacency
      matrix (buffer 500 map units), so `Fault1` is only the later fault in
      the layer. The table has no direction. Pairs are near each other, and
      not always touching.
- [x] Add a function that gives the direction of a pair from two traces. It
      has no Qt code.
- [x] Use it in the calculation from 6.6. Keep the layer order of the faults.
- [x] Keep user-set relationships when the user calculates again.

Acceptance: for two faults where one ends at the other, the Fault Adjacency
table shows the right fault as abutting, and the built fault is cropped on the
right side. A second calculation does not change a relationship that the user
set.

Tests: unit tests for the direction function (a T-junction, a crossing, two
separate traces, and the two input orders giving the same result). A test that
a second calculation keeps a user-set FAULTED pair.

#### 6.8 Clean up the viewer and add isosurfaces from model features

Problem: the viewer code is large and has grown in parts. The files in
`gui/visualisation/` have about 4 000 lines. `feature_list_widget.py` (1 450
lines) mixes the feature tree, the code that builds meshes from the model, and
the code for cross-sections, block models and topography.
`object_properties_widget.py` (1 100 lines) has many places that read
`viewer.meshes` directly and test `current_object_name`. `object_list_widget.py`
(670 lines) holds the object/model view. The user can add only the surfaces that
the model gives (`feature.surfaces()`), so the user cannot choose a value and
make an isosurface of a scalar field.

Goals:

- The viewer classes are smaller and simpler, with one clear job for each.
- The user can add many isosurfaces from a model feature, and can choose the
  value of each one.

Rules:

- One object registry owns the meshes of the viewer (name, mesh, source feature,
  source type, isovalue, style). The widgets read and change objects only through
  it. No widget reads `viewer.meshes` directly.
- The code that builds a mesh from the model (scalar field, surface, vector
  field, isosurface, block model, cross-section) has no Qt code. The widgets
  only call it.
- Each mesh object keeps the information that is needed to build it again (the
  source feature, the type and the isovalue), so "Update viewer objects" works
  for isosurfaces in the same way as for other objects.
- An isosurface is an object like a surface, with its own name, colour, opacity
  and visibility. It does not replace the surfaces that the model gives.

Tasks:

- [x] Read the three files and write a short list of what each class does and
      which methods are duplicated or not used. Remove dead code first.
- [x] Add an object registry class (no Qt) for the meshes and their source
      information. Move the reads and writes of `viewer.meshes` to it.
- [x] Split `feature_list_widget.py`: move the mesh builders to a module without
      Qt code (`mesh_builders.py`), and move the cross-section, block model and
      topography actions out of the tree widget.
- [x] Simplify `object_properties_widget.py`: one handler for the selected
      object, and the controls shown for each source type, not a check for the
      object name in each method.
- [x] Simplify the object/model view (`object_list_widget.py`): group the
      objects by source feature, and show the type and the isovalue of each
      object.
- [x] Add "Add isosurface..." to the menu of a model feature. The user enters
      one or more values (a list, or a start, an end and a count). The default
      values come from the range of the scalar field. A pure function gives the
      values from the input.
- [x] Build the isosurfaces with the scalar field of the feature
      (`feature.surfaces(value)`). Give each object a name with its value, for
      example `Fault_1_iso_0.50`. A value outside the range of the field gives
      a message in the message bar, not an error dialog.
- [x] Let the user change the value of an existing isosurface in the object
      properties. The object is built again.
- [x] Update the docs for the viewer.

Acceptance: the user adds five isosurfaces from one feature in one action. They
show in the object list under that feature, each with its value. The user
changes one value and only that object changes. After the model is updated,
"Update viewer objects" builds the isosurfaces again with the same values.

Tests: unit tests for the registry and for the function that gives the values
(a list, a range, a value outside the range, a repeated value). A QGIS test that
the menu action adds the objects with the right names and isovalues.

#### 6.9 True clipping relationships with loop_cgal

Problem: the model has no way to cut one surface with another. A surface that
goes above the DEM stays in the model and in the exports. The user can only hide
it in the viewer. The same is true for a surface that must end at another
surface, for example a unit that an unconformity cuts. `loop_cgal` does mesh
boolean operations (exact geometry), so it can make true cuts. The plugin does
not use `loop_cgal` now.

Status: the plugin has no `loop_cgal` code. I did not read the `loop_cgal` API.
Confirm which operations it has (clip a mesh with a mesh, keep the part above or
below, and the result type) and how to install it in the QGIS Python
environment before the design is final.

Rules:

- `loop_cgal` is optional. If it is not installed, the clip controls are
  disabled with a tooltip that says why, and the model builds as before.
- A clipping relationship has a target surface, a clipping surface (the DEM, a
  feature surface, or the bounding box) and a side to keep (above or below).
- The cut is made on the output meshes (the surfaces for the viewer and the
  export). It does not change the solved interpolator or the model data.
- The cut is a relationship in the model state. It is saved and loaded with the
  state, and the user can turn it off. Old state files have no clipping.
- Cutting by the DEM is a one-step action: "Cut all surfaces by the DEM". It
  uses the DEM from step 1 and makes one relationship for each surface.
- The viewer and the export (step 5) use the clipped meshes. The unclipped mesh
  is kept, so the user can remove the cut.

Tasks:

- [ ] Confirm the `loop_cgal` operations and the install method. Add the
      dependency check and a clear message when it is missing.
- [ ] Add a module without Qt code (`main/clipping.py`) with a function that
      clips a mesh with a mesh and returns the new mesh, and a function that
      makes a surface mesh from the DEM in the model bounding box.
- [ ] Add a `ClippingRelationship` record (target, clipping surface, side, on
      or off) to the model manager, with save and load. Add the result to the
      object registry of 6.8, so each object has a clipped and an unclipped
      mesh.
- [ ] Add "Cut all surfaces by the DEM" to the viewer and to step 5. Add a
      "Clip by..." action to the menu of one surface for a cut by another
      feature surface.
- [ ] Use the clipped meshes in the surface export and in the cross-section and
      block model code where they make sense. Say in the docs which outputs the
      cut changes (the block model is not cut).
- [ ] Block model filter: the block model is not cut, but the user can choose
      to show only the cells below the DEM. Add a "Below DEM" cell array to the
      block model (true when the cell centre is below the DEM height at its x,
      y), and a "Show only below DEM" check box in the object properties. The
      check box hides the other cells with a threshold filter in the viewer.
      It does not delete cells, and it does not need `loop_cgal`. The export of
      the block model has the same option, off by default.
- [ ] Handle failures: an open or self-crossing mesh, no overlap, and an empty
      result. Show the reason in the message bar and keep the unclipped mesh.
- [ ] Docs: say what the cut does, that it changes only the output meshes, and
      how to install `loop_cgal`.

Acceptance: a model has a DEM and five surfaces, some of which go above the
ground. After "Cut all surfaces by the DEM", no surface in the viewer or in the
export is above the DEM. The user turns the cut off and the full surfaces come
back. With "Show only below DEM" on, the block model shows only the cells below
the ground, and with it off all cells show again. The state saves and loads with
the cut. Without `loop_cgal`, the model
builds and the clip controls are disabled.

Tests: unit tests for the clipping function with simple meshes (a plane cut by a
plane, no overlap, an empty result) that skip when `loop_cgal` is missing. Unit
tests for the relationship save and load. A QGIS test of the DEM cut action.

Order and links between the parts: 6.1 first, because it defines what the model
reads in each workflow. 6.2 depends on the same checks, so do it next. 6.3
comes after 6.2, because it must lay out the final content of the pages. 6.4
does not depend on the others. 6.5 comes after 6.2, because it changes the
same checks. 6.6 does not depend on the others. 6.7 goes with 6.6, because both change the
same calculation. 6.8 does not depend on the others. 6.9 comes
after 6.8, because it uses the object registry.

### Phase 7: Fold modelling

Problem: LoopStructural can model folds with a fold frame and the discrete
fold interpolator (DFI). The plugin gives access to a part of this code only,
and the access is not complete:

- "Attach fold frame" (`FoliationFeatureDetailsPanel`) and "Convert to
  Structural Frame" change the feature in the current model only. They are not
  in the spec of the feature. The next build (`update_model`) loses them, and
  they are not saved with the state. The `folded_feature_name` key of
  `add_foliation` is not used.
- `fold_frames` returns all structural frames. The user cannot make a fold
  frame from axial surface data directly.
- The fold weights in `FoldedFeatureDetailsPanel` set only a value. The user
  cannot turn a fold constraint off. LoopStructural turns a constraint off when
  its weight is `None`, not `0`.
- The S-plot dialog (`splot.py`) exists, but no button opens it. It shows the
  limb rotation data only. It does not show the fitted curve, and the user
  cannot change the wavelength or the profile type.
- A fold frame cannot be folded by an older fold frame. Thus the user cannot
  make a refolded fold.

Aim: the user can model a fold with the axial surface constraint, the fold
axis constraint and the S-plot, all at one time, one at a time, or in pairs.
The user can make a polyphase fold model, for example the "Refolded folds"
example of the LoopStructural documentation
(`examples/2_fold/plot_2_refolded_folds.py`, data from `load_laurent2016`).

#### Terms

| Term | Meaning | LoopStructural |
|---|---|---|
| Fold event | One fold generation (for example F1). It has a name, an axial surface, a fold axis setting and S-plot settings. | `FoldEvent` |
| Fold frame | The curvilinear coordinate system of a fold event. Coordinate 0 is the axial surface. Coordinate 1 is the fold axis direction field. Coordinate 2 is normal to both. | `FoldFrame`, `create_and_add_fold_frame` |
| Folded feature | A foliation (for example bedding S0) that a fold event folds. | `create_and_add_folded_foliation` |
| Folded fold frame | The fold frame of an older fold event that a younger fold event folds (for example S1 folded by F2). | `create_and_add_folded_fold_frame` |
| Axial surface constraint | The gradient of the folded feature is normal to the fold direction. The fold direction comes from the fold frame and the fold limb rotation angle. | DFI `fold_orientation` |
| Fold axis constraint | The gradient of the folded feature is normal to the fold axis. | DFI `fold_axis_w` |
| S-plot | A plot of a fold rotation angle against a fold frame coordinate, with a fitted profile. The limb S-plot uses coordinate 0. The axis S-plot uses coordinate 1. | `fold_limb_rotation`, `fold_axis_rotation`, `SVariogram`, `limb_wl`, `axis_wl` |

#### The three fold controls

Each folded feature has three controls. Each control has a check box. The
user can select any combination that is in the table below.

1. **Axial surface.** The user selects the fold event (and thus its fold
   frame). This adds the axial surface constraint (`fold_orientation`).
2. **Fold axis.** The user selects the source of the fold axis:
   - constant: plunge and azimuth (as now);
   - lineations. The user selects one of two lineation sources:
     1. **Lineation layer**: a point layer (for example a shapefile) with
        measured fold axes or intersection lineations. The user selects the
        plunge field and the trend (plunge direction) field.
     2. **Calculated intersection lineations**: the plugin calculates a
        lineation at each orientation point of the folded feature. The
        lineation is the intersection of the folded foliation and the axial
        foliation (coordinate 0 of the fold frame) at that point
        (`FoldFrame.calculate_intersection_lineation`). This source needs an
        axial surface.

     Then the user selects how the plugin uses the lineations:
     - **average**: the fold axis is the mean of the lineations, and it is
       constant in the model (`av_fold_axis` for the calculated lineations,
       as now);
     - **fit**: the plugin fits the fold axis rotation angle of the
       lineations to coordinate 1 (the axis S-plot), so that the fold axis
       can change in the model. This needs an axial surface.

   This adds the fold axis constraint (`fold_axis_w`).

   | Lineation source | Average | Fit (axis S-plot) | Needs an axial surface |
   |---|---|---|---|
   | Lineation layer | yes | yes | only for "fit" |
   | Calculated intersection lineations | yes | yes | yes |

   The UI shows the lineations of the selected source in the 3D view and in
   the axis S-plot, so that the user can compare the two sources.
3. **S-plot.** The user controls the rotation angle profiles: the profile
   type (Fourier series, trigonometric), the wavelength, and fixed values for
   the profile parameters. Without this control, the plugin fits the
   profiles automatically (the LoopStructural default: Fourier series, and a
   wavelength from the S-variogram).

| Axial surface | Fold axis | S-plot | Result |
|---|---|---|---|
| - | - | - | A standard foliation. No fold constraint. |
| x | - | - | Fold frame and DFI. Axial surface constraint on. The fold axis is the average of the calculated intersection lineations, but the fold axis constraint is off (`fold_axis_w = None`). Automatic profiles. |
| - | x | - | No fold frame. The plugin adds the fold axis as tangent constraints on a regular grid in the bounding box (gradient . axis = 0). The interpolator of the feature does not change. Only a constant fold axis is possible: plunge and azimuth, or the average of a lineation layer. |
| x | x | - | Fold frame and DFI. Both constraints on. Automatic profiles. |
| x | - | x | As "axial surface only", but with the limb profile of the user. |
| x | x | x | All constraints on. The limb profile of the user. With lineations and "fit", also the axis profile of the user. |
| - | - | x, or - x x | Not possible. An S-plot needs a fold frame coordinate. The S-plot check box is disabled until the user selects an axial surface. The tooltip says why. |

Rules:

- A control that is off sets its weight to `None`. Do not use `0` to turn a
  constraint off.
- The weight of each constraint is in an "Advanced" section under its
  control. The defaults are the LoopStructural defaults (`fold_orientation`
  10, `fold_axis_w` 10, `fold_normalisation` 1, `fold_norm` 1,
  `fold_regularisation` [0.1, 0.01, 0.01]).
- A folded feature always uses DFI. The interpolator combo shows "DFI (fold)"
  and is disabled. A fold frame uses the interpolator of the settings.

#### Polyphase folds

- A fold event can have "Folded by": an other, younger fold event. Then its
  fold frame is a folded fold frame, and its own three fold controls apply to
  coordinate 0 of that frame.
- A foliation, or the stratigraphic column group of the map workflow, can
  have "Folded by": one fold event.
- The fold events and the folded features make a graph. The build order comes
  from this graph: the youngest fold event first, then each feature after the
  fold event that folds it. A cycle (F1 folded by F2, F2 folded by F1) is an
  error. The UI does not let the user make a cycle.
- The feature list in step 4 shows the graph as a tree: each fold event, then
  the features that it folds, under it.

Workflow for the "Refolded folds" example. The user has three point layers
with orientations: `s2`, `s1` and `s0`.

1. Step 1: set the bounding box. Select "Interpolate surfaces from
   constraints".
2. Step 4: "Add Fold Event" F2. Axial surface data: the `s2` layer
   (orientation) and one value point. Fold axis: off. Build F2. The plugin
   shows the fold frame.
3. "Add Fold Event" F1. Axial surface data: the `s1` layer. Folded by: F2.
   Axial surface: on. Fold axis: average. S-plot: on. The plugin builds the F2
   frame (current, so not again) and calculates the rotation angles of `s1`.
   The S-plot shows the limb rotation angle of `s1` against F2 coordinate 0.
   The user sets the wavelength to 4 (the S-variogram suggests a value).
   Build F1.
4. "Add Foliation" S0 from the `s0` layer. Folded by: F1. Axial surface: on.
   Fold axis: average. S-plot: on. The S-plot shows `s0` against F1
   coordinate 0. Build the model.
5. Step 5: view S0, S1 and S2 in the 3D view, and export the surfaces.

#### Data model

- Add `fold_events: Dict[str, dict]` to the model manager, in the form of
  `manual_foliations` and `parametric_faults`. A spec has:
  - `name`;
  - `axial_surface_data`: layer dicts in the form of `add_foliation`, with a
    `coord` key (0 for the axial foliation and the axial traces, 1 for the
    fold axis direction data);
  - `folded_by`: the name of a fold event, or `None`;
  - `fold`: the fold controls of the fold frame (only when `folded_by` is
    set), see below;
  - the interpolator settings of the frame.
- Add a `fold` key to the spec of a manual foliation and to the generated
  stratigraphic group:
  - `fold_event`: the name of the fold event, or `None`;
  - `axial_surface`: on or off, and `fold_orientation` weight;
  - `fold_axis`: `source` (off, `constant` or `lineations`), the plunge and
    azimuth for `constant`, the `fold_axis_w` weight, and for `lineations`:
    - `lineation_source`: `layer` (layer dict with the plunge and trend
      fields) or `intersection` (calculated);
    - `use`: `average` or `fit`;
  - `splot`: off or on; for the limb and for the axis profile: the type, the
    wavelength (or "automatic"), and the fixed parameters;
  - `fold_normalisation`, `fold_norm`, `fold_regularisation`.
- Replace the `folded_feature_name` key with `fold.fold_event`. Load old
  state files with `fold_event = None`.
- `update_model` builds the fold events in the graph order, then the
  features. It uses `create_and_add_fold_frame`,
  `create_and_add_folded_fold_frame` and `create_and_add_folded_foliation`.
  It does not use `add_fold_to_feature` on the current model.
- Save `fold_events` and the `fold` keys with the state
  (`*_to_dict` / `*_from_dict`).
- Put the logic that does not need QGIS (the graph order, the cycle check,
  the conversion from the controls to the LoopStructural arguments) in
  `main/fold_spec.py`, so that unit tests can use it.

#### Staged build for the S-plot

The S-plot needs the fold frame before the folded feature is built. Thus:

- "Calculate rotation angles" builds the fold frame (and the fold events that
  fold it) if it is not current. Then it calculates the lineations (for the
  "calculated intersection lineations" source) and the rotation angles of the
  data of the feature. It does not build the folded feature. Run it in a
  background task with progress.
- The S-plot panel shows the data points, the fitted curve, the S-variogram
  and the suggested wavelengths. When the user changes the profile type, the
  wavelength or a parameter, the plugin fits the curve again at once. This
  does not interpolate.
- The values of the S-plot go into the spec. The next build uses them.
- When the fold frame changes (new data, a new interpolator setting), the
  rotation angles are out of date. Use the derived-data record of phase 1:
  the S-plot shows "Rotation angles are out of date" and an **Update**
  button. The build calculates them again before it builds the folded
  feature.

#### Tasks

Do the parts in this order. Each part is a separate pull request.

7.1 Fold specs and build order

- [ ] `main/fold_spec.py`: the spec form, the graph order, the cycle check,
      and the conversion of the fold controls to the arguments of
      `create_and_add_folded_foliation` (`fold_weights`, `av_fold_axis`,
      `fold_axis`, `limb_wl`, `axis_wl`, profile types).
- [ ] Model manager: `fold_events`, the `fold` key, the build in graph order,
      save and load. Remove the uses of `add_fold_to_feature` and of
      `convert_feature_to_structural_frame` from the UI, or make them write
      the spec.
- [ ] `fold_frames` returns the fold frames of the fold events only.

7.2 Fold events in step 4

- [ ] "Add Feature -> Add Fold Event": a dialog with the name, the axial
      surface layers (orientation, value, form line, with coordinate 0 or 1)
      and "Folded by".
- [ ] A details panel for a fold event: data, "Folded by", interpolator
      settings, and (for a folded fold frame) the fold controls. Use
      `SectionStack` (6.3).
- [ ] The feature list shows the fold graph as a tree.
- [ ] Step check: a fold event with no orientation data for coordinate 0 is a
      problem. A coordinate 0 with no value constraint is a warning ("Add an
      axial trace or a point with a value").

7.3 The three fold controls

- [ ] Replace "Attach fold frame" and the weight boxes of
      `FoldedFeatureDetailsPanel` with one "Fold" section: "Folded by", and
      the three controls with their check boxes and "Advanced" weights.
- [ ] Apply the rules of the combination table. Disable the S-plot control
      when there is no axial surface.
- [ ] Fold axis "lineations": a choice of the two lineation sources. For
      "lineation layer", a point layer picker with the plunge and trend
      fields. For "calculated intersection lineations", no input (disabled
      without an axial surface).
- [ ] Fold axis "average" or "fit" for the lineations. Disable "fit" without
      an axial surface.
- [ ] Convert the plunge and trend of the layer to vectors, and give them
      with their points (N x 6) to the fold axis calculation
      (`main/fold_spec.py`).
- [ ] Fold axis without axial surface: make the tangent constraints on a grid
      (`main/fold_spec.py`). The grid step comes from the bounding box and
      the number of elements.
- [ ] Add "Folded by" to the stratigraphic column group in the map workflow.

7.4 S-plot panel

- [ ] Replace `SPlotDialog` with an S-plot panel: limb and axis tabs, data
      points, fitted curve, S-variogram with suggested wavelengths, profile
      type, wavelength, fixed parameters, misfit.
- [ ] "Calculate rotation angles" as a background task (staged build).
- [ ] Out-of-date state of the rotation angles in the derived-data record.

7.5 Polyphase example and docs

- [ ] Test data: the `load_laurent2016` data as three GeoPackage point layers
      in `tests/data/`.
- [ ] A user guide page in `docs/usage` for the "Refolded folds" workflow,
      with the S-plots.

Acceptance: a user makes the "Refolded folds" model of the LoopStructural
documentation from the three layers, with the steps above and without Python.
The result is the same as the result of the example script (see the tests).
For one folded feature, the user can turn each of the three controls on and
off, and the build uses only the constraints that are on. After the user saves
and opens the project, the fold events, the "Folded by" links and the S-plot
values are the same, and a build gives the same model.

Tests:

- Unit tests (no QGIS) for `main/fold_spec.py`: the graph order of
  F2 -> F1 -> S0; a cycle is an error; each row of the combination table gives
  the correct arguments (a control that is off gives `None`); the S-plot is
  refused without an axial surface; old specs with `folded_feature_name` load.
- Unit tests for the two lineation sources: the plunge and trend of a layer
  give the correct vectors; the calculated intersection lineation of a known
  folded foliation and a known axial foliation is their cross product; the
  "average" of both sources gives the same axis for the same data; "fit" and
  the calculated source are refused without an axial surface.
- A QGIS test that builds the refolded fold from the test layers and compares
  the S0 scalar field on a coarse grid with the result of the LoopStructural
  calls of the example (same data, same arguments).
- A test that the save and load of the state keeps the fold specs.

Order and links: 7.1 first, because the other parts use the spec. 7.2 and 7.3
depend on 7.1. 7.4 depends on 7.3 (the S-plot control). 7.5 comes last. Phase 7
depends on 6.1 (the workflow mode), 6.3 (`SectionStack`) and 6.4 (the number of
elements of each feature, which is also used for the fold frames).

### Phase 8: Advanced 3D viewer

A second 3D viewer for hard 3D problems. It is a standalone application
(Rust, Bevy) with a live link to QGIS. The PyVista viewer stays as the default
viewer. The new viewer shows geological data objects that are similar to
those of Geoscience ANALYST (`geoh5` types): points, curves, surfaces,
sections, block models, drillholes and orientations.

This phase is large, and most of the work is in a separate repository
(`geoviewer`). The tasks, the protocol, the risks and the open questions are
in the viewer plan of that repository (`docs/viewer-plan.md`).

Acceptance: from step 5, a user opens the advanced viewer. The viewer shows
the model and its input data, and updates after each build. A pick in the
viewer selects the feature in the dock and shows the point on the map.

### Phase 9: Demo mode

Problem: a new user cannot see what the finished workflow looks like before
they use their own data. The dock has five steps and many buttons. The docs
have screenshots, but they go out of date. Trainers and developers also need a
repeatable way to show the plugin, and a way to test the full workflow through
the real UI.

Aim: a demo mode runs the workflow by itself. It clicks the real buttons, in
the order that the user must use them, with sample data, until a model is
built. The user watches and can pause, step or stop at any time.

The demo does not use a second code path. It calls the same widgets as a user
does. Thus the demo also shows when a step is broken, and it is a UI test.

#### Rules

- **Real controls.** The demo changes a control (a layer picker, a combo, a
  check box) and presses a button through the widget. It does not call the
  model manager or the data manager directly. If a control is hidden or
  disabled, the demo stops with an error. This is a test failure, not a case
  to work around.
- **Visible.** Before each action, the demo moves a highlight (an overlay frame
  and a one-line caption) to the control. It waits a set time, then it acts.
  The caption says what the action does and why ("Build column from the map:
  the order of units comes from the geology layer").
- **Same speed as the work.** The demo waits for the end of each background
  task (extraction, thickness, build) with the task signals. It does not wait
  a fixed time. If a task fails, the demo stops and shows the error.
- **User control.** A small demo bar shows Pause, Step, Speed (slow, normal,
  fast) and Stop. The demo also stops if the user clicks or types in the dock.
  The demo never runs by itself at start-up.
- **Safe project.** The demo works in a new, empty QGIS project, and it asks
  before it replaces the current project. If the current project has unsaved
  changes, the demo asks the user to save them first. Stop removes the demo
  layers and restores the plugin state to the state before the demo.
- **Sample data.** The demo uses a small data set that the plugin includes
  (see 9.1). It does not need a network.
- **Both entries.** There are two demos: "Build from a geological map" and
  "Interpolate surfaces from constraints". The user selects one in the demo
  menu.
- **No modal dialogs.** The demo does not open a modal dialog. If a step uses
  a dialog (for example "Build column" or "Add Foliation"), the demo drives
  the dialog and closes it. A dialog that the demo cannot drive is a problem
  in the step (see the general rules, rule 2).

#### Design

A demo is a list of steps in data. A step has a target, an action and a
caption. The runner is a small state machine. The list and the runner do not
import QGIS widgets, so unit tests can run them.

```
demo script (data)                      runner                      dock
------------------                      ------                      ----
 step: target "step2.build_column"  ->  find control by id     ->   highlight
       action  click                    wait (speed)                click()
       wait_for "column_changed"        wait for signal        <-   signal
       caption "..."                    next step
```

- **Target ids.** Each control that a demo uses has a stable `objectName`
  (for example `step2.build_column`, `step4.primary_button`). The runner finds
  the control with `findChild`. A rename of an id fails a test. The ids are
  also usable by the other UI tests.
- **Actions.** `click`, `set_text`, `select_layer`, `select_item` (a combo or
  a menu entry), `check`, `go_to_step`, `wait_for` (a signal or a condition
  with a time limit).
- **Order from the dock.** The script does not hold the order of the workflow
  as a second copy. Where the next action is "press Next" or "press the primary
  button", the runner reads `choose_primary_action` and the footer text from the
  dock. A step that does not match the dock is a failure.
- **Checks.** After a step, the runner can assert a condition (the step status
  is "done", the footer shows no problem). A failed check stops the demo and
  names the step. This lets the CI run the same script without the delays.
- **Headless mode.** The same runner runs with no highlight and with zero
  delay, in the QGIS test job. This is the end-to-end test.

#### The two scripts

Map demo (about 20 actions):

1. Step 1: set the bounding box from the geology layer, set the CRS, and
   select the DEM.
2. Step 2: select the geology layer and the unit name field. "Build column"
   from the map. Calculate basal contacts and thickness ("Derive from map").
3. Step 3: select the fault layer and the name field. "Calculate topology".
   Show the adjacency tables.
4. Step 4: press the primary button (build and solve).
5. Step 5: "Open 3D view". Show an export action, with the output in a
   temporary folder.

Constraints demo (about 12 actions):

1. Step 1: set the bounding box. Select "Interpolate surfaces from
   constraints".
2. Step 4: "Add Foliation" from a value layer and an orientation layer, then
   press the primary button.
3. Step 4: "Add Fold Event" and a folded foliation, if phase 7 is merged.
4. Step 5: "Open 3D view".

Each demo ends with a message in the message bar and the demo bar shows
"Demo finished. Stop to remove the demo data, or keep it to explore."

#### Tasks

Do the parts in this order. Each part is a separate pull request.

9.1 Sample data

- [ ] Choose a small open data set that gives a model in less than one
      minute (a part of the Hamersley data, or a synthetic area). Check the
      licence, and record the source in the docs.
- [ ] Add the layers as one GeoPackage and one small DEM in
      `loopstructural/resources/demo/`. Keep the package size small (state the
      limit in the pull request, for example 5 MB).
- [ ] A function that adds the layers to a new project, with names and styles,
      and a function that removes them. It does not need the widgets.

9.2 Ids and signals

- [ ] Give each control that the demos use a stable `objectName`. Add a test
      that lists the ids and finds each one in the dock.
- [ ] Check that each action of the demos ends with a signal that the runner
      can wait for (column changed, derived data updated, topology
      calculated, model built or failed). Add the signal where it is missing.

9.3 Runner and overlay

- [ ] `gui/demo/script.py`: the step form, the actions, the speed settings. No
      QGIS import.
- [ ] `gui/demo/runner.py`: the state machine (run, pause, step, stop,
      error). It takes the time source and the control finder as arguments, so
      unit tests can use fakes.
- [ ] `gui/demo/overlay.py`: the highlight frame and the caption. It follows the
      control when the dock moves or resizes, and it works for a dock that is
      floating, tabbed or in a separate window (`separate_dock_widgets`).
- [ ] `gui/demo/demo_bar.py`: Pause, Step, Speed and Stop. Stop on a user click
      in the dock.

9.4 Scripts and entry

- [ ] The map demo and the constraints demo as data in `gui/demo/scripts/`.
- [ ] "Demo" in the dock header menu and in the Plugins menu. It asks before it
      replaces the project, then loads the sample data and starts the script.
- [ ] Stop removes the demo layers, resets the plugin state and restores the
      state before the demo (use the save and load of the application state).

9.5 Tests and docs

- [ ] A headless QGIS test that runs each script with zero delay and checks the
      result: the model is solved, and the number of features is as expected.
      Run it in the QGIS test job, so a change to the UI that breaks the
      workflow fails the build.
- [ ] A user guide page in `docs/usage` ("Try the demo"). Say what the demo
      does, how to stop it, and what it changes in the project.
- [ ] Use the demo to make the screenshots of the docs, so that they match the
      current UI.

Files: new `gui/demo/` module, `resources/demo/`, `plugin_main.py`,
`gui/modelling/steps/header.py`, and the step pages (ids and signals only).

Acceptance: a new user opens the demo from the dock menu. The plugin loads the
sample data and clicks through the steps, with a caption for each action, and
it ends with a solved model in the 3D view. The user can pause, step and stop.
After Stop, the project and the plugin state are as they were before the demo.
A script that is out of date (for example, a control was renamed or a step does
not become "done") stops with an error that names the step.

Tests: unit tests for the runner (run, pause, step, stop; a missing control; a
timeout; a failed check; a failed task) with a fake clock and fake controls.
Unit tests for the script form and for the sample data functions. A QGIS test
that runs both demos end to end with zero delay.

Order and links: 9.1 and 9.2 do not depend on each other. 9.3 depends on 9.2.
9.4 depends on 9.1 and 9.3. 9.5 comes last. Phase 9 depends on phase 3 (the
steps), phase 4 (the primary button and the two entries) and phase 5 (step 5).
The Fold Event part of the constraints demo depends on phase 7, and the 3D
view action can use the PyVista viewer or the viewer of phase 8.

## Risks

- **Large UI change.** Users of the current version must learn the new layout.
  Update `docs/usage` in the same pull request as each phase.
- **Saved state files.** Phases 1 and 4 add new data to the state. Load old
  state files without errors, and use default values for new keys.
- **Dialogs and Processing algorithms share code.** Phase 1 must not change the
  Processing algorithm parameters.
- **Two dock modes.** The `separate_dock_widgets` setting must work after
  phase 3.
- **Build time.** Extraction and thickness calculation at build time make the
  build slower. Calculate only the results that are out of date. Show the
  progress of each part.
- **User edits to a derived layer.** A user can edit the contacts layer that
  the plugin made. With "Calculate from geology polygons", the next update
  overwrites these edits. Show a warning before the overwrite, and offer to
  change the contacts source to "Use a contacts layer".

- **Saved fixed number of elements (phase 6.4).** Now the saved setting has no
  effect on a build. After the fix, a user who saved a small or large number
  sees a change in the result. Make "Automatic" the default, and tell the user
  in the change log.
- **Hidden data (phase 6.1).** The "constraints" mode keeps the map data but
  does not use it. Show a short message in step 4 ("The column and the map
  layers are not used in this mode"), so the user knows why a unit is not in
  the model.
- **Fold build time (phase 7).** A folded feature uses DFI, and a polyphase
  model builds a chain of frames. The build is slow. Build only the frames
  that are out of date, and show the progress of each frame.
- **Fold changes in old state files (phase 7).** A fold that the user added
  with "Attach fold frame" is not in the saved state. Thus an old project
  opens without that fold. Tell the user in the change log.
- **LoopStructural API (phase 7).** The plugin uses the fold builder
  arguments (`limb_wl`, `axis_wl`, `av_fold_axis`, the profile types). Some of
  them are keyword arguments, not public API. Pin the LoopStructural version
  and add a test for each argument.
- **Demo scripts become out of date (phase 9).** A script depends on the ids and
  the order of the controls. Run both scripts in the QGIS test job, so that a UI
  change that breaks them fails the build. Keep the script as data, with no
  copy of the workflow order.
- **Demo changes the user project (phase 9).** The demo adds layers and
  changes the plugin state. Use a new project, ask before it replaces the
  current one, and restore the state on Stop.
- **Package size (phase 9).** The sample data increases the size of the plugin
  package. Keep it small, and decide in the review if it must be a download.

## Open questions

1. Must the steps be strict (the user cannot go to step 4 before step 2 is
   done), or only a guide? Recommendation: only a guide. Show problems, but do
   not lock steps.
2. Is the Data Conversion dialog part of step 1, or a separate tool?
3. ~~In direct mode, which constraint types does each interpolator (FDI, PLI,
   surfe) support?~~ Resolved: all interpolators accept the same constraint
   types. LoopStructural converts them as needed. The UI shows the same types
   for every interpolator and does not hide any.
4. Is there a minimum QGIS version for the new widgets?
5. Must the Processing algorithms also use the derived-data record, or only
   the dock? Recommendation: only the dock. Processing runs are single runs
   with explicit inputs.
6. (6.2) After the move, step 2 has two geology pickers (the column group and
   the stratigraphic layers group). Must one of them be removed?
   Recommendation: keep the picker in the stratigraphic layers group, and show
   the geology layer in the column group as a read-only summary.
7. (6.4) Are the numbers of the element rule right? Test it with 3 or 4 real
   models (small and large, folded and simple) before the default is "Automatic".
   Does a fault need a different rule from a foliation?
8. (6.1) Must a manual unconformity or fold in the "constraints" mode use the
   column? Recommendation: no. It uses only the features of that mode.
9. (7) How does the plugin give the lineations of a layer to LoopStructural?
   `FoldFrame.calculate_fold_axis_rotation` has a `fold_axis` argument (an
   N x 6 array of points and lineations), but
   `FoldedFeatureBuilder.set_fold_axis` does not use it, and there is no build
   argument for it. "Average" of a lineation layer is easy: the plugin
   calculates the mean and gives it as `fold_axis`. For "fit", either the
   plugin calls `calculate_fold_axis_rotation` itself and sets
   `fold.fold_axis_rotation`, or LoopStructural gets a build argument for the
   lineations. Recommendation: add the build argument to LoopStructural, and
   use the plugin call until that version is released.
10. (7) Is "fold axis without axial surface" (tangent constraints on a grid)
    good enough, or must the plugin make a simple fold frame from the fold
    axis? Recommendation: tangent constraints first. Compare the two on the
    single fold example (`load_noddy_single_fold`).
11. (7) Must a fault that cuts a fold frame also cut the folded features?
    LoopStructural calculates the rotation angles in the restored space.
    Recommendation: yes, use the same faults. Test it before 7.5.
12. (9) Must the sample data be in the plugin package, or a download from the
    first demo run? Recommendation: in the package if it is below 5 MB. If it
    is larger, download it once and keep it in the QGIS profile folder.
13. (9) Must the demo also work from the Processing toolbox or the Python
    console (for example, `loopstructural.run_demo("map")`)? Recommendation:
    yes, one function. The test job and the screenshot job use it.
