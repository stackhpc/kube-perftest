#!/usr/bin/env bash

#####
## Script that understands how to execute fio as part of a Fio benchmark
## with configuration from environment variables
#####

set -e

CONFIG_FILE="${CONFIG_FILE:-/fio/job.fio}"
WORK_DIR="${WORK_DIR:-/scratch}"
NUM_CLIENTS="${NUM_CLIENTS:-1}"

# Benchmark and pod name are required
if [ -z "$BENCHMARK_NAME" ]; then
    echo "BENCHMARK_NAME is not set" 1>&2
    exit 1
fi
if [ -z "$POD_NAME" ]; then
    echo "POD_NAME is not set" 1>&2
    exit 1
fi

# Derive the lock and data directories
LOCK_DIR="${WORK_DIR}/${BENCHMARK_NAME}.lock"
DATA_DIR="${WORK_DIR}/${POD_NAME}"

# Wait for each client to make an entry in the lock directory before proceeding
rm -rf $LOCK_DIR
mkdir -p $LOCK_DIR
while true; do
    echo "READY" > "${LOCK_DIR}/${POD_NAME}"
    if [ "$(ls $LOCK_DIR | wc -l)" -ge "$NUM_CLIENTS" ]; then
        break
    fi
    sleep 1
done

# Once the clients have synchronised, remove the lock directory
# This prevents clients which error out from successfully restarting unless ALL the
# clients error out and restart, hence preventing the overall job from succeeding
# but not actually executing N clients in parallel as expected
rm -rf $LOCK_DIR

# Make the directory to create test resources in
mkdir -p $DATA_DIR

# Execute fio
fio $CONFIG_FILE --directory=$DATA_DIR --output=/dev/stdout --output-format=json+

# Clean up the directory afterwards
rm -rf $DATA_DIR
