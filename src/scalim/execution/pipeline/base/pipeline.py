"""`Pipeline` 实现.

此模块刻意不放在包的 `__init__.py` 中,以保持导入面精简.
"""

# region imports

import contextlib
import gc
import sys
import time
import warnings
from abc import ABC, abstractmethod
from collections.abc import Mapping
from concurrent.futures import Executor
from typing import Any, Callable, Dict, FrozenSet, Hashable, Iterable, Iterator, List, Optional, Sequence, Set, Tuple, cast

from ....events import EventType
from ....hooks import HookManager
from ....ob.manager import ObserverManager
from ....planning.operators import ComputeOperatorIr, LoadOperatorIr, LoadRefOperatorIr
from ....planning.plan import ExecutionPlan
from ....sinks import IColumnSink, IRowSink, ISink
from ....sinks._internal.base import SupportsPreloadGetOrLoad, SupportsWriteColumnAligned, discard_sink
from ....spec.ir import DemandIr, FieldIr, SourceIr
from ....spec.ir._helpers import coerce_loader_result_mapping
from ....spec.ir.aliases import LoaderResultMapCallable
from ....spec.ir.binding import LoaderCallContextIr
from ....typedefs import FieldValue, LoaderCallKwargs, LoaderResultMapping, RowData, RuntimeValue, SinkRowKeySeq
from ....utils.relation_signature import build_relation_signature, can_group_by_relation, has_rows_binding
from ....vendor.compact.typing_extensionsx import override
from ...context import BatchContext, create_batch_context_for_rows
from ...executor.batch._internal.stage_spans import (
    StageWriteClock,
    attach_write_clock,
    get_write_clock,
    init_stage_span_tracking,
)
from ...executor.batch.executor import BatchExecutor
from ...executor.runtime.runtime import ExecutionRuntime
from ...loader_call_params import build_loader_call_params
from ...loader_retry import CALLSITE_MAIN_SOURCE, CALLSITE_PRELOAD_FOREVER, call_with_loader_retry
from ...workflow_cache_pool import build_preload_forever_signature
from ...write_precompute import LateColumnMaterializer, LateFieldMaterializer
from ..overrides import PipelineOverrides, chunk_iterable
from ._adaptive_pool import maybe_create_adaptive_pool
from ._row_emission import RowEmissionCoordinator

# endregion


class _ReverseSortValue:
    __slots__: Tuple[str, ...] = ("value",)

    def __init__(self, value: Any) -> None:
        self.value: Any = value

    def __lt__(self, other: "_ReverseSortValue") -> bool:
        return other.value < self.value


def _make_noarg_loader_call(callable_ref: LoaderResultMapCallable, call_kwargs: LoaderCallKwargs) -> Callable[[], LoaderResultMapping]:
    if call_kwargs:

        def call() -> LoaderResultMapping:
            return cast("LoaderResultMapping", callable_ref(**call_kwargs))  # pragma: allow-cast loader callable return boundary

        return call

    def call() -> LoaderResultMapping:
        return cast("LoaderResultMapping", callable_ref())  # pragma: allow-cast loader callable return boundary

    return call


