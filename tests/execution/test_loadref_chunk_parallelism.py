"""LoadRef `lookup_chunk_size` 分片并行(c30: opt-in + adaptive-only)测试."""

import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Tuple

import pytest

from scalim.events import Event, EventType
from scalim.execution.adaptive.loadref_scheduler import AdaptiveLoadRefScheduler
from scalim.execution.chunk_parallelism import LookupChunkParallelismPolicy
from scalim.execution.context import BatchContext
from scalim.execution.executor.operators.load_ref.executor import LoadRefOperatorExecutor
from scalim.execution.executor.runtime.runtime import ExecutionRuntime
from scalim.execution.pipeline.overrides import PipelineOverrides
from scalim.execution.runtime_bindings import RuntimeBindings
from scalim.ob.manager import ObserverManager
from scalim.ob.observer import Observer
from scalim.planning.operators import LoadRefOperatorIr, OperatorType
from scalim.planning.plan import ExecutionPlan
from scalim.spec.ir import FieldIr, KeyIr, LookupStepIr, SourceIr
from scalim.spec.ir.binding import BindingIr, LoaderIr
from scalim.spec.ir.callable_refs import RuntimeHandleIdIr

from tests.fixtures.executor_operator_fixtures import _make_main_source, _make_runtime

CI_TIMEOUT_S = 20.0


class _CaptureLoaderCallObserver(Observer):
    event_types = {EventType.LOADER_CALL}

    def __init__(self) -> None:
        self.events: List[Event] = []
        self._lock = threading.Lock()

    def on_event(self, event: Event) -> None:
        with self._lock:
            self.events.append(event)


class _Scenario(object):
    def __init__(
        self,
        runtime: ExecutionRuntime,
        operator: LoadRefOperatorIr,
        plan: ExecutionPlan,
        context: BatchContext,
        row_ids: List[int],
    ) -> None:
        self.runtime = runtime
        self.operator = operator
        self.plan = plan
        self.context = context
        self.row_ids = row_ids

    def execute(self) -> None:
        LoadRefOperatorExecutor().execute(self.operator, self.context, self.row_ids, self.runtime)

    def field_values(self) -> Dict[int, Any]:
        return {row_id: self.context.get_field_value("target_name", row_id) for row_id in self.row_ids}


def _keys_params_builder(ctx):  # type: ignore[no-untyped-def]
    return (), {"ids": list(ctx.lookup_keys_list or [])}


def _rows_params_builder(ctx):  # type: ignore[no-untyped-def]
    return (), {"rows": list(ctx.batch_rows or [])}


def _build_scenario(
    *,
    loader,  # type: ignore[no-untyped-def]
    chunk_size: Optional[int] = 2,
    row_count: int = 6,
    parallel_mode: str = "seq",
    parallelize_lookup_chunks: bool = False,
    max_workers: int = 0,
    max_chunk_workers: Optional[int] = None,
    binding_kwargs: Optional[Dict[str, Any]] = None,
    observer_manager: Optional[ObserverManager] = None,
) -> _Scenario:
    runtime_bindings = RuntimeBindings()
    runtime_bindings.source_loaders["targets"] = loader

    resolved_binding_kwargs = dict(binding_kwargs or {})
    is_rows_mode = resolved_binding_kwargs.get("mode") == "rows"
    runtime_bindings.params_builders[("targets", "target_id")] = _rows_params_builder if is_rows_mode else _keys_params_builder

    target_source = SourceIr(
        source_id="targets",
        key=KeyIr(key="target_id"),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr("source_loader:targets")),
        lookup_chunk_size=chunk_size,
    )
    field_spec = FieldIr(field_id="target_name", name="Target", source=target_source, data_key="name")
    binding = BindingIr(
        key_field="target_id",
        params_builder_ref=RuntimeHandleIdIr("params_builder:targets:target_id"),
        **resolved_binding_kwargs,
    )
    steps = (LookupStepIr(from_field="fk_id", to_source=target_source, bind=binding),)
    operator = LoadRefOperatorIr(
        operator_id="load_ref",
        operator_type=OperatorType.LOAD_REF.value,
        source_id="targets",
        field_key="target_name",
        lookup_steps=steps,
    )
    plan = ExecutionPlan(field_specs={"target_name": field_spec}, operators=(operator,))
    runtime = _make_runtime(
        plan,
        _make_main_source(),
        observer_manager=observer_manager,
        runtime_bindings=runtime_bindings,
        parallel_mode=parallel_mode,
        max_workers=max_workers,
        parallelize_lookup_chunks=parallelize_lookup_chunks,
        max_chunk_workers=max_chunk_workers,
    )

    context = BatchContext()
    row_ids = list(range(1, row_count + 1))
    for row_id in row_ids:
        context.set_field_value("fk_id", row_id, row_id)
    return _Scenario(runtime, operator, plan, context, row_ids)


