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


@pytest.mark.parametrize(
    ("resources_wait", "path", "match"),
    [
        (0, "workflow.options.resources_wait", "must be a mapping"),
        ({"max_wait_s": 0}, "workflow.options.resources_wait.max_wait_s", "finite positive"),
        ({"max_wait_s": -1}, "workflow.options.resources_wait.max_wait_s", "finite positive"),
        ({"max_wait_s": {}}, "workflow.options.resources_wait.max_wait_s", "finite positive"),
        ({"max_wait_s": "inf"}, "workflow.options.resources_wait.max_wait_s", "finite positive"),
        ({"max_wait_s": "nope"}, "workflow.options.resources_wait.max_wait_s", "finite positive"),
        ({"diagnostics": 1}, "workflow.options.resources_wait.diagnostics", "must be a mapping"),
        ({"diagnostics": {"enabled": "x"}}, "workflow.options.resources_wait.diagnostics.enabled", "must be a bool"),
        ({"diagnostics": {"warn_after_s": -1}}, "workflow.options.resources_wait.diagnostics.warn_after_s", "finite non-negative"),
        ({"diagnostics": {"repeat_every_s": 0}}, "workflow.options.resources_wait.diagnostics.repeat_every_s", "finite positive"),
    ],
)
def test_load_workflow_config_from_mapping_resources_wait_rejects_invalid_values(
    resources_wait: object,
    path: str,
    match: str,
) -> None:
    from scalim.dsl.by_yaml.workflow import ScalimWorkflowConfigError, load_workflow_config_from_mapping

    root = _base_root()
    root.setdefault("workflow", {}).setdefault("options", {})["resources_wait"] = resources_wait

    with pytest.raises(ScalimWorkflowConfigError, match=match) as excinfo:
        _ = load_workflow_config_from_mapping(root)
    assert excinfo.value.path == path


def test_resources_wait_diagnostics_defaults_when_omitted_from_resources_wait_block() -> None:
    from scalim.dsl.by_yaml.workflow import load_workflow_config_from_mapping

    root = _base_root()
    root.setdefault("workflow", {}).setdefault("options", {})["resources_wait"] = {"max_wait_s": 12.5}
    cfg = load_workflow_config_from_mapping(root)

    assert cfg.options.resources_wait.max_wait_s == 12.5
    assert cfg.options.resources_wait.diagnostics.enabled is False
    assert cfg.options.resources_wait.diagnostics.warn_after_s == 30.0
    assert cfg.options.resources_wait.diagnostics.repeat_every_s is None
    assert cfg.options.resources_wait.diagnostics.capture_owner_callsite is False


def test_resources_wait_diagnostics_repeat_every_s_is_optional() -> None:
    from scalim.dsl.by_yaml.workflow import load_workflow_config_from_mapping

    root = _base_root()
    root.setdefault("workflow", {}).setdefault("options", {})["resources_wait"] = {"diagnostics": {"enabled": True}}
    cfg = load_workflow_config_from_mapping(root)

    assert cfg.options.resources_wait.diagnostics.enabled is True
    assert cfg.options.resources_wait.diagnostics.repeat_every_s is None


def test_resources_wait_diagnostics_repeat_every_s_can_be_null() -> None:
    from scalim.dsl.by_yaml.workflow import load_workflow_config_from_mapping

    root = _base_root()
    root.setdefault("workflow", {}).setdefault("options", {})["resources_wait"] = {"diagnostics": {"enabled": True, "repeat_every_s": None}}
    cfg = load_workflow_config_from_mapping(root)

    assert cfg.options.resources_wait.diagnostics.enabled is True
    assert cfg.options.resources_wait.diagnostics.repeat_every_s is None


def test_resources_wait_flows_from_yaml_to_ir_to_runtime(tmp_path: Path) -> None:
    from scalim.dsl.by_yaml import workflow_compile as workflow_compile_mod
    from scalim.dsl.by_yaml.workflow import load_workflow_config_from_mapping
    from scalim.spec.ir._workflow import WorkflowArtifactsIr, WorkflowIr
    from scalim.workflow import execute as workflow_execute_mod

    root = _base_root()
    root["workflow"]["options"] = {
        "resources_wait": {
            "max_wait_s": 12.5,
            "diagnostics": {
                "enabled": True,
                "warn_after_s": 0.1,
                "repeat_every_s": 0.2,
                "capture_owner_callsite": True,
            },
        }
    }
    wf_obj = load_workflow_config_from_mapping(root)
    options_ir = workflow_compile_mod._build_workflow_options_ir(wf_obj)  # noqa: SLF001
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
