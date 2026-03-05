#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../../.." && pwd)"
wheels_dir="${repo_root}/frontend/scalim-yaml-dsl-editor/public/wheels"
manifest_path="${repo_root}/frontend/scalim-yaml-dsl-editor/public/scalim-wheel.json"

mkdir -p "${wheels_dir}"
rm -f "${wheels_dir}/scalim-"*.whl

echo "wheel: building scalim into ${wheels_dir}"
uv build --wheel -o "${wheels_dir}" --no-create-gitignore "${repo_root}"

wheel_path="$(ls -1t "${wheels_dir}"/scalim-*.whl | head -n 1)"
wheel_file="$(basename "${wheel_path}")"

cat >"${manifest_path}" <<JSON
{
  "fileName": "${wheel_file}"
}
JSON

echo "wheel: ${wheel_file}"
echo "wheel: wrote ${manifest_path}"
