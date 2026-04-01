import time
from typing import Any, Dict, List, Sequence, Set, Tuple, Union

from ..spec.ir import SourceIr
from ..utils.relation_signature import RelationSignature, build_relation_signature, has_rows_binding
from ..vendor.compact.typing_extensionsx import Protocol, TypedDict
from .operators import LoadRefOperatorIr, PlanOperatorIr

_RefLoaderOrderingDep = Union[str, Tuple[str, ...]]
_RefLoaderField = Tuple[str, _RefLoaderOrderingDep]
_RefLoaderSequenceItem = Tuple[SourceIr, List[_RefLoaderField]]


class _ExecutionPlanLike(Protocol):
    operators: Tuple[PlanOperatorIr, ...]
    ref_loader_sequence: List[_RefLoaderSequenceItem]
    target_fields: List[str]


class _VizTask(TypedDict):
    task_id: str
    chain: List[str]
    fields: List[str]
    rows_binding: bool


def _build_ref_deps(plan: _ExecutionPlanLike) -> Dict[str, Tuple[str, ...]]:
    deps: Dict[str, Tuple[str, ...]] = {}
    for _source, items in plan.ref_loader_sequence:
        for field_key, dep_ref_field_keys in items:
            if not dep_ref_field_keys:
                deps[str(field_key)] = ()
            elif isinstance(dep_ref_field_keys, tuple):
                deps[str(field_key)] = tuple(str(dep) for dep in dep_ref_field_keys)
            else:
                deps[str(field_key)] = (str(dep_ref_field_keys),)
    return deps


def _build_layers(field_keys: Sequence[str], *, deps: Dict[str, Tuple[str, ...]]) -> List[List[str]]:
    remaining: Set[str] = set(field_keys)
    done: Set[str] = set()
    layers: List[List[str]] = []

    # 确定性的 O(n^2) 分层,与规划/算子顺序对齐.
    while remaining:
        ready: List[str] = []
        for key in field_keys:
            if key not in remaining:
                continue
            key_deps = deps.get(key, ())
            if all(dep in done or dep not in remaining for dep in key_deps):
                ready.append(key)

        if not ready:
            # 若存在环或缺失信号: 回退为按算子顺序串行执行.
            layers.append([k for k in field_keys if k in remaining])
            break

        layers.append(ready)
        for key in ready:
            remaining.remove(key)
            done.add(key)

    return layers


def build_viz_schedule_plan(
    plan: _ExecutionPlanLike,
) -> Dict[str, Any]:
    """生成 `viz_schedule_plan.json` (用于 `adaptive` 计划视角的可视化).

    说明:
    - 该产物用于表达“计划后大致会如何 `fanout`/`fanin`/屏障/串行退化”, 不表示真实运行时序.
    - 当前仅包含 `load_ref` 维度 (与 `adaptive scheduler` 的分层/分组逻辑对齐).
    """

    loadref_ops = [op for op in plan.operators if isinstance(op, LoadRefOperatorIr)]
    op_by_field_key: Dict[str, LoadRefOperatorIr] = {op.field_key: op for op in loadref_ops}
    field_keys: List[str] = [op.field_key for op in loadref_ops]

    deps = _build_ref_deps(plan)
    layers = _build_layers(field_keys, deps=deps)

    layer_items: List[Dict[str, Any]] = []
    for layer_index, layer_field_keys in enumerate(layers):
        layer_ops: List[LoadRefOperatorIr] = []
        for key in layer_field_keys:
            op = op_by_field_key.get(key)
            if op is not None:
                layer_ops.append(op)

        rows_barrier = any(has_rows_binding(op.lookup_steps) for op in layer_ops)

        groups: Dict[RelationSignature, _VizTask] = {}
        group_order: List[RelationSignature] = []

        for op in layer_ops:
            sig = build_relation_signature(op.lookup_steps)
            item = groups.get(sig)
            if item is None:
                chain = [step[0] for step in sig]
                new_item: _VizTask = {
                    "task_id": "t{}".format(len(group_order)),
                    "chain": chain,
                    "fields": [],
                    "rows_binding": bool(has_rows_binding(op.lookup_steps)),
                }
                groups[sig] = new_item
                group_order.append(sig)
                item = new_item
            item["fields"].append(str(op.field_key))

        tasks = [groups[key] for key in group_order]
        layer_items.append(
            {
                "layer_index": int(layer_index),
                "op_count": len(layer_ops),
                "rows_binding_barrier": bool(rows_barrier),
                "task_group_count": len(tasks),
                "tasks": tasks,
            }
        )

    targets = list(plan.target_fields or [])
    return {
        "meta": {
            "created_at": time.time(),
            "target_fields": targets,
        },
        "targets": targets,
        "load_ref": {
            "op_count": len(loadref_ops),
            "layer_count": len(layer_items),
            "layers": layer_items,
        },
    }


__all__ = ("build_viz_schedule_plan",)
