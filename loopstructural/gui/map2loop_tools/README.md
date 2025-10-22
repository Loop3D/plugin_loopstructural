# Map2Loop Tools Widgets

This directory contains self-contained GUI widgets for map2loop processing tools.

## Widgets

### SorterWidget
GUI interface for automatic stratigraphic column sorting using various map2loop sorting algorithms:
- Age-based sorting
- NetworkX topological sorting
- Adjacency α sorting
- Maximise contacts sorting
- Observation projections sorting

**Features:**
- Dynamic UI that shows/hides fields based on selected algorithm
- Support for observation projections with structure and DTM data
- Field mapping for geology layers
- Integrated with QGIS processing framework

### UserDefinedSorterWidget
GUI interface for manually defining stratigraphic columns.

**Features:**
- Table-based interface for entering unit names
- Move up/down buttons for reordering units
- Add/remove row functionality
- Order from youngest (top) to oldest (bottom)

### SamplerWidget
GUI interface for contact sampling using Decimator and Spacing algorithms.

**Features:**
- Support for both Decimator and Spacing samplers
- Dynamic UI based on selected sampler type
- Decimator requires DTM and geology layers
- Spacing works with optional DTM and geology

### BasalContactsWidget
GUI interface for extracting basal contacts from geology layers.

**Features:**
- Support for fault layers
- Stratigraphic order integration
- Units to ignore configuration
- Extracts both basal contacts and all contacts

### ThicknessCalculatorWidget
GUI interface for calculating stratigraphic unit thickness using InterpolatedStructure or StructuralPoint methods.

**Features:**
- Two calculation methods: InterpolatedStructure and StructuralPoint
- Support for orientation data (dip direction or strike)
- DTM and bounding box configuration
- Integration with sampled contacts and basal contacts

## Usage

All widgets follow the same pattern:

1. They extend `QWidget`
2. Load UI from corresponding `.ui` file
3. Connect signals to update UI state dynamically
4. Provide `get_parameters()` and `set_parameters()` methods for reusability
5. Include a "Run" button that executes the corresponding processing algorithm

### Example

```python
from loopstructural.gui.map2loop_tools import SorterWidget

# Create widget
sorter_widget = SorterWidget(parent=None, data_manager=data_manager)

# Get parameters
params = sorter_widget.get_parameters()

# Set parameters
sorter_widget.set_parameters(params)
```

## Integration

The widgets are integrated into the main dock widget through `Map2LoopToolsTab`, which creates a new tab in the `ModellingWidget` containing all map2loop processing tools in collapsible group boxes.

## File Structure

```
map2loop_tools/
├── __init__.py                          # Package exports
├── sorter_widget.py                     # Automatic sorter widget
├── sorter_widget.ui                     # Automatic sorter UI
├── user_defined_sorter_widget.py        # User-defined sorter widget
├── user_defined_sorter_widget.ui        # User-defined sorter UI
├── sampler_widget.py                    # Sampler widget
├── sampler_widget.ui                    # Sampler UI
├── basal_contacts_widget.py             # Basal contacts widget
├── basal_contacts_widget.ui             # Basal contacts UI
├── thickness_calculator_widget.py       # Thickness calculator widget
└── thickness_calculator_widget.ui       # Thickness calculator UI
```

## Design Principles

Following the plugin's architectural guidelines:

1. **Thin Interface Layer**: Widgets only handle UI and user interaction, delegating to map2loop algorithms
2. **Modularity**: Each widget is self-contained and encapsulated
3. **Object-Oriented Design**: Clear responsibilities and interfaces
4. **Consistency**: Follows existing widget patterns in the codebase
