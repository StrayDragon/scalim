from typing import Any, Callable, Dict, Optional, Sequence, Set, Tuple

from ...planning.operators import LoadRefOperatorIr
from ..context import BatchContext
from ..executor.runtime.runtime import ExecutionRuntime


def commit_task_result(
    result: Any,
    *,
    context: BatchContext,
    runtime: ExecutionRuntime,
    committed_relation_keys: Set[Tuple[Tuple[object, ...], ...]],
) -> None:
    for field_key in sorted(result.overlay.keys()):
        values = result.overlay[field_key]
        for row_id, value in values.items():
            context.set_field_value(field_key, row_id, value)

    if result.group_enabled and result.relation_key not in committed_relation_keys:
        committed_relation_keys.add(result.relation_key)
        runtime.load_ref_group_executed.add(result.relation_key)

    for event in result.hook_events:
        runtime.hook_manager.emit_typed(event.event_type, event.payload)
    for event in result.observer_events:
        runtime.instrumentation.emit_recorded_event(event)


def commit_layer_results(
    layer_ops: Sequence[LoadRefOperatorIr],
    *,
    skipped_field_keys: Set[str],
    op_task_key: Dict[str, Tuple[str, object]],
    results_by_key: Dict[Tuple[str, object], object],
    context: BatchContext,
    runtime: ExecutionRuntime,
    committed_relation_keys: Set[Tuple[Tuple[object, ...], ...]],
    after_operator: Optional[Callable[[LoadRefOperatorIr], None]],
) -> None:
    committed: Set[Tuple[str, object]] = set()
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


__all__ = ["commit_layer_results", "commit_task_result"]
