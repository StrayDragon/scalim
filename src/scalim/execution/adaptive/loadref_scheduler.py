import os
import pickle
import threading
import time
from collections.abc import Callable, Hashable, Sequence
from concurrent.futures import Executor, Future, as_completed
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from ...events.catalog import EVENT_ADAPTIVE_SCHEDULER_DECISION
from ...events.event import Event
from ...events.events import AdaptiveSchedulerDecisionEvent
from ...planning.operators import LoadRefOperatorIr
from ...planning.plan import ExecutionPlan
from ...spec.ir.sources import MainSourceIr
from ...typedefs import FieldValue
from ...vendor.compact.typing_extensionsx import override
from ..context import BatchContext
from ..executor.helpers.relation_signature import build_relation_signature, can_group_by_relation, has_rows_binding
from ..executor.operators.load_ref.executor import LoadRefOperatorExecutor
from ..executor.runtime.runtime import ExecutionRuntime
from ..guardrails import GuardrailsPolicy
from .capture import HookCaptureManager, HookRecordedEvent
from .overlay_context import OverlayBatchContext
from .policy import (
    ADAPTIVE_BACKEND_PROCESS,
    PROCESS_FAILURE_FAIL_FAST,
    PROCESS_FAILURE_FALLBACK_SERIAL,
    AdaptiveLayerDecision,
    AdaptivePolicy,
    DefaultAdaptivePolicy,
)
from .tuning import DEFAULT_ADAPTIVE_POOL, AdaptiveTuning

if TYPE_CHECKING:
    from ..pipeline.overrides import PipelineOverrides


def resolve_adaptive_max_workers(max_workers: int) -> int:
    """解析自适应模式下的 `max_workers`.

    - 0 或负数表示自动.
    - 解析后的值必须 `>= 1`.
    """
    if max_workers and max_workers > 0:
        return max(1, int(max_workers))
    cpu = os.cpu_count() or 1
    # 与 Python 的 `ThreadPoolExecutor` 默认启发式保持一致.
    return max(1, min(32, cpu + 4))


@dataclass(frozen=True)
class _AdaptiveTaskResult:
    overlay: dict[str, dict[Hashable, FieldValue]]
    hook_events: list[HookRecordedEvent]
    observer_events: list[Event]
    relation_key: tuple[tuple[object, ...], ...]
    group_enabled: bool


@dataclass
class _PoolWaitStats:
    wait_seconds_total: float = 0.0
    wait_seconds_max: float = 0.0
    wait_count: int = 0


@dataclass
class _LayerScheduleStats:
    pool_limits: dict[str, int]
    pool_wait: dict[str, _PoolWaitStats]


_POOL_WAIT_EPSILON_SECONDS = 0.000_001


