#!/bin/sh
set -eu

for storage_path in /app/projects /app/backups /app/database-credentials; do
    if [ ! -d "$storage_path" ]; then
        echo "Required storage volume is unavailable." >&2
        exit 1
    fi

    owner="$(stat -c '%u:%g' "$storage_path")"
    if [ "$owner" != "10001:10001" ]; then
        chown -R --no-dereference 10001:10001 "$storage_path"
    fi
done
