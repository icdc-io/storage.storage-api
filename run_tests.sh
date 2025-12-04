#!/bin/bash

set -e  # Exit immediately if a command exits with a non-zero status
set -u  # Treat unset variables as an error
set -o pipefail  # Prevent errors in a pipeline from being masked

# Constants
IMAGE_NAME="$1"
NETWORK_NAME="storage-net"
DB_CONTAINER="storage-postgres"
APP_CONTAINER="storage"
DB_IMAGE="docker.io/library/postgres:16"
DB_PORT=5432
MAX_ATTEMPTS=10
SLEEP_INTERVAL=5
CR_SERVER="artifactory.icz.icdc.io/icdc-docker-proxy"

export DATABASE_HOST="$DB_CONTAINER"
export DATABASE_PORT="$DB_PORT"

log() {
  echo "[INFO] $1"
}

error() {
  echo "[ERROR] $1" >&2
  exit "$2"
}

# Ensure the custom network exists
if ! podman network exists "$NETWORK_NAME"; then
  log "Creating network: $NETWORK_NAME"
  podman network create "$NETWORK_NAME"
else
  log "Network $NETWORK_NAME already exists"
fi

# Stop and remove all running containers
log "Stopping and removing all running containers"
podman stop -a || true
podman rm -a || true

# Run the PostgreSQL database container
log "Starting PostgreSQL container: $DB_CONTAINER"
if ! podman run --rm -d --name "$DB_CONTAINER" \
  --env POSTGRES_USER="${DATABASE_USERNAME}" \
  --env POSTGRES_PASSWORD="${DATABASE_PASSWORD}" \
  --env POSTGRES_DB="${DATABASE_NAME}" \
  --network="$NETWORK_NAME" \
  --hostname "$DB_CONTAINER" \
  -p "$DB_PORT:$DB_PORT" \
  "$DB_IMAGE"; then
  error "Failed to start the database container" 2
fi

# Wait for the database to be ready
log "Waiting for database to be ready..."
export PGPASSWORD="${DATABASE_PASSWORD}"
attempt_counter=0

until podman exec -e PGPASSWORD="${DATABASE_PASSWORD}" "$DB_CONTAINER" \
  psql -h localhost -U "${DATABASE_USERNAME}" -d postgres -c '\l' | grep -q "${DATABASE_NAME}"; do
  if [ "$attempt_counter" -ge "$MAX_ATTEMPTS" ]; then
    error "Max attempts reached. test_gateways database is not available." 3
  fi

  log "Database not ready yet. Retrying in $SLEEP_INTERVAL seconds... (Attempt: $((attempt_counter+1))/$MAX_ATTEMPTS)"
  attempt_counter=$((attempt_counter+1))
  sleep "$SLEEP_INTERVAL"
done

log "Database is available!"

log "Starting application container: $APP_CONTAINER and running tests"
if ! podman run --rm --name "$APP_CONTAINER" \
  --env DATABASE_USERNAME="${DATABASE_USERNAME}" \
  --env DATABASE_PASSWORD="${DATABASE_PASSWORD}" \
  --env DATABASE_NAME="${DATABASE_NAME}" \
  --env DATABASE_HOST="${DATABASE_HOST}" \
  --env DATABASE_PORT="${DATABASE_PORT}" \
  --env CEPH_HOST="${CEPH_HOST}" \
  --env CEPH_ACCESS_KEY="${CEPH_ACCESS_KEY}" \
  --env CEPH_SECRET_KEY="${CEPH_SECRET_KEY}" \
  --env CEPH_SSH_KEY="${CEPH_SSH_KEY}" \
  --env FIXTURES_FILE="/tmp/fixtures.yaml" \
  -v "${FIXTURES_FILE}:/tmp/fixtures.yaml:z" \
  -v "${CEPH_SSH_KEYFILE}:/.ssh/id_ed25519:ro,z" \
  -v ./htmlcov:/usr/src/app/htmlcov:z \
  -v ./report.xml:/usr/src/app/report.xml:z \
  --network="$NETWORK_NAME" \
  "$IMAGE_NAME" sh -c "pytest -s -v --setup-show --junitxml=/usr/src/app/report.xml"; then
  error "Tests failed" 4
fi

# Stop and remove all running containers
log "Stopping and removing all running containers"
podman stop -a || true
podman rm -a || true

log "Tests completed successfully!"
