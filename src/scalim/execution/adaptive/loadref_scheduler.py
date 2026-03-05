import os
import pickle
from concurrent.futures import Executor, Future
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Dict, Hashable, List, Optional, Sequence, Set, Tuple, cast

from ...events.catalog import EVENT_ADAPTIVE_SCHEDULER_DECISION
from ...events.event import Event
from ...events.events import AdaptiveSchedulerDecisionEvent
from ...planning.operators import LoadRefOperatorIr
from ...planning.plan import ExecutionPlan
from ...spec.ir.sources import MainSourceIr
from ...typedefs import FieldValue
from ...vendor.compact.typing_extensionsx import override
from ..context import BatchContext
from ..executor.helpers.relation_signature import build_relation_signature, has_rows_binding
from ..executor.operators.load_ref.executor import LoadRefOperatorExecutor
from ..executor.runtime.runtime import ExecutionRuntime
from ..guardrails import GuardrailsPolicy
from ..loader_retry import LoaderRetryPolicies
from .aggregation_unit import commit_layer_results as _commit_layer_results_unit
from .capture import HookCaptureManager, HookRecordedEvent
from .overlay_context import OverlayBatchContext
from .policy import (
    ADAPTIVE_BACKEND_ASYNC,
    ADAPTIVE_BACKEND_PROCESS,
    ADAPTIVE_BACKEND_THREAD,
    PROCESS_FAILURE_FAIL_FAST,
    PROCESS_FAILURE_FALLBACK_SERIAL,
    AdaptiveLayerDecision,
    AdaptivePolicy,
    DefaultAdaptivePolicy,
)
from .strategy_unit import TaskSpec as _TaskSpec
from .strategy_unit import build_task_specs as _build_task_specs_unit
from .strategy_unit import collect_layer_executable_ops as _collect_layer_executable_ops_unit
from .submission_unit import LayerScheduleStats as _LayerScheduleStats
from .submission_unit import run_tasks_in_pool as _run_tasks_in_pool_unit
from .tuning import DEFAULT_ADAPTIVE_POOL, AdaptiveTuning

if TYPE_CHECKING:
    from ..pipeline.overrides import PipelineOverrides


def resolve_adaptive_max_workers(max_workers: int, cpu_count_fn: Optional[Callable[[], Optional[int]]] = None) -> int:
    """解析自适应模式下的 `max_workers`.

    - 0/负数表示自动
    - 解析后的值必须 >= 1
    """
    if max_workers and max_workers > 0:
        return max(1, int(max_workers))
    resolver = cpu_count_fn or os.cpu_count
    cpu = resolver() or 1
    # 与 `ThreadPoolExecutor` 的默认启发式保持一致.
    return max(1, min(32, cpu + 4))


@dataclass(frozen=True)
class _AdaptiveTaskResult:
    overlay: Dict[str, Dict[Hashable, FieldValue]]
    hook_events: List[HookRecordedEvent]
    observer_events: List[Event]
    relation_key: Tuple[Tuple[object, ...], ...]
    group_enabled: bool


def _run_task_in_process(
    plan: ExecutionPlan,
    op: LoadRefOperatorIr,
    relation_key: Tuple[Tuple[object, ...], ...],
    base_context: BatchContext,
    batch_row_nth: List[Hashable],
    main_source: Optional[MainSourceIr],
    guardrails: GuardrailsPolicy,
    loader_retry: LoaderRetryPolicies,
    preloaded_cache: Dict[str, Dict[Hashable, FieldValue]],
    batch_num: int,
    required_fields: Optional[Set[str]],
    *,
    group_enabled: bool,
) -> _AdaptiveTaskResult:
    # 注意: 进程后端仍属实验特性;钩子/观测器不会跨进程执行.
    from ...hooks.base import HookManager  # noqa: PLC0415
    from ...ob.manager import ObserverManager  # noqa: PLC0415

    task_runtime = ExecutionRuntime(
        plan=plan,
        hook_manager=HookManager(),
        observer_manager=ObserverManager(),
        main_source=main_source,
        guardrails=guardrails,
        loader_retry=loader_retry,
        parallel_mode="seq",
        max_workers=0,
    )
    task_runtime.preloaded_cache = preloaded_cache
    task_runtime.batch_num = int(batch_num)

    task_context = OverlayBatchContext(base_context, required_fields=required_fields)
    LoadRefOperatorExecutor().execute(op, task_context, batch_row_nth, task_runtime)

    overlay = task_context.drain_overlay()
    return _AdaptiveTaskResult(
        overlay=overlay,
        hook_events=[],
        observer_events=[],
        relation_key=relation_key,
        group_enabled=bool(group_enabled),
    )


