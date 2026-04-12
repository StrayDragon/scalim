from pathlib import Path

import pytest

from scalim.dsl.yaml_dsl import DemandDiagnosticsOverride, DemandDiagnosticsPolicy, RunOptions, compile
from scalim.dsl.yaml_dsl._internal.config_parsing.error_envelope import ScalimYamlValidationError

_ALLOWED_MODULES = frozenset(["tests.fixtures.mock_loaders"])


def test_yaml_validate_unique_field_names_is_rejected_with_migration_guidance(tmp_path: Path) -> None:
    yaml_text = """
name: demo
validate_unique_field_names: false
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
""".lstrip()

    yaml_path = tmp_path / "demand.yaml"
    yaml_path.write_text(yaml_text, encoding="utf-8")

    with pytest.raises(ScalimYamlValidationError) as excinfo:
        _ = compile(str(yaml_path), options=RunOptions(allowed_modules=_ALLOWED_MODULES))

    assert any(env.path == "validate_unique_field_names" for env in excinfo.value.errors)
    assert any("demand_diagnostics=DemandDiagnosticsPolicy" in env.message for env in excinfo.value.errors)


def test_yaml_include_full_error_message_is_rejected_with_migration_guidance(tmp_path: Path) -> None:
    yaml_text = """
name: demo
include_full_error_message: true
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
""".lstrip()

    yaml_path = tmp_path / "demand.yaml"
    yaml_path.write_text(yaml_text, encoding="utf-8")

    with pytest.raises(ScalimYamlValidationError) as excinfo:
        _ = compile(str(yaml_path), options=RunOptions(allowed_modules=_ALLOWED_MODULES))

    assert any(env.path == "include_full_error_message" for env in excinfo.value.errors)
    assert any("demand_diagnostics=DemandDiagnosticsPolicy" in env.message for env in excinfo.value.errors)


def test_runtime_demand_diagnostics_policy_is_applied(tmp_path: Path) -> None:
    yaml_text = """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
resources:
  files:
    detail_csv: {kind: csv_file, path: ./out}
outputs:
  - name: detail
    to: {file: detail_csv}
    fields: [order_id]
""".lstrip()

    yaml_path = tmp_path / "demand.yaml"
    yaml_path.write_text(yaml_text, encoding="utf-8")

    compilation = compile(str(yaml_path), options=RunOptions(allowed_modules=_ALLOWED_MODULES))
    assert compilation.request.output_composition is not None
    assert compilation.config.include_full_error_message is False
    assert compilation.request.output_composition.include_full_error_message is False

    compilation_full = compile(
        str(yaml_path),
        options=RunOptions(
            allowed_modules=_ALLOWED_MODULES,
            demand_diagnostics=DemandDiagnosticsPolicy(include_full_error_message=True),
        ),
    )
    assert compilation_full.request.output_composition is not None
    assert compilation_full.config.include_full_error_message is True
    assert compilation_full.request.output_composition.include_full_error_message is True


def test_demand_diagnostics_policy_rejects_non_bool_include_full_error_message() -> None:
    with pytest.raises(TypeError, match=r"DemandDiagnosticsPolicy\.include_full_error_message must be a boolean"):
        _ = DemandDiagnosticsPolicy(include_full_error_message="true")  # type: ignore[arg-type]


def test_demand_diagnostics_policy_rejects_non_bool_validate_unique_field_names() -> None:
    with pytest.raises(TypeError, match=r"DemandDiagnosticsPolicy\.validate_unique_field_names must be a boolean"):
        _ = DemandDiagnosticsPolicy(validate_unique_field_names="false")  # type: ignore[arg-type]


def test_demand_diagnostics_override_rejects_invalid_include_full_error_message() -> None:
    with pytest.raises(TypeError, match=r"DemandDiagnosticsOverride\.include_full_error_message must be a boolean or UNSET"):
        _ = DemandDiagnosticsOverride(include_full_error_message="true")  # type: ignore[arg-type]


