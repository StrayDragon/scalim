import heapq
import logging

from ...spec.ir.sources import SourceIr
from ...utils import graph

_logger = logging.getLogger(__name__)
_UNMAPPED_DEPS_PREVIEW_LIMIT = 10


def sort_ref_loaders(  # noqa: C901, PLR0912
    ref_loaders: list[tuple[SourceIr, list[tuple[str, str | tuple[str, ...]]]]],
) -> list[tuple[SourceIr, list[tuple[str, str | tuple[str, ...]]]]]:
    """Topologically sort ref loaders using ref-field dependency signals.

    Ordering contract:
    - Dependency signals come from ref field lookup steps (`from_field` field keys).
    - Sorter maps those field keys back to their owning ref loader, builds a loader
      dependency graph and runs a topological sort.
    - If some dependency keys cannot be mapped, the sorter MUST warn once and
      fall back to stable tie-break (`source_id` lexicographic).
    """
    if len(ref_loaders) <= 1:
        return ref_loaders

    loader_ids = [source.source_id for source, _ in ref_loaders]
    loader_deps: dict[str, set[str]] = {loader_id: set() for loader_id in loader_ids}
    field_to_loader: dict[str, str] = {}

    for source, ref_fields in ref_loaders:
        for field_key, _ in ref_fields:
            field_to_loader[field_key] = source.source_id

    unmapped_dep_keys: set[str] = set()
    for source, ref_fields in ref_loaders:
        loader_id = source.source_id
        for _field_key, dep_ref_field_keys in ref_fields:
            dep_keys = [dep_ref_field_keys] if isinstance(dep_ref_field_keys, str) else list(dep_ref_field_keys)
            for dep_key in dep_keys:
                if not dep_key:
                    continue
                dep_loader = field_to_loader.get(dep_key)
                if dep_loader is None:
                    unmapped_dep_keys.add(dep_key)
                    continue
                if dep_loader != loader_id:
                    loader_deps[loader_id].add(dep_loader)

    if unmapped_dep_keys:
        unmapped_preview = ", ".join(sorted(unmapped_dep_keys)[:_UNMAPPED_DEPS_PREVIEW_LIMIT])
        if len(unmapped_dep_keys) > _UNMAPPED_DEPS_PREVIEW_LIMIT:
            unmapped_preview += ", ..."
        _logger.warning(
            (
                "Ref loader ordering degraded: %d dependency keys could not be mapped to a ref loader; "
                "falling back to stable tie-break (source_id). keys=%s"
            ),
            len(unmapped_dep_keys),
            unmapped_preview,
        )

    in_degree: dict[str, int] = dict.fromkeys(loader_ids, 0)
    reverse_deps: dict[str, list[str]] = {loader_id: [] for loader_id in loader_ids}
    for loader_id, deps in loader_deps.items():
        for dep in deps:
            in_degree[loader_id] += 1
            reverse_deps.setdefault(dep, []).append(loader_id)

    ready = [name for name, degree in in_degree.items() if degree == 0]
    heapq.heapify(ready)
    sorted_loaders: list[str] = []
    while ready:
        name = heapq.heappop(ready)
        sorted_loaders.append(name)
        for dependent in sorted(reverse_deps.get(name, [])):
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                heapq.heappush(ready, dependent)

    if len(sorted_loaders) != len(in_degree):
        cycles = graph.detect_cycles(loader_ids, lambda name: sorted(loader_deps.get(name, set())))
        cycle_str = "; ".join(" -> ".join(cycle) for cycle in cycles) if cycles else "<unknown>"
        msg = f"检测到 ref loader 循环依赖: {cycle_str}"
        raise graph.CyclicDependencyError(msg, cycles)

    loader_map = {source.source_id: (source, fields) for source, fields in ref_loaders}
    return [loader_map[name] for name in sorted_loaders if name in loader_map]


__all__ = [
    "sort_ref_loaders",
]
