#!/usr/bin/env bash

#####
## Lightweight script that understands how to pass all the files from a
## directory as jobs for fio
#####

set -e

CONF_DIRECTORY="${CONF_DIRECTORY:-/fio}"
if [ -d "$CONF_DIRECTORY" ]; then
    JOB_FILES="$(find $CONF_DIRECTORY -mindepth 1 -maxdepth 1 -type f)"
fi

exec fio "$@" $JOB_FILES
