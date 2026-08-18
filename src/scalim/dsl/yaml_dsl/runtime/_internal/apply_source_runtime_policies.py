"""将 `DemandRunRuntimeOptions` 的 `typed` 覆盖应用到 `DemandIr.sources` 目录.

`DemandIr.sources` 是 `SourceIr` 的 `SSOT`(含 `LookupChunking` / `SourceCache` / `RowsReuse`).
`FieldIr.source_id` / `LookupStepIr.to_source_id` 只是图边身份;
执行与规划按 `id` 回目录解析,不得把嵌套快照当成策略真源.
"""

from typing import Dict, Mapping, Optional, Tuple

from .....execution.lookup_chunking import LookupChunking
from .....spec.ir import DemandIr, SourceIr
from .....spec.ir.aliases import NormalizedLookupKeySpec  # noqa: TC001 — used in runtime Dict annotations (py36)
from .....spec.ir.binding import BindingIr  # noqa: TC001 — used in runtime Dict annotations (py36)
from .....vendor.dataclassesx import replace
from ..source_policies import RowsReuse, SourceCache


def apply_source_runtime_policies(
    demand_ir: DemandIr,
    *,
    lookup_chunking: Mapping[str, LookupChunking],
    source_cache: Mapping[str, SourceCache],
    rows_reuse: Mapping[str, RowsReuse],
) -> DemandIr:
    """按优先级覆盖 **`source` 目录** 上的缓存/分片与 `rows` 复用策略."""
    if not lookup_chunking and not source_cache and not rows_reuse:
        return demand_ir

    next_sources: Dict[str, SourceIr] = {}
    changed = False
    for source_id, source in demand_ir.sources.items():
        next_source, source_changed = _apply_one_source_policies(
            source,
            chunk_policy=lookup_chunking.get(source_id),
            cache_policy=source_cache.get(source_id),
            reuse_policy=rows_reuse.get(source_id),
        )
        next_sources[source_id] = next_source
        changed = changed or source_changed

    if not changed:
        return demand_ir
    return replace(demand_ir, sources=next_sources)


def resolve_chunk_parallelism_from_runtime(
    *,
    parallelize_lookup_chunks: bool,
    max_chunk_workers: Optional[int],
    lookup_chunking: Mapping[str, LookupChunking],
) -> Tuple[bool, Optional[int]]:
    """合并旧平铺布尔与 `LookupChunking.sized(parallel=...)`.

    返回 `(enabled, workers)`:
    - `enabled`: 任一 `sized(parallel=True)` 或遗留 `parallelize_lookup_chunks=True`
    - `workers`: 取顶层 `max_chunk_workers` 与各 `sized` 策略中非 `None` 值的**最小值**(更紧的帽优先);
      若全部为 `None` 则保持 `None`(由 `runtime` 另按 `max_workers` 解析)
    """
    any_parallel = any(policy.wants_parallel() for policy in lookup_chunking.values())
    enabled = bool(parallelize_lookup_chunks) or any_parallel

    workers = max_chunk_workers
    for policy in lookup_chunking.values():
        if policy.max_chunk_workers is None:
            continue
        if workers is None or int(policy.max_chunk_workers) < int(workers):
            workers = int(policy.max_chunk_workers)
    return enabled, workers


def _apply_one_source_policies(
    source: SourceIr,
    *,
    chunk_policy: Optional[LookupChunking],
    cache_policy: Optional[SourceCache],
    reuse_policy: Optional[RowsReuse],
) -> Tuple[SourceIr, bool]:
    next_source = source
    changed = False

    if cache_policy is not None:
        mode = cache_policy.to_ir_mode()
        if next_source.cache_mode != mode:
            next_source = replace(next_source, cache_mode=mode)
            changed = True

    if chunk_policy is not None:
        size = chunk_policy.effective_chunk_size()
        parallel = bool(chunk_policy.wants_parallel()) if chunk_policy.is_sized() else False
        if next_source.lookup_chunk_size != size or next_source.lookup_chunk_parallel != parallel:
            next_source = replace(
                next_source,
                lookup_chunk_size=size,
                lookup_chunk_parallel=parallel,
            )
            changed = True

    if reuse_policy is not None:
        patched = _apply_rows_reuse(next_source, reuse_policy)
        if patched is not next_source:
            next_source = patched
            changed = True

    return next_source, changed


def _apply_rows_reuse(source: SourceIr, policy: RowsReuse) -> SourceIr:
    mode = policy.to_binding_cache_mode()
    bind = source.bind
    next_bind = bind
    if bind is not None and bind.mode == "rows" and bind.cache_mode != mode:
        next_bind = replace(bind, cache_mode=mode)

    next_bindings: Dict[NormalizedLookupKeySpec, BindingIr] = {}
    bindings_changed = False
    for key, binding in source.bindings.items():
        if binding.mode == "rows" and binding.cache_mode != mode:
            next_bindings[key] = replace(binding, cache_mode=mode)
            bindings_changed = True
        else:
            next_bindings[key] = binding

    if next_bind is bind and not bindings_changed:
        return source
    return replace(
        source,
        bind=next_bind,
        bindings=next_bindings if bindings_changed else source.bindings,
    )


__all__ = ()
