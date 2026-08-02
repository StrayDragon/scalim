"""`late_fields` 推导: 识别“仅用于最终写出”的派生字段(`write-precompute`).

判定只依赖 `Plan`/`IR` 的显式依赖边(`field_dependencies`)与字段规格;
任何不确定的情况都保持早算(保守回退到既有 `compute` 段).
"""

from typing import Dict, List, Mapping, Optional, Sequence, Set, Tuple

from ..._internal.utils import graph
from ...spec.ir import DerivedFieldIr, FieldIr, SupportedFieldIr


def _is_late_candidate(field_spec: Optional[SupportedFieldIr]) -> bool:
    if not isinstance(field_spec, DerivedFieldIr):
        return False
    if field_spec.is_constant_compute:
        # 常量 `compute` 在批次内只求值一次;延后到逐行写出会改变求值次数.
        return False
    # 需要 `$ctx` / `$ctx.<attr>` 注入的 `call_by` 必须留在 `compute` 段.
    return field_spec.call_ctx_key is None


def _build_candidate_consumers(field_dependencies: Mapping[str, Tuple[str, ...]], candidates: Set[str]) -> Dict[str, Set[str]]:
    """只为候选字段建反向边(其余字段的消费者与判定无关)."""
    consumers: Dict[str, Set[str]] = {}
    for field_key, deps in field_dependencies.items():
        for dep in deps:
            if dep not in candidates:
                continue
            existing = consumers.get(dep)
            if existing is None:
                consumers[dep] = {field_key}
            else:
                existing.add(field_key)
    return consumers


def _is_available_at_write(
    dep_key: str,
    *,
    late_set: Set[str],
    target_set: Set[str],
    field_specs: Mapping[str, SupportedFieldIr],
    main_source_id: Optional[str],
) -> bool:
    """依赖在写出点是否必然可得.

    只接受三类依赖:
    - 同属 `late` 子图(按拓扑顺序先行物化);
    - 写出目标字段(行写出前已就绪 / 列写出时已在上下文);
    - 主数据源直取字段(批次开始即预填充).
    """
    if dep_key in late_set or dep_key in target_set:
        return True

    dep_spec = field_specs.get(dep_key)
    if dep_spec is None:
        # 未声明的依赖走主行透传提取,与主数据源字段同批预填充.
        return True
    if not isinstance(dep_spec, FieldIr):
        return False
    if dep_spec.lookup_steps or dep_spec.relation:
        return False
    return bool(main_source_id) and dep_spec.source.source_id == main_source_id


def _is_rejected(
    field_key: str,
    candidates: Set[str],
    *,
    consumers: Mapping[str, Set[str]],
    field_dependencies: Mapping[str, Tuple[str, ...]],
    target_set: Set[str],
    field_specs: Mapping[str, SupportedFieldIr],
    main_source_id: Optional[str],
) -> bool:
    """候选是否必须退回早算(存在子图外消费者,或依赖在写出点不可得)."""
    for consumer in consumers.get(field_key, ()):
        if consumer not in candidates:
            return True
    for dep_key in field_dependencies.get(field_key, ()):
        if not _is_available_at_write(
            dep_key,
            late_set=candidates,
            target_set=target_set,
            field_specs=field_specs,
            main_source_id=main_source_id,
        ):
            return True
    return False


def _shrink_to_fixed_point(
    candidates: Set[str],
    *,
    consumers: Mapping[str, Set[str]],
    field_dependencies: Mapping[str, Tuple[str, ...]],
    target_set: Set[str],
    field_specs: Mapping[str, SupportedFieldIr],
    main_source_id: Optional[str],
) -> Set[str]:
    """工作表收缩到不动点: 踢出一个候选后,只需复查与它相邻的候选."""
    pending = set(candidates)
    while pending:
        field_key = pending.pop()
        if field_key not in candidates:  # pragma: no cover  # pragma: allow-no-cover invariant: re-enqueue guarded by membership
            continue
        if not _is_rejected(
            field_key,
            candidates,
            consumers=consumers,
            field_dependencies=field_dependencies,
            target_set=target_set,
            field_specs=field_specs,
            main_source_id=main_source_id,
        ):
            continue
        candidates.discard(field_key)
        # 该字段退回早算后: 它的候选依赖多了一个子图外消费者,它的候选消费者少了一个可得依赖.
        for dep_key in field_dependencies.get(field_key, ()):
            if dep_key in candidates:
                pending.add(dep_key)
        for consumer in consumers.get(field_key, ()):
            if consumer in candidates:
                pending.add(consumer)
    return candidates


def derive_late_fields(
    *,
    field_specs: Mapping[str, SupportedFieldIr],
    field_dependencies: Mapping[str, Tuple[str, ...]],
    target_fields: Sequence[str],
    key_fields: Set[str],
    protected_fields: Set[str],
    main_source_id: Optional[str],
) -> Tuple[str, ...]:
    """推导可延迟到写出前物化的派生字段(按拓扑序返回).

    参数:
        `field_specs`: 字段规格映射
        `field_dependencies`: 字段显式依赖映射(含关联连接键方向)
        `target_fields`: 最终写出目标字段
        `key_fields`: 主键/外键字段(不可 `late`)
        `protected_fields`: 其它必须早算的字段(例如 `order_by` 排序键)
        `main_source_id`: 主数据源标识
    """
    target_set = set(target_fields)
    candidates: Set[str] = set()
    for field_key in target_fields:
        if field_key in key_fields or field_key in protected_fields:
            continue
        if _is_late_candidate(field_specs.get(field_key)):
            candidates.add(field_key)

    if not candidates:
        return ()

    candidates = _shrink_to_fixed_point(
        candidates,
        consumers=_build_candidate_consumers(field_dependencies, candidates),
        field_dependencies=field_dependencies,
        target_set=target_set,
        field_specs=field_specs,
        main_source_id=main_source_id,
    )

    if not candidates:
        return ()

    chained = [field_key for field_key in candidates if any(dep in candidates for dep in field_dependencies.get(field_key, ()))]
    if not chained:
        # 无 `late` -> `late` 边: 直接按写出顺序返回,省掉一次拓扑排序.
        return tuple(field_key for field_key in target_fields if field_key in candidates)

    def _late_deps(field_key: str) -> List[str]:
        return [dep for dep in field_dependencies.get(field_key, ()) if dep in candidates]

    return tuple(graph.topological_sort(candidates, _late_deps))


__all__ = ("derive_late_fields",)
