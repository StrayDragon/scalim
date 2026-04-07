import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from tests.support.pathing import repo_root as _repo_root


def test_public_reexports_importable() -> None:
    from scalim.dsl import yaml_dsl
    from scalim.dsl.yaml_dsl import RunOverrides, compile, run
    from scalim.execution import ScalimEngine
    from scalim.ob import Observability
    from scalim.planning import PlanBuilder
    from scalim.spec.ir import DemandIr

    _ = yaml_dsl
    _ = DemandIr
    _ = PlanBuilder
    _ = RunOverrides
    _ = ScalimEngine
    _ = Observability
    _ = compile
    _ = run


@pytest.mark.parametrize(
    "import_stmt",
    [
        "import scalim",
        "import scalim.dsl",
        "import scalim.dsl.yaml_dsl",
    ],
    ids=["import-scalim", "import-dsl", "import-by-yaml"],
)
def test_import_does_not_eagerly_load_optional_deps(import_stmt: str) -> None:
    repo_root = _repo_root()
    optional_module_names = [
        "pandas",
        "rich",
        "openpyxl",
        "jsonschema",
    ]

    code = textwrap.dedent(
        """
        import json
        import sys

        before = set(sys.modules)
        {import_stmt}
        after = set(sys.modules)

        optional = {optional_module_names!r}
        loaded = [name for name in optional if name in after and name not in before]
        print(json.dumps(loaded))
        """
    ).format(
        import_stmt=import_stmt,
        optional_module_names=optional_module_names,
    )

    out = subprocess.check_output([sys.executable, "-c", code], cwd=str(repo_root), text=True)
    loaded = json.loads(out)
    assert loaded == []
