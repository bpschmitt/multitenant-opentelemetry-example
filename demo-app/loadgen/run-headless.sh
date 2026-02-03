#!/bin/sh
# Headless Locust runner script
# Runs Locust without web UI for Kubernetes jobs

TARGET_HOST=${TARGET_HOST:-"http://sender:8000"}
# Strip quotes from numeric values if present (Helm may add them)
USERS=$(echo ${USERS:-10} | tr -d '"')
SPAWN_RATE=$(echo ${SPAWN_RATE:-2} | tr -d '"')

# Strip quotes from RUN_TIME if present
if [ -n "$RUN_TIME" ]; then
    RUN_TIME=$(echo "$RUN_TIME" | tr -d '"')
fi

echo "Starting Locust in headless mode"
echo "Target: $TARGET_HOST"
echo "Users: $USERS"
echo "Spawn rate: $SPAWN_RATE"
if [ -n "$RUN_TIME" ]; then
    echo "Run time: $RUN_TIME"
else
    echo "Run time: unlimited (no time limit)"
fi

LOCUST_ARGS="--headless --host=$TARGET_HOST --users=$USERS --spawn-rate=$SPAWN_RATE"
if [ -n "$RUN_TIME" ]; then
    LOCUST_ARGS="$LOCUST_ARGS --run-time=$RUN_TIME"
fi
exec locust $LOCUST_ARGS --html=/tmp/report.html --csv=/tmp/stats --loglevel=INFO

