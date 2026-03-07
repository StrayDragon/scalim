# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownParameterType=false, reportUnknownLambdaType=false, reportMissingParameterType=false, reportAttributeAccessIssue=false, reportUnknownMemberType=false, reportUnannotatedClassAttribute=false, reportUninitializedInstanceVariable=false, reportPrivateUsage=false, reportCallIssue=false, reportArgumentType=false, reportUnusedFunction=false, reportImplicitOverride=false, reportUnusedImport=false, reportMissingTypeArgument=false, reportUnnecessaryComparison=false, reportUnnecessaryCast=false
import pickle
from typing import TYPE_CHECKING, Callable, Dict, Hashable, List, Optional, Sequence, Set, Tuple, cast

if TYPE_CHECKING:
    from concurrent.futures import Executor, Future

from ....planning.operators import LoadRefOperatorIr
from ...context import BatchContext
from ...executor.operators.load_ref.executor import LoadRefOperatorExecutor
from ...executor.runtime.runtime import ExecutionRuntime
from ..capture import HookCaptureManager
from ..overlay_context import OverlayBatchContext
from ..policy import (
    ADAPTIVE_BACKEND_PROCESS,
    PROCESS_FAILURE_FAIL_FAST,
    PROCESS_FAILURE_FALLBACK_SERIAL,
)
from ..strategy_unit import TaskSpec as _TaskSpec
from ..submission_unit import LayerScheduleStats as _LayerScheduleStats
from ..submission_unit import run_tasks_in_pool as _run_tasks_in_pool_unit
from .loadref_scheduler_support import AdaptiveTaskResult as _AdaptiveTaskResult
from .loadref_scheduler_support import run_task_in_process as _run_task_in_process


class AdaptiveLoadRefSchedulerExecutionMixin:
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

    def _submit_process_task(
        self,
        spec: _TaskSpec,
        *,
        pool: "Executor",
        context: BatchContext,
        batch_row_nth: List[Hashable],
        runtime: ExecutionRuntime,
        required_fields: Optional[Set[str]],
    ) -> "Future[_AdaptiveTaskResult]":
        serialized_context = pickle.loads(pickle.dumps(context))  # noqa: S301
        return pool.submit(
            _run_task_in_process,
            self._plan,
            spec.op,
            spec.relation_key,
            serialized_context,
            list(batch_row_nth),
            runtime.main_source,
            runtime.guardrails,
            runtime.loader_retry,
            runtime.preloaded_cache,
            int(runtime.batch_num),
            required_fields,
            group_enabled=spec.group_enabled,
        )

    def _process_failure_mode(self, runtime: ExecutionRuntime) -> str:
        failure_mode = runtime.adaptive_process_failure_mode or self._policy.choose_process_failure_mode(
            plan=self._plan,
            runtime=runtime,
            tuning=self._tuning,
        )
        if failure_mode not in (PROCESS_FAILURE_FAIL_FAST, PROCESS_FAILURE_FALLBACK_SERIAL):
            return PROCESS_FAILURE_FAIL_FAST
        return failure_mode

    def _should_use_process_backend(self, backend: str) -> bool:
        return backend == ADAPTIVE_BACKEND_PROCESS
