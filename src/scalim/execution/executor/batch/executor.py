"""批量执行器实现.

此模块刻意不放在包的 `__init__.py` 中,以保持导入面精简.
"""

# region imports

import time
from concurrent.futures import Executor
from typing import Callable, Dict, Hashable, List, Optional, Sequence, Set, cast

from ....events import EventType
from ....planning.builder_helpers.fusion_groups import MIN_FUSION_GROUP_SIZE, ComputeFusionGroup
from ....planning.operators import ComputeOperatorIr, OperatorType, SupportedOperatorIr
from ....planning.operators import LoadRefOperatorIr as LoadRefOp
from ....planning.plan import ExecutionPlan
from ....sinks import ISink
from ....typedefs import FieldValue, RowData
from ...adaptive.config import resolve_adaptive_policy_tuning_and_workers
from ...adaptive.loadref_scheduler import AdaptiveLoadRefScheduler
from ...context import BatchContext, create_batch_context_for_rows
from ...pipeline.overrides import PipelineOverrides
from ..operators.base import OperatorExecutor
from ..operators.compute.executor import ComputeOperatorExecutor
from ..operators.compute.fusion import active_fusion_members, execute_fused_compute_group, fusion_disabled_reason
from ..operators.load import LoadOperatorExecutor
from ..operators.load_ref.executor import LoadRefOperatorExecutor
from ..operators.release import ReleaseOperatorExecutor
from ..operators.write import WriteColumnOperatorExecutor, WriteRowOperatorExecutor
from ..runtime.runtime import ExecutionRuntime
from ._internal.segments import iter_operator_segments
from ._internal.stage_spans import init_stage_span_tracking
from ._main_prefill import prefill_main_source_fields

# endregion


def _try_execute_fused_compute(
    *,
    field_key: str,
    fusion_by_field: Dict[str, ComputeFusionGroup],
    fused_done: Set[str],
    context: BatchContext,
    batch_row_nth: List[Hashable],
    runtime: ExecutionRuntime,
    wants_stage_spans: bool,
    stage_map: Dict[str, str],
    stage_durations: Dict[str, float],
    stage_perf_counter_fn: Optional[Callable[[], float]],
) -> bool:
    """若 `field_key` 是可融合组的首字段则执行融合并返回 `True`."""
    if field_key in fused_done:
        return True
    group = fusion_by_field.get(field_key)
    if group is None:
        return False
    active = active_fusion_members(group, runtime.late_fields)
    if len(active) < MIN_FUSION_GROUP_SIZE or field_key != active[0]:
        return False
    if fusion_disabled_reason(runtime, group, active) is not None:
        return False

    stage = stage_map.get(OperatorType.COMPUTE.value)
    if wants_stage_spans and stage:
        perf_counter = stage_perf_counter_fn or time.perf_counter
        start = perf_counter()
        execute_fused_compute_group(
            group=group,
            field_keys=active,
            context=context,
            batch_row_nth=batch_row_nth,
            runtime=runtime,
        )
        stage_durations[stage] += max(0.0, perf_counter() - start)
    else:
        execute_fused_compute_group(
            group=group,
            field_keys=active,
            context=context,
            batch_row_nth=batch_row_nth,
            runtime=runtime,
        )
    fused_done.update(active)
    return True


