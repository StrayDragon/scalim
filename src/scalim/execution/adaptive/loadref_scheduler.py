from concurrent.futures import Executor, Future
from typing import TYPE_CHECKING, Callable, Dict, Hashable, List, Optional, Sequence, Set, Tuple

from ...events.catalog import EVENT_ADAPTIVE_SCHEDULER_DECISION
from ...planning.operators import LoadRefOperatorIr
from ...planning.plan import ExecutionPlan
from ...vendor.compact.typing_extensionsx import override
from ..context import BatchContext
from ..executor.helpers.relation_signature import build_relation_signature, has_rows_binding
from ..executor.runtime.runtime import ExecutionRuntime
from ._internal.loadref_scheduler_execution import AdaptiveLoadRefSchedulerExecutionMixin
from ._internal.loadref_scheduler_planning import AdaptiveLoadRefSchedulerPlanningMixin
from ._internal.loadref_scheduler_support import AdaptiveTaskResult as _AdaptiveTaskResult
from ._internal.loadref_scheduler_support import build_layers as _build_layers
from ._internal.loadref_scheduler_support import build_ref_deps as _build_ref_deps
from ._internal.loadref_scheduler_support import resolve_adaptive_max_workers
from .policy import (
    ADAPTIVE_BACKEND_ASYNC,
    ADAPTIVE_BACKEND_PROCESS,
    ADAPTIVE_BACKEND_THREAD,
    AdaptivePolicy,
    DefaultAdaptivePolicy,
)
from .strategy_unit import TaskSpec as _TaskSpec
from .tuning import AdaptiveTuning

if TYPE_CHECKING:
    from ..pipeline.overrides import PipelineOverrides


