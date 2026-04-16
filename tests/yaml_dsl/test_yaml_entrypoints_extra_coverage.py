from pathlib import Path
from types import SimpleNamespace
import warnings

import pytest


def _write_minimal_demand_yaml(tmp_path: Path) -> Path:
    yaml_path = tmp_path / "demand.yaml"
    yaml_path.write_text(
        (
            """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
"""
        ).lstrip(),
        encoding="utf-8",
    )
    return yaml_path


def _make_execution_result(*, demand_ir: object, in_memory_rows) -> object:  # type: ignore[no-untyped-def]
    from scalim.execution.contracts import ExecutionResult

    return ExecutionResult(
        output_path=None,
        total_rows=0,
        duration=0.0,
        demand_ir=demand_ir,
        plan=object(),
        in_memory_rows=in_memory_rows,
    )


def test_public_run_capture_rows_enabled_but_no_rows_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from scalim.dsl.yaml_dsl import CaptureRows, DemandRunOptions, DemandRunOutputOptions, DemandRunSecurityOptions
    from scalim.dsl.yaml_dsl.runtime import entrypoints as entrypoints_mod

    yaml_path = _write_minimal_demand_yaml(tmp_path)

    def _fake_run_ir(demand_ir, request, **kwargs):  # type: ignore[no-untyped-def]
        _ = request, kwargs
        return _make_execution_result(demand_ir=demand_ir, in_memory_rows=None)

    monkeypatch.setattr(entrypoints_mod, "run_ir", _fake_run_ir)

    options = DemandRunOptions(
        security=DemandRunSecurityOptions(allowed_modules=frozenset(["tests.fixtures.mock_loaders"])),
        outputs=DemandRunOutputOptions(capture=CaptureRows()),
    )

    with pytest.raises(RuntimeError, match=r"CaptureRows enabled but no rows were captured"):
        _ = entrypoints_mod.run(str(yaml_path), options=options)


