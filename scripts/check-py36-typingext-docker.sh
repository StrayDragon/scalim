#!/usr/bin/env bash
set -euo pipefail

install_with_retry() {
    python -m pip install  "$@" || python -m pip install -i http://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com "$@"
}

tmp_root=$(mktemp -d /tmp/scalim-py36-typingext.XXXXXX)
trap 'rm -rf "$tmp_root"' EXIT

python -m venv "$tmp_root/venv"
. "$tmp_root/venv/bin/activate"

install_with_retry --upgrade "pip<22" "setuptools<60" "wheel<0.38"
install_with_retry dataclasses "typing-extensions==4.1.1" "pyyaml>=5.4.1,<6.0.2"

PYTHONPATH=/repo/src python -m compileall -q /repo/src/scalim
PYTHONPATH=/repo/src python -c "from scalim.dsl.by_yaml import Compilation, RunOverrides; from scalim.execution import ScalimEngine; from scalim.ob import Observability; from scalim.planning import PlanBuilder; from scalim.spec.ir import DemandIr; from scalim.vendor.compact.typing_extensionsx import Self, override; _ = (Compilation, DemandIr, Observability, PlanBuilder, RunOverrides, ScalimEngine, Self, override); print('OK: py36 + typing-extensions 4.1.1')"
