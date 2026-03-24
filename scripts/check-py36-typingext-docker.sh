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
PYTHONPYCACHEPREFIX="$pycache_prefix" PYTHONPATH="$repo_root/src" python - <<'PY'
# 说明:
# - 该检查刻意不安装 openpyxl/pandas 等可选依赖,用于捕获“import 时炸”的回归.
# - compileall 仅能发现语法问题; import smoke test 才能覆盖注解求值差异等问题(Python 3.6 典型坑).

from scalim.dsl.by_yaml import *  # noqa: F401,F403
from scalim.dsl.by_yaml import workflow_entrypoints  # noqa: F401
from scalim.execution import ScalimEngine  # noqa: F401
from scalim.execution import output_composition  # noqa: F401
from scalim.execution.preload_cache import PreloadCache  # noqa: F401
from scalim.ob import Observability  # noqa: F401
from scalim.planning import PlanBuilder  # noqa: F401
from scalim.spec.ir import DemandIr  # noqa: F401
from scalim.vendor.compact.typing_extensionsx import Self, override  # noqa: F401

_ = (
    DemandIr,
    Observability,
    PlanBuilder,
    PreloadCache,
    ScalimEngine,
    Self,
    output_composition,
    override,
    workflow_entrypoints,
)

print("检查通过: py36 + typing-extensions 4.1.1 + workflow import smoke")
PY