class _RecordingLoader(object):
    """记录每次分片调用的键与调用线程(用于区分串行/并行)."""

    def __init__(self) -> None:
        self.calls: List[List[int]] = []
        self.threads: List[str] = []
        self.cache_sizes: List[int] = []
        self._lock = threading.Lock()
        self.runtime: Optional[ExecutionRuntime] = None

    def __call__(self, ids: List[int]) -> Dict[int, Dict[str, Any]]:
        with self._lock:
            self.calls.append(list(ids))
            self.threads.append(threading.current_thread().name)
            if self.runtime is not None:
                self.cache_sizes.append(len(self.runtime.load_ref_cache))
        return {key: {"name": "Name{}".format(key)} for key in ids}


def _expected_values(row_ids: List[int]) -> Dict[int, str]:
    return {row_id: "Name{}".format(row_id) for row_id in row_ids}


def test_seq_with_opt_in_never_parallelizes_chunks() -> None:
    loader = _RecordingLoader()
    scenario = _build_scenario(loader=loader, parallel_mode="seq", parallelize_lookup_chunks=True, max_workers=4)

    assert scenario.runtime.is_chunk_parallelism_enabled() is False
    assert scenario.runtime.chunk_inflight_semaphore is None
    assert scenario.runtime.resolve_chunk_fanout(3) == 1

    scenario.execute()

    assert loader.calls == [[1, 2], [3, 4], [5, 6]]
    assert set(loader.threads) == {threading.current_thread().name}
    assert scenario.field_values() == _expected_values(scenario.row_ids)


def test_adaptive_without_opt_in_stays_serial() -> None:
    loader = _RecordingLoader()
    scenario = _build_scenario(loader=loader, parallel_mode="adaptive", max_workers=4)

    assert scenario.runtime.is_chunk_parallelism_enabled() is False
    assert scenario.runtime.chunk_inflight_semaphore is None

    scenario.execute()

    assert loader.calls == [[1, 2], [3, 4], [5, 6]]
    assert set(loader.threads) == {threading.current_thread().name}


def test_lookup_chunk_size_alone_is_not_a_parallel_switch() -> None:
    loader = _RecordingLoader()
    scenario = _build_scenario(loader=loader, chunk_size=2, parallel_mode="adaptive", max_workers=4)

    scenario.execute()

    assert len(loader.calls) == 3
    assert set(loader.threads) == {threading.current_thread().name}


def test_adaptive_opt_in_merge_equals_serial() -> None:
    serial_loader = _RecordingLoader()
    serial = _build_scenario(loader=serial_loader, parallel_mode="seq")
    serial.execute()

    parallel_loader = _RecordingLoader()
    parallel = _build_scenario(
        loader=parallel_loader,
        parallel_mode="adaptive",
        parallelize_lookup_chunks=True,
        max_workers=3,
    )
    assert parallel.runtime.is_chunk_parallelism_enabled() is True
    parallel.execute()

    assert parallel.field_values() == serial.field_values()
    # 调用次数与串行分片一致(= 分片数),只是等待被重叠.
    assert len(parallel_loader.calls) == len(serial_loader.calls) == 3
    assert sorted(parallel_loader.calls) == sorted(serial_loader.calls)
    assert parallel_loader.threads != [threading.current_thread().name] * 3


