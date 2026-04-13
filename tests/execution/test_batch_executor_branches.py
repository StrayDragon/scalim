from types import SimpleNamespace

from scalim.execution.executor.batch.executor import BatchExecutor
from scalim.execution.pipeline.overrides import PipelineOverrides


def test_batch_executor_still_calls_after_operator_when_executor_is_missing() -> None:
    class _InstrumentationStub:
        def wants(self, _event_type: str) -> bool:
            return False

    class _RuntimeStub:
        def __init__(self) -> None:
            self.instrumentation = _InstrumentationStub()
            self.parallel_mode = "seq"

    runtime = _RuntimeStub()
    operator = SimpleNamespace(operator_type="unknown")

    executor = BatchExecutor.__new__(BatchExecutor)
    executor.plan = SimpleNamespace(operators=[operator])  # type: ignore[assignment]
    executor._executors = {}  # type: ignore[attr-defined]
    executor._overrides = PipelineOverrides()  # type: ignore[attr-defined]

    seen = []
    executor.execute_operators(  # type: ignore[arg-type]
        context=object(),
        batch_row_nth=[1],
        runtime=runtime,  # type: ignore[arg-type]
        required_fields=None,
        adaptive_pool=None,
        after_operator=seen.append,
    )

    assert seen == [operator]

