from typing import Hashable, List, cast

from ....planning.operators import SupportedOperatorIr, WriteColumnOperatorIr, WriteRowOperatorIr
from ....sinks import IColumnSink, IRowSink
from ....vendor.compact.typing_extensionsx import override
from ...context import BatchContext
from ..helpers.batch_data import build_column_data, build_row
from ..runtime.runtime import ExecutionRuntime
from .base import OperatorExecutor


class WriteColumnOperatorExecutor(OperatorExecutor):
    """列写入算子执行器"""

    @override
    def execute(
        self,
        operator: SupportedOperatorIr,
        context: BatchContext,
        batch_row_nth: List[Hashable],
        runtime: ExecutionRuntime,
    ) -> None:
        op = cast("WriteColumnOperatorIr", operator)  # pragma: allow-cast operator dispatch typed narrowing
        field_key = op.field_key

        if not isinstance(runtime.sink, IColumnSink):
            return

        col_data = build_column_data(context, field_key, batch_row_nth)

        runtime.sink.write_column(field_key, col_data)

        runtime.instrumentation.emit_column_write(
            field_key=field_key,
            row_count=len(col_data),
            batch_num=runtime.batch_num,
        )

        if op.can_release_after:
            context.delete_field(field_key)
            runtime.instrumentation.emit_field_slim(
                field_key=field_key,
                reason="列写入后释放",
                batch_num=runtime.batch_num,
                remaining_fields=context.get_field_count(),
            )


class WriteRowOperatorExecutor(OperatorExecutor):
    """行写入算子执行器"""

    @override
    def execute(
        self,
        operator: SupportedOperatorIr,
        context: BatchContext,
        batch_row_nth: List[Hashable],
        runtime: ExecutionRuntime,
    ) -> None:
        op = cast("WriteRowOperatorIr", operator)  # pragma: allow-cast operator dispatch typed narrowing
        target_fields = list(op.target_fields)

        if not isinstance(runtime.sink, IRowSink):
            return

        for row_index, row_id in enumerate(batch_row_nth):
            row = build_row(context, row_id, target_fields)
            runtime.sink.write_row(row)

            runtime.instrumentation.emit_row_write(
                row_id=row_id,
                field_count=len(row),
                batch_num=runtime.batch_num,
                row_index=row_index,
            )


__all__ = ()
