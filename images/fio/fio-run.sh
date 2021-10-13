#!/usr/bin/env bash

#####
## Lightweight script that understands how to pass all the files from a
## directory as jobs for fio
#####

set -e

# Allow the conf directory to come from an environment variable
CONF_DIRECTORY="${CONF_DIRECTORY:-/fio}"
if [ -d "$CONF_DIRECTORY" ]; then
    JOB_FILES="$(find $CONF_DIRECTORY -mindepth 1 -maxdepth 1)"
fi

# Extract the given directory from the arguments without consuming them
DIRECTORY="$PWD"
for arg in "$@"; do
    case "$arg" in
        --directory=*)
            DIRECTORY="${arg#*=}"
            ;;
    esac
done

# Execute FIO with the given arguments
fio "$@" $JOB_FILES

# Clean up the directory afterwards
rm -rf "$DIRECTORY"