"""LoadRef operator executor implementation (internal).

Import `LoadRefOperatorExecutor` from `scalim.execution.executor.operators.load_ref.executor`.
"""

from collections.abc import Hashable
from typing import Any, cast

from .....planning.operators import LoadRefOperatorIr, SupportedOperatorIr
from .....vendor.compact.typing_extensionsx import override
from ....context import BatchContext
from ...helpers.relation_signature import build_relation_signature, can_group_by_relation
from ...runtime.runtime import ExecutionRuntime
from ..base import OperatorExecutor
from .context import LoadRefExecutionContext
from .flow import build_next_mapping, init_first_fk_mapping, write_final_step
from .loader import load_step_data


class LoadRefOperatorExecutor(OperatorExecutor):
    """关联加载算子执行器."""

    @override
    def execute(
        self,
        operator: SupportedOperatorIr,
        context: BatchContext,
        batch_row_nth: list[Hashable],
        runtime: ExecutionRuntime,
    ) -> None:
        op = cast("LoadRefOperatorIr", operator)
        field_key = op.field_key
        steps = op.lookup_steps

        if not steps or not runtime.main_source:
            return

        relation_key = build_relation_signature(steps)
        group_enabled = can_group_by_relation(steps)
        if group_enabled and relation_key in runtime.load_ref_group_executed:
            return

        exec_ctx = LoadRefExecutionContext(runtime, context, batch_row_nth, field_key, relation_key)
        group_field_keys = runtime.load_ref_group_fields.get(relation_key, (field_key,))
        if not group_enabled:
            group_field_keys = (field_key,)
        else:
            runtime.load_ref_group_executed.add(relation_key)

        pk_to_first_fk = init_first_fk_mapping(exec_ctx, steps[0], null_fill_fields=group_field_keys)
        if not pk_to_first_fk:
            return

        current_mapping: dict[Hashable, Hashable | tuple[Any, ...]] = pk_to_first_fk

        for step_idx, step in enumerate(steps):
            lookup_keys = set(current_mapping.values())
            if not lookup_keys:
                break

            is_final_step = step_idx == len(steps) - 1
            intermediate_result = load_step_data(
                exec_ctx=exec_ctx,
                step=step,
                lookup_keys=lookup_keys,
                is_final_step=is_final_step,
                group_field_keys=group_field_keys,
            )

            for row_id, fk_value in current_mapping.items():
                lookup_result = "hit" if fk_value in intermediate_result else "miss"
                exec_ctx.record_lookup(row_id, fk_value, fk_value, step.to_source, lookup_result)

            if step_idx == len(steps) - 1:
                write_final_step(exec_ctx, current_mapping, intermediate_result, step.to_source, group_field_keys)
            else:
                current_mapping = build_next_mapping(
                    exec_ctx,
                    current_mapping,
                    intermediate_result,
                    steps[step_idx + 1],
                    null_fill_fields=group_field_keys,
                )
