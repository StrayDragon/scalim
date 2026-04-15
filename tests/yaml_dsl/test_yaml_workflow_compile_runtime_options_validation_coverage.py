import pytest

from scalim.dsl.yaml_dsl import workflow_compile as workflow_compile_mod
from scalim.dsl.yaml_dsl.workflow_types import (
    WorkflowCachePoolPin,
    WorkflowCachePoolPreloadForeverShared,
    WorkflowCachePoolPreset,
    WorkflowExecutionOptions,
    WorkflowRuntimeOptions,
)


def test_workflow_compile_normalize_and_validate_execution_options_rejects_invalid_inputs_cover_branches() -> None:
    with pytest.raises(TypeError, match="workflow_runtime_options.execution must be a WorkflowExecutionOptions"):
        workflow_compile_mod._normalize_and_validate_workflow_execution_options(object())  # noqa: SLF001

    with pytest.raises(TypeError, match="workflow_runtime_options.execution.max_concurrency must be an int >= 1"):
        workflow_compile_mod._normalize_and_validate_workflow_execution_options(  # noqa: SLF001
            WorkflowExecutionOptions(max_concurrency=True, failure_policy="all_fail")
        )

    with pytest.raises(ValueError, match="workflow_runtime_options.execution.max_concurrency must be >= 1"):
        workflow_compile_mod._normalize_and_validate_workflow_execution_options(  # noqa: SLF001
            WorkflowExecutionOptions(max_concurrency=0, failure_policy="all_fail")
        )

    with pytest.raises(TypeError, match="workflow_runtime_options.execution.failure_policy must be a string"):
        workflow_compile_mod._normalize_and_validate_workflow_execution_options(  # noqa: SLF001
            WorkflowExecutionOptions(max_concurrency=1, failure_policy=1)  # type: ignore[arg-type]
        )

    with pytest.raises(ValueError, match="workflow_runtime_options.execution.failure_policy must be one of"):
        workflow_compile_mod._normalize_and_validate_workflow_execution_options(  # noqa: SLF001
            WorkflowExecutionOptions(max_concurrency=1, failure_policy="nope")
        )


def test_workflow_compile_build_cache_pool_ir_from_runtime_rejects_invalid_inputs_cover_branches() -> None:
    with pytest.raises(TypeError, match="workflow_runtime_options.cache_pool must be a WorkflowCachePoolPreset"):
        workflow_compile_mod._build_workflow_cache_pool_ir_from_runtime(object())  # noqa: SLF001

    with pytest.raises(TypeError, match="workflow_runtime_options.cache_pool.max_entries must be an int >= 1"):
        workflow_compile_mod._build_workflow_cache_pool_ir_from_runtime(  # noqa: SLF001
            WorkflowCachePoolPreloadForeverShared(max_entries=True)
        )

    with pytest.raises(ValueError, match="workflow_runtime_options.cache_pool.max_entries must be >= 1"):
        workflow_compile_mod._build_workflow_cache_pool_ir_from_runtime(  # noqa: SLF001
            WorkflowCachePoolPreloadForeverShared(max_entries=0)
        )

    class _OtherPreset(WorkflowCachePoolPreset):
        pass

    with pytest.raises(TypeError, match="Unsupported workflow_runtime_options.cache_pool preset"):
        workflow_compile_mod._build_workflow_cache_pool_ir_from_runtime(_OtherPreset())  # noqa: SLF001

    cfg = WorkflowCachePoolPreloadForeverShared(
        max_entries=16,
        pin=(WorkflowCachePoolPin(kind="preload_forever", source_id="s1"),),
    )
    ir = workflow_compile_mod._build_workflow_cache_pool_ir_from_runtime(cfg)  # noqa: SLF001
    assert ir is not None
    assert len(ir.pin) == 1
    assert ir.pin[0].kind == "preload_forever"
    assert ir.pin[0].source_id == "s1"


def test_workflow_compile_normalize_and_validate_workflow_runtime_options_rejects_invalid_inputs_cover_branches() -> None:
    with pytest.raises(TypeError, match="workflow_runtime_options must be a WorkflowRuntimeOptions"):
        workflow_compile_mod._normalize_and_validate_workflow_runtime_options(object())  # noqa: SLF001

    with pytest.raises(TypeError, match="workflow_runtime_options.scheduler must be a PipelineSchedulerOptions"):
        workflow_compile_mod._normalize_and_validate_workflow_runtime_options(  # noqa: SLF001
            WorkflowRuntimeOptions(scheduler=object())  # type: ignore[arg-type]
        )
