# Installation Instructions for Windows

## Step 1: Install QGIS
1. Visit the [QGIS official website](https://qgis.org/en/site/forusers/download.html).
2. Download the latest QGIS installer for Windows.
3. Run the installer and follow the on-screen instructions to complete the installation.

## Step 2: Open the OSGeo4W Shell
1. After installing QGIS, locate the **OSGeo4W Shell**. You can find it in the Start Menu under the QGIS folder.
2. Open the **OSGeo4W Shell**. This shell provides a command-line environment for managing QGIS and its dependencies.

## Step 3: Install Dependencies Using `pip`
1. In the **OSGeo4W Shell**, ensure that Python is available by typing:
   ```bash
   python --version
   ```
   This should display the Python version bundled with QGIS.
2. Use `pip` to install the required dependencies. Run the following command:
   ```bash
   pip install LoopStructural pyvista pyvistaqt meshio geoh5py
   ```

## Step 4: Install the Plugin Using the QGIS Plugin Manager
1. Open QGIS.
2. Navigate to the **Plugins** menu and select **Manage and Install Plugins**.
3. In the Plugin Manager, search for the plugin by name (e.g., "LoopStructural").
4. Click **Install** to download and install the plugin.
5. Once installed, the plugin will be available in the QGIS interface.

## Step 5: Verify Installation
1. Restart QGIS to ensure all changes take effect.
2. Check the **Plugins** menu or toolbar for the installed plugin.
3. Open the plugin and verify that it is functioning as expected.