def _run_task_in_process(
    plan: ExecutionPlan,
    op: LoadRefOperatorIr,
    relation_key: tuple[tuple[object, ...], ...],
    base_context: BatchContext,
    batch_row_nth: list[Hashable],
    main_source: MainSourceIr | None,
    guardrails: GuardrailsPolicy,
    preloaded_cache: dict[str, dict[Hashable, FieldValue]],
    batch_num: int,
    required_fields: set[str] | None,
    *,
    group_enabled: bool,
) -> _AdaptiveTaskResult:
    # 注意:进程后端仍属实验性质;钩子与观察者事件不会跨进程执行.
    from ...hooks.base import HookManager  # noqa: PLC0415
    from ...ob.manager import ObserverManager  # noqa: PLC0415

    task_runtime = ExecutionRuntime(
        plan=plan,
        hook_manager=HookManager(),
        observer_manager=ObserverManager(),
        main_source=main_source,
        guardrails=guardrails,
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


def _build_ref_deps(plan: ExecutionPlan) -> dict[str, tuple[str, ...]]:
    deps: dict[str, tuple[str, ...]] = {}
    for _source, items in plan.ref_loader_sequence:
        for field_key, dep_ref_field_keys in items:
            deps[str(field_key)] = tuple(str(dep) for dep in (dep_ref_field_keys or ()))
    return deps


def _build_layers(
    field_keys: Sequence[str],
    *,
    deps: dict[str, tuple[str, ...]],
) -> list[list[str]]:
    remaining: set[str] = set(field_keys)
    done: set[str] = set()
    layers: list[list[str]] = []

    # 与执行计划/算子顺序一致的确定性 `O(n^2)` 分层.
    while remaining:
        ready: list[str] = []
        for key in field_keys:
            if key not in remaining:
                continue
            key_deps = deps.get(key, ())
            if all(dep in done or dep not in remaining for dep in key_deps):
                ready.append(key)

        if not ready:
            # 出现环或信号缺失时:按算子顺序退回到串行执行.
            layers.append([k for k in field_keys if k in remaining])
            break

        layers.append(ready)
        for key in ready:
            remaining.remove(key)
            done.add(key)

    return layers


@dataclass(frozen=True)
class _TaskSpec:
    op: LoadRefOperatorIr
    relation_key: tuple[tuple[object, ...], ...]
    group_enabled: bool
    pool_name: str


class AdaptiveLoadRefScheduler:
    _plan: ExecutionPlan
    _deps: dict[str, tuple[str, ...]]
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
        return f"AdaptiveLoadRefScheduler(min_parallel_tasks={self._tuning.min_parallel_tasks_per_layer})"

    def _collect_layer_executable_ops(
        self,
        layer_ops: Sequence[LoadRefOperatorIr],
        *,
        runtime: ExecutionRuntime,
        after_operator: Callable[[LoadRefOperatorIr], None] | None,
    ) -> tuple[set[str], list[LoadRefOperatorIr]]:
        skipped_field_keys: set[str] = set()
        executable_ops: list[LoadRefOperatorIr] = []

        for op in layer_ops:
            relation_key = cast("tuple[tuple[object, ...], ...]", build_relation_signature(op.lookup_steps))
            group_enabled = can_group_by_relation(op.lookup_steps)
            if group_enabled and relation_key in runtime.load_ref_group_executed:
                skipped_field_keys.add(op.field_key)
                if after_operator is not None:
                    after_operator(op)
                continue
            executable_ops.append(op)

        return skipped_field_keys, executable_ops

    def _build_loadref_executor(self) -> LoadRefOperatorExecutor:
        factory = getattr(self._overrides, "adaptive_loadref_executor_factory", None)
        if factory is not None:
            return cast("LoadRefOperatorExecutor", factory())
        return LoadRefOperatorExecutor()

    def _execute_ops_serially(
        self,
        ops: Sequence[LoadRefOperatorIr],
        *,
        context: BatchContext,
        batch_row_nth: list[Hashable],
        runtime: ExecutionRuntime,
        serial_executor: LoadRefOperatorExecutor,
        after_operator: Callable[[LoadRefOperatorIr], None] | None,
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
        pool: Executor | None,
        max_workers: int,
        layer_lookup_keys: dict[str, int] | None,
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
            msg = f"AdaptivePolicy returned unknown pool '{pool_name}' for field '{op.field_key}'"
            raise ValueError(msg)
        return pool_name

    def _estimate_first_step_lookup_key_count(
        self,
        op: LoadRefOperatorIr,
        *,
        context: BatchContext,
        batch_row_nth: list[Hashable],
    ) -> int:
        if not op.lookup_steps:
            return 0

        step = op.lookup_steps[0]
        seen: set[Hashable] = set()

        if step.is_multi_field():
            from_fields = step.get_from_fields()
            for row_id in batch_row_nth:
                raw_parts: list[FieldValue] = [context.get_field_value(key, row_id) for key in from_fields]
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
    ) -> tuple[list[tuple[str, object]], dict[tuple[str, object], _TaskSpec], dict[str, tuple[str, object]]]:
        task_specs: dict[tuple[str, object], _TaskSpec] = {}
        op_task_key: dict[str, tuple[str, object]] = {}
        task_order: list[tuple[str, object]] = []

        for op in ops:
            relation_key = cast("tuple[tuple[object, ...], ...]", build_relation_signature(op.lookup_steps))
            group_enabled = True
            task_key: tuple[str, object] = ("relation", relation_key)

            op_task_key[op.field_key] = task_key
            if task_key not in task_specs:
                pool_name = self._resolve_task_pool(op)
                task_specs[task_key] = _TaskSpec(op=op, relation_key=relation_key, group_enabled=group_enabled, pool_name=pool_name)
                task_order.append(task_key)

        return task_order, task_specs, op_task_key

    def _run_task(
        self,
        spec: _TaskSpec,
        base_context: BatchContext,
        batch_row_nth: list[Hashable],
        runtime: ExecutionRuntime,
        required_fields: set[str] | None,
    ) -> _AdaptiveTaskResult:
        hook_manager = HookCaptureManager(runtime.hook_manager)
        observer_manager = runtime.observer_manager.create_capture_manager()

        task_runtime = ExecutionRuntime(
            plan=self._plan,
            hook_manager=hook_manager,
            observer_manager=observer_manager,
            main_source=runtime.main_source,
            guardrails=runtime.guardrails,
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

    def _run_tasks_in_pool(  # noqa: C901, PLR0912, PLR0915
        self,
        task_order: Sequence[tuple[str, object]],
        task_specs: dict[tuple[str, object], _TaskSpec],
        *,
        max_workers: int,
        submit_task: Callable[[_TaskSpec], Future[_AdaptiveTaskResult]],
        collect_stats: bool,
    ) -> tuple[dict[tuple[str, object], _AdaptiveTaskResult], _LayerScheduleStats | None]:
        resolved_workers = max(1, int(max_workers))
        global_sem = threading.BoundedSemaphore(resolved_workers)

        pool_sems: dict[str, threading.BoundedSemaphore] = {}
        pool_limits: dict[str, int] = {}
        pool_wait: dict[str, _PoolWaitStats] = {}
        for task_key in task_order:
            spec = task_specs[task_key]
            if spec.pool_name not in pool_sems:
                limit = self._tuning.resolve_pool_limit(spec.pool_name, resolved_max_workers=resolved_workers)
                pool_limits[spec.pool_name] = int(limit)
                pool_sems[spec.pool_name] = threading.BoundedSemaphore(limit)

        futures: dict[tuple[str, object], Future[_AdaptiveTaskResult]] = {}
        future_to_key: dict[Future[_AdaptiveTaskResult], tuple[str, object]] = {}

        def _release_tokens(pool_name: str) -> None:
            pool_sems[pool_name].release()
            global_sem.release()

        for task_key in task_order:
            spec = task_specs[task_key]
            _ = global_sem.acquire()
            if collect_stats:
                wait_start = time.perf_counter()
                _ = pool_sems[spec.pool_name].acquire()
                waited = max(0.0, time.perf_counter() - wait_start)
                stats = pool_wait.get(spec.pool_name)
                if stats is None:
                    stats = _PoolWaitStats()
                    pool_wait[spec.pool_name] = stats
                stats.wait_seconds_total += waited
                stats.wait_seconds_max = max(stats.wait_seconds_max, waited)
                if waited > _POOL_WAIT_EPSILON_SECONDS:
                    stats.wait_count += 1
            else:
                _ = pool_sems[spec.pool_name].acquire()
            try:
                fut = submit_task(spec)
            except Exception:
                _release_tokens(spec.pool_name)
                raise

            futures[task_key] = fut
            future_to_key[fut] = task_key
            fut.add_done_callback(lambda _fut, pool_name=spec.pool_name: _release_tokens(pool_name))

        results_by_key: dict[tuple[str, object], _AdaptiveTaskResult] = {}
        try:
            for fut in as_completed(list(futures.values())):
                done_key = future_to_key.get(fut)
                if done_key is None:  # pragma: no cover
                    continue
                results_by_key[done_key] = fut.result()
        except Exception:
            for fut in futures.values():
                _ = fut.cancel()
            raise

        layer_stats = None
        if collect_stats:
            layer_stats = _LayerScheduleStats(pool_limits=pool_limits, pool_wait=pool_wait)
        return results_by_key, layer_stats

    def _commit_task_result(
        self,
        result: _AdaptiveTaskResult,
        *,
        context: BatchContext,
        runtime: ExecutionRuntime,
        committed_relation_keys: set[tuple[tuple[object, ...], ...]],
    ) -> None:
        for field_key in sorted(result.overlay.keys()):
            values = result.overlay[field_key]
            for row_id, value in values.items():
                context.set_field_value(field_key, row_id, value)

        if result.group_enabled and result.relation_key not in committed_relation_keys:
            committed_relation_keys.add(result.relation_key)
            runtime.load_ref_group_executed.add(result.relation_key)

        for event in result.hook_events:
            runtime.hook_manager.emit_typed(event.event_type, event.payload)
        for event in result.observer_events:
            runtime.instrumentation.emit_recorded_event(event)

    def _commit_layer_results(
        self,
        layer_ops: Sequence[LoadRefOperatorIr],
        *,
        skipped_field_keys: set[str],
        op_task_key: dict[str, tuple[str, object]],
        results_by_key: dict[tuple[str, object], _AdaptiveTaskResult],
        context: BatchContext,
        runtime: ExecutionRuntime,
        committed_relation_keys: set[tuple[tuple[object, ...], ...]],
        after_operator: Callable[[LoadRefOperatorIr], None] | None,
    ) -> None:
        committed: set[tuple[str, object]] = set()
        for op in layer_ops:
            if op.field_key in skipped_field_keys:
                continue
            task_key = op_task_key[op.field_key]
            if task_key not in committed:
                self._commit_task_result(
                    results_by_key[task_key],
                    context=context,
                    runtime=runtime,
                    committed_relation_keys=committed_relation_keys,
                )
                committed.add(task_key)

            if after_operator is not None:
                after_operator(op)

    def _emit_scheduler_decision(
        self,
        *,
        runtime: ExecutionRuntime,
        layer_index: int,
        decision: str,
        backend: str,
        reason: str | None,
        layer_task_count: int | None,
        process_failure_mode: str | None = None,
        layer_stats: _LayerScheduleStats | None = None,
    ) -> None:
        def _build_payload() -> AdaptiveSchedulerDecisionEvent:
            pool_limits: dict[str, int] | None = None
            pool_wait_ms_total: dict[str, float] | None = None
            pool_wait_ms_max: dict[str, float] | None = None
            pool_wait_count: dict[str, int] | None = None

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
        batch_row_nth: list[Hashable],
        runtime: ExecutionRuntime,
        pool: Executor | None,
        max_workers: int,
        required_fields: set[str] | None,
        after_operator: Callable[[LoadRefOperatorIr], None] | None,
    ) -> None:
        if not ops:
            return

        wants_scheduler_decisions = runtime.instrumentation.wants(EVENT_ADAPTIVE_SCHEDULER_DECISION)

        ordered_ops = list(ops)
        field_keys = [op.field_key for op in ordered_ops]
        op_by_field_key: dict[str, LoadRefOperatorIr] = {op.field_key: op for op in ordered_ops}

        layers = _build_layers(field_keys, deps=self._deps)

        serial_executor = self._build_loadref_executor()
        committed_relation_keys: set[tuple[tuple[object, ...], ...]] = set()

        for layer_index, layer_field_keys in enumerate(layers):
            layer_ops = [op_by_field_key[key] for key in layer_field_keys]

            # 保持 `seq` 语义:如果某个“关联签名分组”在本批次更早已执行过,
            # 则后续的 `LoadRef` 算子视为“空操作”(但仍会为 `sink` 调用 `after_operator`).
            skipped_field_keys, executable_ops = self._collect_layer_executable_ops(
                layer_ops,
                runtime=runtime,
                after_operator=after_operator,
            )

            if not executable_ops:
                continue

            # `rows` 绑定是层级屏障:为保持 `batch_rows` 语义并避免隐式依赖,需要串行执行.
            if any(has_rows_binding(op.lookup_steps) for op in executable_ops):
                if wants_scheduler_decisions:
                    backend = self._policy.choose_backend(plan=self._plan, runtime=runtime, tuning=self._tuning)
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
                    backend = self._policy.choose_backend(plan=self._plan, runtime=runtime, tuning=self._tuning)
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

            # 在安全的前提下按关联签名去重任务(保持“关联复用”语义).
            task_order, task_specs, op_task_key = self._build_task_specs(executable_ops)
            task_ops = [task_specs[task_key].op for task_key in task_order]

            layer_lookup_keys: dict[str, int] | None = None
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
                    backend = self._policy.choose_backend(plan=self._plan, runtime=runtime, tuning=self._tuning)
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

            backend = self._policy.choose_backend(plan=self._plan, runtime=runtime, tuning=self._tuning)
            process_failure_mode: str | None = None

            resolved_pool = pool

            submit_task: Callable[[_TaskSpec], Future[_AdaptiveTaskResult]]
            if backend == ADAPTIVE_BACKEND_PROCESS:
                failure_mode = self._policy.choose_process_failure_mode(plan=self._plan, runtime=runtime, tuning=self._tuning)
                if failure_mode not in (PROCESS_FAILURE_FAIL_FAST, PROCESS_FAILURE_FALLBACK_SERIAL):
                    msg = f"Invalid process failure mode '{failure_mode}'"
                    raise ValueError(msg)
                process_failure_mode = failure_mode

                if runtime.hook_manager.hooks or runtime.observer_manager.observers:
                    msg = (
                        "adaptive process backend is not compatible with hooks/observers "
                        f"(hooks={len(runtime.hook_manager.hooks)}, observers={len(runtime.observer_manager.observers)})"
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
                            runtime.preloaded_cache,
                            runtime.batch_num,
                            required_fields,
                        )
                    )
                except Exception as exc:
                    msg = f"adaptive process backend cannot pickle shared context: {type(exc).__name__}: {exc}"
                    if failure_mode == PROCESS_FAILURE_FAIL_FAST:
                        raise TypeError(msg) from exc
                    process_pickle_failed = True

                if not process_pickle_failed:
                    for task_key in task_order:
                        spec = task_specs[task_key]
                        try:
                            _ = pickle.dumps((spec.op, spec.relation_key, spec.group_enabled))
                        except Exception as exc:
                            msg = (
                                f"adaptive process backend cannot pickle task '{spec.op.field_key}' "
                                f"(pool='{spec.pool_name}'): {type(exc).__name__}: {exc}"
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

                def _submit_task_process(spec: _TaskSpec, *, _pool: Executor = resolved_pool) -> Future[_AdaptiveTaskResult]:
                    return _pool.submit(  # type: ignore[no-any-return]
                        _run_task_in_process,
                        self._plan,
                        spec.op,
                        spec.relation_key,
                        context,
                        batch_row_nth,
                        runtime.main_source,
                        runtime.guardrails,
                        runtime.preloaded_cache,
                        runtime.batch_num,
                        required_fields,
                        group_enabled=spec.group_enabled,
                    )

                submit_task = _submit_task_process

            else:

                def _submit_task_thread(spec: _TaskSpec, *, _pool: Executor = resolved_pool) -> Future[_AdaptiveTaskResult]:
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


__all__ = ["AdaptiveLoadRefScheduler", "resolve_adaptive_max_workers"]
