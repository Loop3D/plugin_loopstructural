# MacOS

## Installation Instructions Using Homebrew or MacPorts

### Step 1: Install QGIS
1. Open a terminal on your Mac.
2. Install Homebrew if you haven't already:
   ```bash
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```
3. Use Homebrew to install QGIS:
   ```bash
   brew install qgis
   ```
   
### Step 2: Install Dependencies Using pip
1. Ensure you have `pip` installed. If not, install it using:
   ```bash
   sudo easy_install pip
   ```
2. Use `pip` to install the required dependencies for the plugin. Navigate to the directory containing the `requirements` files and run:
   ```bash
   pip install -r requirements.txt
   ```

### Step 3: Install the Plugin via QGIS Plugin Manager
1. Open QGIS on your system.
2. Navigate to the **Plugins** menu and select **Manage and Install Plugins**.
3. In the Plugin Manager, search for the plugin by name (e.g., `LoopStructural`).
4. Click **Install Plugin** to download and install it.

### Step 4: Verify Installation
1. Restart QGIS if necessary.
2. Confirm that the plugin is available under the **Plugins** menu.

You are now ready to use the plugin on your MacOS system!