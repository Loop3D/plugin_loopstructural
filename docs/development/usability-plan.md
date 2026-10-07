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

Four changes that come from use of phases 3 to 5. Do them in this order. Each
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

- [ ] Remove `StratigraphicLayersWidget` from `ModelDefinitionTab`. Step 1 has
      only the bounding box, the CRS and the DEM.
- [ ] Add the widget to `StratigraphyStep`, as a collapsible group (see 6.3).
- [ ] The first layer picker depends on the contacts source:
  - "Calculate from geology polygons": the picker shows polygon layers. It
    reads and writes the `geology` and `geology_unit_field` roles. It does not
    call `set_basal_contacts`. The Z-coordinate check box is hidden.
  - "Use a contacts layer": the picker shows line and point layers, as now. It
    reads and writes the `basal_contacts` role.
  - Change the group title and the label to match ("Geology layer" or
    "Contacts layer").
- [ ] When the user changes the source, do not write the old selection to the
      other role. Keep one selection for each source.
- [ ] The `set_basal_contacts` callback (a tool or a build made a new contacts
      layer) does not change the picker in the "geology" source. The layer is for
      display.
- [ ] Keep the geology picker of the column group in sync with the new picker
      (both use the same roles). Decide in the review if one of them must be
      removed (see the open questions).
- [x] Move the "Select the geology layer" and "Select the structure layer"
      items from `check_data` to `check_stratigraphy`.
- [ ] Update the text that says "in step 1" for these layers
      (`derived_refresh.py`, `checks.py`, `pages.py`, the docs).
- [ ] Keep the saved widget settings key `stratigraphic_layers_widget`, so old
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

- [ ] Add a small `SectionStack` widget in `gui/modelling/steps/`. It holds
      collapsible sections, the maximum number of open sections, and the
      collapsed state of each section. It saves the state in the widget
      settings.
- [ ] Use it in steps 1, 2, 3 and in the feature details panel of step 4
      (`Data Layers`, `Interpolator Settings`, `Preview`, `Export Feature`).
- [ ] Remove the scroll areas that are inside other scroll areas
      (`BaseTab(scrollable=True)`, the scroll area of
      `feature_details_panel/_base.py`).
- [ ] Give the page a header summary for each collapsed section, for example
      "Geology layer: Geology, UNITNAME", so the user does not need to expand
      it to read the value.
- [ ] Reduce the vertical use of the dock: the header and the footer use one
      row each. The footer text is one line with a tooltip.
- [ ] In step 4, the problems list is collapsed to one line ("3 problems") with
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

- [ ] `main/interpolation_size.py` with `summarise_data` and `suggest_nelements`.
- [ ] Setting, settings page and preference test.
- [ ] Model manager: one method for the interpolator arguments, used in all
      build paths. Fix the use of the class defaults.
- [ ] Feature panel: show the number, and an "Automatic" check box.
- [ ] Docs: say how the number is chosen, and what the user can change.

Acceptance: a model with 20 contact points and a model with 5 000 points get
different numbers of elements, both inside the limits. A saved fixed number is
used when "Automatic" is off. A user-added foliation gets a number.

Tests: unit tests for the function: more data gives more or equal elements; the
limits; no data; parallel and spread orientations; orientation signs do not
matter.

Order and links between the parts: 6.1 first, because it defines what the model
reads in each workflow. 6.2 depends on the same checks, so do it next. 6.3
comes after 6.2, because it must lay out the final content of the pages. 6.4
does not depend on the others.

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
