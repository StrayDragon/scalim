import contextlib
import logging
import time
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Callable, List, Optional, Tuple, cast

from .....events import EventType
from .....spec.ir import LookupStepIr
from .....spec.ir._helpers import coerce_loader_result_mapping
from .....spec.ir._source_contracts import LookupSourceRefIrBase
from .....spec.ir.binding import BindingIr, LoaderCallContextIr, build_stable_lookup_key_list
from .....typedefs import LoaderCallKwargs, LoaderResultMap, LoaderResultMapping, LookupKeyList, LookupKeySet, RowData, RuntimeValue
from .....utils.relation_signature import LoadRefCacheKey, build_step_signature, normalize_key_field
from .....vendor.compact.typing_extensionsx import Protocol
from .....vendor.dataclassesx import dataclass
from ....loader_call_params import build_loader_call_params
from ....loader_retry import CALLSITE_LOAD_REF, call_with_loader_retry
from ...guardrails import build_loader_result_guardrail_payload, fail_guardrail
from ...runtime.runtime import ExecutionRuntime, LoadRefCacheEntry
from .context import LoadRefExecutionContext

if TYPE_CHECKING:
    from concurrent.futures import Future

# 模块级日志记录器
_logger = logging.getLogger(__name__.rsplit(".", 1)[0])


class _LoaderResultWithNormalizeStats(Protocol):
    skipped_none_rows: int


def build_ref_loader_context(
    exec_ctx: LoadRefExecutionContext,
    source_id: str,
    event_field_keys: Tuple[str, ...],
    batch_rows: Optional[List[RowData]],
    lookup_keys_set: LookupKeySet,
    lookup_keys_list: LookupKeyList,
) -> LoaderCallContextIr:
    return LoaderCallContextIr(
        batch_row_nth=exec_ctx.batch_row_nth,
        source_id=source_id,
        field_keys=list(event_field_keys),
        is_ref_loader=True,
        lookup_keys=lookup_keys_set,
        lookup_keys_list=lookup_keys_list,
        batch_rows=batch_rows,
    )


def _trigger_ref_loader_call(
    runtime: ExecutionRuntime,
    source_id: str,
    binding: Optional[BindingIr],
    loader_context: LoaderCallContextIr,
    result: RuntimeValue,
    duration: float,
    *,
    cache_enabled: bool,
    lookup_key_count: int,
    event_field_keys: Tuple[str, ...],
    cache_status: Optional[str],
    chunk_offset: Optional[int] = None,
) -> None:
    if not runtime.instrumentation.wants(EventType.LOADER_CALL):
        return
    call_kwargs: LoaderCallKwargs = {}
    if binding:
        _, call_kwargs = build_loader_call_params(
            binding=binding,
            context=loader_context,
            runtime_bindings=runtime.runtime_bindings,
        )
    result_obj: RuntimeValue = result
    skipped_none_rows: Optional[int] = None
    with contextlib.suppress(AttributeError):
        skipped_none_rows = cast(
            "_LoaderResultWithNormalizeStats", result_obj
        ).skipped_none_rows  # pragma: allow-cast normalize stats payload
    runtime.instrumentation.emit_loader_call(
        loader_name=source_id,
        params=call_kwargs,
        result=result,
        duration=duration,
        batch_num=runtime.batch_num,
        cache_status=cache_status if cache_enabled else None,
        cache_scope="batch" if cache_enabled else None,
        lookup_key_count=lookup_key_count,
        field_keys=list(event_field_keys),
        skipped_none_rows=skipped_none_rows,
        chunk_offset=chunk_offset,
    )


def _call_with_inflight_cap(runtime: ExecutionRuntime, call: Callable[[], RuntimeValue]) -> RuntimeValue:
    """在启用分片并行时,让所有 `ref-loader` 调用共享全局在途帽(容量 = `W`).

    说明:
    - 未启用分片并行(信号量为 `None`)时零开销,行为与改前一致.
    - 持有槽位期间**不会**再等待其它分片 `future`(等待发生在未持槽的父线程),因此不存在同帽嵌套死锁.
    """
    semaphore = runtime.chunk_inflight_semaphore
    if semaphore is None:
        return call()
    _ = semaphore.acquire()
    try:
        return call()
    finally:
        semaphore.release()