def test_chunk_merge_is_first_wins_by_offset_even_when_completion_order_reverses() -> None:
    late_chunk_done = threading.Event()
    calls: List[List[int]] = []
    lock = threading.Lock()

    def _loader(ids: List[int]) -> Dict[int, Dict[str, Any]]:
        with lock:
            calls.append(list(ids))
        result: Dict[int, Dict[str, Any]] = {key: {"name": "Name{}".format(key)} for key in ids}
        if 1 in ids:
            # 第一个分片(offset=0)最后完成:合并顺序仍须按 offset 升序.
            assert late_chunk_done.wait(timeout=CI_TIMEOUT_S) is True
            return result
        if 5 in ids:
            # 最后一个分片对 offset=0 已返回的 `key` 给出冲突值.
            result[1] = {"name": "LateConflict"}
            late_chunk_done.set()
        return result

    scenario = _build_scenario(
        loader=_loader,
        parallel_mode="adaptive",
        parallelize_lookup_chunks=True,
        max_workers=3,
    )
    scenario.execute()

    assert len(calls) == 3
    # 先写入者胜(offset 较小的分片): 与串行 `for-loop` 完全一致.
    assert scenario.context.get_field_value("target_name", 1) == "Name1"
    assert scenario.field_values() == _expected_values(scenario.row_ids)


def test_inflight_loader_calls_are_capped_by_resolved_workers() -> None:
    barrier = threading.Barrier(2)
    lock = threading.Lock()
    state = {"inflight": 0, "max_inflight": 0, "calls": 0}

    def _loader(ids: List[int]) -> Dict[int, Dict[str, Any]]:
        with lock:
            state["inflight"] += 1
            state["calls"] += 1
            state["max_inflight"] = max(state["max_inflight"], state["inflight"])
        try:
            # 帽为 2: 每次恰好 2 个分片在途;若退化为串行则此处会超时失败.
            barrier.wait(timeout=CI_TIMEOUT_S)
        finally:
            with lock:
                state["inflight"] -= 1
        return {key: {"name": "Name{}".format(key)} for key in ids}

    scenario = _build_scenario(
        loader=_loader,
        row_count=8,
        parallel_mode="adaptive",
        parallelize_lookup_chunks=True,
        max_workers=2,
    )

    assert scenario.runtime.chunk_inflight_capacity == 2
    assert scenario.runtime.resolve_chunk_fanout(4) == 2

    scenario.execute()

    assert state["calls"] == 4
    assert state["max_inflight"] == 2
    assert scenario.field_values() == _expected_values(scenario.row_ids)


def test_max_chunk_workers_limits_step_fanout() -> None:
    loader = _RecordingLoader()
    scenario = _build_scenario(
        loader=loader,
        row_count=8,
        parallel_mode="adaptive",
        parallelize_lookup_chunks=True,
        max_workers=8,
        max_chunk_workers=2,
    )

    assert scenario.runtime.chunk_inflight_capacity == 8
    assert scenario.runtime.resolve_chunk_fanout(4) == 2
    assert scenario.runtime.resolve_chunk_fanout(1) == 1

    scenario.execute()

    assert len(loader.calls) == 4
    assert scenario.field_values() == _expected_values(scenario.row_ids)


