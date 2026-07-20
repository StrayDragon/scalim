import shutil
from pathlib import Path

import scalim.dsl.yaml_dsl.compiler_frontend.compiler as frontend_compiler
from scalim.dsl.yaml_dsl.compiler_frontend import compile_demand_frontend, compile_demand_frontend_diagnostics
from scalim.dsl.yaml_dsl.compiler_frontend.contracts import StaticCompilation
from scalim.dsl.yaml_dsl._internal.config_parsing.error_envelope import ErrorEnvelope, ErrorLoc, ScalimYamlValidationError

from tests.support.pathing import fixtures_dir
from tests.support.snapshots import assert_json_snapshot
from tests.support.yaml_dsl_lsp_contracts import assert_no_path_leaks, normalize_json


def _scenario_dir(name: str) -> Path:
    return fixtures_dir() / "yaml_dsl_compiler_frontend" / str(name)


def _snapshot_path(scenario: str, filename: str) -> Path:
    return _scenario_dir(scenario) / "snapshots" / str(filename)


def _copy_workspace_fixture(scenario: str, dst: Path) -> None:
    src = _scenario_dir(scenario) / "workspace"
    shutil.copytree(src, dst)


def test_frontend_compilation_builds_plan_without_allowlist(tmp_path: Path) -> None:
    scenario = "basic_plan"
    workspace = tmp_path / "workspace"
    _copy_workspace_fixture(scenario, workspace)

    yaml_path = workspace / "demo.yaml"
    yaml_text = yaml_path.read_text(encoding="utf-8")

    diagnostics_only = compile_demand_frontend_diagnostics(
        yaml_path,
        yaml_text=yaml_text,
        allowed_yaml_roots=(workspace,),
    )
    assert diagnostics_only.diagnostics.ok()
    assert diagnostics_only.plan is None

    compilation = compile_demand_frontend(
        yaml_path,
        yaml_text=yaml_text,
        allowed_yaml_roots=(workspace,),
    )
    assert compilation.diagnostics.ok()
    assert compilation.plan is not None
    assert compilation.plan_snapshot is not None
    assert compilation.deps_snapshot is not None

    frontend_snapshot = normalize_json(compilation.as_frontend_snapshot(), workspace=workspace)
    plan_snapshot = normalize_json(compilation.plan_snapshot, workspace=workspace)
    deps_snapshot = normalize_json(compilation.deps_snapshot, workspace=workspace)

    assert_no_path_leaks(frontend_snapshot, workspace=workspace)
    assert_no_path_leaks(plan_snapshot, workspace=workspace)
    assert_no_path_leaks(deps_snapshot, workspace=workspace)

    assert_json_snapshot(_snapshot_path(scenario, "frontend.json"), frontend_snapshot)
    assert_json_snapshot(_snapshot_path(scenario, "plan.json"), plan_snapshot)
    assert_json_snapshot(_snapshot_path(scenario, "deps.json"), deps_snapshot)


def test_iter_file_import_cache_paths_filters_keys(tmp_path: Path) -> None:
    existing = tmp_path / "frag.yaml"
    existing.write_text("a: 1\n", encoding="utf-8")
    existing_dir = tmp_path / "dir"
    existing_dir.mkdir()

    cache = {
        "": {},
        "scalim://builtin": {},
        str(existing_dir): {},
        str(tmp_path / "missing.yaml"): {},
        str(existing): {},
    }
    paths = frontend_compiler._iter_file_import_cache_paths(cache)  # type: ignore[attr-defined]

    assert paths == [str(existing.resolve(strict=False))]


def test_static_compilation_as_frontend_snapshot_omits_effective_yaml_when_missing() -> None:
    snapshot = StaticCompilation(effective_yaml=None).as_frontend_snapshot()
    assert "effective_yaml" not in snapshot


def test_error_envelope_as_dict_omits_loc_when_missing() -> None:
    envelope = ErrorEnvelope(code="c", message="m", source_path="p", path="x", loc=None)
    assert envelope.as_dict() == {"code": "c", "message": "m", "source_path": "p", "path": "x"}


def test_frontend_diagnostics_reads_yaml_file_when_text_is_missing(tmp_path: Path) -> None:
    scenario = "basic_plan"
    workspace = tmp_path / "workspace"
    _copy_workspace_fixture(scenario, workspace)

    yaml_path = workspace / "demo.yaml"

    compilation = compile_demand_frontend_diagnostics(
        yaml_path,
        allowed_yaml_roots=(workspace,),
    )
    assert compilation.diagnostics.ok()
    assert compilation.effective_yaml is not None


def test_frontend_diagnostics_degrades_when_yaml_file_is_missing(tmp_path: Path) -> None:
    yaml_path = tmp_path / "missing.yaml"
    compilation = compile_demand_frontend_diagnostics(yaml_path)

    assert not compilation.diagnostics.ok()
    assert compilation.diagnostics.errors
    assert compilation.diagnostics.errors[0].code == "yaml_read_failed"


