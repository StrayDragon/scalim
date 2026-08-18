from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple

from ...planning.operators import LoadRefOperatorIr
from ...spec.ir import SourceIr
from ...utils.relation_signature import RelationSignature, build_relation_signature, can_group_by_relation
from ...vendor.dataclassesx import dataclass
from ..executor.runtime.runtime import ExecutionRuntime

AdaptiveTaskKey = Tuple[str, RelationSignature]


@dataclass(frozen=True)
class TaskSpec:
    op: LoadRefOperatorIr
    relation_key: RelationSignature
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
        relation_key = build_relation_signature(op.lookup_steps, runtime.sources)
        group_enabled = can_group_by_relation(op.lookup_steps, runtime.sources)
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
    sources: Dict[str, SourceIr],
) -> Tuple[List[AdaptiveTaskKey], Dict[AdaptiveTaskKey, TaskSpec], Dict[str, AdaptiveTaskKey]]:
    task_specs: Dict[AdaptiveTaskKey, TaskSpec] = {}
    op_task_key: Dict[str, AdaptiveTaskKey] = {}
    task_order: List[AdaptiveTaskKey] = []

    for op in ops:
        relation_key = build_relation_signature(op.lookup_steps, sources)
        group_enabled = can_group_by_relation(op.lookup_steps, sources)
        task_key: AdaptiveTaskKey = ("relation", relation_key)

        op_task_key[op.field_key] = task_key
        if task_key not in task_specs:
            pool_name = resolve_task_pool(op)
            task_specs[task_key] = TaskSpec(op=op, relation_key=relation_key, group_enabled=group_enabled, pool_name=pool_name)
            task_order.append(task_key)

    return task_order, task_specs, op_task_key


__all__ = ("AdaptiveTaskKey", "TaskSpec", "build_task_specs", "collect_layer_executable_ops")
