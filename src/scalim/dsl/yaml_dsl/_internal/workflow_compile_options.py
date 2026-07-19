"""`workflow` 编译: 运行时选项归一化/校验与 `IR` 构建.

职责:
- 纯规则/校验: 将 `WorkflowRuntimeOptions` 及其子配置归一化为可用于状态边界的稳定值.
- 产物构建: 基于归一化后的选项构造 `WorkflowOptionsIr`.

边界:
- 本模块不进行 `filesystem IO`.
- 本模块不负责 `workflow DAG` / `resources` / `outputs` 等编译逻辑.
"""

import math
from typing import Any, Optional

from ....spec.ir._workflow import (
    WorkflowCachePoolBudgetIr,
    WorkflowCachePoolIr,
    WorkflowCachePoolPinIr,
    WorkflowOptionsIr,
    WorkflowOutputStagingOptionsIr,
    WorkflowResourcesWaitDiagnosticsIr,
    WorkflowResourcesWaitOptionsIr,
)
from ....typedefs import FailurePolicy, parse_failure_policy
from ..workflow_config._models import (
    WorkflowOutputStagingOptions,
    WorkflowResourcesWaitDiagnosticsOptions,
    WorkflowResourcesWaitOptions,
)
from ..workflow_types import (
    PipelineSchedulerOptions,
    StageBarrierSchedulerOptions,
    WorkflowCachePoolDisabled,
    WorkflowCachePoolPreloadForeverShared,
    WorkflowCachePoolPreloadForeverUnlimited,
    WorkflowCachePoolPreset,
    WorkflowExecutionOptions,
    WorkflowRuntimeOptions,
)


def _normalize_and_validate_workflow_execution_options(raw: Any) -> WorkflowExecutionOptions:
    if not isinstance(raw, WorkflowExecutionOptions):
        msg = "workflow_runtime_options.execution must be a WorkflowExecutionOptions"
        raise TypeError(msg)

    max_concurrency_raw = raw.max_concurrency
    if isinstance(max_concurrency_raw, bool) or not isinstance(max_concurrency_raw, int):
        msg = "workflow_runtime_options.execution.max_concurrency must be an int >= 1"
        raise TypeError(msg)
    if int(max_concurrency_raw) < 1:
        msg = "workflow_runtime_options.execution.max_concurrency must be >= 1"
        raise ValueError(msg)

    failure_policy_raw = raw.failure_policy
    if not isinstance(failure_policy_raw, str):
        msg = "workflow_runtime_options.execution.failure_policy must be a string"
        raise TypeError(msg)
    failure_policy = parse_failure_policy(
        failure_policy_raw,
        label="workflow_runtime_options.execution.failure_policy",
    )

    return WorkflowExecutionOptions(
        max_concurrency=int(max_concurrency_raw),
        failure_policy=failure_policy,
    )


def _build_workflow_cache_pool_ir_from_runtime(raw: Any) -> Optional[WorkflowCachePoolIr]:
    if not isinstance(raw, WorkflowCachePoolPreset):
        msg = "workflow_runtime_options.cache_pool must be a WorkflowCachePoolPreset"
        raise TypeError(msg)

    if isinstance(raw, WorkflowCachePoolDisabled):
        return None

    if isinstance(raw, WorkflowCachePoolPreloadForeverUnlimited):
        return WorkflowCachePoolIr(
            conflict_policy="error",
            release_policy="workflow_end",
            budget=None,
            pin=(),
        )

    if isinstance(raw, WorkflowCachePoolPreloadForeverShared):
        max_entries_raw = raw.max_entries
        if isinstance(max_entries_raw, bool) or not isinstance(max_entries_raw, int):
            msg = "workflow_runtime_options.cache_pool.max_entries must be an int >= 1"
            raise TypeError(msg)
        if int(max_entries_raw) < 1:
            msg = "workflow_runtime_options.cache_pool.max_entries must be >= 1"
            raise ValueError(msg)
        budget = WorkflowCachePoolBudgetIr(
            max_entries=int(max_entries_raw),
            over_budget_policy="fail_fast",
        )
        return WorkflowCachePoolIr(
            conflict_policy="error",
            release_policy="dag_refcount",
            budget=budget,
            pin=tuple(WorkflowCachePoolPinIr(kind=str(p.kind), source_id=str(p.source_id)) for p in (raw.pin or ())),
        )

    msg = "Unsupported workflow_runtime_options.cache_pool preset: {!r}".format(type(raw).__name__)
    raise TypeError(msg)