def _call_ref_loader(
    *,
    runtime: ExecutionRuntime,
    source: LookupSourceRefIrBase,
    binding: Optional[BindingIr],
    loader_context: LoaderCallContextIr,
    cache_enabled: bool,
    lookup_key_count: int,
    event_field_keys: Tuple[str, ...],
    cache_status: str,
    chunk_offset: Optional[int] = None,
) -> LoaderResultMapping:
    loader_fn = runtime.runtime_bindings.require_source_loader(source.source_id)

    def _call_loader() -> RuntimeValue:
        args, kwargs = build_loader_call_params(
            binding=binding,
            context=loader_context,
            runtime_bindings=runtime.runtime_bindings,
        )
        return loader_fn(*args, **kwargs)

    def _call_loader_with_retry() -> RuntimeValue:
        return call_with_loader_retry(
            call=_call_loader,
            instrumentation=runtime.instrumentation,
            policy=policy,
            loader_name=source.source_id,
            callsite=CALLSITE_LOAD_REF,
            batch_num=runtime.batch_num,
        )

    loader_start = time.perf_counter()
    policy = runtime.loader_retry.resolve(source.source_id)
    result_raw: RuntimeValue = _call_with_inflight_cap(runtime, _call_loader_with_retry)
    loader_duration = time.perf_counter() - loader_start

    result_obj: RuntimeValue = result_raw
    normalize_spec = source.normalize
    if normalize_spec is not None:
        normalize_call_by = runtime.runtime_bindings.get_source_normalize_call_by(source.source_id)
        result_obj = normalize_spec.apply(result_raw, source_id=source.source_id, call_by=normalize_call_by)

    result_mapping = coerce_loader_result_mapping(result_obj)
    _trigger_ref_loader_call(
        runtime=runtime,
        source_id=source.source_id,
        binding=binding,
        loader_context=loader_context,
        result=result_mapping,
        duration=loader_duration,
        cache_enabled=cache_enabled,
        lookup_key_count=lookup_key_count,
        event_field_keys=event_field_keys,
        cache_status=cache_status,
        chunk_offset=chunk_offset,
    )
    guardrails = runtime.guardrails
    if guardrails.enabled and guardrails.loader.validate_result and not isinstance(result_obj, Mapping):
        fail_guardrail(
            runtime,
            code="loader_result_not_mapping",
            message="Loader result must be a Mapping",
            context=build_loader_result_guardrail_payload(runtime, source_id=source.source_id, result=result_obj, is_ref_loader=True),
            action_mode="fast_fail",
        )
    return result_mapping


def _get_cached_ref_result(
    runtime: ExecutionRuntime,
    cache_key: LoadRefCacheKey,
    binding: Optional[BindingIr],
    loader_context: LoaderCallContextIr,
    lookup_key_count: int,
    event_field_keys: Tuple[str, ...],
    source_id: str,
) -> Optional[LoaderResultMapping]:
    cached_entry = runtime.load_ref_cache.get(cache_key)
    if cached_entry is None:
        return None
    cached_context = loader_context
    if cached_entry.batch_rows is not None:
        cached_context = LoaderCallContextIr(
            batch_row_nth=loader_context.batch_row_nth,
            source_id=loader_context.source_id,
            field_keys=loader_context.field_keys,
            is_ref_loader=loader_context.is_ref_loader,
            lookup_keys=loader_context.lookup_keys,
            lookup_keys_list=loader_context.lookup_keys_list,
            batch_rows=cached_entry.batch_rows,
        )
    _trigger_ref_loader_call(
        runtime=runtime,
        source_id=source_id,
        binding=binding,
        loader_context=cached_context,
        result=cached_entry.result,
        duration=0.0,
        cache_enabled=True,
        lookup_key_count=lookup_key_count,
        event_field_keys=event_field_keys,
        cache_status="hit",
    )
    return cached_entry.result


def _resolve_lookup_chunk_size(
    source: LookupSourceRefIrBase,
    *,
    cache_enabled: bool,
    lookup_key_count: int,
    binding: Optional[BindingIr],
) -> Optional[int]:
    if not cache_enabled:
        return None
    if binding is not None and binding.mode == "rows":
        return None
    chunk_size = source.lookup_chunk_size
    if chunk_size is None or chunk_size <= 0 or chunk_size >= lookup_key_count:
        return None
    return chunk_size


