#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../../.." && pwd)"

pyodide_dir="${repo_root}/frontend/scalim-yaml-dsl-editor/public/pyodide"
manifest_path="${repo_root}/frontend/scalim-yaml-dsl-editor/public/scalim-wheel.json"
wheels_dir="${repo_root}/frontend/scalim-yaml-dsl-editor/public/wheels"

missing=0
require_local_pyodide="${SCALIM_YAML_DSL_EDITOR_REQUIRE_LOCAL_PYODIDE:-0}"

need_file() {
  local path="$1"
  if [ ! -f "${path}" ]; then
    echo "missing: ${path}" >&2
    missing=1
  fi
}

need_dir() {
  local path="$1"
  if [ ! -d "${path}" ]; then
    echo "missing: ${path} (dir)" >&2
    missing=1
  fi
}

check_pyodide=0
if [ -n "${require_local_pyodide}" ] && [ "${require_local_pyodide}" != "0" ]; then
  check_pyodide=1
fi

if [ "${check_pyodide}" -eq 1 ]; then
  need_dir "${pyodide_dir}"
  need_file "${pyodide_dir}/pyodide.mjs"
  need_file "${pyodide_dir}/pyodide.asm.js"
  need_file "${pyodide_dir}/pyodide.asm.wasm"
  need_file "${pyodide_dir}/python_stdlib.zip"
  need_file "${pyodide_dir}/pyodide-lock.json"
  need_file "${pyodide_dir}/_packages.min.txt"

  if [ -f "${pyodide_dir}/_packages.min.txt" ]; then
    while IFS= read -r file_name; do
      if [ -z "${file_name}" ]; then
        continue
      fi
      need_file "${pyodide_dir}/${file_name}"
    done <"${pyodide_dir}/_packages.min.txt"
  fi
else
  echo "note: local pyodide assets not checked (CDN fallback enabled). Set SCALIM_YAML_DSL_EDITOR_REQUIRE_LOCAL_PYODIDE=1 to require local assets."
fi

need_file "${manifest_path}"

wheel_file=""
if [ -f "${manifest_path}" ]; then
  wheel_file="$(
    python - "${manifest_path}" <<'PY'
import json
import sys

path = sys.argv[1]
with open(path, "r", encoding="utf-8") as handle:
    data = json.load(handle)
print(str(data.get("fileName", "")).strip())
PY
  )"
  if [ -z "${wheel_file}" ]; then
    echo "invalid: ${manifest_path} missing fileName" >&2
    missing=1
  else
    need_file "${wheels_dir}/${wheel_file}"
  fi
fi

if [ "${missing}" -ne 0 ]; then
  echo "" >&2
  echo "Fix:" >&2
  echo "  bash frontend/scalim-yaml-dsl-editor/scripts/build_scalim_wheel.sh" >&2
  echo "  # Optional (offline/local Pyodide assets):" >&2
  echo "  bash frontend/scalim-yaml-dsl-editor/scripts/prepare_pyodide.sh" >&2
  exit 1
fi

echo "ok: scalim wheel assets present"
