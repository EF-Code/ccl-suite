#!/usr/bin/env bash

set -euo pipefail

base_url="${CCL_API_URL:-http://127.0.0.1:8000}"
project_root="${CCL_PROJECT_ROOT:-projects}"
suffix="$(date +%s)"
project_name="friday-backup-demo-${suffix}"

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required." >&2
  exit 1
fi
if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required." >&2
  exit 1
fi

owner_json="$(curl --fail --silent --show-error -X POST "${base_url}/users" \
  -H 'Content-Type: application/json' \
  -d "{\"external_ref\":\"${project_name}-owner\",\"role\":\"staff\"}")"
owner_id="$(printf '%s' "${owner_json}" | jq -r '.id')"

project_json="$(curl --fail --silent --show-error -X POST "${base_url}/projects" \
  -H 'Content-Type: application/json' \
  -H "X-User-ID: ${owner_id}" \
  -d "{\"title\":\"${project_name}\",\"description\":\"Friday backup recovery demo\",\"owner_id\":\"${owner_id}\"}")"
project_id="$(printf '%s' "${project_json}" | jq -r '.id')"

curl --fail --silent --show-error -X POST "${base_url}/project-folders" \
  -H 'Content-Type: application/json' \
  -H "X-User-ID: ${owner_id}" \
  -d "{\"project_name\":\"${project_name}\"}" >/dev/null

sample_path="${project_root}/${project_name}/incoming/recovery-check.txt"
mkdir -p "$(dirname -- "${sample_path}")"
printf 'Friday recovery check\n' >"${sample_path}"

backup_json="$(curl --fail --silent --show-error -X POST "${base_url}/projects/${project_id}/backups" \
  -H 'Content-Type: application/json' \
  -H "X-User-ID: ${owner_id}" \
  -d '{}')"
backup_id="$(printf '%s' "${backup_json}" | jq -r '.id')"

verify_json="$(curl --fail --silent --show-error -X POST "${base_url}/projects/${project_id}/backups/${backup_id}/verify" \
  -H 'Content-Type: application/json' \
  -H "X-User-ID: ${owner_id}" \
  -d '{}')"

restore_destination="restored/${project_name}"
restore_json="$(curl --fail --silent --show-error -X POST "${base_url}/projects/${project_id}/backups/${backup_id}/restore" \
  -H 'Content-Type: application/json' \
  -H "X-User-ID: ${owner_id}" \
  -d "{\"destination_path\":\"${restore_destination}\"}")"
restored_path="${project_root}/${restore_destination}/incoming/recovery-check.txt"

cmp -- "${sample_path}" "${restored_path}"

echo "Backup ID: ${backup_id}"
printf '%s\n' "${verify_json}" | jq '{entries_verified, files_verified, bytes_verified}'
printf '%s\n' "${restore_json}" | jq '{destination_path, files_restored, bytes_restored, archive_checksum_sha256, manifest_checksum_sha256}'
echo "Source and restored sample file match: ${restored_path}"
