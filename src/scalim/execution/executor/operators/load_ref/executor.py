# pragma: allow-c901-file plan: c60
"""`LoadRef` 算子执行器实现(内部模块).

请从 `scalim.execution.executor.operators.load_ref.executor` 导入 `LoadRefOperatorExecutor`.
"""

import logging
from typing import TYPE_CHECKING, Dict, Hashable, List, Set

from ....._internal.utils.converters import auto_str_normalize_key
from .....events import EventType
from .....planning.operators import LoadRefOperatorIr, SupportedOperatorIr
from .....spec.ir import LookupStepIr
from .....typedefs import LoaderResultMapping
from .....utils.relation_signature import RelationSignature, build_relation_signature, can_group_by_relation
from .....vendor.compact.typing_extensionsx import override
from ....context import BatchContext
from ...runtime.runtime import ExecutionRuntime
from ..base import OperatorExecutor
from .context import LoadRefExecutionContext
from .flow import build_next_mapping, init_first_fk_mapping, write_final_step
from .loader import load_step_data

if TYPE_CHECKING:
    from .....typedefs import LookupKey


_logger = logging.getLogger(__name__)


def _maybe_emit_key_normalization_key_space_mismatch_warning(
    *,
    runtime: ExecutionRuntime,
    relation_signature: RelationSignature,
    step: LookupStepIr,
    field_id: str,
    lookup_keys: "Set[LookupKey]",
    intermediate_result: LoaderResultMapping,
) -> None:
    if runtime.key_normalization != "auto_str":
        return

    source = runtime.resolve_lookup_source(step)
    has_explicit_cast = step.lookup_cast is not None or source.key.cast is not None
    if not has_explicit_cast:
        return

    mismatch_key = (relation_signature, str(source.source_id))
    if mismatch_key in runtime.key_space_mismatch_logged:
        return

    for key in lookup_keys:
        if key in intermediate_result:
            continue
        normalized_key, status, _error_message = auto_str_normalize_key(key)
        if status != "ok" or normalized_key is None:
            continue
        if normalized_key in intermediate_result:
            runtime.key_space_mismatch_logged.add(mismatch_key)
            runtime.instrumentation.emit_diagnostic_warning(
                message=(
                    "key_normalization key-space mismatch detected (redacted): "
                    "key_normalization='auto_str' with explicit cast uses the casted key space, "
                    "but loader mapping appears to use stable string keys (a miss becomes a hit after normalization). "
                    "Consider removing the explicit cast, switching to key_normalization='force_str', "
                    "or updating the loader to return keys in the casted key space."
                ),
                source_id=source.source_id,
                field_id=field_id,
                lookup_key=None,
                row_id="(redacted)",
            )
            return


def _maybe_emit_ref_default_applied_summary(*, runtime: ExecutionRuntime, exec_ctx: LoadRefExecutionContext) -> None:
    counts = dict(exec_ctx.default_applied_counts or {})
    if not counts:
        return
    text = ", ".join("{}={}".format(k, int(counts[k])) for k in sorted(counts.keys()))
    _logger.info(
        "`LoadRef` 已应用关联缺失缺省值: %s (批次=%s, 字段=%s, 关联=%s)",
        text,
        runtime.batch_num,
        exec_ctx.field_key,
        exec_ctx.relation_signature,
    )


class LoadRefOperatorExecutor(OperatorExecutor):
    """关联加载算子执行器."""

    @override
    def execute(  # noqa: C901, PLR0912
        self,
        operator: SupportedOperatorIr,
        context: BatchContext,
        batch_row_nth: List[Hashable],
        runtime: ExecutionRuntime,
    ) -> None:
        if not isinstance(operator, LoadRefOperatorIr):
            return

        op = operator
        field_key = op.field_key
        steps = op.lookup_steps

        if not steps or not runtime.main_source:
            return

        relation_key = build_relation_signature(steps, runtime.sources)
        group_enabled = can_group_by_relation(steps, runtime.sources)
        if group_enabled and relation_key in runtime.load_ref_group_executed:
            return
        wants_relation_lookup = runtime.instrumentation.wants(EventType.RELATION_LOOKUP)

        exec_ctx = LoadRefExecutionContext(runtime, context, batch_row_nth, field_key, relation_key)
        try:
            group_field_keys = runtime.load_ref_group_fields.get(relation_key, (field_key,))
            if not group_enabled:
                group_field_keys = (field_key,)
            else:
                runtime.load_ref_group_executed.add(relation_key)

            pk_to_first_fk = init_first_fk_mapping(exec_ctx, steps[0], null_fill_fields=group_field_keys)
            if not pk_to_first_fk:
                return

            current_mapping: Dict[Hashable, "LookupKey"] = pk_to_first_fk

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

                _maybe_emit_key_normalization_key_space_mismatch_warning(
                    runtime=runtime,
                    relation_signature=relation_key,
                    step=step,
                    field_id=field_key,
                    lookup_keys=lookup_keys,
                    intermediate_result=intermediate_result,
                )

                # 热路径 `wants-gated`: 当无人订阅 `relation_lookup` 时,跳过逐行 `hit/miss` 分类诊断.
                live_source = runtime.resolve_lookup_source(step)
                if wants_relation_lookup:
                    for row_id, fk_value in current_mapping.items():
                        lookup_result = "hit" if fk_value in intermediate_result else "miss"
                        exec_ctx.record_lookup(row_id, fk_value, fk_value, live_source, lookup_result)

                if step_idx == len(steps) - 1:
                    write_final_step(exec_ctx, current_mapping, intermediate_result, live_source, group_field_keys)
                else:
                    current_mapping = build_next_mapping(
                        exec_ctx,
                        current_mapping,
                        intermediate_result,
                        steps[step_idx + 1],
                        null_fill_fields=group_field_keys,
                    )
        finally:
            _maybe_emit_ref_default_applied_summary(runtime=runtime, exec_ctx=exec_ctx)


__all__ = ()
