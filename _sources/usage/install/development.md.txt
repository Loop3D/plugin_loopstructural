## Development version

If you want to install the development version of LoopStructural plugin, you can clone the repository and install the dependencies using `pip`.
1. Clone the repository:
   ```bash
   git clone https://github.com/Loop3d/plugin_loopstructural.git
   ```
2. Navigate to the cloned directory:
    ```bash
    cd plugin_loopstructural
    ```
3. Install the required dependencies:
    ```bash
    pip install -r loopstructural/requirements.txt
    ```
4. To add the plugin to QGIS make a symbolic link between the plugin location and the QGIS plugin folder:

 **linux**
 ```bash
 ln -s $(pwd)/loopstructural ~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/LoopStructural
 ```
**macOS**

```bash
ln -s $(pwd)/loopstructural ~/Library/Application\ Support/QGIS/QGIS3/profiles/default/python/plugins/LoopStructural
```

**Windows**

```bash
mklink /D "%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\LoopStructural" "%cd%\loopstructural"
```
5. Restart QGIS to load the plugin.
6. Install plugin autoreload
