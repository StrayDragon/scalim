from types import SimpleNamespace

from scalim.events import EventType
from scalim.events._events import OperatorSpanEvent
from scalim.execution.context import BatchContext
from scalim.execution.executor.batch.executor import BatchExecutor
from scalim.execution.pipeline.base.pipeline import Pipeline
from scalim.execution.runtime_bindings import RuntimeBindings
from scalim.ob.hub import InstrumentationHub
from scalim.ob.manager import ObserverManager
from scalim.ob.observer import EventDispatchObserver
from scalim.planning.builder_helpers.fusion_groups import ComputeFusionGroup
from scalim.planning.operators import ComputeOperatorIr, OperatorType
from scalim.spec.ir import DerivedFieldIr


def test_instrumentation_hub_emit_operator_span_wants_gated() -> None:
    hub = InstrumentationHub()
    hub.emit_operator_span("compute", field_key="a", batch_num=1, duration=0.1)

    class _Observer(EventDispatchObserver):
        event_types = {EventType.OPERATOR_SPAN}

        def __init__(self) -> None:
            self.payloads = []

        def on_operator_span(self, event) -> None:  # type: ignore[override]
            self.payloads.append(event.payload)

    obs = _Observer()
    hub = InstrumentationHub(observer_manager=ObserverManager(observers=[obs]))
    hub.emit_operator_span("compute", field_key="a", batch_num=2, duration=0.2)
    assert obs.payloads and obs.payloads[0].batch_num == 2


def test_pipeline_iter_row_batches_records_stream_duration_when_unbatched_and_wanted() -> None:
    times = [1.0, 2.5]

    def _perf_counter():  # type: ignore[no-untyped-def]
        return times.pop(0)

    class _Instr:
        def wants(self, event_type):  # type: ignore[no-untyped-def]
            return event_type == EventType.STAGE_SPAN

    fake_self = SimpleNamespace(
        batch_size=None,
        runtime=SimpleNamespace(instrumentation=_Instr()),
        _overrides=SimpleNamespace(stage_perf_counter_fn=_perf_counter, chunk_iterable=None),
    )

    batches = list(Pipeline._iter_row_batches(fake_self, [{"x": 1}, {"x": 2}]))
    assert len(batches) == 1
    _row_ids, _row_map, stream_duration_s = batches[0]
    assert stream_duration_s == 1.5


def test_batch_executor_emits_operator_span_for_compute_when_wanted() -> None:
    times = [10.0, 11.0]

    def _perf_counter():  # type: ignore[no-untyped-def]
        return times.pop(0)

    class _Instr:
        def __init__(self) -> None:
            self.spans = []

        def wants(self, event_type):  # type: ignore[no-untyped-def]
            return event_type == EventType.OPERATOR_SPAN

        def emit_operator_span(self, **kwargs):  # type: ignore[no-untyped-def]
            self.spans.append(kwargs)

    class _Exec:
        def execute(self, operator, context, batch_row_nth, runtime):  # type: ignore[no-untyped-def]
            _ = (operator, context, batch_row_nth, runtime)

    runtime = SimpleNamespace(instrumentation=_Instr(), parallel_mode="seq", batch_num=7)
    plan = SimpleNamespace(
        operators=[
            ComputeOperatorIr(
                operator_id="op1",
                operator_type=OperatorType.COMPUTE.value,
                field_key="a",
                input_fields=(),
            )
        ],
        compute_fusion_groups=(),
    )
    fake_self = SimpleNamespace(
        plan=plan,
        _executors={OperatorType.COMPUTE.value: _Exec()},
        _overrides=SimpleNamespace(stage_perf_counter_fn=_perf_counter),
    )

    _ = BatchExecutor.execute_operators(
        fake_self,
        context=object(),
        batch_row_nth=[0],
        runtime=runtime,
        required_fields=None,
        adaptive_pool=None,
        after_operator=None,
    )
    assert runtime.instrumentation.spans and runtime.instrumentation.spans[0]["field_key"] == "a"


def test_batch_executor_accumulates_compute_stage_duration_for_fused_group() -> None:
    times = [20.0, 21.5]

    def _perf_counter():  # type: ignore[no-untyped-def]
        return times.pop(0)

    class _Instr:
        def wants(self, event_type):  # type: ignore[no-untyped-def]
            return event_type == EventType.STAGE_SPAN

    class _Guardrails:
        enabled = False

        def effective_compute_mode(self):  # type: ignore[no-untyped-def]
            return "full"

    field_specs = {key: DerivedFieldIr(field_id=key, name=key, dependencies=("v",), compute_expr="v + 1") for key in ("a", "b")}
    runtime = SimpleNamespace(
        instrumentation=_Instr(),
        parallel_mode="seq",
        batch_num=7,
        sink=None,
        guardrails=_Guardrails(),
        call_by_memoization=None,
        late_fields=frozenset(),
        field_specs=field_specs,
        runtime_bindings=RuntimeBindings(derived_calculators={"a": (lambda v: int(v) + 1), "b": (lambda v: int(v) + 2)}),
    )
    plan = SimpleNamespace(
        operators=[
            ComputeOperatorIr(operator_id="op-a", operator_type=OperatorType.COMPUTE.value, field_key="a", input_fields=()),
            ComputeOperatorIr(operator_id="op-b", operator_type=OperatorType.COMPUTE.value, field_key="b", input_fields=()),
        ],
        compute_fusion_groups=(ComputeFusionGroup(segment="pre_ref", field_keys=("a", "b"), deps=("v",)),),
    )
    fake_self = SimpleNamespace(
        plan=plan,
        _executors={},
        _overrides=SimpleNamespace(stage_perf_counter_fn=_perf_counter),
    )

    context = BatchContext()
    context.set_field_value("v", 0, 10)
    seen = []

    stage_durations = BatchExecutor.execute_operators(
        fake_self,
        context=context,
        batch_row_nth=[0],
        runtime=runtime,
        required_fields=None,
        adaptive_pool=None,
        after_operator=seen.append,
    )

    assert stage_durations == {"loader": 0.0, "compute": 1.5, "write": 0.0}
    assert context.get_field_value("a", 0) == 11
    assert context.get_field_value("b", 0) == 12
    # 组内两个 `compute` 算子都要继续回调 `after_operator`,但计时只发生一次.
    assert len(seen) == 2