class Pipeline(ABC):
    """`Pipeline` 抽象基类.

    用于继承后实现不同执行策略,比如:
    - `SeqPipeline`: 顺序执行
    """

    plan: ExecutionPlan
    executor: BatchExecutor
    runtime: ExecutionRuntime
    hook_manager: HookManager
    observer_manager: ObserverManager
    batch_size: Optional[int]
    gc_interval: int
    demand: DemandIr
    _required_fields: Set[str]
    _overrides: PipelineOverrides
    _late_fields: FrozenSet[str]
    _late_materializer: Optional[LateFieldMaterializer]
    _late_column_materializer: Optional[LateColumnMaterializer]

    def __init__(
        self,
        plan: ExecutionPlan,
        executor: BatchExecutor,
        runtime: ExecutionRuntime,
        hook_manager: HookManager,
        observer_manager: ObserverManager,
        demand: DemandIr,
        batch_size: Optional[int] = 1000,
        gc_interval: int = 10,
        overrides: Optional[PipelineOverrides] = None,
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
        self._late_fields = frozenset(plan.late_fields)
        self._late_materializer = LateFieldMaterializer(runtime=self.runtime, late_fields=plan.late_fields) if self._late_fields else None
        # 列写出布局按需构建: 行写出路径不必为它付出建表成本.
        self._late_column_materializer = None

    def _ensure_late_column_materializer(self) -> Optional[LateColumnMaterializer]:
        materializer = self._late_materializer
        if materializer is None:
            return None
        late_columns = self._late_column_materializer
        if late_columns is None:
            late_columns = LateColumnMaterializer(
                materializer=materializer,
                field_dependencies=dict(self.plan.field_dependencies),
            )
            self._late_column_materializer = late_columns
        return late_columns

    def _compute_required_fields(self) -> Set[str]:
        """计算需要保留的字段集合(包含传递闭包).

        使用 `plan.field_dependencies` 而不是 `field_spec.get_dependencies()`,
        因为 `field_dependencies` 是基于主数据源方向正确推断的依赖.
        """
        required: Set[str] = set()
        visited: Set[str] = set()

        def collect(field_key: str) -> None:
            if field_key in visited:
                return
            visited.add(field_key)
            required.add(field_key)
            # 使用 `plan.field_dependencies` 获取正确的依赖
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
    ) -> Tuple[int, Any]:
        value = context.get_field_value(field_key, row_id)
        if value is None:
            return (1, 0)
        if direction == "desc":
            return (0, _ReverseSortValue(value))
        return (0, value)

    def _sort_row_ids_for_write(
        self,
        row_ids: List[Hashable],
        context: BatchContext,
    ) -> List[Hashable]:
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
        main_rows: Optional[Iterable[RowData]] = None,
        sink: Optional[ISink] = None,
    ) -> Sequence[RowData]:
        """执行管线."""

    def _preload_cache_get_or_load_or_none(
        self,
        *,
        cache: RuntimeValue,
        source: SourceIr,
        source_id: str,
        rendered_params: LoaderCallKwargs,
        load_fn: Callable[[], LoaderResultMapping],
    ) -> Optional[LoaderResultMapping]:
        """通过 `preloaded_cache.get_or_load` 扩展点加载/复用结果(若不存在则返回 `None`)."""
        if not isinstance(cache, SupportsPreloadGetOrLoad):
            return None
        get_or_load = cache.get_or_load
        if not callable(get_or_load):
            return None

        guardrail_enabled = False
        for cls in type(cache).mro():
            if "signature_guardrail_enabled" not in cls.__dict__:
                continue
            value = cls.__dict__["signature_guardrail_enabled"]
            if isinstance(value, property):
                guardrail_enabled = bool(value.__get__(cache, type(cache)))
            else:
                guardrail_enabled = bool(value)
            break

        if guardrail_enabled:
            digest = build_preload_forever_signature(source, rendered_params=rendered_params).digest()
            return get_or_load(source_id, load_fn, signature_digest=digest)
        return get_or_load(source_id, load_fn)

    def _preload_cached_sources(self) -> None:
        """预加载缓存数据源"""
        for source in self.plan.preload_sources:
            if source.is_preload_forever():
                if self.runtime.is_source_cached(source.source_id):
                    continue

                binding = source.bind
                call_kwargs: LoaderCallKwargs = {}
                loader_fn = self.runtime.runtime_bindings.require_source_loader(source.source_id)
                if binding is not None:
                    preload_ctx = LoaderCallContextIr(source_id=source.source_id, is_ref_loader=False)
                    _args, call_kwargs = build_loader_call_params(
                        binding=binding,
                        context=preload_ctx,
                        runtime_bindings=self.runtime.runtime_bindings,
                    )
                call = _make_noarg_loader_call(loader_fn, call_kwargs)

                source_id = source.source_id
                normalize = source.normalize
                normalize_call_by = self.runtime.runtime_bindings.get_source_normalize_call_by(source_id)

                def _load_preload_forever_source(
                    *,
                    source_id: str = source_id,
                    normalize: Any = normalize,
                    normalize_call_by: Any = normalize_call_by,
                    call: Callable[[], LoaderResultMapping] = call,
                    call_kwargs: LoaderCallKwargs = call_kwargs,
                ) -> LoaderResultMapping:
                    loader_start = time.perf_counter()
                    policy = self.runtime.loader_retry.resolve(source_id)
                    result = call_with_loader_retry(
                        call=call,
                        instrumentation=self.runtime.instrumentation,
                        policy=policy,
                        loader_name=source_id,
                        callsite=CALLSITE_PRELOAD_FOREVER,
                        batch_num=self.runtime.batch_num,
                    )
                    loader_duration = time.perf_counter() - loader_start

                    result_obj: RuntimeValue = result
                    if normalize is not None:
                        result_obj = normalize.apply(
                            result,
                            source_id=source_id,
                            call_by=normalize_call_by,
                        )
                    is_mapping = isinstance(result_obj, Mapping)
                    if not is_mapping:
                        msg = "Loader '{}' result must be a Mapping".format(source_id)
                        raise TypeError(msg)
                    result_mapping = coerce_loader_result_mapping(
                        cast("LoaderResultMapping", result_obj)  # pragma: allow-cast Mapping generic params unknown after isinstance
                    )

                    self.runtime.instrumentation.emit_loader_call(
                        loader_name=source_id,
                        params=call_kwargs,
                        result=result_mapping,
                        duration=loader_duration,
                        cache_scope="preload_forever",
                    )
                    return result_mapping

                cache = self.runtime.preloaded_cache
                cache_pool = self.runtime.workflow_cache_pool
                workflow_node_id = self.runtime.workflow_node_id
                if cache_pool is not None and workflow_node_id is not None:
                    signature = build_preload_forever_signature(source, rendered_params=call_kwargs)
                    result_mapping = cache_pool.get_or_load(
                        signature,
                        workflow_node_id=workflow_node_id,
                        load_fn=_load_preload_forever_source,
                    )
                    cache[source_id] = result_mapping
                    continue

                result_mapping = self._preload_cache_get_or_load_or_none(
                    cache=cache,
                    source=source,
                    source_id=source_id,
                    rendered_params=call_kwargs,
                    load_fn=_load_preload_forever_source,
                )
                if result_mapping is not None:
                    cache[source_id] = result_mapping
                    continue

                result_mapping = _load_preload_forever_source()
                cache[source_id] = result_mapping

    def _load_main_rows(self) -> Iterable[RowData]:
        """加载主数据源行(按行流)."""
        main_source = self.demand.main_source
        loader_fn = self.runtime.runtime_bindings.require_main_source_loader(main_source.source_id)
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
    ) -> Iterator[Tuple[List[Hashable], List[RowData], Optional[float]]]:
        """按行顺序产出批次(`row_ids`, `row_rows`, `stream_duration_s`)."""
        row_iter = iter(main_rows)
        next_row_id = 0
        wants_stage_spans = self.runtime.instrumentation.wants(EventType.STAGE_SPAN)
        perf_counter = self._overrides.stage_perf_counter_fn or time.perf_counter

        def _make_row_ids(start: int, count: int) -> List[Hashable]:
            ids: List[Hashable] = []
            ids.extend(range(start, start + count))
            return ids

        if self.batch_size is None:
            stream_duration_s: Optional[float] = None
            if wants_stage_spans:
                start = perf_counter()
                batch_rows = list(row_iter)
                stream_duration_s = max(0.0, perf_counter() - start)
            else:
                batch_rows = list(row_iter)
            if batch_rows:
                row_ids = _make_row_ids(next_row_id, len(batch_rows))
                yield row_ids, batch_rows, stream_duration_s
            return

        chunk_size = self.batch_size
        chunk_iter = self._overrides.chunk_iterable(row_iter, chunk_size)
        while True:
            stream_duration_s = None
            if wants_stage_spans:
                start = perf_counter()
                try:
                    batch_rows = next(chunk_iter)
                except StopIteration:
                    break
                stream_duration_s = max(0.0, perf_counter() - start)
            else:
                try:
                    batch_rows = next(chunk_iter)
                except StopIteration:
                    break

            if not batch_rows:
                break
            row_ids = _make_row_ids(next_row_id, len(batch_rows))
            next_row_id += len(batch_rows)
            yield row_ids, batch_rows, stream_duration_s


