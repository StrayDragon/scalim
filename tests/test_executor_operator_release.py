"""Executor operator tests: release."""

from scalim.execution.context import BatchContext
from scalim.execution.executor.operators.release import ReleaseOperatorExecutor
from scalim.hooks.base import HookManager
from scalim.planning.operators import OperatorType, ReleaseOperatorIr
from scalim.planning.plan import ExecutionPlan
from scalim.sinks.sink_memory import InMemoryColumnSink

from .fixtures.executor_operator_fixtures import _CaptureHook, _make_runtime


def test_release_operator_deletes_field_and_emits_field_slim() -> None:
    hook = _CaptureHook()
    hook_manager = HookManager()
    hook_manager.register(hook)

    runtime = _make_runtime(ExecutionPlan(), None, hook_manager=hook_manager)
    runtime.sink = InMemoryColumnSink()
    runtime.batch_num = 4

    context = BatchContext()
    context.set_field_value("status", 1, "ok")

    release_op = ReleaseOperatorIr(
        operator_id="release_status",
        operator_type=OperatorType.RELEASE.value,
        field_key="status",
        reason="done",
    )
    ReleaseOperatorExecutor().execute(release_op, context, [1], runtime)

    assert context.has_field("status") is False
    assert len(hook.field_slims) == 1