def test_demand_diagnostics_override_rejects_invalid_validate_unique_field_names() -> None:
    with pytest.raises(TypeError, match=r"DemandDiagnosticsOverride\.validate_unique_field_names must be a boolean or UNSET"):
        _ = DemandDiagnosticsOverride(validate_unique_field_names="false")  # type: ignore[arg-type]


def test_workflow_run_options_patch_demand_diagnostics_none_disables_policy() -> None:
    from scalim.dsl.yaml_dsl.runtime.contracts import RunOptions
    from scalim.dsl.yaml_dsl.workflow_entrypoints import _apply_workflow_run_options_patch_demand_diagnostics
    from scalim.dsl.yaml_dsl.workflow_types import WorkflowRunOptionsPatch

    base = RunOptions(
        allowed_modules=_ALLOWED_MODULES,
        demand_diagnostics=DemandDiagnosticsPolicy(include_full_error_message=True, validate_unique_field_names=False),
    )
    patch = WorkflowRunOptionsPatch(demand_diagnostics=None)

    next_options = _apply_workflow_run_options_patch_demand_diagnostics(base, patch)
    assert next_options.demand_diagnostics is None


def test_workflow_run_options_patch_demand_diagnostics_invalid_type_rejected() -> None:
    from scalim.dsl.yaml_dsl.runtime.contracts import RunOptions
    from scalim.dsl.yaml_dsl.workflow_entrypoints import _apply_workflow_run_options_patch_demand_diagnostics
    from scalim.dsl.yaml_dsl.workflow_types import WorkflowRunOptionsPatch

    base = RunOptions(allowed_modules=_ALLOWED_MODULES)
    patch = WorkflowRunOptionsPatch(demand_diagnostics="bad")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match=r"WorkflowRunOptionsPatch\.demand_diagnostics must be a DemandDiagnosticsOverride or None"):
        _ = _apply_workflow_run_options_patch_demand_diagnostics(base, patch)


def test_workflow_run_options_patch_demand_diagnostics_all_unset_is_noop() -> None:
    from scalim.dsl.yaml_dsl.runtime.contracts import RunOptions
    from scalim.dsl.yaml_dsl.workflow_entrypoints import _apply_workflow_run_options_patch_demand_diagnostics
    from scalim.dsl.yaml_dsl.workflow_types import WorkflowRunOptionsPatch

    base = RunOptions(
        allowed_modules=_ALLOWED_MODULES,
        demand_diagnostics=DemandDiagnosticsPolicy(include_full_error_message=True, validate_unique_field_names=False),
    )
    patch = WorkflowRunOptionsPatch(demand_diagnostics=DemandDiagnosticsOverride())

    next_options = _apply_workflow_run_options_patch_demand_diagnostics(base, patch)
    assert next_options is base


def test_workflow_run_options_patch_demand_diagnostics_merges_fields_with_unset_inheritance() -> None:
    from scalim.dsl.yaml_dsl.runtime.contracts import RunOptions
    from scalim.dsl.yaml_dsl.workflow_entrypoints import _apply_workflow_run_options_patch_demand_diagnostics
    from scalim.dsl.yaml_dsl.workflow_types import WorkflowRunOptionsPatch

    base = RunOptions(
        allowed_modules=_ALLOWED_MODULES,
        demand_diagnostics=DemandDiagnosticsPolicy(include_full_error_message=True, validate_unique_field_names=True),
    )
    patch = WorkflowRunOptionsPatch(demand_diagnostics=DemandDiagnosticsOverride(validate_unique_field_names=False))

    next_options = _apply_workflow_run_options_patch_demand_diagnostics(base, patch)
    assert next_options.demand_diagnostics is not None
    assert next_options.demand_diagnostics.include_full_error_message is True
    assert next_options.demand_diagnostics.validate_unique_field_names is False
