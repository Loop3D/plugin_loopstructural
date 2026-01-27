#!/usr/bin/env bash
set -euo pipefail

PLUGIN_NAME=${1:-loopstructural}
TEST_DIR=/tests_directory

if [ ! -d "$TEST_DIR/$PLUGIN_NAME" ]; then
  echo "Plugin folder '$PLUGIN_NAME' not present in $TEST_DIR"
  exit 1
fi

# Create QGIS python plugins dir if it doesn't exist
mkdir -p /usr/share/qgis/python/plugins

# Copy plugin
cp -r "$TEST_DIR/$PLUGIN_NAME" /usr/share/qgis/python/plugins/

# Ensure python path
export PYTHONPATH=/usr/share/qgis/python/plugins:/usr/share/qgis/python:.

echo "Plugin installed to /usr/share/qgis/python/plugins/$PLUGIN_NAME"
