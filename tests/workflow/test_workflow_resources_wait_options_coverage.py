from pathlib import Path
from typing import Any, Dict

import pytest


def _base_root() -> Dict[str, Any]:
    return {
        "workflow": {
            "runs": [
                {
                    "id": "a",
                    "demand": "a.yaml",
                }
            ]
        }
    }


def test_load_workflow_config_from_mapping_resources_wait_defaults_are_present() -> None:
    from scalim.dsl.by_yaml.workflow import load_workflow_config_from_mapping

    cfg = load_workflow_config_from_mapping(_base_root())
    assert cfg.options.resources_wait.max_wait_s == 600.0
    assert cfg.options.resources_wait.diagnostics.enabled is False
    assert cfg.options.resources_wait.diagnostics.warn_after_s == 30.0
    assert cfg.options.resources_wait.diagnostics.repeat_every_s is None
    assert cfg.options.resources_wait.diagnostics.capture_owner_callsite is False


def test_load_workflow_config_from_mapping_rejects_resources_wait_key() -> None:
    from scalim.dsl.by_yaml.workflow import ScalimWorkflowConfigError, load_workflow_config_from_mapping

    root = _base_root()
    root.setdefault("workflow", {}).setdefault("options", {})["resources_wait"] = {"max_wait_s": 12.5}

    with pytest.raises(ScalimWorkflowConfigError, match="moved out of workflow YAML") as excinfo:
        _ = load_workflow_config_from_mapping(root)
    assert excinfo.value.path == "workflow.options.resources_wait"


def test_resources_wait_flows_from_runtime_to_ir_to_runtime(tmp_path: Path) -> None:
    from scalim.dsl.by_yaml import workflow_compile as workflow_compile_mod
    from scalim.dsl.by_yaml.workflow import load_workflow_config_from_mapping
    from scalim.dsl.by_yaml.workflow_types import WorkflowResourcesWaitDiagnosticsOptions, WorkflowResourcesWaitOptions
    from scalim.spec.ir._workflow import WorkflowArtifactsIr, WorkflowIr
    from scalim.workflow import execute as workflow_execute_mod

    wf_obj = load_workflow_config_from_mapping(_base_root())
    resources_wait = WorkflowResourcesWaitOptions(
        max_wait_s=12.5,
        diagnostics=WorkflowResourcesWaitDiagnosticsOptions(
            enabled=True,
            warn_after_s=0.1,
            repeat_every_s=0.2,
            capture_owner_callsite=True,
        ),
    )
    options_ir = workflow_compile_mod._build_workflow_options_ir(wf_obj, workflow_resources_wait=resources_wait)  # noqa: SLF001
    assert options_ir.resources_wait.max_wait_s == 12.5
    assert options_ir.resources_wait.diagnostics.enabled is True
    assert options_ir.resources_wait.diagnostics.warn_after_s == 0.1
    assert options_ir.resources_wait.diagnostics.repeat_every_s == 0.2
    assert options_ir.resources_wait.diagnostics.capture_owner_callsite is True

    workflow_ir = WorkflowIr(
        nodes=(),
        edges=(),
        options=options_ir,
        resources=(),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={}),
    )
    prepared = workflow_execute_mod._prepare_workflow_run_ir(  # noqa: SLF001
        str(tmp_path / "workflow.yaml"),
        workflow_ir,
        components=None,
        bundle_viz_base_config=None,
        cache_pool_logical_keys_by_node_id=None,
        cache_pool_consumers_by_logical_key=None,
    )
    try:
        assert prepared.resource_manager._max_wait_s == 12.5  # noqa: SLF001
        assert prepared.resource_manager._wait_diagnostics.enabled is True  # noqa: SLF001
        assert prepared.resource_manager._wait_diagnostics.warn_after_s == 0.1  # noqa: SLF001
        assert prepared.resource_manager._wait_diagnostics.repeat_every_s == 0.2  # noqa: SLF001
        assert prepared.resource_manager._wait_diagnostics.capture_owner_callsite is True  # noqa: SLF001
    finally:
        workflow_execute_mod._cleanup_workflow_finally(prepared, resources_finalized=True)  # noqa: SLF001


