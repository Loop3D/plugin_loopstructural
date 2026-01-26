#!/usr/bin/env bash
set -euo pipefail

# Start the qgis container in background
docker-compose up -d qgis_test

CONTAINER=$(docker-compose ps -q qgis_test)
if [ -z "$CONTAINER" ]; then
  echo "Failed to start qgis_test container"
  exit 1
fi

echo "Container started: $CONTAINER"

echo "Copying plugin into container..."
# Copy plugin files into QGIS python plugins path inside container
docker cp . "$CONTAINER":/tests_directory

# Exec into container to install requirements and run tests
docker exec -it "$CONTAINER" bash -lc "python3 -m pip install -U pip setuptools wheel && python3 -m pip install -U -r requirements/testing.txt || true"

echo "To run tests interactively inside the container, use: docker exec -it $CONTAINER bash"
