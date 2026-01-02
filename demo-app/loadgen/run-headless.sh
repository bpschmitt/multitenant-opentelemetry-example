#!/bin/sh
# Headless Locust runner script
# Runs Locust without web UI for Kubernetes jobs

TARGET_HOST=${TARGET_HOST:-"http://sender:8000"}
USERS=${USERS:-10}
SPAWN_RATE=${SPAWN_RATE:-2}
RUN_TIME=${RUN_TIME:-"5m"}

echo "Starting Locust in headless mode"
echo "Target: $TARGET_HOST"
echo "Users: $USERS"
echo "Spawn rate: $SPAWN_RATE"
echo "Run time: $RUN_TIME"

exec locust \
    --headless \
    --host="$TARGET_HOST" \
    --users="$USERS" \
    --spawn-rate="$SPAWN_RATE" \
    --run-time="$RUN_TIME" \
    --html=/tmp/report.html \
    --csv=/tmp/stats \
    --loglevel=INFO

