# Design Document for LoopStructural Plugin
## Overview
The LoopStructural plugin is designed to integrate geological modeling capabilities from LoopStructural into QGIS. It provides tools for visualizing, managing, and analyzing geological data, enabling users to create and refine geological models directly within the QGIS environment.

### Design Choices
1. Modular Architecture
The plugin is structured into multiple modules, each responsible for specific functionalities:

    - GUI Module: Contains user interface components such as dialogs, widgets, and tabs for interacting with the plugin.
    - Main Module: Handles core functionalities like data management, model management, and project handling.
    - Processing Module: Provides processing algorithms and tools for geological data analysis.
    - Toolbelt Module: Includes utility functions like logging and preferences management.
    - Resources Module: Stores static resources such as images, translations, and help files.

    This modular design ensures separation of concerns, making the codebase easier to maintain and extend.

2. Integration with QGIS
The plugin leverages QGIS's PyQt-based framework for GUI development and its processing framework for data analysis. Key integration points include:

    - Use of QgsCollapsibleGroupBox for organizing UI components.
    - Implementation of custom processing algorithms using the Processing module.
    - Utilization of QGIS's vector and raster layers for geological data representation.

3. Dynamic UI Components
The plugin dynamically generates UI components based on the data provided by the data_manager. For example:

    - Fault adjacency tables are created dynamically based on unique faults retrieved from the data manager.
    - Stratigraphic units tables are similarly generated, allowing users to interact with geological units.

4. Custom Interactivity
Interactive elements like QPushButton are used extensively in the UI. These buttons allow users to perform actions such as toggling states or cycling through options (e.g., changing colors to represent different statuses).

5. Extensibility
The plugin is designed to be extensible, allowing developers to add new features or modify existing ones with minimal impact on the overall architecture. Examples include:

    - Adding new tabs or widgets to the GUI.
    - Extending the data_manager to support additional geological data types.
    - Implementing new processing algorithms in the Processing module.

6. Resource Management
Static resources such as images and translations are stored in the resources module. This ensures that all assets are centralized and easily accessible.

7. Testing
The plugin includes a tests directory with unit tests for various components. This ensures that changes to the codebase do not introduce regressions.

## Key Components
### GUI Module
- Fault Adjacency Tab: Displays a table of faults with interactive buttons for adjacency settings.
- Stratigraphic Units Tab: Similar to the fault adjacency tab but focused on stratigraphic units.
- Visualization Widgets: Tools for rendering geological models and features.
### Main Module
- Data Manager: Handles loading, saving, and querying geological data.
- Model Manager: Manages geological models, including their creation and modification.
### Processing Module
- Provider: Implements custom processing algorithms for geological data analysis.
### Toolbelt Module
- Log Handler: Provides logging utilities for debugging and monitoring.
- Preferences: Manages user preferences and settings.
## Future Enhancements
- Support for additional geological data types.
- Improved visualization capabilities using advanced rendering libraries.
- Enhanced interactivity with more intuitive UI components.
