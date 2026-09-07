from collections.abc import Callable, Sequence
from dataclasses import dataclass

from ...planning.operators import LoadRefOperatorIr
from ...spec.ir import SourceIr
from ...utils.relation_signature import RelationSignature, build_relation_signature, can_group_by_relation
from ..executor.runtime.runtime import ExecutionRuntime

AdaptiveTaskKey = tuple[str, RelationSignature]


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
    after_operator: Callable[[LoadRefOperatorIr], None] | None,
) -> tuple[set[str], list[LoadRefOperatorIr]]:
    skipped_field_keys: set[str] = set()
    executable_ops: list[LoadRefOperatorIr] = []

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
    sources: dict[str, SourceIr],
) -> tuple[list[AdaptiveTaskKey], dict[AdaptiveTaskKey, TaskSpec], dict[str, AdaptiveTaskKey]]:
    task_specs: dict[AdaptiveTaskKey, TaskSpec] = {}
    op_task_key: dict[str, AdaptiveTaskKey] = {}
    task_order: list[AdaptiveTaskKey] = []

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
