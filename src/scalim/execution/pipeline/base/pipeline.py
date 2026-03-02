"""`Pipeline` 的实现.

之所以不放在包的 `__init__.py` 中,是为了让包级导出保持精简,避免扩大导入面.
"""

# region imports

import contextlib
import gc
import time
from abc import ABC, abstractmethod
from collections.abc import Hashable, Iterable, Iterator, Sequence
from concurrent.futures import Executor
from typing import Any, cast

from ....hooks.base import HookManager
from ....ob.manager import ObserverManager
from ....planning.operators import ComputeOperatorIr, LoadOperatorIr, LoadRefOperatorIr
from ....planning.plan import ExecutionPlan
from ....sinks.sink_base import IColumnSink, IRowSink, ISink
from ....spec.ir.demand import DemandIr
from ....spec.ir.fields import FieldIr
from ....typedefs import FieldValue, RowData, SinkRowKeySeq
from ....vendor.compact.typing_extensionsx import override
from ...context import BatchContext
from ...executor.batch.executor import BatchExecutor
from ...executor.helpers.relation_signature import build_relation_signature, can_group_by_relation, has_rows_binding
from ...executor.runtime.runtime import ExecutionRuntime
from ...loader_retry import CALLSITE_MAIN_SOURCE, CALLSITE_PRELOAD_FOREVER, call_with_loader_retry
from ..overrides import PipelineOverrides, chunk_iterable
from ._adaptive_pool import maybe_create_adaptive_pool
from ._row_emission import RowEmissionCoordinator

# endregion


class _ReverseSortValue:
    __slots__: tuple[str, ...] = ("value",)

    def __init__(self, value: Any) -> None:
        self.value: Any = value

    def __lt__(self, other: "_ReverseSortValue") -> bool:
        return other.value < self.value


class Pipeline(ABC):
    """流水线(`Pipeline`)抽象基类.

    用于继承后实现不同执行策略, 例如:
    - `SeqPipeline`: 顺序执行
    """

    plan: ExecutionPlan
    executor: BatchExecutor
    runtime: ExecutionRuntime
    hook_manager: HookManager
    observer_manager: ObserverManager
    batch_size: int
    gc_interval: int
    demand: DemandIr
    _required_fields: set[str]
    _overrides: PipelineOverrides

    def __init__(
        self,
        plan: ExecutionPlan,
        executor: BatchExecutor,
        runtime: ExecutionRuntime,
        hook_manager: HookManager,
        observer_manager: ObserverManager,
        demand: DemandIr,
        batch_size: int = 1000,
        gc_interval: int = 10,
        overrides: PipelineOverrides | None = None,
    ) -> None:
        self.plan = plan
        self.executor = executor
        self.runtime = runtime
        self.hook_manager = hook_manager
        self.observer_manager = observer_manager
        self.demand = demand
        self.batch_size = batch_size
        self.gc_interval = gc_interval
        self._overrides = overrides or PipelineOverrides(chunk_iterable=chunk_iterable)
        self._required_fields = self._compute_required_fields()

    def _compute_required_fields(self) -> set[str]:
        """计算需要存储的字段集合(包含递归依赖的传递闭包).

        使用 `ExecutionPlan.field_dependencies` 而不是 `field_spec.get_dependencies()`,
        因为 `field_dependencies` 是基于主数据源方向正确推断的依赖.
        """
        required: set[str] = set()
        visited: set[str] = set()

        def collect(field_key: str) -> None:
            if field_key in visited:
                return
            visited.add(field_key)
            required.add(field_key)
            # 使用 `ExecutionPlan.field_dependencies` 获取正确的依赖
            deps = self.plan.field_dependencies.get(field_key, ())
            for dep in deps:
                collect(dep)

        for target in self.plan.target_fields:
            collect(target)

        main_source = self.demand.main_source
        if main_source and main_source.order_by:
            for order_key in main_source.order_by:
                required.add(order_key.field_key)

        return required

    def _order_by_sort_key(
        self,
        context: BatchContext,
        row_id: Hashable,
        field_key: str,
        direction: str,
    ) -> tuple[int, Any]:
        value = context.get_field_value(field_key, row_id)
        if value is None:
            return (1, 0)
        if direction == "desc":
            return (0, _ReverseSortValue(value))
        return (0, value)

    def _sort_row_ids_for_write(
        self,
        row_ids: list[Hashable],
        context: BatchContext,
    ) -> list[Hashable]:
        main_source = self.demand.main_source
        if not main_source or not main_source.order_by:
            return row_ids

        ordered = list(row_ids)
        for order in reversed(main_source.order_by):
            field_key = order.field_key
            direction = order.direction
            ordered.sort(key=lambda rid, fk=field_key, dirn=direction: self._order_by_sort_key(context, rid, fk, dirn))
        return ordered

    @abstractmethod
    def run(
        self,
        main_rows: Iterable[RowData] | None = None,
        sink: ISink | None = None,
    ) -> Sequence[RowData]:
        """执行流水线."""

    def _preload_cached_sources(self) -> None:
        """预加载缓存数据源"""
        for source in self.plan.preload_sources:
            if source.is_preload_forever():
                loader_start = time.perf_counter()
                policy = self.runtime.loader_retry.resolve(source.source_id)
                result = call_with_loader_retry(
                    call=source.loader_spec.callable,
                    instrumentation=self.runtime.instrumentation,
                    policy=policy,
                    loader_name=source.source_id,
                    callsite=CALLSITE_PRELOAD_FOREVER,
                    batch_num=self.runtime.batch_num,
                )
                loader_duration = time.perf_counter() - loader_start

                self.runtime.preloaded_cache[source.source_id] = result

                self.runtime.instrumentation.emit_loader_call(
                    loader_name=f"{source.source_id} [preload_forever]",
                    params={},
                    result=result,
                    duration=loader_duration,
                )

    def _load_main_rows(self) -> Iterable[RowData]:
        """加载主数据源的行(行流)."""
        main_source = self.demand.main_source
        loader_fn = main_source.loader
        params = dict(main_source.params or {})

        loader_start = time.perf_counter()
        policy = self.runtime.loader_retry.resolve(main_source.source_id)
        result = call_with_loader_retry(
            call=(lambda: loader_fn(**params)) if params else loader_fn,
            instrumentation=self.runtime.instrumentation,
            policy=policy,
            loader_name=main_source.source_id,
            callsite=CALLSITE_MAIN_SOURCE,
            batch_num=self.runtime.batch_num,
        )
        loader_duration = time.perf_counter() - loader_start

        self.runtime.instrumentation.emit_loader_call(
            loader_name=main_source.source_id,
            params=params,
            result=result,
            duration=loader_duration,
        )

        return result

    def _iter_row_batches(
        self,
        main_rows: Iterable[RowData],
    ) -> Iterator[tuple[list[Hashable], dict[Hashable, RowData]]]:
        """按原始行顺序产出批次 `(row_ids, row_map)`."""
        row_iter = iter(main_rows)
        next_row_id = 0

        for batch_rows in self._overrides.chunk_iterable(row_iter, self.batch_size):
            if not batch_rows:
                break
            row_ids = cast("list[Hashable]", list(range(next_row_id, next_row_id + len(batch_rows))))
            next_row_id += len(batch_rows)
            batch_map: dict[Hashable, RowData] = dict(zip(row_ids, batch_rows, strict=True))
            yield row_ids, batch_map


