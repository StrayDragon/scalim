"""`compute_fusion_groups` 推导: 同一 compute 段内同 deps 的派生字段组.

第一期硬约束(与 `execution-compute-rowwise-fusion` / c20 决议对齐):
- 同一 pre-ref 或 post-ref 段(以 `LoadRef` 为界);
- 组内 deps **完全相同**;
- 组内互不依赖;
- 成员为 `compute_expr` 或无 `$ctx` 的 `call_by`;
- 排除 `is_constant_compute` / 含 `call_ctx_key`.

`late_fields` **不**在规划期剔除: `execute_batch` 会清空 runtime late,
写出路径再按 `runtime.late_fields` 过滤;组大小 < 2 时运行时回退 field-major.
"""

from typing import List, Mapping, Optional, Sequence, Set, Tuple

from ...spec.ir import DerivedFieldIr, SupportedFieldIr
from ...vendor.dataclassesx import dataclass
from ..operators import ComputeOperatorIr, LoadRefOperatorIr, PlanOperatorIr


@dataclass(frozen=True)
class ComputeFusionGroup:
    """计划期识别的 row-wise 融合组(运行时再过安全外壳)."""

    segment: str
    """`pre_ref` 或 `post_ref`."""

    field_keys: Tuple[str, ...]
    """组内字段(稳定序: 该段 compute 算子出现序)."""

    deps: Tuple[str, ...]
    """组内共享依赖(完全相同)."""


def _is_fusion_member_candidate(field_spec: Optional[SupportedFieldIr]) -> bool:
    if not isinstance(field_spec, DerivedFieldIr):
        return False
    if field_spec.is_constant_compute:
        return False
    if field_spec.call_ctx_key is not None:
        return False
    if field_spec.call_by is None and not field_spec.compute_expr:
        return False
    return True


def _segment_compute_field_keys(operators: Sequence[PlanOperatorIr]) -> List[Tuple[str, Tuple[str, ...]]]:
    """按段切分: 返回 `(segment, field_keys_in_order)` 列表."""
    segments: List[Tuple[str, List[str]]] = []
    current_name = "pre_ref"
    current: List[str] = []
    seen_load_ref = False

    for op in operators:
        if isinstance(op, LoadRefOperatorIr):
            if current:
                segments.append((current_name, current))
                current = []
            seen_load_ref = True
            current_name = "post_ref"
            continue
        if isinstance(op, ComputeOperatorIr):
            if seen_load_ref and current_name != "post_ref":
                current_name = "post_ref"
            current.append(str(op.field_key))

    if current:
        segments.append((current_name, current))

    result: List[Tuple[str, Tuple[str, ...]]] = []
    for name, keys in segments:
        result.append((name, tuple(keys)))
    return result


def _group_keys_in_segment(
    field_keys: Sequence[str],
    *,
    field_specs: Mapping[str, SupportedFieldIr],
    field_dependencies: Mapping[str, Tuple[str, ...]],
) -> List[Tuple[Tuple[str, ...], Tuple[str, ...]]]:
    """在一段内贪心合并连续同 deps 候选;返回 `(field_keys, deps)` 且 len>=2."""
    groups: List[Tuple[Tuple[str, ...], Tuple[str, ...]]] = []
    pending_keys: List[str] = []
    pending_deps: Optional[Tuple[str, ...]] = None
    pending_set: Set[str] = set()

    def _flush() -> None:
        nonlocal pending_keys, pending_deps, pending_set
        if pending_deps is not None and len(pending_keys) >= 2:
            groups.append((tuple(pending_keys), pending_deps))
        pending_keys = []
        pending_deps = None
        pending_set = set()

    for field_key in field_keys:
        spec = field_specs.get(field_key)
        if not _is_fusion_member_candidate(spec):
            _flush()
            continue
        deps = tuple(field_dependencies.get(field_key, ()))
        # 组内互不依赖: 新字段依赖已进组字段 → 断开.
        if any(dep in pending_set for dep in deps):
            _flush()
        if pending_deps is None:
            pending_keys = [field_key]
            pending_deps = deps
            pending_set = {field_key}
            continue
        if deps != pending_deps:
            _flush()
            pending_keys = [field_key]
            pending_deps = deps
            pending_set = {field_key}
            continue
        pending_keys.append(field_key)
        pending_set.add(field_key)

    _flush()
    return groups


def derive_compute_fusion_groups(
    *,
    operators: Sequence[PlanOperatorIr],
    field_specs: Mapping[str, SupportedFieldIr],
    field_dependencies: Mapping[str, Tuple[str, ...]],
) -> Tuple[ComputeFusionGroup, ...]:
    """从 plan operators 推导融合组(仅 size>=2)."""
    out: List[ComputeFusionGroup] = []
    for segment_name, field_keys in _segment_compute_field_keys(operators):
        for keys, deps in _group_keys_in_segment(
            field_keys,
            field_specs=field_specs,
            field_dependencies=field_dependencies,
        ):
            out.append(ComputeFusionGroup(segment=segment_name, field_keys=keys, deps=deps))
    return tuple(out)


__all__ = (
    "ComputeFusionGroup",
    "derive_compute_fusion_groups",
)
