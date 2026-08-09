from types import SimpleNamespace

from scalim.execution.executor.batch.executor import BatchExecutor
from scalim.execution.pipeline.overrides import PipelineOverrides


def test_try_execute_fused_compute_stage_spans_without_write_clock() -> None:
    """`wants_stage_spans` 且无挂载 clock 时走 72/85 假分支."""
    from scalim.execution.context import BatchContext
    from scalim.execution.executor.batch.executor import _try_execute_fused_compute
    from scalim.execution.runtime_bindings import RuntimeBindings
    from scalim.planning.builder_helpers.fusion_groups import ComputeFusionGroup
    from scalim.planning.operators import OperatorType
    from scalim.spec.ir import DerivedFieldIr

    class _Guardrails:
        enabled = False

        def effective_compute_mode(self):  # type: ignore[no-untyped-def]
            return "full"

    field_specs = {key: DerivedFieldIr(field_id=key, name=key, dependencies=("v",), compute_expr="v + 1") for key in ("a", "b")}
    runtime = SimpleNamespace(
        late_fields=frozenset(),
        field_specs=field_specs,
        guardrails=_Guardrails(),
        call_by_memoization=None,
        runtime_bindings=RuntimeBindings(derived_calculators={"a": (lambda v: int(v) + 1), "b": (lambda v: int(v) + 2)}),
        batch_num=1,
        sink=None,
        instrumentation=SimpleNamespace(
            emit_operator_span=lambda **_k: None,
            wants=lambda _et: False,
        ),
    )
    group = ComputeFusionGroup(segment="pre_ref", field_keys=("a", "b"), deps=("v",))
    context = BatchContext()
    context.set_field_value("v", 0, 10)
    stage_durations = {"compute": 0.0}
    ok = _try_execute_fused_compute(
        field_key="a",
        fusion_by_field={"a": group, "b": group},
        fused_done=set(),
        context=context,
        batch_row_nth=[0],
        runtime=runtime,  # type: ignore[arg-type]
        wants_stage_spans=True,
        stage_map={OperatorType.COMPUTE.value: "compute"},
        stage_durations=stage_durations,
        stage_perf_counter_fn=None,
    )
    assert ok is True
    assert context.get_field_value("a", 0) == 11
    assert stage_durations["compute"] >= 0.0


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
    executor.plan = SimpleNamespace(operators=[operator], compute_fusion_groups=())  # type: ignore[assignment]
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