def _build_ref_deps(plan: ExecutionPlan) -> Dict[str, Tuple[str, ...]]:
    deps: Dict[str, Tuple[str, ...]] = {}
    for _source, items in plan.ref_loader_sequence:
        for field_key, dep_ref_field_keys in items:
            deps[str(field_key)] = tuple(str(dep) for dep in (dep_ref_field_keys or ()))
    return deps


def _build_layers(
    field_keys: Sequence[str],
    *,
    deps: Dict[str, Tuple[str, ...]],
) -> List[List[str]]:
    remaining: Set[str] = set(field_keys)
    done: Set[str] = set()
    layers: List[List[str]] = []

    # 确定性的 O(n^2) 分层,与规划/算子顺序对齐.
    while remaining:
        ready: List[str] = []
        for key in field_keys:
            if key not in remaining:
                continue
            key_deps = deps.get(key, ())
            if all(dep in done or dep not in remaining for dep in key_deps):
                ready.append(key)

        if not ready:
            # 若存在环或缺失信号: 回退为按算子顺序串行执行.
            layers.append([k for k in field_keys if k in remaining])
            break

        layers.append(ready)
        for key in ready:
            remaining.remove(key)
            done.add(key)

    return layers


class AdaptiveLoadRefScheduler:
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
    def __repr__(self) -> str:
        return "AdaptiveLoadRefScheduler(min_parallel_tasks={})".format(self._tuning.min_parallel_tasks_per_layer)

    def _collect_layer_executable_ops(
        self,
        layer_ops: Sequence[LoadRefOperatorIr],
        *,
        runtime: ExecutionRuntime,
        after_operator: Optional[Callable[[LoadRefOperatorIr], None]],
    ) -> Tuple[Set[str], List[LoadRefOperatorIr]]:
        return _collect_layer_executable_ops_unit(
            layer_ops,
            runtime=runtime,
            after_operator=after_operator,
        )

    def _build_loadref_executor(self) -> LoadRefOperatorExecutor:
        factory = self._overrides.adaptive_loadref_executor_factory
        if factory is not None:
            return cast("LoadRefOperatorExecutor", factory())
        return LoadRefOperatorExecutor()

    def _execute_ops_serially(
        self,
        ops: Sequence[LoadRefOperatorIr],
        *,
        context: BatchContext,
        batch_row_nth: List[Hashable],
        runtime: ExecutionRuntime,
        serial_executor: LoadRefOperatorExecutor,
        after_operator: Optional[Callable[[LoadRefOperatorIr], None]],
    ) -> None:
        for op in ops:
            serial_executor.execute(op, context, batch_row_nth, runtime)
            if after_operator is not None:
                after_operator(op)

    def _decide_layer_parallelism(
        self,
        layer_task_ops: Sequence[LoadRefOperatorIr],
        *,
        runtime: ExecutionRuntime,
        pool: Optional[Executor],
        max_workers: int,
        layer_lookup_keys: Optional[Dict[str, int]],
    ) -> AdaptiveLayerDecision:
        resolved_workers = max(1, int(max_workers))
        return self._policy.decide_layer_parallelism(
            layer_task_ops,
            tuning=self._tuning,
            runtime=runtime,
            pool_is_available=pool is not None,
            resolved_max_workers=resolved_workers,
            layer_lookup_keys=layer_lookup_keys,
        )

    def _resolve_task_pool(self, op: LoadRefOperatorIr) -> str:
        pool_name = self._policy.choose_task_pool(op=op, tuning=self._tuning) or DEFAULT_ADAPTIVE_POOL
        if pool_name != DEFAULT_ADAPTIVE_POOL and pool_name not in self._tuning.pools:
            msg = "AdaptivePolicy returned unknown pool '{}' for field '{}'".format(pool_name, op.field_key)
            raise ValueError(msg)
        return pool_name

    def _estimate_first_step_lookup_key_count(
        self,
        op: LoadRefOperatorIr,
        *,
        context: BatchContext,
        batch_row_nth: List[Hashable],
    ) -> int:
        if not op.lookup_steps:
            return 0

        step = op.lookup_steps[0]
        seen: Set[Hashable] = set()

        if step.is_multi_field():
            from_fields = step.get_from_fields()
            for row_id in batch_row_nth:
                raw_parts: List[FieldValue] = [context.get_field_value(key, row_id) for key in from_fields]
                if any(val is None for val in raw_parts):
                    continue
                try:
                    raw_key = cast("Hashable", tuple(raw_parts))
                except TypeError:  # pragma: no cover
                    continue
                try:
                    seen.add(raw_key)
                except TypeError:
                    continue
            return len(seen)

        from_field = step.get_from_fields()[0]
        for row_id in batch_row_nth:
            raw_value: FieldValue = context.get_field_value(from_field, row_id)
            if raw_value is None:
                continue
            try:
                seen.add(cast("Hashable", raw_value))
            except TypeError:
                continue
        return len(seen)

    def _build_task_specs(
        self,
        ops: Sequence[LoadRefOperatorIr],
    ) -> Tuple[List[Tuple[str, object]], Dict[Tuple[str, object], _TaskSpec], Dict[str, Tuple[str, object]]]:
        return _build_task_specs_unit(ops, resolve_task_pool=self._resolve_task_pool)

    def _run_task(
        self,
        spec: _TaskSpec,
        base_context: BatchContext,
        batch_row_nth: List[Hashable],
        runtime: ExecutionRuntime,
        required_fields: Optional[Set[str]],
    ) -> _AdaptiveTaskResult:
        hook_manager = HookCaptureManager(runtime.hook_manager)
        observer_manager = runtime.observer_manager.create_capture_manager()

        task_runtime = ExecutionRuntime(
            plan=self._plan,
            hook_manager=hook_manager,
            observer_manager=observer_manager,
            main_source=runtime.main_source,
            guardrails=runtime.guardrails,
            loader_retry=runtime.loader_retry,
            parallel_mode="seq",
            max_workers=0,
        )
        task_runtime.preloaded_cache = runtime.preloaded_cache
        task_runtime.batch_num = runtime.batch_num

        task_context = OverlayBatchContext(base_context, required_fields=required_fields)
        self._build_loadref_executor().execute(spec.op, task_context, batch_row_nth, task_runtime)

        overlay = task_context.drain_overlay()
        hook_events = hook_manager.drain_events()
        observer_events = observer_manager.drain_events()
        return _AdaptiveTaskResult(
            overlay=overlay,
            hook_events=hook_events,
            observer_events=observer_events,
            relation_key=spec.relation_key,
            group_enabled=spec.group_enabled,
        )

    def _run_tasks_in_pool(
        self,
        task_order: Sequence[Tuple[str, object]],
        task_specs: Dict[Tuple[str, object], _TaskSpec],
        *,
        max_workers: int,
        submit_task: Callable[[_TaskSpec], "Future[_AdaptiveTaskResult]"],
        collect_stats: bool,
    ) -> Tuple[Dict[Tuple[str, object], _AdaptiveTaskResult], Optional[_LayerScheduleStats]]:
        results_by_key, layer_stats = _run_tasks_in_pool_unit(
            task_order,
            task_specs,
            max_workers=max_workers,
            submit_task=submit_task,
            collect_stats=collect_stats,
            resolve_pool_limit=lambda pool_name, resolved: self._tuning.resolve_pool_limit(
                pool_name,
                resolved_max_workers=resolved,
            ),
        )
        return cast("Dict[Tuple[str, object], _AdaptiveTaskResult]", results_by_key), layer_stats

    def _commit_layer_results(
        self,
        layer_ops: Sequence[LoadRefOperatorIr],
        *,
        skipped_field_keys: Set[str],
        op_task_key: Dict[str, Tuple[str, object]],
        results_by_key: Dict[Tuple[str, object], _AdaptiveTaskResult],
        context: BatchContext,
        runtime: ExecutionRuntime,
        committed_relation_keys: Set[Tuple[Tuple[object, ...], ...]],
        after_operator: Optional[Callable[[LoadRefOperatorIr], None]],
    ) -> None:
        _commit_layer_results_unit(
            layer_ops,
            skipped_field_keys=skipped_field_keys,
            op_task_key=op_task_key,
            results_by_key=cast("Dict[Tuple[str, object], object]", results_by_key),
            context=context,
            runtime=runtime,
            committed_relation_keys=committed_relation_keys,
            after_operator=after_operator,
        )

    def _emit_scheduler_decision(
        self,
        *,
        runtime: ExecutionRuntime,
        layer_index: int,
        decision: str,
        backend: str,
        reason: Optional[str],
        layer_task_count: Optional[int],
        process_failure_mode: Optional[str] = None,
        layer_stats: Optional[_LayerScheduleStats] = None,
    ) -> None:
        def _build_payload() -> AdaptiveSchedulerDecisionEvent:
            pool_limits: Optional[Dict[str, int]] = None
            pool_wait_ms_total: Optional[Dict[str, float]] = None
            pool_wait_ms_max: Optional[Dict[str, float]] = None
            pool_wait_count: Optional[Dict[str, int]] = None

            if layer_stats is not None:
                pool_limits = dict(layer_stats.pool_limits)
                pool_wait_ms_total = {k: float(v.wait_seconds_total) * 1000.0 for k, v in layer_stats.pool_wait.items()}
                pool_wait_ms_max = {k: float(v.wait_seconds_max) * 1000.0 for k, v in layer_stats.pool_wait.items()}
                pool_wait_count = {k: int(v.wait_count) for k, v in layer_stats.pool_wait.items()}

            return AdaptiveSchedulerDecisionEvent(
                batch_num=int(runtime.batch_num),
                layer_index=int(layer_index),
                decision=str(decision),
                backend=str(backend),
                reason=str(reason) if reason else None,
                layer_task_count=int(layer_task_count) if layer_task_count is not None else None,
                process_failure_mode=str(process_failure_mode) if process_failure_mode else None,
                pool_limits=pool_limits,
                pool_wait_ms_total=pool_wait_ms_total,
                pool_wait_ms_max=pool_wait_ms_max,
                pool_wait_count=pool_wait_count,
            )

        _ = runtime.instrumentation.emit_lazy(EVENT_ADAPTIVE_SCHEDULER_DECISION, _build_payload)

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
        if backend not in (ADAPTIVE_BACKEND_THREAD, ADAPTIVE_BACKEND_PROCESS, ADAPTIVE_BACKEND_ASYNC):
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

            process_failure_mode: Optional[str] = None

            resolved_pool = pool

            submit_task: Callable[[_TaskSpec], "Future[_AdaptiveTaskResult]"]
            if backend == ADAPTIVE_BACKEND_PROCESS:
                failure_mode = runtime.adaptive_process_failure_mode or self._policy.choose_process_failure_mode(
                    plan=self._plan,
                    runtime=runtime,
                    tuning=self._tuning,
                )
                if failure_mode not in (PROCESS_FAILURE_FAIL_FAST, PROCESS_FAILURE_FALLBACK_SERIAL):
                    msg = "Invalid process failure mode '{}'".format(failure_mode)
                    raise ValueError(msg)
                process_failure_mode = failure_mode

                if runtime.hook_manager.hooks or runtime.observer_manager.observers:
                    msg = "adaptive process backend is not compatible with hooks/observers (hooks={}, observers={})".format(
                        len(runtime.hook_manager.hooks),
                        len(runtime.observer_manager.observers),
                    )
                    if wants_scheduler_decisions:
                        self._emit_scheduler_decision(
                            runtime=runtime,
                            layer_index=layer_index,
                            decision="serial",
                            backend=backend,
                            reason="process_backend_incompatible_hooks",
                            layer_task_count=len(task_ops),
                            process_failure_mode=failure_mode,
                        )
                    if failure_mode == PROCESS_FAILURE_FAIL_FAST:
                        raise ValueError(msg)
                    self._execute_ops_serially(
                        executable_ops,
                        context=context,
                        batch_row_nth=batch_row_nth,
                        runtime=runtime,
                        serial_executor=serial_executor,
                        after_operator=after_operator,
                    )
                    continue

                process_pickle_failed = False
                try:
                    _ = pickle.dumps(
                        (
                            self._plan,
                            context,
                            batch_row_nth,
                            runtime.main_source,
                            runtime.guardrails,
                            runtime.loader_retry,
                            runtime.preloaded_cache,
                            runtime.batch_num,
                            required_fields,
                        )
                    )
                except Exception as exc:
                    msg = "adaptive process backend cannot pickle shared context: {}: {}".format(type(exc).__name__, exc)
                    if failure_mode == PROCESS_FAILURE_FAIL_FAST:
                        raise TypeError(msg) from exc
                    process_pickle_failed = True

                if not process_pickle_failed:
                    for task_key in task_order:
                        spec = task_specs[task_key]
                        try:
                            _ = pickle.dumps((spec.op, spec.relation_key, spec.group_enabled))
                        except Exception as exc:
                            msg = "adaptive process backend cannot pickle task '{}' (pool='{}'): {}: {}".format(
                                spec.op.field_key,
                                spec.pool_name,
                                type(exc).__name__,
                                exc,
                            )
                            if failure_mode == PROCESS_FAILURE_FAIL_FAST:
                                raise TypeError(msg) from exc
                            process_pickle_failed = True
                            break

                if process_pickle_failed:
                    if wants_scheduler_decisions:
                        self._emit_scheduler_decision(
                            runtime=runtime,
                            layer_index=layer_index,
                            decision="serial",
                            backend=backend,
                            reason="process_backend_unpicklable_task",
                            layer_task_count=len(task_ops),
                            process_failure_mode=failure_mode,
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

                def _submit_task_process(spec: _TaskSpec, *, _pool: Executor = resolved_pool) -> "Future[_AdaptiveTaskResult]":
                    return _pool.submit(  # type: ignore[no-any-return]
                        _run_task_in_process,
                        self._plan,
                        spec.op,
                        spec.relation_key,
                        context,
                        batch_row_nth,
                        runtime.main_source,
                        runtime.guardrails,
                        runtime.loader_retry,
                        runtime.preloaded_cache,
                        runtime.batch_num,
                        required_fields,
                        group_enabled=spec.group_enabled,
                    )

                submit_task = _submit_task_process

            else:

                def _submit_task_thread(spec: _TaskSpec, *, _pool: Executor = resolved_pool) -> "Future[_AdaptiveTaskResult]":
                    return _pool.submit(  # type: ignore[no-any-return]
                        self._run_task,
                        spec,
                        context,
                        batch_row_nth,
                        runtime,
                        required_fields,
                    )

                submit_task = _submit_task_thread

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
                    process_failure_mode=process_failure_mode,
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
