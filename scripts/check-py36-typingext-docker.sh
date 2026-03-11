#!/usr/bin/env bash
set -euo pipefail

is_ci_enabled() {
    local v="${CI:-}"
    if [ -z "$v" ]; then
        return 1
    fi
    v=$(printf '%s' "$v" | tr '[:upper:]' '[:lower:]')
    case "$v" in
        0 | false | no)
            return 1
            ;;
    esac
    return 0
}

install_with_retry() {
    if is_ci_enabled; then
        python -m pip install -i https://pypi.org/simple "$@"
        return 0
    fi

    python -m pip install -i http://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com "$@" || python -m pip install "$@"
}

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

tmp_root=$(mktemp -d /tmp/scalim-py36-typingext.XXXXXX)
trap 'rm -rf "$tmp_root"' EXIT
pycache_prefix="$tmp_root/pycache"
mkdir -p "$pycache_prefix"

python -m venv "$tmp_root/venv"
. "$tmp_root/venv/bin/activate"

py_is_legacy=$(
    python - <<'PY'
import sys
print("1" if sys.version_info[:2] < (3, 7) else "0")
PY
)

if [ "$py_is_legacy" = "1" ]; then
    install_with_retry --upgrade "pip<22" "setuptools<60" "wheel<0.38"
    install_with_retry dataclasses "typing-extensions==4.1.1" "pyyaml>=5.4.1,<6.0.2"
else
    install_with_retry --upgrade pip setuptools wheel
    install_with_retry "typing-extensions==4.1.1" "pyyaml>=5.4.1,<6.0.2"
fi

PYTHONPYCACHEPREFIX="$pycache_prefix" PYTHONPATH="$repo_root/src" python -m compileall -q "$repo_root/src/scalim"
PYTHONPYCACHEPREFIX="$pycache_prefix" PYTHONPATH="$repo_root/src" python -c "from scalim.dsl.by_yaml import Compilation, RunOverrides; from scalim.execution import ScalimEngine; from scalim.ob import Observability; from scalim.planning import PlanBuilder; from scalim.spec.ir import DemandIr; from scalim.vendor.compact.typing_extensionsx import Self, override; _ = (Compilation, DemandIr, Observability, PlanBuilder, RunOverrides, ScalimEngine, Self, override); print('OK: typing-extensions 4.1.1')"
