from concurrent.futures import Executor
from typing import Any, Callable, Dict, Hashable, List, Optional, Sequence, Set, Tuple, cast

from ....events import EVENT_ADAPTIVE_SCHEDULER_DECISION
from ....events._events import AdaptiveSchedulerDecisionEvent
from ....planning.operators import LoadRefOperatorIr
from ...context import BatchContext
from ...executor.runtime.runtime import ExecutionRuntime
from ..aggregation_unit import commit_layer_results as _commit_layer_results_unit
from ..policy import AdaptiveLayerDecision
from ..strategy_unit import TaskSpec as _TaskSpec
from ..strategy_unit import build_task_specs as _build_task_specs_unit
from ..strategy_unit import collect_layer_executable_ops as _collect_layer_executable_ops_unit
from ..submission_unit import LayerScheduleStats as _LayerScheduleStats
from ..tuning import DEFAULT_ADAPTIVE_POOL
from .loadref_scheduler_base import AdaptiveLoadRefSchedulerBase


class AdaptiveLoadRefSchedulerPlanningMixin(AdaptiveLoadRefSchedulerBase):
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
        policy = self._require_policy()
        tuning = self._require_tuning()
        return policy.decide_layer_parallelism(
            layer_task_ops,
            tuning=tuning,
            runtime=runtime,
            pool_is_available=pool is not None,
            resolved_max_workers=resolved_workers,
            layer_lookup_keys=layer_lookup_keys,
        )

    def _resolve_task_pool(self, op: LoadRefOperatorIr) -> str:
        tuning = self._require_tuning()
        pool_name = self._require_policy().choose_task_pool(op=op, tuning=tuning) or DEFAULT_ADAPTIVE_POOL
        if pool_name != DEFAULT_ADAPTIVE_POOL and pool_name not in tuning.pools:
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
                raw_parts = [context.get_field_value(key, row_id) for key in from_fields]
                if any(val is None for val in raw_parts):
                    continue
                raw_key = cast("Hashable", tuple(raw_parts))  # pragma: allow-cast set key typed narrowing
                try:
                    seen.add(raw_key)
                except TypeError:
                    continue
            return len(seen)

        from_field = step.get_from_fields()[0]
        for row_id in batch_row_nth:
            raw_value = context.get_field_value(from_field, row_id)
            if raw_value is None:
                continue
            try:
                seen.add(cast("Hashable", raw_value))  # pragma: allow-cast set key typed narrowing
            except TypeError:
                continue
        return len(seen)

    def _build_task_specs(
        self,
        ops: Sequence[LoadRefOperatorIr],
    ) -> Tuple[List[Tuple[str, object]], Dict[Tuple[str, object], _TaskSpec], Dict[str, Tuple[str, object]]]:
        return _build_task_specs_unit(ops, resolve_task_pool=self._resolve_task_pool)

    def _commit_layer_results(
        self,
        layer_ops: Sequence[LoadRefOperatorIr],
        *,
        skipped_field_keys: Set[str],
        op_task_key: Dict[str, Tuple[str, object]],
        results_by_key: Dict[Tuple[str, object], Any],
        context: BatchContext,
        runtime: ExecutionRuntime,
        committed_relation_keys: Set[Tuple[Tuple[object, ...], ...]],
        after_operator: Optional[Callable[[LoadRefOperatorIr], None]],
    ) -> None:
        _commit_layer_results_unit(
            layer_ops,
            skipped_field_keys=skipped_field_keys,
            op_task_key=op_task_key,
            results_by_key=results_by_key,
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


__all__ = ()
