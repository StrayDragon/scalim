import shutil
from pathlib import Path

import scalim_yaml_dsl_lsp.core as editor_semantics
from scalim.dsl.yaml_dsl.compiler_frontend import compile_demand_frontend

from tests.support.pathing import fixtures_dir
from tests.support.yaml_dsl_lsp_contracts import assert_no_path_leaks, normalize_json


def _scenario_dir(name: str) -> Path:
    return fixtures_dir() / "yaml_dsl_compiler_frontend" / str(name)


def _copy_workspace_fixture(scenario: str, dst: Path) -> None:
    src = _scenario_dir(scenario) / "workspace"
    shutil.copytree(src, dst)


def test_lsp_semantics_can_build_plan_deps_without_allowlist(tmp_path: Path) -> None:
    scenario = "basic_plan"
    workspace = tmp_path / "workspace"
    _copy_workspace_fixture(scenario, workspace)

    yaml_path = workspace / "demo.yaml"
    yaml_text = yaml_path.read_text(encoding="utf-8")

    result = editor_semantics.compile_yaml_dsl_editor_plan_deps(
        yaml_path,
        yaml_text=yaml_text,
        workspace_root_override=workspace,
    )
    assert result.errors == ()
    assert result.plan_snapshot is not None
    assert result.deps_snapshot is not None

    compilation = compile_demand_frontend(
        yaml_path,
        yaml_text=yaml_text,
        allowed_yaml_roots=(workspace,),
    )
    assert compilation.diagnostics.ok()
    assert compilation.plan_snapshot == result.plan_snapshot
    assert compilation.deps_snapshot == result.deps_snapshot

    payload = normalize_json(result.as_dict(), workspace=workspace)
    assert_no_path_leaks(payload, workspace=workspace)
