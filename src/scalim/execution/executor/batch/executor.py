"""批次执行器实现。

之所以不放在包的 `__init__.py` 中，是为了保持包级导出精简，避免扩大导入面。
"""

# region imports

import time
from collections.abc import Callable, Hashable, Sequence
from concurrent.futures import Executor
from typing import TYPE_CHECKING, cast

from ....planning.operators import LoadRefOperatorIr as LoadRefOp
from ....planning.operators import OperatorType, SupportedOperatorIr
from ....planning.plan import ExecutionPlan
from ....sinks.sink_base import ISink
from ....typedefs import FieldValue, RowData
from ...adaptive.config import resolve_adaptive_policy_tuning_and_workers
from ...context import BatchContext
from ..operators.base import OperatorExecutor
from ..operators.compute.executor import ComputeOperatorExecutor
from ..operators.load import LoadOperatorExecutor
from ..operators.load_ref.executor import LoadRefOperatorExecutor
from ..operators.release import ReleaseOperatorExecutor
from ..operators.write import WriteColumnOperatorExecutor, WriteRowOperatorExecutor
from ..runtime.runtime import ExecutionRuntime
from ._internal.segments import iter_operator_segments
from ._internal.stage_spans import init_stage_span_tracking
from ._main_prefill import prefill_main_source_fields

# endregion

if TYPE_CHECKING:
    from ...adaptive.loadref_scheduler import AdaptiveLoadRefScheduler
    from ...pipeline.overrides import PipelineOverrides


class BatchExecutor:
    """批次执行器"""

    plan: ExecutionPlan
    runtime: ExecutionRuntime
    _executors: dict[str, OperatorExecutor]
    _overrides: "PipelineOverrides"
    _adaptive_scheduler: "AdaptiveLoadRefScheduler"

    def __init__(
        self,
        plan: ExecutionPlan,
        runtime: ExecutionRuntime,
        *,
        overrides: "PipelineOverrides | None" = None,
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
            from ...pipeline.overrides import PipelineOverrides  # noqa: PLC0415

            overrides = PipelineOverrides()
        self._overrides = overrides
        from ...adaptive.loadref_scheduler import AdaptiveLoadRefScheduler  # noqa: PLC0415

        self._adaptive_scheduler = AdaptiveLoadRefScheduler(plan, overrides=self._overrides)

    def prefill_main_source_fields(
        self,
        context: BatchContext,
        main_rows: dict[Hashable, RowData] | None,
        required_fields: set[str] | None = None,
    ) -> None:
        prefill_main_source_fields(
            context=context,
            plan_field_specs=self.plan.field_specs,
            runtime=self.runtime,
            main_rows=main_rows,
            required_fields=required_fields,
        )

    def execute_batch(
        self,
        batch_row_nth: list[Hashable],
        batch_num: int,
        sink: ISink | None = None,
        required_fields: set[str] | None = None,
        main_rows: dict[Hashable, RowData] | None = None,
        *,
        adaptive_pool: Executor | None = None,
    ) -> list[RowData]:
        context = BatchContext(required_fields=required_fields)
        self.runtime.sink = sink
        self.runtime.batch_num = batch_num
        self.runtime.reset_load_ref_cache()

        self.prefill_main_source_fields(context, main_rows, required_fields=required_fields)

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

    def execute_operators(
        self,
        context: BatchContext,
        batch_row_nth: list[Hashable],
        *,
        runtime: ExecutionRuntime,
        required_fields: set[str] | None,
        adaptive_pool: Executor | None,
        after_operator: Callable[[object], None] | None,
    ) -> dict[str, float] | None:
        wants_stage_spans, stage_durations, stage_map = init_stage_span_tracking(runtime)

        resolved_workers = 1
        if runtime.parallel_mode == "adaptive":
            _, _, resolved_workers = resolve_adaptive_policy_tuning_and_workers(runtime=runtime, overrides=self._overrides)

        for is_loadref, segment in iter_operator_segments(cast("Sequence[SupportedOperatorIr]", self.plan.operators)):
            if is_loadref:
                loadref_ops = cast("list[LoadRefOp]", segment)
                stage = stage_map.get(OperatorType.LOAD_REF.value)
                if wants_stage_spans and stage:
                    start = time.perf_counter()
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
                    stage_durations[stage] += max(0.0, time.perf_counter() - start)
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

            operator = cast("SupportedOperatorIr", segment)
            executor = self._executors.get(operator.operator_type)

            if executor:
                stage = stage_map.get(operator.operator_type)
                if wants_stage_spans and stage:
                    start = time.perf_counter()
                    executor.execute(operator, context, batch_row_nth, runtime)
                    stage_durations[stage] += max(0.0, time.perf_counter() - start)
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
        batch_row_nth: list[Hashable],
        runtime: ExecutionRuntime,
        required_fields: set[str] | None,
        adaptive_pool: Executor | None,
        max_workers: int,
        after_operator: Callable[[object], None] | None,
    ) -> None:
        # `seq` 模式：按算子顺序使用现有执行器执行。
        if runtime.parallel_mode != "adaptive":
            executor = self._executors.get(OperatorType.LOAD_REF.value)
            if executor is None:
                return
            for op in ops:
                executor.execute(op, context, batch_row_nth, runtime)
                if after_operator is not None:
                    after_operator(op)
            return

        # `adaptive` 模式：批次内对 `LoadRef(keys)` 做扇出/扇入，并在提交阶段做捕获/回放。
        # 未提供线程池时，退回到串行行为（等同于 `seq`）。
        pool = adaptive_pool
        if pool is None:
            executor = self._executors.get(OperatorType.LOAD_REF.value)
            if executor is None:
                return
            for op in ops:
                executor.execute(op, context, batch_row_nth, runtime)
                if after_operator is not None:
                    after_operator(op)
            return

        self._adaptive_scheduler.execute_segment(
            ops,
            context=context,
            batch_row_nth=batch_row_nth,
            runtime=runtime,
            pool=pool,
            max_workers=max_workers,
            required_fields=required_fields,
            after_operator=cast("Callable[[LoadRefOp], None] | None", after_operator),
        )

    def _extract_results(
        self,
        context: BatchContext,
        batch_row_nth: list[Hashable],
    ) -> list[RowData]:
        """提取批次结果"""
        results: list[RowData] = []
        for row_id in batch_row_nth:
            row: dict[str, FieldValue] = {}
            for field_key in self.plan.target_fields:
                row[field_key] = context.get_field_value(field_key, row_id)
            results.append(row)
        return results


__all__ = ["BatchExecutor"]
