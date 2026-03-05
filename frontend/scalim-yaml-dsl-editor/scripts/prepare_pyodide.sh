#!/usr/bin/env bash
set -euo pipefail

PYODIDE_VERSION="${PYODIDE_VERSION:-0.25.1}"
PYODIDE_BASE_URL="${PYODIDE_BASE_URL:-https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full}"

repo_root="$(cd "$(dirname "$0")/../../.." && pwd)"
target_dir="${repo_root}/frontend/scalim-yaml-dsl-editor/public/pyodide"

mkdir -p "${target_dir}"

echo "pyodide: version=${PYODIDE_VERSION}"
echo "pyodide: base_url=${PYODIDE_BASE_URL}"
echo "pyodide: target_dir=${target_dir}"

download() {
  local url="$1"
  local out="$2"
  if [ -f "${out}" ]; then
    echo "have: $(basename "${out}")"
    return 0
  fi
  echo "get: ${url}"
  curl -fsSL -o "${out}.tmp" "${url}"
  mv "${out}.tmp" "${out}"
}

base_files=(
  "pyodide.mjs"
  "pyodide.asm.js"
  "pyodide.asm.wasm"
  "python_stdlib.zip"
  "pyodide-lock.json"
)

for f in "${base_files[@]}"; do
  download "${PYODIDE_BASE_URL}/${f}" "${target_dir}/${f}"
done

packages_txt="${target_dir}/_packages.min.txt"
python - "${target_dir}/pyodide-lock.json" <<'PY' >"${packages_txt}"
import json
from collections import deque
from pathlib import Path
import sys

lock_path = Path(sys.argv[1])
lock = json.loads(lock_path.read_text(encoding="utf-8"))
packages = lock.get("packages", {})

roots = ["micropip", "pyyaml"]
seen = set()
q = deque(roots)

while q:
    name = q.popleft()
    if name in seen:
        continue
    info = packages.get(name)
    if not info:
        raise SystemExit("pyodide-lock.json missing package: {}".format(name))
    seen.add(name)
    for dep in info.get("depends", []) or []:
        q.append(dep)

for name in sorted(seen):
    print(packages[name]["file_name"])
PY

package_count="$(wc -l <"${packages_txt}" | tr -d ' ')"
echo "pyodide: packages=${package_count}"
while IFS= read -r file_name; do
  if [ -z "${file_name}" ]; then
    continue
  fi
  download "${PYODIDE_BASE_URL}/${file_name}" "${target_dir}/${file_name}"
done <"${packages_txt}"

echo "pyodide: ok"
