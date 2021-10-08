#!/usr/bin/env bash

#####
## Lightweight script that understands how to pass all the files from a
## directory as jobs for fio
#####

set -e

JOBS_DIRECTORY="${JOBS_DIRECTORY:-/fio-jobs}"
if [ -d "$JOBS_DIRECTORY" ]; then
    JOB_FILES="$(find $JOBS_DIRECTORY -mindepth 1 -maxdepth 1 -type f)"
fi

exec fio "$@" $JOB_FILES
