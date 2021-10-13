#!/usr/bin/env bash

#####
## Script that runs the fio setup phase to generate the required files for a test
#####

set -eo pipefail

CONFIG_FILE="${CONFIG_FILE:-/fio/job.fio}"

if [ -z "$BENCHMARK_NAME" ]; then
    echo "BENCHMARK_NAME is not set" 1>&2
    exit 1
fi

DATA_DIR="${WORK_DIR:-/scratch}/${BENCHMARK_NAME}"
mkdir -p $DATA_DIR

# Get the mode from the configuration file
MODE="$(grep -E "^rw=" "$CONFIG_FILE" | sed -E "s/^rw=//")"

# Lay out the files for read mode only
if [ "$MODE" == *read ]; then
    echo "[INFO] Read mode detected - laying out required files"
    fio $CONFIG_FILE --create_only=1 --directory=$DATA_DIR
else
    echo "[INFO] Write mode detected - nothing to do"
fi