class SeqPipeline(Pipeline):
    """顺序执行流水线."""

    @override
    def run(
        self,
        main_rows: Iterable[RowData] | None = None,
        sink: ISink | None = None,
    ) -> Sequence[RowData]:
        start_time = time.perf_counter()

        self.runtime.instrumentation.emit_pipeline_start(self.plan.target_fields, self.batch_size)

        self._preload_cached_sources()

        if main_rows is None:
            main_rows = self._load_main_rows()

        column_sink, streaming_sink = self._classify_sink(sink)

        results: list[RowData] = []
        batch_count = 0

        try:
            with contextlib.ExitStack() as stack:
                adaptive_pool = maybe_create_adaptive_pool(
                    plan=self.plan,
                    runtime=self.runtime,
                    overrides=self._overrides,
                    stack=stack,
                )

                for row_ids, batch_rows in self._iter_row_batches(main_rows):
                    batch_count += 1
                    batch_start_time = time.perf_counter()
                    self.runtime.instrumentation.emit_batch_start(batch_count, list(row_ids))

                    if column_sink is not None:
                        batch_results = self._execute_batch_column_mode(
                            row_ids,
                            batch_rows,
                            column_sink,
                            batch_count,
                            adaptive_pool=adaptive_pool,
                        )
                    elif streaming_sink is not None:
                        batch_results = self._execute_batch_streaming_mode(
                            row_ids,
                            batch_rows,
                            streaming_sink,
                            batch_count,
                            adaptive_pool=adaptive_pool,
                        )
                    else:
                        batch_results = self.executor.execute_batch(
                            row_ids,
                            batch_count,
                            sink,
                            required_fields=self._required_fields,
                            main_rows=batch_rows,
                            adaptive_pool=adaptive_pool,
                        )

                    batch_duration = time.perf_counter() - batch_start_time
                    self.runtime.instrumentation.emit_batch_end(batch_count, batch_duration)

                    self._process_batch_results(batch_results, results, sink, column_sink, streaming_sink)

                    if batch_count % self.gc_interval == 0:
                        _ = gc.collect()

                return self._finalize_run(sink, results, batch_count, start_time)
        except Exception:
            if sink:
                with contextlib.suppress(Exception):
                    sink.close()
            raise
        finally:
            with contextlib.suppress(Exception):
                self.observer_manager.close()

    def _classify_sink(
        self,
        sink: ISink | None,
    ) -> "tuple[IColumnSink | None, IRowSink | None]":
        """分类输出端(`sink`)类型."""
        column_sink: IColumnSink | None = None
        streaming_sink: IRowSink | None = None
        if sink is not None:
            if isinstance(sink, IColumnSink):
                column_sink = sink
            elif isinstance(sink, IRowSink):
                streaming_sink = sink
        return column_sink, streaming_sink

    def _process_batch_results(
        self,
        batch_results: list[RowData],
        results: list[RowData],
        sink: ISink | None,
        column_sink: IColumnSink | None,
        streaming_sink: IRowSink | None,
    ) -> None:
        """处理批次结果"""
        if column_sink is None and streaming_sink is None:
            if sink:
                sink.write_batch(batch_results)
            else:
                results.extend(batch_results)

    def _finalize_run(
        self,
        sink: ISink | None,
        results: list[RowData],
        batch_count: int,
        start_time: float,
    ) -> list[RowData]:
        return_value: list[RowData]
        if sink:
            sink.close()
            return_value = []
        else:
            return_value = results

        total_duration = time.perf_counter() - start_time
        self.runtime.instrumentation.emit_pipeline_end(batch_count, total_duration)

        return return_value

    def _execute_batch_column_mode(
        self,
        row_ids: list[Hashable],
        batch_rows: dict[Hashable, RowData],
        column_sink: IColumnSink,
        batch_num: int,
        *,
        adaptive_pool: Executor | None = None,
    ) -> list[RowData]:
        """列式模式执行批次 (FR023 块列写入)

        真正的块列写入: 每批次独立处理,按列写入后释放内存
        - 批次1 (5行): 写入 col1(5行) → 释放 → 写入 col2(5行) → 释放 → ...
        - 批次2 (5行): 写入 col1(5行) → 释放 → 写入 col2(5行) → 释放 → ...
        """
        context = BatchContext(required_fields=self._required_fields)
        self.runtime.sink = column_sink
        self.runtime.batch_num = batch_num
        self.runtime.reset_load_ref_cache()
        self.executor.prefill_main_source_fields(context, batch_rows, required_fields=self._required_fields)

        write_row_ids = self._sort_row_ids_for_write(row_ids, context)
        column_sink.set_row_ids(cast("SinkRowKeySeq", list(write_row_ids)))

        self._write_main_source_columns(write_row_ids, context, column_sink, batch_num)

        def after_operator(operator: Any) -> None:
            if isinstance(operator, LoadOperatorIr):
                for fk in operator.field_keys:
                    self._write_column_if_target(fk, write_row_ids, context, column_sink, batch_num)
            elif isinstance(operator, LoadRefOperatorIr):
                self._write_column_if_target(operator.field_key, write_row_ids, context, column_sink, batch_num)
            elif isinstance(operator, ComputeOperatorIr):
                self._write_column_if_target(operator.field_spec.field_id, write_row_ids, context, column_sink, batch_num)

        stage_durations = self.executor.execute_operators(
            context,
            row_ids,
            runtime=self.runtime,
            required_fields=self._required_fields,
            adaptive_pool=adaptive_pool,
            after_operator=after_operator,
        )
        if stage_durations is not None:
            for stage_name, duration in stage_durations.items():
                if duration > 0:
                    self.runtime.instrumentation.emit_stage_span(stage_name, batch_num, duration)

        context.clear()
        return []

    def _write_main_source_columns(
        self,
        row_ids: list[Hashable],
        context: BatchContext,
        column_sink: IColumnSink,
        batch_num: int,
    ) -> None:
        main_source = self.runtime.main_source
        if main_source is None:
            return

        main_source_id = main_source.source_id
        for field_key in self.plan.target_fields:
            field_spec = self.plan.field_specs.get(field_key)
            if field_spec is None:
                self._write_column_if_target(field_key, row_ids, context, column_sink, batch_num)
                continue
            if isinstance(field_spec, FieldIr) and field_spec.source.source_id == main_source_id:
                self._write_column_if_target(field_key, row_ids, context, column_sink, batch_num)

    def _write_column_if_target(
        self,
        field_key: str,
        row_ids: list[Hashable],
        context: BatchContext,
        column_sink: IColumnSink,
        batch_num: int,
    ) -> None:
        """如果是目标字段,写入列"""
        if field_key not in self.plan.target_fields:
            return

        col_data: dict[Hashable, FieldValue] = {}
        for row_id in row_ids:
            value = context.get_field_value(field_key, row_id)
            col_data[row_id] = value

        column_sink.write_column(field_key, col_data)

        self.runtime.instrumentation.emit_column_write(
            field_key=field_key,
            row_count=len(col_data),
            batch_num=batch_num,
        )

        if field_key not in self.plan.key_fields and field_key not in self.runtime.reverse_deps:
            context.delete_field(field_key)
            self.runtime.instrumentation.emit_field_slim(
                field_key=field_key,
                reason="目标字段已列式写入,无后续依赖",
                batch_num=batch_num,
                remaining_fields=context.get_field_count(),
            )

    def _resolve_streaming_global_ready_target_fields(self) -> set[str]:
        main_source = self.runtime.main_source
        main_source_id = main_source.source_id if main_source else None

        global_ready_target_fields: set[str] = set()
        for field_key in self.plan.target_fields:
            field_spec = self.plan.field_specs.get(field_key)
            if field_spec is None:
                global_ready_target_fields.add(field_key)
                continue
            if main_source_id and isinstance(field_spec, FieldIr) and field_spec.source.source_id == main_source_id:
                global_ready_target_fields.add(field_key)
        return global_ready_target_fields

    def _collect_streaming_rows_binding_barriers(
        self,
    ) -> tuple[set[tuple[tuple[Any, ...], ...]], set[str]]:
        rows_binding_relations: set[tuple[tuple[Any, ...], ...]] = set()
        rows_binding_ops: set[str] = set()

        for operator in self.plan.operators:
            if not isinstance(operator, LoadRefOperatorIr):
                continue
            if not has_rows_binding(operator.lookup_steps):
                continue
            if can_group_by_relation(operator.lookup_steps):
                rows_binding_relations.add(build_relation_signature(operator.lookup_steps))
            else:
                rows_binding_ops.add(operator.operator_id)

        return rows_binding_relations, rows_binding_ops

    def _execute_batch_streaming_mode(
        self,
        row_ids: list[Hashable],
        batch_rows: dict[Hashable, RowData],
        streaming_sink: IRowSink,
        batch_num: int,
        *,
        adaptive_pool: Executor | None = None,
    ) -> list[RowData]:
        """流式模式执行批次(真正的逐行流式)."""
        self.runtime.sink = streaming_sink
        self.runtime.batch_num = batch_num
        self.runtime.reset_load_ref_cache()

        global_ready_target_fields = self._resolve_streaming_global_ready_target_fields()
        rows_binding_relations, rows_binding_ops = self._collect_streaming_rows_binding_barriers()
        allow_release = not rows_binding_relations and not rows_binding_ops
        coordinator = RowEmissionCoordinator(
            runtime=self.runtime,
            sink=streaming_sink,
            target_fields=self.plan.target_fields,
            retained_fields=set(self.plan.key_fields),
            global_ready_fields=global_ready_target_fields,
            allow_release=allow_release,
        )

        context = BatchContext(required_fields=self._required_fields, on_field_set=coordinator.on_field_set)
        coordinator.attach_context(context)

        self.executor.prefill_main_source_fields(context, batch_rows, required_fields=self._required_fields)
        write_row_ids = self._sort_row_ids_for_write(row_ids, context)
        coordinator.set_write_order(write_row_ids)
        coordinator.flush_ready_rows()

        active_row_ids = list(row_ids)

        def after_operator(operator: Any) -> None:
            if isinstance(operator, LoadRefOperatorIr):
                if operator.operator_id in rows_binding_ops:
                    rows_binding_ops.discard(operator.operator_id)
                relation_key = build_relation_signature(operator.lookup_steps)
                if relation_key in rows_binding_relations and relation_key in self.runtime.load_ref_group_executed:
                    rows_binding_relations.discard(relation_key)
                if not rows_binding_ops and not rows_binding_relations:
                    coordinator.enable_release()

            to_remove = coordinator.drain_rows_to_remove()
            if to_remove:
                active_row_ids[:] = [rid for rid in active_row_ids if rid not in to_remove]

        stage_durations = self.executor.execute_operators(
            context,
            active_row_ids,
            runtime=self.runtime,
            required_fields=self._required_fields,
            adaptive_pool=adaptive_pool,
            after_operator=after_operator,
        )
        if stage_durations is not None:
            for stage_name, duration in stage_durations.items():
                if duration > 0:
                    self.runtime.instrumentation.emit_stage_span(stage_name, batch_num, duration)

        coordinator.finalize()
        context.clear()
        return []


__all__ = ["Pipeline", "SeqPipeline"]
