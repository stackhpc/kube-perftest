#!/usr/bin/env bash

#####
## Script that understands how to execute fio as part of a Fio benchmark
## with configuration from environment variables
#####

set -e

CONFIG_FILE="${CONFIG_FILE:-/fio/job.fio}"
WORK_DIR="${WORK_DIR:-/scratch}"
NUM_CLIENTS="${NUM_CLIENTS:-1}"

# Get the mode from the configuration file
MODE="$(grep -E "^rw=" "$CONFIG_FILE" | sed -E "s/^rw=//")"

# Benchmark and pod name are required
if [ -z "$BENCHMARK_NAME" ]; then
    echo "BENCHMARK_NAME is not set" 1>&2
    exit 1
fi
if [ -z "$POD_NAME" ]; then
    echo "POD_NAME is not set" 1>&2
    exit 1
fi

# For a read job, use the same data directory for all clients
# For a write job, each pod gets it's own directory
if [ "$MODE" == *read ]; then
    DATA_DIR="${WORK_DIR}/${BENCHMARK_NAME}"
else
    DATA_DIR="${WORK_DIR}/${BENCHMARK_NAME}/${POD_NAME}"
fi
mkdir -p "$DATA_DIR"

# We also need directories for the syncing and sentinel files
SYNC_DIR="${WORK_DIR}/${BENCHMARK_NAME}/.sync"
RUN_DIR="${WORK_DIR}/${BENCHMARK_NAME}/.run"

# Wait for each client to make an entry in the sync directory before proceeding
rm -rf "$SYNC_DIR"
while true; do
    mkdir -p "$SYNC_DIR"
    touch "${SYNC_DIR}/${POD_NAME}"
    if [ "$(ls $SYNC_DIR | wc -l)" -ge "$NUM_CLIENTS" ]; then
        break
    fi
    sleep 1
done

# Once the clients have synchronised, remove the sync directory
# This prevents clients which error out from successfully restarting unless ALL the
# clients error out and restart, hence preventing the overall job from succeeding
# but not actually executing N clients in parallel as expected
rm -rf "$SYNC_DIR"

# Create the sentinel file to indicate that we are running
mkdir -p "$RUN_DIR"
touch "$RUN_DIR/$POD_NAME"

# Execute fio
fio "$CONFIG_FILE" --directory="$DATA_DIR" --output=/dev/stdout --output-format=json+

# When running in write mode, clean up the directory
if [ "$MODE" == *write ]; then
    rm -rf $DATA_DIR
fi

# Remove the sentinel file
rm -rf "$RUN_DIR/$POD_NAME"
