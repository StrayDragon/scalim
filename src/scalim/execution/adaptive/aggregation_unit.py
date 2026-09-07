from collections.abc import Callable, Mapping, Sequence
from typing import Any

from ...planning.operators import LoadRefOperatorIr
from ...utils.relation_signature import RelationSignature
from ..context import BatchContext
from ..executor.runtime.runtime import ExecutionRuntime
from .strategy_unit import AdaptiveTaskKey


def commit_task_result(
    result: Any,
    *,
    context: BatchContext,
    runtime: ExecutionRuntime,
    committed_relation_keys: set[RelationSignature],
) -> None:
    for field_key in sorted(result.overlay.keys()):
        values = result.overlay[field_key]
        for row_id, value in values.items():
            context.set_field_value(field_key, row_id, value)

    if result.group_enabled and result.relation_key not in committed_relation_keys:
        committed_relation_keys.add(result.relation_key)
        runtime.load_ref_group_executed.add(result.relation_key)

    for recorded in result.hook_events:
        # `HookCaptureManager` 记录完整 `Event` 信封(`r217`).
        runtime.hook_manager.emit_typed(recorded.event_type, recorded.event)
    for event in result.observer_events:
        runtime.instrumentation.emit_recorded_event(event)


def commit_layer_results(
    layer_ops: Sequence[LoadRefOperatorIr],
    *,
    skipped_field_keys: set[str],
    op_task_key: dict[str, AdaptiveTaskKey],
    results_by_key: Mapping[AdaptiveTaskKey, Any],
    context: BatchContext,
    runtime: ExecutionRuntime,
    committed_relation_keys: set[RelationSignature],
    after_operator: Callable[[LoadRefOperatorIr], None] | None,
) -> None:
    committed: set[AdaptiveTaskKey] = set()
    for op in layer_ops:
        if op.field_key in skipped_field_keys:
            continue
        task_key = op_task_key[op.field_key]
        if task_key not in committed:
            commit_task_result(
                results_by_key[task_key],
                context=context,
                runtime=runtime,
                committed_relation_keys=committed_relation_keys,
            )
            committed.add(task_key)

        if after_operator is not None:
            after_operator(op)


__all__ = ("commit_layer_results", "commit_task_result")
