#!/usr/bin/env bash

set -Eeuo pipefail
umask 077

project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
data_root="${XDG_DATA_HOME:-$HOME/.local/share}"
backup_root="${CCL_DATABASE_BACKUP_DIR:-$data_root/ccl-suite/database-backups}"
retention_days="${CCL_DATABASE_BACKUP_RETENTION_DAYS:-14}"

if [[ ! "$retention_days" =~ ^[0-9]+$ ]] || ((retention_days < 7 || retention_days > 365)); then
  printf 'CCL_DATABASE_BACKUP_RETENTION_DAYS must be an integer from 7 through 365.\n' >&2
  exit 2
fi

for command_name in docker flock sha256sum; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    printf 'Required command is unavailable: %s\n' "$command_name" >&2
    exit 127
  fi
done

if [[ -L "$backup_root" ]]; then
  printf 'Refusing to write backups through a symlink: %s\n' "$backup_root" >&2
  exit 1
fi
install -d -m 0700 -- "$backup_root"
chmod 0700 -- "$backup_root"

lock_file="$backup_root/.backup.lock"
exec 9>"$lock_file"
chmod 0600 -- "$lock_file"
if ! flock -n 9; then
  printf 'Another CCL Suite database backup is already running.\n' >&2
  exit 1
fi

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
revision="$(git -C "$project_root" rev-parse --short=12 HEAD 2>/dev/null || printf 'unknown')"
archive_name="ccl-suite-postgres-${timestamp}-${revision}.dump"
archive_path="$backup_root/$archive_name"
checksum_path="$archive_path.sha256"
temporary_archive="$backup_root/.${archive_name}.partial.$$"
temporary_checksum="$temporary_archive.sha256"

if [[ -e "$archive_path" || -e "$checksum_path" ]]; then
  printf 'Refusing to overwrite an existing backup: %s\n' "$archive_path" >&2
  exit 1
fi
trap 'rm -f -- "$temporary_archive" "$temporary_checksum"' EXIT

docker compose --project-directory "$project_root" exec -T db sh -ec \
  'exec pg_dump --format=custom --no-owner --username="$POSTGRES_USER" --dbname="$POSTGRES_DB"' \
  >"$temporary_archive"
if [[ ! -s "$temporary_archive" ]]; then
  printf 'PostgreSQL produced an empty backup archive.\n' >&2
  exit 1
fi

docker compose --project-directory "$project_root" exec -T db sh -ec \
  'pg_restore --list >/dev/null' <"$temporary_archive"

digest="$(sha256sum -- "$temporary_archive")"
digest="${digest%% *}"
printf '%s  %s\n' "$digest" "$archive_name" >"$temporary_checksum"
chmod 0600 -- "$temporary_archive" "$temporary_checksum"
mv -- "$temporary_archive" "$archive_path"
mv -- "$temporary_checksum" "$checksum_path"
(
  cd -- "$backup_root"
  sha256sum --check "$(basename -- "$checksum_path")" >/dev/null
)

retention_minutes=$((retention_days * 1440))
while IFS= read -r -d '' expired_archive; do
  rm -- "$expired_archive" "${expired_archive}.sha256"
done < <(
  find "$backup_root" -maxdepth 1 -type f \
    -name 'ccl-suite-postgres-*.dump' \
    -mmin "+$retention_minutes" -print0
)

archive_size="$(stat -c '%s' -- "$archive_path")"
printf 'Verified database backup: %s (%s bytes, SHA-256 %s, source revision %s)\n' \
  "$archive_path" "$archive_size" "$digest" "$revision"
