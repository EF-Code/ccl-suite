#!/usr/bin/env bash

set -Eeuo pipefail

project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
archive_argument="${1:-}"
if [[ -z "$archive_argument" || ! -f "$archive_argument" ]]; then
  printf 'Usage: %s /path/to/ccl-suite-postgres-<timestamp>-<revision>.dump\n' "$0" >&2
  exit 2
fi

for command_name in docker realpath sha256sum; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    printf 'Required command is unavailable: %s\n' "$command_name" >&2
    exit 127
  fi
done

archive_path="$(realpath -e -- "$archive_argument")"
archive_directory="$(dirname -- "$archive_path")"
archive_name="$(basename -- "$archive_path")"
checksum_name="${archive_name}.sha256"
if [[ ! -f "$archive_path.sha256" ]]; then
  printf 'Backup checksum file is missing: %s\n' "$archive_path.sha256" >&2
  exit 1
fi
(
  cd -- "$archive_directory"
  sha256sum --check "$checksum_name"
)

restore_database="ccl_restore_check_$(date -u +%Y%m%d%H%M%S)_$$"
if [[ ! "$restore_database" =~ ^[a-z0-9_]+$ ]]; then
  printf 'Generated an unsafe restore database name.\n' >&2
  exit 1
fi

compose=(docker compose --project-directory "$project_root")
source_database="$("${compose[@]}" exec -T db sh -ec 'printf "%s" "$POSTGRES_DB"')"
if [[ "$restore_database" == "$source_database" ]]; then
  printf 'Refusing to restore over the live database.\n' >&2
  exit 1
fi

restore_created=0
cleanup_restore_database() {
  if ((restore_created)); then
    "${compose[@]}" exec -T db sh -ec \
      'dropdb --if-exists --username="$POSTGRES_USER" "$1"' sh "$restore_database" \
      >/dev/null || true
  fi
}
trap cleanup_restore_database EXIT

"${compose[@]}" exec -T db sh -ec \
  'createdb --username="$POSTGRES_USER" "$1"' sh "$restore_database"
restore_created=1
"${compose[@]}" exec -T db sh -ec \
  'pg_restore --exit-on-error --no-owner --username="$POSTGRES_USER" --dbname="$1"' \
  sh "$restore_database" <"$archive_path"

restore_summary="$("${compose[@]}" exec -T db sh -ec \
  'psql --no-psqlrc --set=ON_ERROR_STOP=1 --username="$POSTGRES_USER" --dbname="$1" --tuples-only --no-align --command="SELECT (SELECT version_num FROM alembic_version), (SELECT count(*) FROM users), (SELECT count(*) FROM projects)"' \
  sh "$restore_database")"
if [[ -z "$restore_summary" ]]; then
  printf 'The restored database did not return its schema and record summary.\n' >&2
  exit 1
fi

printf 'Restore rehearsal passed: schema/users/projects summary %s; temporary database will be removed.\n' \
  "$restore_summary"