class BatchExecutor:
    """批次执行器"""

    plan: ExecutionPlan
    runtime: ExecutionRuntime
    _executors: Dict[str, OperatorExecutor]
    _overrides: "PipelineOverrides"
    _adaptive_scheduler: "AdaptiveLoadRefScheduler"

    def __init__(
        self,
        plan: ExecutionPlan,
        runtime: ExecutionRuntime,
        *,
        overrides: Optional["PipelineOverrides"] = None,
    ) -> None:
        self.plan = plan
        self.runtime = runtime
        self._executors = {
            OperatorType.LOAD.value: LoadOperatorExecutor(),
            OperatorType.LOAD_REF.value: LoadRefOperatorExecutor(),
            OperatorType.COMPUTE.value: ComputeOperatorExecutor(),
            OperatorType.WRITE_COLUMN.value: WriteColumnOperatorExecutor(),
            OperatorType.WRITE_ROW.value: WriteRowOperatorExecutor(),
            OperatorType.RELEASE.value: ReleaseOperatorExecutor(),
        }
        if overrides is None:
            overrides = PipelineOverrides()
        self._overrides = overrides
        self._adaptive_scheduler = AdaptiveLoadRefScheduler(plan, overrides=self._overrides)

    def prefill_main_source_fields(
        self,
        context: BatchContext,
        batch_row_nth: List[Hashable],
        main_rows: Optional[Sequence[RowData]],
        required_fields: Optional[Set[str]] = None,
    ) -> None:
        prefill_main_source_fields(
            context=context,
            plan_field_specs=self.plan.field_specs,
            runtime=self.runtime,
            batch_row_nth=batch_row_nth,
            main_rows=main_rows,
            required_fields=required_fields,
        )

    def execute_batch(
        self,
        batch_row_nth: List[Hashable],
        batch_num: int,
        sink: Optional[ISink] = None,
        required_fields: Optional[Set[str]] = None,
        main_rows: Optional[Sequence[RowData]] = None,
        *,
        adaptive_pool: Optional[Executor] = None,
    ) -> List[RowData]:
        context = create_batch_context_for_rows(batch_row_nth, required_fields=required_fields)
        self.runtime.sink = sink
        self.runtime.batch_num = batch_num
        self.runtime.reset_load_ref_cache()
        # 结果需要从 `BatchContext` 逐行提取,`write-precompute` 不适用于该路径.
        self.runtime.late_fields = frozenset()

        self.prefill_main_source_fields(context, batch_row_nth, main_rows, required_fields=required_fields)

        stage_durations = self.execute_operators(
            context,
            batch_row_nth,
            runtime=self.runtime,
            required_fields=required_fields,
            adaptive_pool=adaptive_pool,
            after_operator=None,
        )

        if stage_durations is not None:
            for stage_name, duration in stage_durations.items():
                if duration > 0:
                    self.runtime.instrumentation.emit_stage_span(stage_name, batch_num, duration)

        return self._extract_results(context, batch_row_nth)

    def execute_operators(  # noqa: C901, PLR0912  # pragma: allow-c901 plan: c20-fusion-dispatch
        self,
        context: BatchContext,
        batch_row_nth: List[Hashable],
        *,
        runtime: ExecutionRuntime,
        required_fields: Optional[Set[str]],
        adaptive_pool: Optional[Executor],
        after_operator: Optional[Callable[[SupportedOperatorIr], None]],
    ) -> Optional[Dict[str, float]]:
        wants_stage_spans, stage_durations, stage_map = init_stage_span_tracking(runtime)
        wants_operator_spans = runtime.instrumentation.wants(EventType.OPERATOR_SPAN)

        resolved_workers = 1
        if runtime.parallel_mode == "adaptive":
            _, _, resolved_workers = resolve_adaptive_policy_tuning_and_workers(runtime=runtime, overrides=self._overrides)

        # `field_key` -> 融合组; 同组后续字段在已融合时跳过.
        fusion_by_field: Dict[str, ComputeFusionGroup] = {}
        for group in self.plan.compute_fusion_groups:
            for field_key in group.field_keys:
                fusion_by_field[field_key] = group
        fused_done: Set[str] = set()

        for is_loadref, segment in iter_operator_segments(
            cast("Sequence[SupportedOperatorIr]", self.plan.operators)  # pragma: allow-cast plan operators typed narrowing
        ):
            if is_loadref:
                loadref_ops = cast("List[LoadRefOp]", segment)  # pragma: allow-cast segment typed narrowing
                stage = stage_map.get(OperatorType.LOAD_REF.value)
                if wants_stage_spans and stage:
                    perf_counter = self._overrides.stage_perf_counter_fn or time.perf_counter
                    start = perf_counter()
                    self._execute_loadref_segment(
                        loadref_ops,
                        context=context,
                        batch_row_nth=batch_row_nth,
                        runtime=runtime,
                        required_fields=required_fields,
                        adaptive_pool=adaptive_pool,
                        max_workers=resolved_workers,
                        after_operator=after_operator,
                    )
                    stage_durations[stage] += max(0.0, perf_counter() - start)
                else:
                    self._execute_loadref_segment(
                        loadref_ops,
                        context=context,
                        batch_row_nth=batch_row_nth,
                        runtime=runtime,
                        required_fields=required_fields,
                        adaptive_pool=adaptive_pool,
                        max_workers=resolved_workers,
                        after_operator=after_operator,
                    )
                continue

            operator = cast("SupportedOperatorIr", segment)  # pragma: allow-cast segment typed narrowing

            if operator.operator_type == OperatorType.COMPUTE.value:
                compute_op = cast("ComputeOperatorIr", operator)  # pragma: allow-cast compute operator narrowing
                field_key = str(compute_op.field_key)
                if _try_execute_fused_compute(
                    field_key=field_key,
                    fusion_by_field=fusion_by_field,
                    fused_done=fused_done,
                    context=context,
                    batch_row_nth=batch_row_nth,
                    runtime=runtime,
                    wants_stage_spans=wants_stage_spans,
                    stage_map=stage_map,
                    stage_durations=stage_durations,
                    stage_perf_counter_fn=self._overrides.stage_perf_counter_fn,
                ):
                    if after_operator is not None:
                        after_operator(operator)
                    continue

            executor = self._executors.get(operator.operator_type)

            if executor:
                stage = stage_map.get(operator.operator_type)
                wants_compute_span = wants_operator_spans and operator.operator_type == OperatorType.COMPUTE.value
                if (wants_stage_spans and stage) or wants_compute_span:
                    perf_counter = self._overrides.stage_perf_counter_fn or time.perf_counter
                    start = perf_counter()
                    executor.execute(operator, context, batch_row_nth, runtime)
                    duration = max(0.0, perf_counter() - start)
                    if wants_stage_spans and stage:
                        stage_durations[stage] += duration
                    if wants_compute_span:
                        compute_op = cast("ComputeOperatorIr", operator)  # pragma: allow-cast compute operator narrowing
                        runtime.instrumentation.emit_operator_span(
                            operator_type=OperatorType.COMPUTE.value,
                            field_key=str(compute_op.field_key),
                            batch_num=int(runtime.batch_num),
                            duration=float(duration),
                        )
                else:
                    executor.execute(operator, context, batch_row_nth, runtime)

            if after_operator is not None:
                after_operator(operator)

        return stage_durations if wants_stage_spans else None

    def _execute_loadref_segment(
        self,
        ops: Sequence[LoadRefOp],
        *,
        context: BatchContext,
        batch_row_nth: List[Hashable],
        runtime: ExecutionRuntime,
        required_fields: Optional[Set[str]],
        adaptive_pool: Optional[Executor],
        max_workers: int,
        after_operator: Optional[Callable[[SupportedOperatorIr], None]],
    ) -> None:
        executor = self._executors.get(OperatorType.LOAD_REF.value)
        if executor is None:
            return

        # 串行模式: 按算子顺序使用现有执行器执行.
        if runtime.parallel_mode != "adaptive":
            self._execute_loadref_ops_serially(
                executor,
                ops,
                context=context,
                batch_row_nth=batch_row_nth,
                runtime=runtime,
                after_operator=after_operator,
            )
            return

        # 自适应模式: 在批次内对 `LoadRef(keys)` 做扇出/扇入,并在提交点进行捕获/回放.
        # 当未提供线程池时,回退为串行行为(等同于 `seq`).
        pool = adaptive_pool
        if pool is None:
            self._execute_loadref_ops_serially(
                executor,
                ops,
                context=context,
                batch_row_nth=batch_row_nth,
                runtime=runtime,
                after_operator=after_operator,
            )
            return

        self._adaptive_scheduler.execute_segment(
            ops,
            context=context,
            batch_row_nth=batch_row_nth,
            runtime=runtime,
            pool=pool,
            max_workers=max_workers,
            required_fields=required_fields,
            after_operator=cast(  # pragma: allow-cast callback typed narrowing
                "Optional[Callable[[LoadRefOp], None]]",
                after_operator,
            ),
        )

    def _execute_loadref_ops_serially(
        self,
        executor: OperatorExecutor,
        ops: Sequence[LoadRefOp],
        *,
        context: BatchContext,
        batch_row_nth: List[Hashable],
        runtime: ExecutionRuntime,
        after_operator: Optional[Callable[[SupportedOperatorIr], None]],
    ) -> None:
        for op in ops:
            executor.execute(op, context, batch_row_nth, runtime)
            if after_operator is not None:
                after_operator(op)

    def _extract_results(
        self,
        context: BatchContext,
        batch_row_nth: List[Hashable],
    ) -> List[RowData]:
        """提取批次结果"""
        results: List[RowData] = []
        for row_id in batch_row_nth:
            row: Dict[str, FieldValue] = {}
            for field_key in self.plan.target_fields:
                row[field_key] = context.get_field_value(field_key, row_id)
            results.append(row)
        return results


__all__ = ("BatchExecutor",)