class SeqPipeline(Pipeline):
    """顺序执行 `Pipeline`."""

    def _maybe_consume_clear_main_rows_list(
        self,
        *,
        enabled: bool,
        main_rows: Iterable[RowData],
        row_ids: List[Hashable],
        batch_rows: List[RowData],
    ) -> None:
        if not enabled:
            return
        if not row_ids:
            return
        start_idx = row_ids[0]
        if not isinstance(start_idx, int):
            return

        if not isinstance(main_rows, list):
            return
        rows_list = main_rows
        count = len(batch_rows)
        if count <= 0:
            return
        end_idx = int(start_idx) + int(count)
        if int(start_idx) < 0 or end_idx < int(start_idx) or end_idx > len(rows_list):
            return
        # 使用同类型哨兵替换已消费元素(保持 `list` 长度不变),同时释放原行对象引用.
        cleared_row: RowData = {}
        rows_list[int(start_idx) : end_idx] = [cleared_row] * int(count)

    @override
    def run(
        self,
        main_rows: Optional[Iterable[RowData]] = None,
        sink: Optional[ISink] = None,
    ) -> Sequence[RowData]:
        start_time = time.perf_counter()

        self.runtime.instrumentation.emit_pipeline_start(self.plan.target_fields, self.batch_size)

        self._preload_cached_sources()

        loaded_main_rows = False
        if main_rows is None:
            main_rows = self._load_main_rows()
            loaded_main_rows = True

        # 内存优化: 对“主 `loader` 返回 `list`”的常见形态,在批次消费后清空已消费元素引用,以便更早释放行对象占用的内存.
        #
        # 约束:
        # - 仅在 `main_rows` 由框架内部 `loader` 加载时启用(避免意外修改用户显式传入的 `list`).
        # - 仅做“定长 `slice` 置哨兵”,不改变 `list` 长度,避免影响 `list iterator` 语义.
        consume_clear_main_rows_list = bool(loaded_main_rows and isinstance(main_rows, list))

        column_sink, streaming_sink = self._classify_sink(sink)

        results: List[RowData] = []
        batch_count = 0

        try:
            with contextlib.ExitStack() as stack:
                adaptive_pool = maybe_create_adaptive_pool(
                    plan=self.plan,
                    runtime=self.runtime,
                    overrides=self._overrides,
                    stack=stack,
                    sys_module=self._overrides.sys_module or sys,
                    warnings_module=self._overrides.warnings_module or warnings,
                )

                for row_ids, batch_rows, stream_duration_s in self._iter_row_batches(main_rows):
                    batch_count += 1
                    if stream_duration_s is not None and stream_duration_s > 0:
                        self.runtime.instrumentation.emit_stage_span("stream", batch_count, float(stream_duration_s))
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

                    self._maybe_consume_clear_main_rows_list(
                        enabled=consume_clear_main_rows_list,
                        main_rows=main_rows,
                        row_ids=row_ids,
                        batch_rows=batch_rows,
                    )

                    if batch_count % self.gc_interval == 0:
                        collect_fn = self._overrides.gc_collect_fn or gc.collect
                        _ = collect_fn()

                return self._finalize_run(sink, results, batch_count, start_time)
        except Exception:
            if sink:
                with contextlib.suppress(Exception):
                    discard_sink(sink)
            raise
        finally:
            with contextlib.suppress(Exception):
                self.observer_manager.close()

    def _classify_sink(
        self,
        sink: Optional[ISink],
    ) -> "tuple[Optional[IColumnSink], Optional[IRowSink]]":
        """分类输出端类型."""
        column_sink: Optional[IColumnSink] = None
        streaming_sink: Optional[IRowSink] = None
        if sink is not None:
            if isinstance(sink, IColumnSink):
                column_sink = sink
            elif isinstance(sink, IRowSink):
                streaming_sink = sink
        return column_sink, streaming_sink

    def _process_batch_results(
        self,
        batch_results: List[RowData],
        results: List[RowData],
        sink: Optional[ISink],
        column_sink: Optional[IColumnSink],
        streaming_sink: Optional[IRowSink],
    ) -> None:
        """处理批次结果"""
        if column_sink is None and streaming_sink is None:
            if sink:
                sink.write_batch(batch_results)
            else:
                results.extend(batch_results)

    def _finalize_run(
        self,
        sink: Optional[ISink],
        results: List[RowData],
        batch_count: int,
        start_time: float,
    ) -> List[RowData]:
        return_value: List[RowData]
        if sink:
            wants, durations, _stage_map = init_stage_span_tracking(self.runtime)
            write_delta = 0.0
            if wants:
                perf_counter = self._overrides.stage_perf_counter_fn or time.perf_counter
                clock = get_write_clock(self.runtime)
                owns = False
                if clock is None:
                    clock = StageWriteClock(enabled=True, stage_durations=durations, perf_counter=perf_counter)
                    attach_write_clock(self.runtime, clock)
                    owns = True
                before = float(clock.stage_durations.get("write", 0.0) or 0.0)
                with clock.time_write():
                    sink.close()
                write_delta = max(0.0, float(clock.stage_durations.get("write", 0.0) or 0.0) - before)
                if owns:
                    attach_write_clock(self.runtime, None)
            else:
                sink.close()
            if write_delta > 0:
                # `sink.close()`/`save` 计入 `write`;在 `BATCH_END` 之后 `emit`,并于 `pipeline_end` `fold`.
                self.runtime.instrumentation.emit_stage_span("write", max(1, int(batch_count)), write_delta)
            return_value = []
        else:
            return_value = results

        total_duration = time.perf_counter() - start_time
        self.runtime.instrumentation.emit_pipeline_end(batch_count, total_duration)
        self.runtime.maybe_log_call_by_dep_cardinality_summary()
        self.runtime.maybe_log_call_by_memoization_summary()

        return return_value

    def _execute_batch_column_mode(
        self,
        row_ids: List[Hashable],
        batch_rows: List[RowData],
        column_sink: IColumnSink,
        batch_num: int,
        *,
        adaptive_pool: Optional[Executor] = None,
    ) -> List[RowData]:
        """列式模式执行批次 (FR023 块列写入)

        真正的块列写入: 每批次独立处理,按列写入后释放内存
        - 批次1 (5行): 写入 `col1`(5行) → 释放 → 写入 `col2`(5行) → 释放 → ...
        - 批次2 (5行): 写入 `col1`(5行) → 释放 → 写入 `col2`(5行) → 释放 → ...
        """
        context = create_batch_context_for_rows(row_ids, required_fields=self._required_fields)
        self.runtime.sink = column_sink
        self.runtime.batch_num = batch_num
        self.runtime.reset_load_ref_cache()
        # `write-precompute`(切片 B): `late` 列在写出该列前现场物化.
        self.runtime.late_fields = self._late_fields
        late_columns = self._ensure_late_column_materializer()
        if late_columns is not None:
            late_columns.reset()
        self.executor.prefill_main_source_fields(context, row_ids, batch_rows, required_fields=self._required_fields)

        write_row_ids = self._sort_row_ids_for_write(row_ids, context)
        column_sink.set_row_ids(cast("SinkRowKeySeq", list(write_row_ids)))  # pragma: allow-cast sink row ids typed narrowing

        wants_spans, stage_durations, _stage_map = init_stage_span_tracking(self.runtime)
        perf_counter = self._overrides.stage_perf_counter_fn or time.perf_counter
        clock = StageWriteClock(
            enabled=bool(wants_spans),
            stage_durations=stage_durations,
            perf_counter=perf_counter,
        )
        attach_write_clock(self.runtime, clock)
        try:
            self._write_main_source_columns(write_row_ids, context, column_sink, batch_num)

            def after_operator(operator: Any) -> None:
                if isinstance(operator, LoadOperatorIr):
                    for fk in operator.field_keys:
                        self._write_column_if_target(fk, write_row_ids, context, column_sink, batch_num, late_columns=late_columns)
                elif isinstance(operator, (LoadRefOperatorIr, ComputeOperatorIr)):
                    self._write_column_if_target(
                        operator.field_key,
                        write_row_ids,
                        context,
                        column_sink,
                        batch_num,
                        late_columns=late_columns,
                    )

            returned = self.executor.execute_operators(
                context,
                row_ids,
                runtime=self.runtime,
                required_fields=self._required_fields,
                adaptive_pool=adaptive_pool,
                after_operator=after_operator,
            )
            # 优先用共享 `clock` 时长(含 `main-source` + 嵌套 `writes`).
            emit_durations = clock.stage_durations if wants_spans else returned
            if emit_durations is not None:
                for stage_name, duration in emit_durations.items():
                    if duration > 0:
                        self.runtime.instrumentation.emit_stage_span(stage_name, batch_num, duration)
        finally:
            attach_write_clock(self.runtime, None)

        context.clear()
        return []

    def _write_main_source_columns(
        self,
        row_ids: List[Hashable],
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
            if isinstance(field_spec, FieldIr) and field_spec.source_id == main_source_id:
                self._write_column_if_target(field_key, row_ids, context, column_sink, batch_num)

    def _write_column_if_target(
        self,
        field_key: str,
        row_ids: List[Hashable],
        context: BatchContext,
        column_sink: IColumnSink,
        batch_num: int,
        late_columns: Optional[LateColumnMaterializer] = None,
    ) -> None:
        """如果是目标字段,写入列"""
        if field_key not in self.plan.target_fields:
            return

        is_late = late_columns is not None and late_columns.is_late(field_key)
        if is_late and late_columns is not None:
            # `write-precompute`: 该列此刻才现场物化(未落 `BatchContext`).
            values = late_columns.materialize_column(context, field_key, row_ids)
        else:
            values = [context.get_field_value(field_key, row_id) for row_id in row_ids]

        write_column_aligned = None
        if isinstance(column_sink, SupportsWriteColumnAligned):
            write_column_aligned = column_sink.write_column_aligned
        clock = get_write_clock(self.runtime)
        if write_column_aligned is not None:
            aligned_row_ids = cast("SinkRowKeySeq", row_ids)  # pragma: allow-cast sink row ids typed narrowing
            if clock is not None and clock.enabled:
                with clock.time_write():
                    write_column_aligned(field_key, aligned_row_ids, values)
            else:
                write_column_aligned(field_key, aligned_row_ids, values)
            row_count = len(values)
        else:
            col_data: Dict[Hashable, FieldValue] = dict(zip(row_ids, values))
            if clock is not None and clock.enabled:
                with clock.time_write():
                    column_sink.write_column(field_key, col_data)
            else:
                column_sink.write_column(field_key, col_data)
            row_count = len(col_data)

        if is_late and late_columns is not None:
            late_columns.release_after_write(field_key)

        self.runtime.instrumentation.emit_column_write(
            field_key=field_key,
            row_count=row_count,
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

    def _resolve_streaming_global_ready_target_fields(self) -> Set[str]:
        main_source = self.runtime.main_source
        main_source_id = main_source.source_id if main_source else None

        global_ready_target_fields: Set[str] = set()
        for field_key in self.plan.target_fields:
            field_spec = self.plan.field_specs.get(field_key)
            if field_spec is None:
                global_ready_target_fields.add(field_key)
                continue
            if main_source_id and isinstance(field_spec, FieldIr) and field_spec.source_id == main_source_id:
                global_ready_target_fields.add(field_key)
        return global_ready_target_fields

    def _collect_streaming_rows_binding_barriers(
        self,
    ) -> Tuple[Set[Tuple[Tuple[Any, ...], ...]], Set[str]]:
        rows_binding_relations: Set[Tuple[Tuple[Any, ...], ...]] = set()
        rows_binding_ops: Set[str] = set()

        for operator in self.plan.operators:
            if not isinstance(operator, LoadRefOperatorIr):
                continue
            if not has_rows_binding(operator.lookup_steps, self.runtime.sources):
                continue
            if can_group_by_relation(operator.lookup_steps, self.runtime.sources):
                rows_binding_relations.add(build_relation_signature(operator.lookup_steps, self.runtime.sources))
            else:
                rows_binding_ops.add(operator.operator_id)

        return rows_binding_relations, rows_binding_ops

    def _execute_batch_streaming_mode(
        self,
        row_ids: List[Hashable],
        batch_rows: List[RowData],
        streaming_sink: IRowSink,
        batch_num: int,
        *,
        adaptive_pool: Optional[Executor] = None,
    ) -> List[RowData]:
        """流式模式执行批次(真正的按行流式写出)."""
        self.runtime.sink = streaming_sink
        self.runtime.batch_num = batch_num
        self.runtime.reset_load_ref_cache()
        # `write-precompute`(切片 A): `late` 字段跳过 `compute` 段,在 `write_row` 前逐行物化.
        self.runtime.late_fields = self._late_fields

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
            late_materializer=self._late_materializer,
        )

        on_field_set_fields = coordinator.on_field_set_fields()
        context = create_batch_context_for_rows(
            row_ids,
            required_fields=self._required_fields,
            on_field_set=coordinator.on_field_set,
            on_field_set_fields=on_field_set_fields,
        )
        coordinator.attach_context(context)

        self.executor.prefill_main_source_fields(context, row_ids, batch_rows, required_fields=self._required_fields)
        write_row_ids = self._sort_row_ids_for_write(row_ids, context)
        coordinator.set_write_order(write_row_ids)

        wants_spans, stage_durations, _stage_map = init_stage_span_tracking(self.runtime)
        perf_counter = self._overrides.stage_perf_counter_fn or time.perf_counter
        clock = StageWriteClock(
            enabled=bool(wants_spans),
            stage_durations=stage_durations,
            perf_counter=perf_counter,
        )
        attach_write_clock(self.runtime, clock)
        try:
            coordinator.flush_ready_rows()

            active_row_ids = list(row_ids)

            def after_operator(operator: Any) -> None:
                if isinstance(operator, LoadRefOperatorIr):
                    if operator.operator_id in rows_binding_ops:
                        rows_binding_ops.discard(operator.operator_id)
                    relation_key = build_relation_signature(operator.lookup_steps, self.runtime.sources)
                    if relation_key in rows_binding_relations and relation_key in self.runtime.load_ref_group_executed:
                        rows_binding_relations.discard(relation_key)
                    if not rows_binding_ops and not rows_binding_relations:
                        coordinator.enable_release()

                to_remove = coordinator.drain_rows_to_remove()
                if to_remove:
                    active_row_ids[:] = [rid for rid in active_row_ids if rid not in to_remove]

            returned = self.executor.execute_operators(
                context,
                active_row_ids,
                runtime=self.runtime,
                required_fields=self._required_fields,
                adaptive_pool=adaptive_pool,
                after_operator=after_operator,
            )
            coordinator.finalize()
            emit_durations = clock.stage_durations if wants_spans else returned
            if emit_durations is not None:
                for stage_name, duration in emit_durations.items():
                    if duration > 0:
                        self.runtime.instrumentation.emit_stage_span(stage_name, batch_num, duration)
        finally:
            attach_write_clock(self.runtime, None)

        context.clear()
        return []


__all__ = ("Pipeline", "SeqPipeline")