def test_rows_binding_never_chunks_even_with_opt_in() -> None:
    calls: List[int] = []

    def _loader(rows: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
        calls.append(len(rows))
        return {int(row["fk_id"]): {"name": "Name{}".format(row["fk_id"])} for row in rows}

    scenario = _build_scenario(
        loader=_loader,
        parallel_mode="adaptive",
        parallelize_lookup_chunks=True,
        max_workers=4,
        binding_kwargs={"mode": "rows", "cache_mode": "batch"},
    )
    scenario.execute()

    assert calls == [6]
    assert scenario.field_values() == _expected_values(scenario.row_ids)


def test_load_ref_cache_is_written_once_after_merge() -> None:
    loader = _RecordingLoader()
    scenario = _build_scenario(
        loader=loader,
        parallel_mode="adaptive",
        parallelize_lookup_chunks=True,
        max_workers=3,
    )
    loader.runtime = scenario.runtime

    scenario.execute()

    # 分片期间不得写入批次缓存.
    assert loader.cache_sizes == [0, 0, 0]
    assert len(scenario.runtime.load_ref_cache) == 1
    cached_entry = list(scenario.runtime.load_ref_cache.values())[0]
    assert dict(cached_entry.result) == {row_id: {"name": "Name{}".format(row_id)} for row_id in scenario.row_ids}


def test_chunk_loader_call_events_carry_chunk_offset() -> None:
    observer = _CaptureLoaderCallObserver()
    loader = _RecordingLoader()
    scenario = _build_scenario(
        loader=loader,
        parallel_mode="adaptive",
        parallelize_lookup_chunks=True,
        max_workers=3,
        observer_manager=ObserverManager(observers=[observer]),
    )
    scenario.execute()

    assert len(observer.events) == 3
    # 完成序不保证;`chunk_offset` 保证可重建串行观感.
    assert sorted(event.payload.chunk_offset for event in observer.events) == [0, 2, 4]
    assert {event.payload.lookup_key_count for event in observer.events} == {2}


def test_serial_chunk_loader_call_events_also_carry_chunk_offset() -> None:
    observer = _CaptureLoaderCallObserver()
    loader = _RecordingLoader()
    scenario = _build_scenario(
        loader=loader,
        parallel_mode="seq",
        observer_manager=ObserverManager(observers=[observer]),
    )
    scenario.execute()

    assert [event.payload.chunk_offset for event in observer.events] == [0, 2, 4]


def test_chunk_failure_propagates_and_skips_cache_write() -> None:
    def _loader(ids: List[int]) -> Dict[int, Dict[str, Any]]:
        if 3 in ids:
            msg = "chunk boom"
            raise ValueError(msg)
        return {key: {"name": "Name{}".format(key)} for key in ids}

    serial = _build_scenario(loader=_loader, parallel_mode="seq")
    with pytest.raises(ValueError, match="chunk boom"):
        serial.execute()
    assert serial.runtime.load_ref_cache == {}

    parallel = _build_scenario(
        loader=_loader,
        parallel_mode="adaptive",
        parallelize_lookup_chunks=True,
        max_workers=3,
    )
    with pytest.raises(ValueError, match="chunk boom"):
        parallel.execute()
    # 不得把半份 merged 当成功写入缓存.
    assert parallel.runtime.load_ref_cache == {}


def test_preload_hit_skips_ref_loader_with_chunk_opt_in() -> None:
    def _loader(ids: List[int]) -> Dict[int, Dict[str, Any]]:
        msg = "ref loader must not be called when preload cache hits"
        raise AssertionError(msg)

    scenario = _build_scenario(
        loader=_loader,
        parallel_mode="adaptive",
        parallelize_lookup_chunks=True,
        max_workers=3,
    )
    scenario.runtime.preloaded_cache["targets"] = {row_id: {"name": "Name{}".format(row_id)} for row_id in scenario.row_ids}

    scenario.execute()

    assert scenario.field_values() == _expected_values(scenario.row_ids)
    assert scenario.runtime.load_ref_cache == {}


def test_adaptive_task_runtime_inherits_run_scope_and_shares_inflight_cap() -> None:
    parent = _build_scenario(
        loader=_RecordingLoader(),
        parallel_mode="adaptive",
        parallelize_lookup_chunks=True,
        max_workers=2,
    ).runtime
    child = ExecutionRuntime(
        plan=ExecutionPlan(),
        hook_manager=parent.hook_manager,
        observer_manager=parent.observer_manager,
        main_source=parent.main_source,
        sources={},
        runtime_bindings=parent.runtime_bindings,
        parallel_mode="seq",
        max_workers=0,
    )

    assert child.is_chunk_parallelism_enabled() is False
    child.inherit_chunk_parallelism(parent)

    assert child.parallel_mode == "seq"
    assert child.run_parallel_mode == "adaptive"
    assert child.is_chunk_parallelism_enabled() is True
    assert child.chunk_inflight_capacity == 2
    assert child.chunk_inflight_semaphore is parent.chunk_inflight_semaphore


def test_chunk_parallelism_policy_rejects_invalid_max_chunk_workers() -> None:
    with pytest.raises(ValueError, match="max_chunk_workers must be >= 1"):
        _ = LookupChunkParallelismPolicy(parallelize_lookup_chunks=True, max_chunk_workers=0)
    with pytest.raises(TypeError, match="max_chunk_workers must be an int"):
        _ = LookupChunkParallelismPolicy(max_chunk_workers="2")  # type: ignore[arg-type]


def _build_two_source_plan(
    runtime_bindings: RuntimeBindings,
    *,
    chunked_loader,  # type: ignore[no-untyped-def]
    plain_loader,  # type: ignore[no-untyped-def]
) -> Tuple[ExecutionPlan, LoadRefOperatorIr, LoadRefOperatorIr]:
    operators: List[LoadRefOperatorIr] = []
    field_specs: Dict[str, FieldIr] = {}
    for source_id, field_key, loader, chunk_size in (
        ("chunked", "chunked_name", chunked_loader, 2),
        ("plain", "plain_name", plain_loader, None),
    ):
        runtime_bindings.source_loaders[source_id] = loader
        runtime_bindings.params_builders[(source_id, "target_id")] = _keys_params_builder
        source = SourceIr(
            source_id=source_id,
            key=KeyIr(key="target_id"),
            loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr("source_loader:{}".format(source_id))),
            lookup_chunk_size=chunk_size,
        )
        binding = BindingIr(
            key_field="target_id",
            params_builder_ref=RuntimeHandleIdIr("params_builder:{}:target_id".format(source_id)),
        )
        field_specs[field_key] = FieldIr(field_id=field_key, name=field_key, source=source, data_key="name")
        operators.append(
            LoadRefOperatorIr(
                operator_id="load_ref_{}".format(field_key),
                operator_type=OperatorType.LOAD_REF.value,
                source_id=source_id,
                field_key=field_key,
                lookup_steps=(LookupStepIr(from_field="fk_id", to_source=source, bind=binding),),
            )
        )
    plan = ExecutionPlan(field_specs=field_specs, operators=tuple(operators))
    return plan, operators[0], operators[1]