def test_unsafe_run_injects_sink_when_provided(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    yaml_path = _write_minimal_demand_yaml(tmp_path)
    from scalim.sinks.memory import InMemoryRowDataSink

    sentinel_sink = InMemoryRowDataSink()

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        from scalim.dsl.yaml_dsl.runtime import unsafe_entrypoints as unsafe_mod

    def _fake_run_ir(demand_ir, request, **kwargs):  # type: ignore[no-untyped-def]
        _ = kwargs
        assert request.sink is sentinel_sink
        return _make_execution_result(demand_ir=demand_ir, in_memory_rows=None)

    monkeypatch.setattr(unsafe_mod, "run_ir", _fake_run_ir)

    result = unsafe_mod.unsafe_run(
        str(yaml_path),
        allowed_modules=frozenset(["tests.fixtures.mock_loaders"]),
        batch_size=1,
        sink=sentinel_sink,
    )

    assert result.total_rows == 0


def test_validate_patches_by_run_id_rejects_security_boundary_dict_patch() -> None:
    from scalim.dsl.yaml_dsl import workflow_entrypoints as workflow_entrypoints_mod

    with pytest.raises(TypeError, match=r"security boundary"):
        _ = workflow_entrypoints_mod._validate_patches_by_run_id(  # noqa: SLF001
            {"ok": {"allowed_modules": ["nope"]}},  # type: ignore[arg-type] intentional runtime boundary test
            known_run_ids=frozenset(["ok"]),
        )


def test_build_demand_run_result_impl_handles_missing_request_attribute() -> None:
    from scalim.dsl.yaml_dsl.runtime.contracts import DemandRunResult
    from scalim.dsl.yaml_dsl.schema_dsl.models import DemandConfig
    from scalim.dsl.yaml_dsl import workflow_entrypoints as workflow_entrypoints_mod

    compilation = SimpleNamespace(config=DemandConfig())
    core = _make_execution_result(demand_ir=object(), in_memory_rows=None)

    result = workflow_entrypoints_mod._build_demand_run_result_impl(  # noqa: SLF001
        core,
        compilation=compilation,
        demand_yaml_path="demo.yaml",
        workflow_exec_id="wf",
        workflow_node_id="node",
    )

    assert isinstance(result, DemandRunResult)
    assert result.captured_rows is None


def test_build_demand_run_result_impl_capture_enabled_but_no_rows_raises() -> None:
    from scalim.dsl.yaml_dsl.schema_dsl.models import DemandConfig
    from scalim.dsl.yaml_dsl import workflow_entrypoints as workflow_entrypoints_mod

    compilation = SimpleNamespace(config=DemandConfig(), request=SimpleNamespace(capture_in_memory_rows=True))
    core = _make_execution_result(demand_ir=object(), in_memory_rows=None)

    with pytest.raises(RuntimeError, match=r"CaptureRows enabled but no rows were captured"):
        _ = workflow_entrypoints_mod._build_demand_run_result_impl(  # noqa: SLF001
            core,
            compilation=compilation,
            demand_yaml_path="demo.yaml",
            workflow_exec_id="wf",
            workflow_node_id="node",
        )


def test_build_demand_run_result_impl_capture_enabled_sets_captured_rows() -> None:
    from scalim.dsl.yaml_dsl.schema_dsl.models import DemandConfig
    from scalim.dsl.yaml_dsl import workflow_entrypoints as workflow_entrypoints_mod

    sentinel_rows = object()
    compilation = SimpleNamespace(config=DemandConfig(), request=SimpleNamespace(capture_in_memory_rows=True))
    core = _make_execution_result(demand_ir=object(), in_memory_rows=sentinel_rows)

    result = workflow_entrypoints_mod._build_demand_run_result_impl(  # noqa: SLF001
        core,
        compilation=compilation,
        demand_yaml_path="demo.yaml",
        workflow_exec_id="wf",
        workflow_node_id="node",
    )

    assert result.captured_rows is sentinel_rows


def test_normalize_and_validate_workflow_options_replaces_when_demand_needs_normalization() -> None:
    from scalim.dsl.yaml_dsl import DemandRunOptions, DemandRunSecurityOptions, WorkflowRunOptions
    from scalim.dsl.yaml_dsl import workflow_entrypoints as workflow_entrypoints_mod

    demand = DemandRunOptions(security=DemandRunSecurityOptions(allowed_modules=frozenset(["tests.fixtures.mock_loaders"])))
    object.__setattr__(demand.template, "template_sandbox", " safe ")
    options = WorkflowRunOptions(demand=demand)

    normalized = workflow_entrypoints_mod._normalize_and_validate_workflow_options(options)  # noqa: SLF001
    assert normalized is not options
    assert normalized.demand.template.template_sandbox == "safe"


def test_workflow_run_options_contract_validation_and_normalization_cover_branches() -> None:
    from scalim.dsl.yaml_dsl import DemandRunOptions, DemandRunSecurityOptions, WorkflowRunOptions

    demand = DemandRunOptions(security=DemandRunSecurityOptions(allowed_modules=frozenset(["tests.fixtures.mock_loaders"])))

    with pytest.raises(TypeError, match=r"WorkflowRunOptions\.demand must be a DemandRunOptions"):
        _ = WorkflowRunOptions(demand="nope")  # type: ignore[arg-type] contract validation boundary

    with pytest.raises(TypeError, match=r"WorkflowRunOptions\.patches_by_run_id must be a mapping"):
        _ = WorkflowRunOptions(demand=demand, patches_by_run_id="nope")  # type: ignore[arg-type] contract validation boundary

    with pytest.raises(TypeError, match=r"WorkflowRunOptions\.path_aliases must be a mapping"):
        _ = WorkflowRunOptions(demand=demand, path_aliases="nope")  # type: ignore[arg-type] contract validation boundary

    normalized = WorkflowRunOptions(demand=demand, workflow_components=[object()])  # type: ignore[arg-type] contract normalization boundary
    assert isinstance(normalized.workflow_components, tuple)
    assert len(normalized.workflow_components) == 1
