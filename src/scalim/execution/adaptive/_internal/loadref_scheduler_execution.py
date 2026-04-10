from typing import TYPE_CHECKING, Callable, Dict, Hashable, List, Optional, Sequence, Set, Tuple, cast

if TYPE_CHECKING:
    from concurrent.futures import Future

from ....planning.operators import LoadRefOperatorIr
from ...context import BatchContext
from ...executor.operators.load_ref.executor import LoadRefOperatorExecutor
from ...executor.runtime.runtime import ExecutionRuntime
from ..capture import HookCaptureManager
from ..overlay_context import OverlayBatchContext
from ..strategy_unit import TaskSpec as _TaskSpec
from ..submission_unit import LayerScheduleStats as _LayerScheduleStats
from ..submission_unit import run_tasks_in_pool as _run_tasks_in_pool_unit
from .loadref_scheduler_base import AdaptiveLoadRefSchedulerBase
from .loadref_scheduler_support import AdaptiveTaskResult as _AdaptiveTaskResult


class AdaptiveLoadRefSchedulerExecutionMixin(AdaptiveLoadRefSchedulerBase):
    def _build_loadref_executor(self) -> LoadRefOperatorExecutor:
        factory = self._require_overrides().adaptive_loadref_executor_factory
        if factory is not None:
            return cast("LoadRefOperatorExecutor", factory())  # pragma: allow-cast overrides factory typed narrowing
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
            plan=self._require_plan(),
            hook_manager=hook_manager,
            observer_manager=observer_manager,
            main_source=runtime.main_source,
            sources=runtime.sources,
            runtime_bindings=runtime.runtime_bindings,
            guardrails=runtime.guardrails,
            loader_retry=runtime.loader_retry,
            parallel_mode="seq",
            max_workers=0,
            key_normalization=runtime.key_normalization,
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
            resolve_pool_limit=lambda pool_name, resolved: self._require_tuning().resolve_pool_limit(
                pool_name,
                resolved_max_workers=resolved,
            ),
        )
        return results_by_key, layer_stats


__all__ = ()