def test_chunks_parallelize_inside_adaptive_worker_task_without_pool_deadlock() -> None:
    """`adaptive` 工作线程内的分片并行:运行级范围被继承,且独立池不会与 `adaptive` 池互相等待."""
    # `barrier` 只被 `chunked` 源的分片调用触及: 只有「同一 LoadRef 任务内的两个分片并发」才能凑齐.
    barrier = threading.Barrier(2)
    lock = threading.Lock()
    state = {"inflight": 0, "max_inflight": 0, "calls": 0}

    def _chunked_loader(ids: List[int]) -> Dict[int, Dict[str, Any]]:
        with lock:
            state["inflight"] += 1
            state["calls"] += 1
            state["max_inflight"] = max(state["max_inflight"], state["inflight"])
        try:
            assert barrier.wait(timeout=CI_TIMEOUT_S) is not None
        finally:
            with lock:
                state["inflight"] -= 1
        return {key: {"name": "Name{}".format(key)} for key in ids}

    def _plain_loader(ids: List[int]) -> Dict[int, Dict[str, Any]]:
        return {key: {"name": "Plain{}".format(key)} for key in ids}

    runtime_bindings = RuntimeBindings()
    plan, chunked_op, plain_op = _build_two_source_plan(
        runtime_bindings,
        chunked_loader=_chunked_loader,
        plain_loader=_plain_loader,
    )
    runtime = _make_runtime(
        plan,
        _make_main_source(),
        runtime_bindings=runtime_bindings,
        parallel_mode="adaptive",
        max_workers=2,
        parallelize_lookup_chunks=True,
    )
    context = BatchContext()
    row_ids = list(range(1, 9))
    for row_id in row_ids:
        context.set_field_value("fk_id", row_id, row_id)

    scheduler = AdaptiveLoadRefScheduler(plan, overrides=PipelineOverrides())
    with ThreadPoolExecutor(max_workers=2) as pool:
        scheduler.execute_segment(
            [chunked_op, plain_op],
            context=context,
            batch_row_nth=row_ids,
            runtime=runtime,
            pool=pool,
            max_workers=2,
            required_fields=None,
            after_operator=None,
        )

    assert state["calls"] == 4
    assert state["max_inflight"] == 2
    assert {row_id: context.get_field_value("chunked_name", row_id) for row_id in row_ids} == _expected_values(row_ids)
    assert context.get_field_value("plain_name", 1) == "Plain1"
