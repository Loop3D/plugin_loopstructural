# Linux

## Installation Instructions

### Step 1: Install QGIS
1. Open a terminal on your Linux system.
2. Add the QGIS repository to your system:
   ```bash
   sudo add-apt-repository ppa:ubuntugis/ubuntugis-unstable
   sudo add-apt-repository ppa:qgis/qgis-stable
   ```
3. Update your package list:
   ```bash
   sudo apt update
   ```
4. Install QGIS:
   ```bash
   sudo apt install qgis python3-qgis
   ```



### Step 2: Install Dependencies Using pip
1. Ensure you have `pip` installed. If not, install it using:
   ```bash
   sudo apt install python3-pip
   ```
2. Use `pip` to install the required dependencies for the plugin. Navigate to the directory containing the `requirements` files and run:
   ```bash
   pip install -e requirements.txt
   ```

### Step 3: Install the Plugin via QGIS Plugin Manager
1. Open QGIS on your system.
2. Navigate to the **Plugins** menu and select **Manage and Install Plugins**.
3. In the Plugin Manager, search for the plugin by name (e.g., `LoopStructural`).
4. Click **Install Plugin** to download and install it.

### Step 4: Verify Installation
1. Restart QGIS if necessary.
2. Confirm that the plugin is available under the **Plugins** menu.

You are now ready to use the plugin on your Linux system!