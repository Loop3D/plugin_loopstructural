Param()

# Start container
Write-Host "Starting qgis_test container..."
docker-compose up -d qgis_test | Out-Null

$container = docker-compose ps -q qgis_test
if (-not $container) {
    Write-Error "Failed to start qgis_test container"
    exit 1
}

Write-Host "Container started: $container"

Write-Host "Copying plugin into container..."
docker cp . "$container":/tests_directory

Write-Host "Installing python requirements inside container..."
docker exec -it $container bash -lc "python3 -m pip install -U pip setuptools wheel && python3 -m pip install -U -r requirements/testing.txt || true"

Write-Host "Start an interactive shell in the container with:`n    docker exec -it $container bash"
