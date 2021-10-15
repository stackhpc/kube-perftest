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

# Job and pod names are required
if [ -z "$JOB_NAME" ]; then
    echo "JOB_NAME is not set" 1>&2
    exit 1
fi
if [ -z "$POD_NAME" ]; then
    echo "POD_NAME is not set" 1>&2
    exit 1
fi

# For a read job, use the same data directory for all clients
# For a write job, each pod gets it's own directory
if [[ "$MODE" == *read ]]; then
    DATA_DIR="${WORK_DIR}/read"
else
    DATA_DIR="${WORK_DIR}/${POD_NAME}"
fi
mkdir -p "$DATA_DIR"

# We also need a job-specific directory for the lock files
LOCK_DIR="${WORK_DIR}/${JOB_NAME}.lock"

# Wait for each client to make an entry in the sync directory before proceeding
rm -rf "$LOCK_DIR"
while true; do
    mkdir -p "$LOCK_DIR"
    touch "${LOCK_DIR}/${POD_NAME}"
    if [ "$(ls $LOCK_DIR | wc -l)" -ge "$NUM_CLIENTS" ]; then
        break
    fi
    sleep 1
done

# Once the clients have synchronised, remove the lock directory
# This prevents clients which error out from successfully restarting unless ALL the
# clients error out and restart, hence preventing the overall job from succeeding
# but not actually executing N clients in parallel as expected
rm -rf "$LOCK_DIR"

# Execute fio
fio "$CONFIG_FILE" --directory="$DATA_DIR" --output=/dev/stdout --output-format=json+

# When running in write mode, clean up the directory
if [[ "$MODE" == *write ]]; then
    rm -rf $DATA_DIR
fi
