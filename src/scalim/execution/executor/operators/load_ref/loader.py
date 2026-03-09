import logging
import time
from collections.abc import Mapping
from typing import List, Optional, Tuple, cast

from .....events.catalog import EVENT_LOADER_CALL
from .....spec.ir.binding import BindingIr, LoaderCallContextIr, build_stable_lookup_key_list
from .....spec.ir.helpers import call_loader_with_binding, coerce_loader_result_mapping
from .....spec.ir.relations import LookupStepIr
from .....spec.ir.source_contracts import LookupSourceRefIrBase
from .....typedefs import LoaderCallKwargs, LoaderResultMap, LoaderResultMapping, LookupKeyList, LookupKeySet, RowData
from ....loader_retry import CALLSITE_LOAD_REF, call_with_loader_retry
from ...guardrails import build_loader_result_guardrail_payload, fail_guardrail
from ...helpers.relation_signature import LoadRefCacheKey, build_step_signature, normalize_key_field
from ...runtime.runtime import ExecutionRuntime, LoadRefCacheEntry
from .context import LoadRefExecutionContext

# 模块级日志记录器
_logger = logging.getLogger(__name__.rsplit(".", 1)[0])


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
    result: LoaderResultMapping,
    duration: float,
    *,
    cache_enabled: bool,
    lookup_key_count: int,
    event_field_keys: Tuple[str, ...],
    cache_status: Optional[str],
) -> None:
    if not runtime.instrumentation.wants(EVENT_LOADER_CALL):
        return
    call_kwargs: LoaderCallKwargs = {}
    if binding:
        _, call_kwargs = binding.build_params(loader_context)
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
    )


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
) -> LoaderResultMapping:
    loader_start = time.perf_counter()
    policy = runtime.loader_retry.resolve(source.source_id)
    result: object = call_with_loader_retry(
        call=lambda: call_loader_with_binding(binding, loader_context, source.loader_spec.callable),
        instrumentation=runtime.instrumentation,
        policy=policy,
        loader_name=source.source_id,
        callsite=CALLSITE_LOAD_REF,
        batch_num=runtime.batch_num,
    )
    loader_duration = time.perf_counter() - loader_start

    _trigger_ref_loader_call(
        runtime=runtime,
        source_id=source.source_id,
        binding=binding,
        loader_context=loader_context,
        result=coerce_loader_result_mapping(result),
        duration=loader_duration,
        cache_enabled=cache_enabled,
        lookup_key_count=lookup_key_count,
        event_field_keys=event_field_keys,
        cache_status=cache_status,
    )
    guardrails = runtime.guardrails
    if guardrails.enabled and guardrails.loader.validate_result and not isinstance(result, Mapping):
        fail_guardrail(
            runtime,
            code="loader_result_not_mapping",
            message="Loader result must be a Mapping",
            context=build_loader_result_guardrail_payload(runtime, source_id=source.source_id, result=result, is_ref_loader=True),
            action_mode="fast_fail",
        )
    result_obj = cast("object", result)
    return coerce_loader_result_mapping(result_obj)


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
        runtime.load_ref_cache[cache_key] = LoadRefCacheEntry(
            result=result,
            batch_rows=loader_context.batch_rows,
        )
    return result


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
    merged: LoaderResultMap = {}
    for offset in range(0, len(lookup_keys_list), chunk_size):
        chunk_list = lookup_keys_list[offset : offset + chunk_size]
        chunk_set = set(chunk_list)
        loader_context = build_ref_loader_context(
            exec_ctx,
            source.source_id,
            event_field_keys,
            batch_rows,
            chunk_set,
            chunk_list,
        )

        result = _call_ref_loader(
            runtime=runtime,
            source=source,
            binding=binding,
            loader_context=loader_context,
            cache_enabled=True,
            lookup_key_count=len(chunk_set),
            event_field_keys=event_field_keys,
            cache_status="miss",
        )

        for key, value in result.items():
            if key not in merged:
                merged[key] = value

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
    source = step.to_source
    runtime = exec_ctx.runtime

    if runtime.is_source_cached(source.source_id):
        return runtime.preloaded_cache[source.source_id]

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
                    "已启用 `LoadRef` 的 `rows` 批次缓存: 来源 '%s'(字段=%s). "
                    "若加载器有副作用或依赖可变的 `batch_rows`, 请将 `to_bind.use_rows.cache_mode` 设置为 `none`."
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


__all__ = [
    "build_ref_loader_context",
    "load_step_data",
]
