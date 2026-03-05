import heapq
import logging
from typing import Dict, List, Set, Tuple, Union

from ...spec.ir.sources import SourceIr
from ...utils import graph

_logger = logging.getLogger(__name__)
_UNMAPPED_DEPS_PREVIEW_LIMIT = 10

REF_LOADER_ORDERING_DEGRADED_PREFIX = "引用加载器排序退化"
REF_LOADER_ORDERING_DEGRADED_WARNING = (
    REF_LOADER_ORDERING_DEGRADED_PREFIX + ": 有 %d 个依赖键无法映射到对应的引用加载器; 将回退到稳定的并列裁决(`source_id`). 键=%s"
)


def sort_ref_loaders(  # noqa: C901, PLR0912
    ref_loaders: List[Tuple[SourceIr, List[Tuple[str, Union[str, Tuple[str, ...]]]]]],
) -> List[Tuple[SourceIr, List[Tuple[str, Union[str, Tuple[str, ...]]]]]]:
    """基于引用字段的依赖信号对引用加载器进行拓扑排序.

    排序约束:
    - 依赖信号来自引用字段的关联步骤(`from_field` 对应的字段键).
    - 排序器会将这些字段键映射回其所属的引用加载器,构建加载器依赖图并执行拓扑排序.
    - 如果部分依赖键无法映射,排序器会仅警告一次,并回退到稳定的并列裁决(按 `source_id` 字典序).
    """
    if len(ref_loaders) <= 1:
        return ref_loaders

    loader_ids = [source.source_id for source, _ in ref_loaders]
    loader_deps: Dict[str, Set[str]] = {loader_id: set() for loader_id in loader_ids}
    field_to_loader: Dict[str, str] = {}

    for source, ref_fields in ref_loaders:
        for field_key, _ in ref_fields:
            field_to_loader[field_key] = source.source_id

    unmapped_dep_keys: Set[str] = set()
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
        _logger.warning(REF_LOADER_ORDERING_DEGRADED_WARNING, len(unmapped_dep_keys), unmapped_preview)

    in_degree: Dict[str, int] = dict.fromkeys(loader_ids, 0)
    reverse_deps: Dict[str, List[str]] = {loader_id: [] for loader_id in loader_ids}
    for loader_id, deps in loader_deps.items():
        for dep in deps:
            in_degree[loader_id] += 1
            reverse_deps.setdefault(dep, []).append(loader_id)

    ready = [name for name, degree in in_degree.items() if degree == 0]
    heapq.heapify(ready)
    sorted_loaders: List[str] = []
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
        msg = "检测到 ref loader 循环依赖: {}".format(cycle_str)
        raise graph.CyclicDependencyError(msg, cycles)

    loader_map = {source.source_id: (source, fields) for source, fields in ref_loaders}
    return [loader_map[name] for name in sorted_loaders if name in loader_map]


__all__ = [
    "sort_ref_loaders",
]
