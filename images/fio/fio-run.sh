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
# For a write job, each client gets it's own directory
if [[ "$MODE" == *read ]]; then
    DATA_DIR="${WORK_DIR}/read"
else
    DATA_DIR="${WORK_DIR}/${POD_NAME}"
fi
mkdir -p "$DATA_DIR"

# For read mode jobs, one client is designated to prepare the files
# The first client to create the sentinel file in the DATA_DIR wins
if [[ "$MODE" == *read ]] && [ ! -f "$DATA_DIR/.lock" ]; then
    touch "$DATA_DIR/.lock"
    fio "$CONFIG_FILE" --create_only=1 --directory="$DATA_DIR" 1>/dev/null
    rm "$DATA_DIR/.lock"
fi

# Wait for each client to make an entry in the lock directory for the job before proceeding
LOCK_DIR="${WORK_DIR}/${JOB_NAME}.lock"
mkdir -p "$LOCK_DIR"
while true; do
    touch "${LOCK_DIR}/${POD_NAME}"
    if [ "$(ls $LOCK_DIR | wc -l)" -ge "$NUM_CLIENTS" ]; then
        break
    fi
    sleep 1
done

# Execute fio
fio "$CONFIG_FILE" --directory="$DATA_DIR" --output=/dev/stdout --output-format=json+

# Each pod removes it's own lock file
rm "${LOCK_DIR}/${POD_NAME}"
# The last one out removes the directory
rmdir "$LOCK_DIR" || true
# In write mode, remove the whole data directory
if [[ "$MODE" == *write ]]; then
    rm -rf "$DATA_DIR"
fi