class AdaptiveLoadRefScheduler(AdaptiveLoadRefSchedulerPlanningMixin, AdaptiveLoadRefSchedulerExecutionMixin):
    _plan: ExecutionPlan
    _deps: Dict[str, Tuple[str, ...]]
    _overrides: "PipelineOverrides"
    _tuning: AdaptiveTuning
    _policy: AdaptivePolicy

    def __init__(self, plan: ExecutionPlan, *, overrides: "PipelineOverrides") -> None:
        self._plan = plan
        self._deps = _build_ref_deps(plan)
        self._overrides = overrides
        policy = overrides.adaptive_policy or DefaultAdaptivePolicy()
        tuning = overrides.adaptive_tuning
        if tuning is None:
            tuning = AdaptiveTuning(min_parallel_tasks_per_layer=int(overrides.adaptive_min_parallel_tasks or 2))
        tuning = policy.resolve_tuning(tuning)
        tuning.validate()
        self._tuning = tuning
        self._policy = policy

    @override
    def _require_plan(self) -> ExecutionPlan:
        return self._plan

    @override
    def _require_overrides(self) -> "PipelineOverrides":
        return self._overrides

    @override
    def _require_tuning(self) -> AdaptiveTuning:
        return self._tuning

    @override
    def _require_policy(self) -> AdaptivePolicy:
        return self._policy

    @override
    def __repr__(self) -> str:
        return "AdaptiveLoadRefScheduler(min_parallel_tasks={})".format(self._tuning.min_parallel_tasks_per_layer)

    def execute_segment(  # noqa: C901, PLR0912, PLR0915
        self,
        ops: Sequence[LoadRefOperatorIr],
        *,
        context: BatchContext,
        batch_row_nth: List[Hashable],
        runtime: ExecutionRuntime,
        pool: Optional[Executor],
        max_workers: int,
        required_fields: Optional[Set[str]],
        after_operator: Optional[Callable[[LoadRefOperatorIr], None]],
    ) -> None:
        if not ops:
            return

        wants_scheduler_decisions = runtime.instrumentation.wants(EVENT_ADAPTIVE_SCHEDULER_DECISION)
        backend = runtime.adaptive_backend or self._policy.choose_backend(plan=self._plan, runtime=runtime, tuning=self._tuning)
        if backend in (ADAPTIVE_BACKEND_PROCESS, ADAPTIVE_BACKEND_ASYNC):
            # `NOTE`: 若需回加 `process`/`async` 后端,请恢复对应实现模块与测试.
            msg = "adaptive backend '{}' 暂不支持: 当前仅支持 thread;请将 backend 改为 'thread'".format(backend)
            raise ValueError(msg)
        if backend != ADAPTIVE_BACKEND_THREAD:
            msg = "Invalid adaptive backend '{}'".format(backend)
            raise ValueError(msg)

        ordered_ops = list(ops)
        field_keys = [op.field_key for op in ordered_ops]
        op_by_field_key: Dict[str, LoadRefOperatorIr] = {op.field_key: op for op in ordered_ops}

        layers = _build_layers(field_keys, deps=self._deps)

        serial_executor = self._build_loadref_executor()
        committed_relation_keys: Set[Tuple[Tuple[object, ...], ...]] = set()

        for layer_index, layer_field_keys in enumerate(layers):
            layer_ops = [op_by_field_key[key] for key in layer_field_keys]

            # 保持顺序语义: 若本批次更早已执行过某个关联分组,
            # 则将后续的 `LoadRef` 算子视为无操作(但仍需为输出端调用 `after_operator`).
            skipped_field_keys, executable_ops = self._collect_layer_executable_ops(
                layer_ops,
                runtime=runtime,
                after_operator=after_operator,
            )

            if not executable_ops:
                continue

            # 行绑定是层级屏障: 为保持 `batch_rows` 语义并避免隐式依赖,此层按串行执行.
            if any(has_rows_binding(op.lookup_steps) for op in executable_ops):
                if wants_scheduler_decisions:
                    self._emit_scheduler_decision(
                        runtime=runtime,
                        layer_index=layer_index,
                        decision="serial",
                        backend=backend,
                        reason="rows_binding_barrier",
                        layer_task_count=len(executable_ops),
                    )
                self._execute_ops_serially(
                    executable_ops,
                    context=context,
                    batch_row_nth=batch_row_nth,
                    runtime=runtime,
                    serial_executor=serial_executor,
                    after_operator=after_operator,
                )
                continue

            resolved_workers = max(1, int(max_workers))
            if pool is None or resolved_workers <= 1:
                if wants_scheduler_decisions:
                    reason = "no_pool" if pool is None else "single_worker"
                    self._emit_scheduler_decision(
                        runtime=runtime,
                        layer_index=layer_index,
                        decision="serial",
                        backend=backend,
                        reason=reason,
                        layer_task_count=len(executable_ops),
                    )
                self._execute_ops_serially(
                    executable_ops,
                    context=context,
                    batch_row_nth=batch_row_nth,
                    runtime=runtime,
                    serial_executor=serial_executor,
                    after_operator=after_operator,
                )
                continue

            # 在安全情况下按关联签名对任务去重(保持“关联复用”语义).
            task_order, task_specs, op_task_key = self._build_task_specs(executable_ops)
            task_ops = [task_specs[task_key].op for task_key in task_order]

            layer_lookup_keys: Optional[Dict[str, int]] = None
            if int(self._tuning.min_total_lookup_keys_per_layer or 0) > 0 or int(self._tuning.min_lookup_keys_per_task or 0) > 0:
                layer_lookup_keys = {}
                for task_key in task_order:
                    spec = task_specs[task_key]
                    layer_lookup_keys[str(spec.op.field_key)] = self._estimate_first_step_lookup_key_count(
                        spec.op,
                        context=context,
                        batch_row_nth=batch_row_nth,
                    )

            decision = self._decide_layer_parallelism(
                task_ops,
                runtime=runtime,
                pool=pool,
                max_workers=resolved_workers,
                layer_lookup_keys=layer_lookup_keys,
            )
            if not decision.should_parallelize:
                if wants_scheduler_decisions:
                    self._emit_scheduler_decision(
                        runtime=runtime,
                        layer_index=layer_index,
                        decision="serial",
                        backend=backend,
                        reason=decision.reason or "policy_forced_serial",
                        layer_task_count=len(task_ops),
                    )
                self._execute_ops_serially(
                    executable_ops,
                    context=context,
                    batch_row_nth=batch_row_nth,
                    runtime=runtime,
                    serial_executor=serial_executor,
                    after_operator=after_operator,
                )
                continue

            resolved_pool = pool

            def _submit_task_thread(spec: _TaskSpec, *, _pool: Executor = resolved_pool) -> "Future[_AdaptiveTaskResult]":
                return _pool.submit(  # type: ignore[no-any-return]
                    self._run_task,
                    spec,
                    context,
                    batch_row_nth,
                    runtime,
                    required_fields,
                )

            submit_task: Callable[[_TaskSpec], "Future[_AdaptiveTaskResult]"] = _submit_task_thread

            results_by_key, layer_stats = self._run_tasks_in_pool(
                task_order,
                task_specs,
                max_workers=resolved_workers,
                submit_task=submit_task,
                collect_stats=wants_scheduler_decisions,
            )
            if wants_scheduler_decisions:
                self._emit_scheduler_decision(
                    runtime=runtime,
                    layer_index=layer_index,
                    decision="parallel",
                    backend=backend,
                    reason=None,
                    layer_task_count=len(task_ops),
                    layer_stats=layer_stats,
                )
            self._commit_layer_results(
                layer_ops,
                skipped_field_keys=skipped_field_keys,
                op_task_key=op_task_key,
                results_by_key=results_by_key,
                context=context,
                runtime=runtime,
                committed_relation_keys=committed_relation_keys,
                after_operator=after_operator,
            )


__all__ = ["AdaptiveLoadRefScheduler", "build_relation_signature", "resolve_adaptive_max_workers"]
