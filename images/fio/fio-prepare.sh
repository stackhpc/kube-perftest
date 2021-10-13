#!/usr/bin/env bash

#####
## Script that runs the fio setup phase to generate the required files for a read test
#####

set -eo pipefail

CONFIG_FILE="${CONFIG_FILE:-/fio/job.fio}"
DATA_DIR="${WORK_DIR:-/scratch}/read"

mkdir -p "$DATA_DIR"

fio "$CONFIG_FILE" --create_only=1 --directory="$DATA_DIR" --rw=read
