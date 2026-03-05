from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple

from ...planning.operators import LoadRefOperatorIr
from ..executor.helpers.relation_signature import build_relation_signature, can_group_by_relation
from ..executor.runtime.runtime import ExecutionRuntime


@dataclass(frozen=True)
class TaskSpec:
    op: LoadRefOperatorIr
    relation_key: Tuple[Tuple[object, ...], ...]
    group_enabled: bool
    pool_name: str


def collect_layer_executable_ops(
    layer_ops: Sequence[LoadRefOperatorIr],
    *,
    runtime: ExecutionRuntime,
    after_operator: Optional[Callable[[LoadRefOperatorIr], None]],
) -> Tuple[Set[str], List[LoadRefOperatorIr]]:
    skipped_field_keys: Set[str] = set()
    executable_ops: List[LoadRefOperatorIr] = []

    for op in layer_ops:
        relation_key = build_relation_signature(op.lookup_steps)
        group_enabled = can_group_by_relation(op.lookup_steps)
        if group_enabled and relation_key in runtime.load_ref_group_executed:
            skipped_field_keys.add(op.field_key)
            if after_operator is not None:
                after_operator(op)
            continue
        executable_ops.append(op)

    return skipped_field_keys, executable_ops


def build_task_specs(
    ops: Sequence[LoadRefOperatorIr],
    *,
    resolve_task_pool: Callable[[LoadRefOperatorIr], str],
) -> Tuple[List[Tuple[str, object]], Dict[Tuple[str, object], TaskSpec], Dict[str, Tuple[str, object]]]:
    task_specs: Dict[Tuple[str, object], TaskSpec] = {}
    op_task_key: Dict[str, Tuple[str, object]] = {}
    task_order: List[Tuple[str, object]] = []

    for op in ops:
        relation_key = build_relation_signature(op.lookup_steps)
        group_enabled = True
        task_key: Tuple[str, object] = ("relation", relation_key)

        op_task_key[op.field_key] = task_key
        if task_key not in task_specs:
            pool_name = resolve_task_pool(op)
            task_specs[task_key] = TaskSpec(op=op, relation_key=relation_key, group_enabled=group_enabled, pool_name=pool_name)
            task_order.append(task_key)

    return task_order, task_specs, op_task_key


__all__ = ["TaskSpec", "build_task_specs", "collect_layer_executable_ops"]