def _normalize_and_validate_workflow_runtime_options(raw: Any) -> WorkflowRuntimeOptions:
    if raw is None:
        return WorkflowRuntimeOptions.preset_default()
    if not isinstance(raw, WorkflowRuntimeOptions):
        msg = "workflow_runtime_options must be a WorkflowRuntimeOptions"
        raise TypeError(msg)

    execution = _normalize_and_validate_workflow_execution_options(raw.execution)

    resources_wait = _validate_workflow_resources_wait_override(raw.resources_wait)
    output_staging = _normalize_workflow_output_staging_override(raw.output_staging)

    scheduler = raw.scheduler
    if not isinstance(scheduler, (PipelineSchedulerOptions, StageBarrierSchedulerOptions)):
        msg = "workflow_runtime_options.scheduler must be a PipelineSchedulerOptions or StageBarrierSchedulerOptions"
        raise TypeError(msg)

    _ = _build_workflow_cache_pool_ir_from_runtime(raw.cache_pool)

    # 注意: 返回归一化实例供下游调用方/测试使用.
    return WorkflowRuntimeOptions(
        execution=execution,
        cache_pool=raw.cache_pool,
        resources_wait=resources_wait,
        output_staging=output_staging,
        scheduler=scheduler,
    )


def _parse_workflow_option_finite_number(raw: Any, *, path: str, positive: bool) -> float:
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        msg = "{} must be a finite {}number".format(path, "positive " if positive else "")
        raise TypeError(msg)
    value = float(raw)
    if not math.isfinite(value):
        msg = "{} must be a finite {}number".format(path, "positive " if positive else "")
        raise ValueError(msg)
    if positive and value <= 0:
        msg = "{} must be a finite positive number".format(path)
        raise ValueError(msg)
    if not positive and value < 0:
        msg = "{} must be a finite non-negative number".format(path)
        raise ValueError(msg)
    return float(value)


def _validate_workflow_resources_wait_override(raw: Any) -> WorkflowResourcesWaitOptions:
    if not isinstance(raw, WorkflowResourcesWaitOptions):
        msg = "workflow_runtime_options.resources_wait must be a WorkflowResourcesWaitOptions"
        raise TypeError(msg)

    diagnostics = raw.diagnostics
    if not isinstance(diagnostics, WorkflowResourcesWaitDiagnosticsOptions):
        msg = "workflow_runtime_options.resources_wait.diagnostics must be a WorkflowResourcesWaitDiagnosticsOptions"
        raise TypeError(msg)
    if not isinstance(diagnostics.enabled, bool):
        msg = "workflow_runtime_options.resources_wait.diagnostics.enabled must be a bool"
        raise TypeError(msg)
    if not isinstance(diagnostics.capture_owner_callsite, bool):
        msg = "workflow_runtime_options.resources_wait.diagnostics.capture_owner_callsite must be a bool"
        raise TypeError(msg)

    _ = _parse_workflow_option_finite_number(raw.max_wait_s, path="workflow_runtime_options.resources_wait.max_wait_s", positive=True)
    _ = _parse_workflow_option_finite_number(
        diagnostics.warn_after_s,
        path="workflow_runtime_options.resources_wait.diagnostics.warn_after_s",
        positive=False,
    )
    if diagnostics.repeat_every_s is not None:
        _ = _parse_workflow_option_finite_number(
            diagnostics.repeat_every_s,
            path="workflow_runtime_options.resources_wait.diagnostics.repeat_every_s",
            positive=True,
        )
    return raw


def _build_workflow_resources_wait_ir(raw_resources_wait: WorkflowResourcesWaitOptions) -> WorkflowResourcesWaitOptionsIr:
    raw_diagnostics = raw_resources_wait.diagnostics
    return WorkflowResourcesWaitOptionsIr(
        max_wait_s=float(raw_resources_wait.max_wait_s),
        diagnostics=WorkflowResourcesWaitDiagnosticsIr(
            enabled=bool(raw_diagnostics.enabled),
            warn_after_s=float(raw_diagnostics.warn_after_s),
            repeat_every_s=float(raw_diagnostics.repeat_every_s) if raw_diagnostics.repeat_every_s is not None else None,
            capture_owner_callsite=bool(raw_diagnostics.capture_owner_callsite),
        ),
    )