def _load_ref_once(
    runtime: ExecutionRuntime,
    source: LookupSourceRefIrBase,
    binding: Optional[BindingIr],
    loader_context: LoaderCallContextIr,
    *,
    cache_enabled: bool,
    lookup_key_count: int,
    event_field_keys: Tuple[str, ...],
    cache_key: Optional[LoadRefCacheKey],
) -> LoaderResultMapping:
    result = _call_ref_loader(
        runtime=runtime,
        source=source,
        binding=binding,
        loader_context=loader_context,
        cache_enabled=cache_enabled,
        lookup_key_count=lookup_key_count,
        event_field_keys=event_field_keys,
        cache_status="miss",
    )
    if cache_enabled and cache_key is not None:
        cached_batch_rows = loader_context.batch_rows
        if binding is not None and binding.mode == "rows":
            # 避免将可能很大的 `batch_rows` 列表保存在长生命周期 `cache` 中.
            cached_batch_rows = None
        # `NOTE:` `load_ref_cache` 在 `parallel_mode="adaptive"` 下会被多个工作线程读写.
        # `NOTE:` 并发下此处写入可能导致重复 `loader` 调用或覆盖写入(取决于调度/命中时序),但在 `CPython`+`GIL` 下通常不应导致崩溃.
        # `WARN:` `free-threaded`/`no-GIL` 的 `Python` 不在支持范围内;若要支持,必须为该共享 `dict` 引入锁或线程安全容器.
        runtime.load_ref_cache[cache_key] = LoadRefCacheEntry(
            result=result,
            batch_rows=cached_batch_rows,
        )
    return result


@dataclass(frozen=True)
class _ChunkPlan:
    """单个 `lookup_chunk_size` 分片的调用计划(`loader_context` 在父线程预先构造)."""

    offset: int
    lookup_key_count: int
    loader_context: LoaderCallContextIr


def _chunk_count(n_keys: int, chunk_size: int) -> int:
    # `n_keys == 0` 时整除结果亦为 0,无需单独分支.
    return (n_keys + chunk_size - 1) // chunk_size


def _build_one_chunk_plan(
    *,
    exec_ctx: LoadRefExecutionContext,
    source: LookupSourceRefIrBase,
    event_field_keys: Tuple[str, ...],
    lookup_keys_list: LookupKeyList,
    batch_rows: Optional[List[RowData]],
    chunk_size: int,
    offset: int,
) -> _ChunkPlan:
    chunk_list = lookup_keys_list[offset : offset + chunk_size]
    chunk_set = set(chunk_list)
    return _ChunkPlan(
        offset=offset,
        lookup_key_count=len(chunk_set),
        loader_context=build_ref_loader_context(
            exec_ctx,
            source.source_id,
            event_field_keys,
            batch_rows,
            chunk_set,
            chunk_list,
        ),
    )


def _build_chunk_plans(
    *,
    exec_ctx: LoadRefExecutionContext,
    source: LookupSourceRefIrBase,
    event_field_keys: Tuple[str, ...],
    lookup_keys_list: LookupKeyList,
    batch_rows: Optional[List[RowData]],
    chunk_size: int,
) -> List[_ChunkPlan]:
    """仅并行路径使用:提交 `futures` 前需要全部 `plan` 已构造."""
    plans: List[_ChunkPlan] = []
    for offset in range(0, len(lookup_keys_list), chunk_size):
        plans.append(
            _build_one_chunk_plan(
                exec_ctx=exec_ctx,
                source=source,
                event_field_keys=event_field_keys,
                lookup_keys_list=lookup_keys_list,
                batch_rows=batch_rows,
                chunk_size=chunk_size,
                offset=offset,
            )
        )
    return plans


def _load_one_chunk(
    *,
    runtime: ExecutionRuntime,
    source: LookupSourceRefIrBase,
    binding: Optional[BindingIr],
    event_field_keys: Tuple[str, ...],
    plan: _ChunkPlan,
) -> LoaderResultMapping:
    return _call_ref_loader(
        runtime=runtime,
        source=source,
        binding=binding,
        loader_context=plan.loader_context,
        cache_enabled=True,
        lookup_key_count=plan.lookup_key_count,
        event_field_keys=event_field_keys,
        cache_status="miss",
        chunk_offset=plan.offset,
    )