def test_frontend_diagnostics_degrades_on_unexpected_yaml_parse_error(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    def _boom(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(frontend_compiler, "load_yaml_mapping_text", _boom)

    yaml_path = tmp_path / "demo.yaml"
    compilation = compile_demand_frontend_diagnostics(yaml_path, yaml_text="a: 1\n")

    assert not compilation.diagnostics.ok()
    assert compilation.diagnostics.errors
    assert compilation.diagnostics.errors[0].code == "yaml_parse_failed"


def test_frontend_diagnostics_degrades_on_unexpected_imports_expansion_error(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    def _is_import(_payload: object) -> bool:
        return True

    def _boom(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(frontend_compiler, "contains_import_syntax", _is_import)
    monkeypatch.setattr(frontend_compiler, "expand_imports_inplace", _boom)

    yaml_path = tmp_path / "demo.yaml"
    compilation = compile_demand_frontend_diagnostics(yaml_path, yaml_text="a: 1\n")

    assert not compilation.diagnostics.ok()
    assert compilation.diagnostics.errors
    assert compilation.diagnostics.errors[0].code == "yaml_import_expansion_error"
    assert "unexpectedly" in compilation.diagnostics.errors[0].message


def test_frontend_compilation_returns_base_when_diagnostics_fail(tmp_path: Path) -> None:
    yaml_path = tmp_path / "demo.yaml"
    compilation = compile_demand_frontend(
        yaml_path,
        yaml_text="name: demo\n",
    )

    assert not compilation.diagnostics.ok()
    assert compilation.plan is None


def test_frontend_compilation_reports_config_validation_error(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    scenario = "basic_plan"
    workspace = tmp_path / "workspace"
    _copy_workspace_fixture(scenario, workspace)

    yaml_path = workspace / "demo.yaml"
    yaml_text = yaml_path.read_text(encoding="utf-8")

    err = ErrorEnvelope(
        code="boom",
        message="boom",
        source_path=str(yaml_path),
        path="(root)",
        loc=ErrorLoc(1, 1),
    )

    def _raise(_self, _raw_demand):
        raise ScalimYamlValidationError("boom", errors=(err,))

    monkeypatch.setattr(frontend_compiler.YamlDemandLoader, "parse_raw_demand", _raise)

    compilation = compile_demand_frontend(
        yaml_path,
        yaml_text=yaml_text,
        allowed_yaml_roots=(workspace,),
    )

    assert not compilation.diagnostics.ok()
    assert compilation.diagnostics.errors == (err,)
    assert compilation.effective_yaml is not None
    assert {Path(p).name for p in compilation.import_fragment_files} == {"frag.yaml"}


def test_frontend_compilation_reports_unexpected_config_error(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    scenario = "basic_plan"
    workspace = tmp_path / "workspace"
    _copy_workspace_fixture(scenario, workspace)

    yaml_path = workspace / "demo.yaml"
    yaml_text = yaml_path.read_text(encoding="utf-8")

    def _raise(_self, _raw_demand):
        raise RuntimeError("boom")

    monkeypatch.setattr(frontend_compiler.YamlDemandLoader, "parse_raw_demand", _raise)

    compilation = compile_demand_frontend(
        yaml_path,
        yaml_text=yaml_text,
        allowed_yaml_roots=(workspace,),
    )

    assert not compilation.diagnostics.ok()
    assert compilation.diagnostics.errors
    assert compilation.diagnostics.errors[0].code == "yaml_frontend_config_error"


def test_frontend_compilation_reports_ir_error(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    scenario = "basic_plan"
    workspace = tmp_path / "workspace"
    _copy_workspace_fixture(scenario, workspace)

    yaml_path = workspace / "demo.yaml"
    yaml_text = yaml_path.read_text(encoding="utf-8")

    def _raise(_self, _demand_config):
        raise RuntimeError("boom")

    monkeypatch.setattr(frontend_compiler.ConfigToIRConverter, "convert", _raise)

    compilation = compile_demand_frontend(
        yaml_path,
        yaml_text=yaml_text,
        allowed_yaml_roots=(workspace,),
    )

    assert not compilation.diagnostics.ok()
    assert compilation.diagnostics.errors
    assert compilation.diagnostics.errors[0].code == "yaml_frontend_ir_error"
    assert compilation.effective_yaml is not None


def test_frontend_compilation_reports_plan_error(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    scenario = "basic_plan"
    workspace = tmp_path / "workspace"
    _copy_workspace_fixture(scenario, workspace)

    yaml_path = workspace / "demo.yaml"
    yaml_text = yaml_path.read_text(encoding="utf-8")

    def _raise(_self, *, targets):
        raise RuntimeError("boom")

    monkeypatch.setattr(frontend_compiler.PlanBuilder, "build", _raise)

    compilation = compile_demand_frontend(
        yaml_path,
        yaml_text=yaml_text,
        allowed_yaml_roots=(workspace,),
    )

    assert not compilation.diagnostics.ok()
    assert compilation.diagnostics.errors
    assert compilation.diagnostics.errors[0].code == "yaml_frontend_plan_error"
    assert compilation.demand_ir is not None


def test_validate_demand_yaml_maps_warnings(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    from scalim.dsl.yaml_dsl._internal.config_parsing.validators.issues import ValidationReport

    class _WarnOnlyValidator:
        def validate_report(self, _data, *, strict_unknown_fields: bool = False):  # type: ignore[no-untyped-def]
            _ = strict_unknown_fields
            report = ValidationReport()
            report.add_warning("soft-issue", path="fields.x")
            return report

    monkeypatch.setattr(frontend_compiler, "ConfigValidator", lambda: _WarnOnlyValidator())

    diagnostics = frontend_compiler._validate_demand_yaml(  # type: ignore[attr-defined]
        {"name": "demo"},
        yaml_path=tmp_path / "demo.yaml",
        locations={},
    )
    assert diagnostics.ok()
    assert len(diagnostics.warnings) == 1
    assert diagnostics.warnings[0].code == "yaml_validate_warning"
    assert diagnostics.warnings[0].path == "fields.x"