def _normalize_workflow_output_staging_override(raw: Any) -> WorkflowOutputStagingOptions:
    if not isinstance(raw, WorkflowOutputStagingOptions):
        msg = "workflow_runtime_options.output_staging must be a WorkflowOutputStagingOptions"
        raise TypeError(msg)

    dir_name = str(raw.dir_name or "").strip()
    if not dir_name:
        msg = "workflow_runtime_options.output_staging.dir_name must be a non-empty string"
        raise ValueError(msg)
    if dir_name in (".", "..") or "/" in dir_name or "\\" in dir_name:
        msg = "workflow_runtime_options.output_staging.dir_name must be a simple directory name (no separators)"
        raise ValueError(msg)
    if not isinstance(raw.keep_on_success, bool):
        msg = "workflow_runtime_options.output_staging.keep_on_success must be a bool"
        raise TypeError(msg)
    if not isinstance(raw.keep_on_failure, bool):
        msg = "workflow_runtime_options.output_staging.keep_on_failure must be a bool"
        raise TypeError(msg)

    return WorkflowOutputStagingOptions(
        dir_name=str(dir_name),
        keep_on_success=bool(raw.keep_on_success),
        keep_on_failure=bool(raw.keep_on_failure),
    )


def _build_workflow_output_staging_ir(raw_output_staging: WorkflowOutputStagingOptions) -> WorkflowOutputStagingOptionsIr:
    return WorkflowOutputStagingOptionsIr(
        dir_name=str(raw_output_staging.dir_name),
        keep_on_success=bool(raw_output_staging.keep_on_success),
        keep_on_failure=bool(raw_output_staging.keep_on_failure),
    )


def _build_workflow_options_ir(
    *,
    workflow_runtime_options: Any,
) -> WorkflowOptionsIr:
    runtime = _normalize_and_validate_workflow_runtime_options(workflow_runtime_options)
    cache_pool = _build_workflow_cache_pool_ir_from_runtime(runtime.cache_pool)
    resources_wait = _build_workflow_resources_wait_ir(runtime.resources_wait)
    output_staging = _build_workflow_output_staging_ir(runtime.output_staging)
    execution = runtime.execution
    scheduler = runtime.scheduler
    schedule_mode = "pipeline"
    if isinstance(scheduler, StageBarrierSchedulerOptions):
        schedule_mode = "stage_barrier"
    return WorkflowOptionsIr(
        max_concurrency=int(execution.max_concurrency),
        failure_policy=str(execution.failure_policy or FailurePolicy.ALL_FAIL.value),
        schedule_mode=str(schedule_mode),
        cache_pool=cache_pool,
        resources_wait=resources_wait,
        output_staging=output_staging,
    )


__all__ = ()


def normalize_and_validate_workflow_execution_options(raw: Any) -> WorkflowExecutionOptions:
    return _normalize_and_validate_workflow_execution_options(raw)


def build_workflow_cache_pool_ir_from_runtime(raw: Any) -> Optional[WorkflowCachePoolIr]:
    return _build_workflow_cache_pool_ir_from_runtime(raw)


def normalize_and_validate_workflow_runtime_options(raw: Any) -> WorkflowRuntimeOptions:
    return _normalize_and_validate_workflow_runtime_options(raw)


def parse_workflow_option_finite_number(raw: Any, *, path: str, positive: bool) -> float:
    return _parse_workflow_option_finite_number(raw, path=path, positive=positive)


def validate_workflow_resources_wait_override(raw: Any) -> WorkflowResourcesWaitOptions:
    return _validate_workflow_resources_wait_override(raw)


def build_workflow_resources_wait_ir(raw_resources_wait: WorkflowResourcesWaitOptions) -> WorkflowResourcesWaitOptionsIr:
    return _build_workflow_resources_wait_ir(raw_resources_wait)


def normalize_workflow_output_staging_override(raw: Any) -> WorkflowOutputStagingOptions:
    return _normalize_workflow_output_staging_override(raw)


def build_workflow_output_staging_ir(raw_output_staging: WorkflowOutputStagingOptions) -> WorkflowOutputStagingOptionsIr:
    return _build_workflow_output_staging_ir(raw_output_staging)


def build_workflow_options_ir(
    *,
    workflow_runtime_options: Any,
) -> WorkflowOptionsIr:
    return _build_workflow_options_ir(workflow_runtime_options=workflow_runtime_options)