def _merge_chunk_result(merged: LoaderResultMap, result: LoaderResultMapping) -> None:
    # 先写入者胜: 与串行分片 `for-loop` 完全一致(见 `ir-source-relations` `r694`).
    for key, value in result.items():
        if key not in merged:
            merged[key] = value


def _load_chunks_serially(
    *,
    exec_ctx: LoadRefExecutionContext,
    runtime: ExecutionRuntime,
    source: LookupSourceRefIrBase,
    binding: Optional[BindingIr],
    event_field_keys: Tuple[str, ...],
    lookup_keys_list: LookupKeyList,
    batch_rows: Optional[List[RowData]],
    chunk_size: int,
) -> LoaderResultMap:
    """默认/未扇出路径:按 `offset` 懒建单个 `plan`,避免一次性物化全部分片上下文."""
    merged: LoaderResultMap = {}
    for offset in range(0, len(lookup_keys_list), chunk_size):
        plan = _build_one_chunk_plan(
            exec_ctx=exec_ctx,
            source=source,
            event_field_keys=event_field_keys,
            lookup_keys_list=lookup_keys_list,
            batch_rows=batch_rows,
            chunk_size=chunk_size,
            offset=offset,
        )
        result = _load_one_chunk(
            runtime=runtime,
            source=source,
            binding=binding,
            event_field_keys=event_field_keys,
            plan=plan,
        )
        _merge_chunk_result(merged, result)
    return merged


def _load_chunks_in_parallel(
    *,
    runtime: ExecutionRuntime,
    source: LookupSourceRefIrBase,
    binding: Optional[BindingIr],
    event_field_keys: Tuple[str, ...],
    plans: List[_ChunkPlan],
    fanout: int,
) -> LoaderResultMap:
    """`opt-in` 分片并行:独立小池扇出 + 全局在途帽;合并顺序仍按 `offset` 升序."""
    merged: LoaderResultMap = {}
    executor = ThreadPoolExecutor(max_workers=fanout)
    try:
        futures: List[Tuple[_ChunkPlan, "Future[LoaderResultMapping]"]] = [
            (
                plan,
                executor.submit(
                    _load_one_chunk,
                    runtime=runtime,
                    source=source,
                    binding=binding,
                    event_field_keys=event_field_keys,
                    plan=plan,
                ),
            )
            for plan in plans
        ]
        try:
            # 按 `offset` 升序取结果并即时 `merge`:失败时抛出「串行会最先遇到」的异常,
            # 且不把全部 `chunk` `dict` 同时挂在 `results_by_offset` 上抬高峰值.
            for _plan, future in futures:
                result = future.result()
                _merge_chunk_result(merged, result)
        finally:
            # 尽力取消未开始的分片(已在跑的线程无法强杀,与 `adaptive` 池 `shutdown` 语义一致).
            for _plan, pending in futures:
                _ = pending.cancel()
    finally:
        executor.shutdown(wait=True)
    return merged


def _load_ref_chunked(
    *,
    exec_ctx: LoadRefExecutionContext,
    source: LookupSourceRefIrBase,
    binding: Optional[BindingIr],
    runtime: ExecutionRuntime,
    event_field_keys: Tuple[str, ...],
    lookup_keys_list: LookupKeyList,
    batch_rows: Optional[List[RowData]],
    chunk_size: int,
    cache_key: Optional[LoadRefCacheKey],
) -> LoaderResultMap:
    fanout = runtime.resolve_chunk_fanout(_chunk_count(len(lookup_keys_list), chunk_size))
    source_parallel = getattr(
        source, "lookup_chunk_parallel", None
    )  # pragma: allow-dynattr optional-interface: LookupSourceRefIrBase.lookup_chunk_parallel
    if source_parallel is False:
        fanout = 1
    if fanout > 1:
        # 仅并行路径一次性构造全部 `plan`(提交 `futures` 需要);串行保持懒建.
        plans = _build_chunk_plans(
            exec_ctx=exec_ctx,
            source=source,
            event_field_keys=event_field_keys,
            lookup_keys_list=lookup_keys_list,
            batch_rows=batch_rows,
            chunk_size=chunk_size,
        )
        merged = _load_chunks_in_parallel(
            runtime=runtime,
            source=source,
            binding=binding,
            event_field_keys=event_field_keys,
            plans=plans,
            fanout=fanout,
        )
    else:
        merged = _load_chunks_serially(
            exec_ctx=exec_ctx,
            runtime=runtime,
            source=source,
            binding=binding,
            event_field_keys=event_field_keys,
            lookup_keys_list=lookup_keys_list,
            batch_rows=batch_rows,
            chunk_size=chunk_size,
        )

    # 分片期间不写 `load_ref_cache`;全部合并完成后至多写一次(异常时不写半份).
    if cache_key is not None:
        runtime.load_ref_cache[cache_key] = LoadRefCacheEntry(
            result=merged,
            batch_rows=batch_rows,
        )
    return merged


