#!/bin/sh
# Entrypoint script for Locust deployment mode (with web UI)
# Uses TARGET_HOST environment variable if set, otherwise defaults

TARGET_HOST=${TARGET_HOST:-"http://sender:8000"}

echo "Starting Locust with web UI"
echo "Target host: $TARGET_HOST"

exec locust \
    --host="$TARGET_HOST" \
    --web-host=0.0.0.0 \
    --web-port=8089

