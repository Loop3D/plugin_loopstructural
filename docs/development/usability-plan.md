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

- [ ] Add a step navigation widget with a status for each step.
- [ ] Add a `check()` function for each step. It returns a status and a list of
      problems.
- [ ] Move the existing tabs into the steps, in the order of the target design.
- [ ] Move Save, Open, Reset and Settings into the dock header.
- [ ] Move the dialogs into their steps as buttons or menus. Keep the dialogs.
      Do not rewrite them in this phase.
- [ ] Move the Fault Topology Calculator into step 3.
- [ ] Reduce the toolbar to three actions. Put the dialogs in a "Tools"
      submenu.
- [ ] Keep the `separate_dock_widgets` setting.

Files: `loop_widget.py`, `modelling/modelling_widget.py`, `plugin_main.py`,
new `gui/modelling/steps/` module.

Acceptance: a new user can go from an empty project to a solved model with the
"Next" button only. Each step shows why it is not done.

### Phase 4: Model step and direct interpolation

- [ ] Replace "Initialize Model", "Solve Model" and "Update Model Data" with one
      primary button. Its text and action come from the model state.
- [ ] Show the problems from all steps before the build.
- [ ] Before the build, calculate all out-of-date derived data again: basal
      contacts first, then calculated thicknesses. Run this in a background
      task with progress. If the calculation fails, stop the build and show
      the error.
- [ ] With "Calculate from geology polygons", give the extracted contacts
      directly to the model. Update the project contacts layer for display
      only.
- [ ] Add the start choice: "Build from a geological map" or "Interpolate
      surfaces from constraints". Save the choice with the state.
- [ ] Constraint list for each feature: source layer, constraint type, field
      mapping, weight, Z source (layer Z, DEM or constant).
- [ ] Add the constraint types: value, interface, gradient/normal, tangent,
      inequality, pairwise inequality.
- [ ] Show generated constraints as read-only rows. Add "Detach" to make a
      generated feature editable.
- [ ] Build and preview one feature: an isoline on the map canvas, or a surface
      in the 3D view.
- [ ] Implement "Add Fault" in the model step.

Files: `geological_model_tab/*.py`, `layer_selection_table.py`,
`feature_details_panel/*.py`, `main/model_manager.py`.

Acceptance: a user can make a model from constraint layers only, without a
stratigraphic column. A user can add a direct-constraint feature to a
column-based model. After the user changes the column order and builds the
model, the model uses basal contacts and thicknesses that match the new order.

### Phase 5: View and export

- [ ] Show "Open 3D view" as the next action after a successful build.
- [ ] Add export of surfaces, block model and cross-sections to step 5.

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

## Open questions

1. Must the steps be strict (the user cannot go to step 4 before step 2 is
   done), or only a guide? Recommendation: only a guide. Show problems, but do
   not lock steps.
2. Is the Data Conversion dialog part of step 1, or a separate tool?
3. In direct mode, which constraint types does each interpolator (FDI, PLI,
   surfe) support? The UI must hide types that the selected interpolator does
   not support.
4. Is there a minimum QGIS version for the new widgets?
5. Must the Processing algorithms also use the derived-data record, or only
   the dock? Recommendation: only the dock. Processing runs are single runs
   with explicit inputs.
