#!/bin/bash

# Docker/OpenShift Wrapper Script
# This script ensures that a user entry exists in /etc/passwd before executing commands.
# Especially useful in containerized environments where a valid user entry might be required.

# Check if the current user exists in /etc/passwd
if ! whoami &> /dev/null; then
  # Check if we can write to /etc/passwd
  if [ -w /etc/passwd ]; then
    # Add the user entry to /etc/passwd
    echo "${USER_NAME:-default}:x:$(id -u):0:${USER_NAME:-default} user:${HOME}:/sbin/nologin" >> /etc/passwd

  fi
fi

# Run migrations and seeding.
# The WebSocket service shares this image but must not race the API pod on
# migrations, so it starts with SKIP_MIGRATIONS=1.
if [ "${SKIP_MIGRATIONS:-0}" != "1" ]; then
  FLASK_APP=main:flask_app flask db upgrade --directory migrations -x dummy=1
fi

# Execute the provided command
exec "$@"
