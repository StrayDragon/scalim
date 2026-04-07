import os
import subprocess
import sys
from pathlib import Path

import pytest

from scalim.secure_compute_contracts import SecureComputeCalculatorContract, is_secure_compute_calculator
from tests.support.pathing import repo_root as _repo_root


def _run(code: str) -> str:
    repo_root = _repo_root()
    env = dict(os.environ)

    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(repo_root / "src") + (os.pathsep + existing_pythonpath if existing_pythonpath else "")

    return subprocess.check_output([sys.executable, "-c", code], cwd=str(repo_root), env=env, universal_newlines=True)


def test_compute_executor_import_does_not_pull_yaml_dsl_modules() -> None:
    output = _run(
        "import sys\n"
        "import scalim.execution.executor.operators.compute.executor\n"
        "mods = sorted(m for m in sys.modules if m.startswith('scalim.dsl.yaml_dsl'))\n"
        "print('\\n'.join(mods))\n"
    )
    assert output.strip() == ""


def test_import_orders_do_not_trigger_cycles() -> None:
    _ = _run("import scalim.execution.executor.operators.compute.executor\nimport scalim.dsl.yaml_dsl._internal.config_parsing.security\n")
    _ = _run("import scalim.dsl.yaml_dsl._internal.config_parsing.security\nimport scalim.execution.executor.operators.compute.executor\n")


def test_secure_compute_contract_default_call_is_not_implemented() -> None:
    class _Dummy(SecureComputeCalculatorContract):
        def __call__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            return None

    dummy = _Dummy()
    assert is_secure_compute_calculator(dummy)

    with pytest.raises(NotImplementedError):
        SecureComputeCalculatorContract.__call__(dummy)