def test_resources_wait_default_timeout_is_enabled_in_runtime(tmp_path: Path) -> None:
    from scalim.spec.ir._workflow import WorkflowArtifactsIr, WorkflowIr, WorkflowOptionsIr
    from scalim.workflow import execute as workflow_execute_mod

    workflow_ir = WorkflowIr(
        nodes=(),
        edges=(),
        options=WorkflowOptionsIr(),
        resources=(),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={}),
    )
    prepared = workflow_execute_mod._prepare_workflow_run_ir(  # noqa: SLF001
        str(tmp_path / "workflow.yaml"),
        workflow_ir,
        components=None,
        bundle_viz_base_config=None,
        cache_pool_logical_keys_by_node_id=None,
        cache_pool_consumers_by_logical_key=None,
    )
    try:
        assert prepared.resource_manager._max_wait_s == 600.0  # noqa: SLF001
        assert prepared.resource_manager._wait_diagnostics.enabled is False  # noqa: SLF001
    finally:
        workflow_execute_mod._cleanup_workflow_finally(prepared, resources_finalized=True)  # noqa: SLF001


@pytest.mark.parametrize(
    ("raw", "positive", "exc_type", "match"),
    [
        (True, True, TypeError, r"must be a finite positive number"),
        (float("inf"), True, ValueError, r"must be a finite positive number"),
        (0, True, ValueError, r"must be a finite positive number"),
        (-0.1, False, ValueError, r"must be a finite non-negative number"),
    ],
)
def test_parse_workflow_option_finite_number_rejects_invalid_values(
    raw: object,
    positive: bool,
    exc_type: type[Exception],
    match: str,
) -> None:
    from scalim.dsl.by_yaml import workflow_compile as workflow_compile_mod

    with pytest.raises(exc_type, match=match):
        _ = workflow_compile_mod._parse_workflow_option_finite_number(raw, path="x", positive=positive)  # noqa: SLF001


@pytest.mark.parametrize(
    ("raw", "exc_type", "match"),
    [
        ({}, TypeError, r"workflow_resources_wait must be a WorkflowResourcesWaitOptions"),
        ("x", TypeError, r"workflow_resources_wait must be a WorkflowResourcesWaitOptions"),
        (None, TypeError, r"workflow_resources_wait must be a WorkflowResourcesWaitOptions"),
    ],
)
def test_validate_workflow_resources_wait_override_rejects_wrong_type(raw: object, exc_type: type[Exception], match: str) -> None:
    from scalim.dsl.by_yaml import workflow_compile as workflow_compile_mod

    with pytest.raises(exc_type, match=match):
        _ = workflow_compile_mod._validate_workflow_resources_wait_override(raw)  # noqa: SLF001


def test_validate_workflow_resources_wait_override_rejects_invalid_diagnostics_type() -> None:
    from scalim.dsl.by_yaml import workflow_compile as workflow_compile_mod
    from scalim.dsl.by_yaml.workflow_types import WorkflowResourcesWaitOptions

    with pytest.raises(TypeError, match=r"workflow_resources_wait\.diagnostics must be a WorkflowResourcesWaitDiagnosticsOptions"):
        _ = workflow_compile_mod._validate_workflow_resources_wait_override(  # noqa: SLF001
            WorkflowResourcesWaitOptions(diagnostics="x")  # type: ignore[arg-type] intentional runtime boundary test
        )


def test_validate_workflow_resources_wait_override_rejects_non_bool_enabled() -> None:
    from scalim.dsl.by_yaml import workflow_compile as workflow_compile_mod
    from scalim.dsl.by_yaml.workflow_types import WorkflowResourcesWaitDiagnosticsOptions, WorkflowResourcesWaitOptions

    diagnostics = WorkflowResourcesWaitDiagnosticsOptions(enabled="x")  # type: ignore[arg-type] intentional runtime boundary test
    with pytest.raises(TypeError, match=r"workflow_resources_wait\.diagnostics\.enabled must be a bool"):
        _ = workflow_compile_mod._validate_workflow_resources_wait_override(  # noqa: SLF001
            WorkflowResourcesWaitOptions(diagnostics=diagnostics)
        )


def test_validate_workflow_resources_wait_override_rejects_non_bool_capture_owner_callsite() -> None:
    from scalim.dsl.by_yaml import workflow_compile as workflow_compile_mod
    from scalim.dsl.by_yaml.workflow_types import WorkflowResourcesWaitDiagnosticsOptions, WorkflowResourcesWaitOptions

    diagnostics = WorkflowResourcesWaitDiagnosticsOptions(
        capture_owner_callsite="x"  # type: ignore[arg-type] intentional runtime boundary test
    )
    with pytest.raises(TypeError, match=r"workflow_resources_wait\.diagnostics\.capture_owner_callsite must be a bool"):
        _ = workflow_compile_mod._validate_workflow_resources_wait_override(  # noqa: SLF001
            WorkflowResourcesWaitOptions(diagnostics=diagnostics)
        )
