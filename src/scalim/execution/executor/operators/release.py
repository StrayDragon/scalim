from typing import Hashable, List, cast

from ....planning.operators import ReleaseOperatorIr, SupportedOperatorIr
from ....vendor.compact.typing_extensionsx import override
from ...context import BatchContext
from ..runtime.runtime import ExecutionRuntime
from .base import OperatorExecutor


class ReleaseOperatorExecutor(OperatorExecutor):
    """释放算子执行器"""

    @override
    def execute(
        self,
        operator: SupportedOperatorIr,
        context: BatchContext,
        batch_row_nth: List[Hashable],
        runtime: ExecutionRuntime,
    ) -> None:
        op = cast("ReleaseOperatorIr", operator)  # pragma: allow-cast operator dispatch typed narrowing
        field_key = op.field_key

        context.delete_field(field_key)
        runtime.instrumentation.emit_field_slim(
            field_key=field_key,
            reason=op.reason or "显式释放",
            batch_num=runtime.batch_num,
            remaining_fields=context.get_field_count(),
        )


__all__ = ()