def load_step_data(
    *,
    exec_ctx: LoadRefExecutionContext,
    step: LookupStepIr,
    lookup_keys: LookupKeySet,
    is_final_step: bool,
    group_field_keys: Tuple[str, ...],
) -> LoaderResultMapping:
    runtime = exec_ctx.runtime
    source = runtime.resolve_lookup_source(step)

    if runtime.is_source_cached(source.source_id):
        return runtime.get_cached_source_mapping(step)

    to_key = step.get_to_key_or_source_key()
    binding_key = normalize_key_field(to_key)

    lookup_keys_list = build_stable_lookup_key_list(lookup_keys)
    lookup_keys_set = lookup_keys

    binding = step.bind or source.get_binding(binding_key)
    cache_enabled = False
    if binding is not None and (binding.mode == "keys" or (binding.mode == "rows" and binding.cache_mode == "batch")):
        cache_enabled = True

    batch_rows: Optional[List[RowData]] = None
    event_field_keys = group_field_keys if is_final_step else (exec_ctx.field_key,)
    loader_context = build_ref_loader_context(
        exec_ctx,
        source.source_id,
        event_field_keys,
        batch_rows,
        lookup_keys_set,
        lookup_keys_list,
    )

    cache_key = None
    if cache_enabled:
        lookup_keys_fingerprint = frozenset(lookup_keys_set)
        cache_key = (build_step_signature(step), lookup_keys_fingerprint)
        cached = _get_cached_ref_result(
            runtime=runtime,
            cache_key=cache_key,
            binding=binding,
            loader_context=loader_context,
            lookup_key_count=len(lookup_keys_set),
            event_field_keys=event_field_keys,
            source_id=source.source_id,
        )
        if cached is not None:
            return cached

    if binding is not None and binding.mode == "rows":
        batch_rows = exec_ctx.build_batch_rows()
        loader_context = build_ref_loader_context(
            exec_ctx,
            source.source_id,
            event_field_keys,
            batch_rows,
            lookup_keys_set,
            lookup_keys_list,
        )
        if cache_enabled and exec_ctx.relation_signature not in runtime.rows_cache_logged:
            _logger.info(
                (
                    "已启用 `LoadRef` 的 `rows` 批次复用: 来源 '%s'(字段=%s). "
                    "注意: 大批次下构造 `batch_rows` 可能较重;"
                    "系统默认不会将完整 `batch_rows` 存入长生命周期缓存(避免驻留放大). "
                    "若加载器有副作用或依赖可变的 `batch_rows`, "
                    "请将该 `source` 的 `params` 模板设置为 `$rows: {cache_mode: none}` 禁用复用."
                ),
                source.source_id,
                ",".join(event_field_keys),
            )
            runtime.rows_cache_logged.add(exec_ctx.relation_signature)

    chunk_size = _resolve_lookup_chunk_size(
        source,
        cache_enabled=cache_enabled,
        lookup_key_count=len(lookup_keys_list),
        binding=binding,
    )
    if chunk_size is not None:
        return _load_ref_chunked(
            exec_ctx=exec_ctx,
            source=source,
            binding=binding,
            runtime=runtime,
            event_field_keys=event_field_keys,
            lookup_keys_list=lookup_keys_list,
            batch_rows=batch_rows,
            chunk_size=chunk_size,
            cache_key=cache_key,
        )

    return _load_ref_once(
        runtime=runtime,
        source=source,
        binding=binding,
        loader_context=loader_context,
        cache_enabled=cache_enabled,
        lookup_key_count=len(lookup_keys_set),
        event_field_keys=event_field_keys,
        cache_key=cache_key,
    )


__all__ = (
    "build_ref_loader_context",
    "load_step_data",
)
