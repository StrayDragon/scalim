"""执行器算子测试:`write`."""

from scalim.execution.context import BatchContext
from scalim.execution.executor.operators.write import WriteColumnOperatorExecutor, WriteRowOperatorExecutor
from scalim.hooks.base import HookManager
from scalim.planning.operators import OperatorType, WriteColumnOperatorIr, WriteRowOperatorIr
from scalim.planning.plan import ExecutionPlan
from scalim.sinks.sink_memory import InMemoryColumnSink, InMemoryRowSink

from .fixtures.executor_operator_fixtures import _CaptureHook, _make_runtime


def test_write_column_operator_writes_column_and_emits_hooks() -> None:
    hook = _CaptureHook()
    hook_manager = HookManager()
    hook_manager.register(hook)

    runtime = _make_runtime(ExecutionPlan(), None, hook_manager=hook_manager)
    runtime.batch_num = 4

    context = BatchContext()
    context.set_field_value("amount", 1, 100)
    context.set_field_value("amount", 2, 200)

    runtime.sink = InMemoryRowSink()
    WriteColumnOperatorExecutor().execute(
        WriteColumnOperatorIr(
            operator_id="write_amount",
            operator_type=OperatorType.WRITE_COLUMN.value,
            field_key="amount",
            can_release_after=True,
        ),
        context,
        [1, 2],
        runtime,
    )
    assert context.has_field("amount") is True

    runtime.sink = InMemoryColumnSink()
    WriteColumnOperatorExecutor().execute(
        WriteColumnOperatorIr(
            operator_id="write_amount",
            operator_type=OperatorType.WRITE_COLUMN.value,
            field_key="amount",
            can_release_after=True,
        ),
        context,
        [1, 2],
        runtime,
    )

    assert context.has_field("amount") is False
    assert runtime.sink.get_column("amount")[1] == 100
    assert len(hook.column_writes) == 1
    assert len(hook.field_slims) == 1


def test_write_row_operator_writes_rows() -> None:
    hook = _CaptureHook()
    hook_manager = HookManager()
    hook_manager.register(hook)

    runtime = _make_runtime(ExecutionPlan(), None, hook_manager=hook_manager)
    runtime.batch_num = 2

    context = BatchContext()
    context.set_field_value("name", 1, "Alice")
    context.set_field_value("age", 1, 30)
    context.set_field_value("name", 2, "Bob")
    context.set_field_value("age", 2, 31)

    runtime.sink = InMemoryColumnSink()
    WriteRowOperatorExecutor().execute(
        WriteRowOperatorIr(
            operator_id="write_rows",
            operator_type=OperatorType.WRITE_ROW.value,
            target_fields=("name", "age"),
        ),
        context,
        [1, 2],
        runtime,
    )
    assert hook.row_writes == []

    runtime.sink = InMemoryRowSink()
    WriteRowOperatorExecutor().execute(
        WriteRowOperatorIr(
            operator_id="write_rows",
            operator_type=OperatorType.WRITE_ROW.value,
            target_fields=("name", "age"),
        ),
        context,
        [1, 2],
        runtime,
    )

    assert runtime.sink.get_data() == [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 31}]
    assert len(hook.row_writes) == 2
