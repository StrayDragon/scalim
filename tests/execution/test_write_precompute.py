"""write-precompute(延迟物化)执行契约.

对应 specs: `execution-hotpath-fastpaths` r38 / r579 / r950 / r951 / r952 / r953 / r954.
"""

from typing import Any, Callable, Dict, List, Optional, Sequence

import pytest

from scalim.events import Event, EventType
from scalim.execution.compute_phase import COMPUTE_PHASE_META_KEY, COMPUTE_PHASE_OPERATOR, COMPUTE_PHASE_WRITE_PRECOMPUTE
from scalim.execution.engine import ScalimEngine
from scalim.execution.guardrails import GuardrailsPolicy, ScalimGuardrailViolationError
from scalim.execution.runtime_bindings import RuntimeBindings
from scalim.ob.manager import ObserverManager
from scalim.ob.observer import Observer
from scalim.planning import PlanBuilder
from scalim.planning.plan import ExecutionPlan
from scalim.sinks.memory import InMemoryColumnSink, InMemoryRowDataSink
from scalim.spec.ir import (
    CallBySpecIr,
    CallByValueIr,
    DemandIr,
    DerivedFieldIr,
    FieldIr,
    RuntimeHandleIdIr,
)

from tests.fixtures.planning_fixtures import make_main_source

_ROWS = [{"order_id": i, "amount": float(i), "cost": float(i % 3)} for i in range(7)]


class _CapturingObserver(Observer):
    event_types = {EventType.FIELD_COMPUTE, EventType.ROW_RELEASE}

    def __init__(self) -> None:
        self.events: List[Event] = []

    def on_event(self, event: Event) -> None:
        self.events.append(event)


def _make_sink(sink_kind: str, targets: Sequence[str]) -> Any:
    if sink_kind == "row":
        return InMemoryRowDataSink()
    return InMemoryColumnSink(field_names=list(targets))


def _sink_rows(sink: Any) -> List[Dict[str, Any]]:
    if isinstance(sink, InMemoryColumnSink):
        return list(sink.get_rows())
    return list(sink.get_data())


def _call_by(field_id: str, dep_fields: Sequence[str]) -> CallBySpecIr:
    return CallBySpecIr(
        reference=RuntimeHandleIdIr(handle_id="derived.{}".format(field_id)),
        args=tuple(CallByValueIr(kind="field", value=dep) for dep in dep_fields),
        field_names=tuple(dep_fields),
    )


def _build_demand(
    *,
    chain_depth: int = 2,
    with_ctx_field: bool = False,
    failing_late: bool = False,
    calls: Optional[Dict[str, int]] = None,
) -> "tuple[DemandIr, RuntimeBindings, List[str]]":
    """构造 “主源直取 + 平坦 late 派生 + 链式 late 派生” 的最小需求."""
    main = make_main_source("orders")
    fields: List[Any] = [
        FieldIr(field_id="order_id", name="订单ID", source_id=main.source_id, is_primary=True),
        FieldIr(field_id="amount", name="金额", source_id=main.source_id),
        FieldIr(field_id="cost", name="成本", source_id=main.source_id),
    ]
    targets = ["order_id", "amount", "cost"]
    calculators: Dict[str, Callable[..., Any]] = {}

    def _counted(field_id: str, fn: Callable[..., Any]) -> Callable[..., Any]:
        if calls is None:
            return fn

        def _wrapped(*args: Any) -> Any:
            calls[field_id] = calls.get(field_id, 0) + 1
            return fn(*args)

        return _wrapped

    fields.append(
        DerivedFieldIr(
            field_id="profit",
            name="利润",
            dependencies=("amount", "cost"),
            call_by=_call_by("profit", ["amount", "cost"]),
        )
    )
    calculators["profit"] = _counted("profit", lambda a, b: float(a) - float(b))
    targets.append("profit")

    if failing_late:
        fields.append(
            DerivedFieldIr(
                field_id="boom",
                name="炸弹",
                dependencies=("amount",),
                call_by=_call_by("boom", ["amount"]),
            )
        )

        def _boom(value: Any) -> Any:
            if float(value) >= 3.0:
                msg = "boom"
                raise ValueError(msg)
            return float(value)

        calculators["boom"] = _counted("boom", _boom)
        targets.append("boom")

    prev = "amount"
    for depth in range(chain_depth):
        field_id = "c{}".format(depth)
        fields.append(
            DerivedFieldIr(
                field_id=field_id,
                name=field_id,
                dependencies=(prev,),
                compute_expr="{} + 1".format(prev),
            )
        )
        calculators[field_id] = _counted(field_id, lambda value: float(value) + 1.0)
        targets.append(field_id)
        prev = field_id

    if with_ctx_field:
        fields.append(
            DerivedFieldIr(
                field_id="tagged",
                name="带上下文",
                dependencies=("amount",),
                call_by=_call_by("tagged", ["amount"]),
                call_ctx_key="$ctx",
            )
        )
        calculators["tagged"] = _counted("tagged", lambda value, ctx=None: "{}@{}".format(value, ctx.field_id))
        targets.append("tagged")

    demand = DemandIr.from_irs(sources=[], fields=fields, main_source=main)
    return demand, RuntimeBindings(derived_calculators=calculators), targets


def _make_engine(
    demand: DemandIr,
    plan: ExecutionPlan,
    bindings: RuntimeBindings,
    *,
    guardrails: Optional[GuardrailsPolicy] = None,
    observer_manager: Optional[ObserverManager] = None,
) -> ScalimEngine:
    return ScalimEngine(
        demand=demand,
        plan=plan,
        runtime_bindings=bindings,
        batch_size=3,
        guardrails=guardrails,
        observer_manager=observer_manager,
    )


def test_row_sink_output_matches_eager_batch_path() -> None:
    demand, bindings, targets = _build_demand(chain_depth=3, with_ctx_field=True)
    plan = PlanBuilder(demand).build(targets=targets)
    assert plan.late_fields

    eager_rows = list(_make_engine(demand, plan, bindings).run(main_rows=list(_ROWS)))

    with InMemoryRowDataSink() as sink:
        _make_engine(demand, plan, bindings).run(main_rows=list(_ROWS), sink=sink)
        late_rows = list(sink.get_data())

    assert late_rows == eager_rows


def test_column_sink_output_matches_eager_batch_path() -> None:
    demand, bindings, targets = _build_demand(chain_depth=3, with_ctx_field=True)
    plan = PlanBuilder(demand).build(targets=targets)
    assert plan.late_fields

    eager_rows = list(_make_engine(demand, plan, bindings).run(main_rows=list(_ROWS)))

    with InMemoryColumnSink(field_names=list(targets)) as sink:
        _make_engine(demand, plan, bindings).run(main_rows=list(_ROWS), sink=sink)
        late_rows = list(sink.get_rows())

    assert late_rows == eager_rows


@pytest.mark.parametrize("sink_kind", ["row", "column"])
def test_late_chain_materializes_in_topological_order(sink_kind: str) -> None:
    demand, bindings, targets = _build_demand(chain_depth=4)
    plan = PlanBuilder(demand).build(targets=targets)
    assert plan.late_fields == ("c0", "c1", "c2", "c3", "profit")

    if sink_kind == "row":
        with InMemoryRowDataSink() as row_sink:
            _make_engine(demand, plan, bindings).run(main_rows=list(_ROWS), sink=row_sink)
            rows = list(row_sink.get_data())
    else:
        with InMemoryColumnSink(field_names=list(targets)) as column_sink:
            _make_engine(demand, plan, bindings).run(main_rows=list(_ROWS), sink=column_sink)
            rows = list(column_sink.get_rows())

    for idx, row in enumerate(rows):
        amount = float(idx)
        assert row["c0"] == amount + 1
        assert row["c1"] == amount + 2
        assert row["c2"] == amount + 3
        assert row["c3"] == amount + 4


@pytest.mark.parametrize("sink_kind", ["row", "column"])
def test_late_calculator_call_count_matches_eager(sink_kind: str) -> None:
    eager_calls: Dict[str, int] = {}
    demand, bindings, targets = _build_demand(chain_depth=2, calls=eager_calls)
    plan = PlanBuilder(demand).build(targets=targets)
    _make_engine(demand, plan, bindings).run(main_rows=list(_ROWS))

    late_calls: Dict[str, int] = {}
    demand2, bindings2, targets2 = _build_demand(chain_depth=2, calls=late_calls)
    plan2 = PlanBuilder(demand2).build(targets=targets2)
    if sink_kind == "row":
        with InMemoryRowDataSink() as row_sink:
            _make_engine(demand2, plan2, bindings2).run(main_rows=list(_ROWS), sink=row_sink)
    else:
        with InMemoryColumnSink(field_names=list(targets2)) as column_sink:
            _make_engine(demand2, plan2, bindings2).run(main_rows=list(_ROWS), sink=column_sink)

    assert late_calls == eager_calls
    assert late_calls["profit"] == len(_ROWS)


@pytest.mark.parametrize("sink_kind", ["row", "column"])
def test_field_compute_events_carry_compute_phase_meta(sink_kind: str) -> None:
    demand, bindings, targets = _build_demand(chain_depth=1, with_ctx_field=True)
    plan = PlanBuilder(demand).build(targets=targets)
    observer = _CapturingObserver()

    with _make_sink(sink_kind, targets) as sink:
        _make_engine(
            demand,
            plan,
            bindings,
            observer_manager=ObserverManager(observers=[observer]),
        ).run(main_rows=list(_ROWS), sink=sink)

    phases: Dict[str, set] = {}
    for event in observer.events:
        if event.event_type is not EventType.FIELD_COMPUTE:
            continue
        phases.setdefault(event.payload.field_key, set()).add(event.meta.get(COMPUTE_PHASE_META_KEY))

    assert phases["profit"] == {COMPUTE_PHASE_WRITE_PRECOMPUTE}
    assert phases["c0"] == {COMPUTE_PHASE_WRITE_PRECOMPUTE}
    # 含 `$ctx` 的 `call_by` 必须留在 `compute` 算子段.
    assert phases["tagged"] == {COMPUTE_PHASE_OPERATOR}


def test_late_results_are_not_written_back_to_batch_context() -> None:
    demand, bindings, targets = _build_demand(chain_depth=1)
    plan = PlanBuilder(demand).build(targets=targets)
    observer = _CapturingObserver()

    with InMemoryRowDataSink() as sink:
        _make_engine(
            demand,
            plan,
            bindings,
            observer_manager=ObserverManager(observers=[observer]),
        ).run(main_rows=list(_ROWS), sink=sink)

    released: set = set()
    for event in observer.events:
        if event.event_type is EventType.ROW_RELEASE:
            released.update(event.payload.released_fields)

    assert released
    assert "profit" not in released
    assert "c0" not in released
    assert "amount" in released


def test_no_field_compute_tax_without_subscribers() -> None:
    demand, bindings, targets = _build_demand(chain_depth=1)
    plan = PlanBuilder(demand).build(targets=targets)
    engine = _make_engine(demand, plan, bindings)

    with InMemoryRowDataSink() as sink:
        engine.run(main_rows=list(_ROWS), sink=sink)
        rows = list(sink.get_data())

    assert len(rows) == len(_ROWS)
    assert not engine._pipeline.runtime.instrumentation.wants(EventType.FIELD_COMPUTE)  # noqa: SLF001


@pytest.mark.parametrize("sink_kind", ["row", "column"])
def test_quiet_mode_degrades_failed_late_cells_to_none(sink_kind: str) -> None:
    demand, bindings, targets = _build_demand(chain_depth=1, failing_late=True)
    plan = PlanBuilder(demand).build(targets=targets)
    assert "boom" in plan.late_fields

    guardrails = GuardrailsPolicy(enabled=True, mode="quiet")
    with _make_sink(sink_kind, targets) as sink:
        _make_engine(demand, plan, bindings, guardrails=guardrails).run(main_rows=list(_ROWS), sink=sink)
        rows = _sink_rows(sink)

    assert len(rows) == len(_ROWS)
    assert [row["boom"] for row in rows] == [0.0, 1.0, 2.0, None, None, None, None]


@pytest.mark.parametrize("sink_kind", ["row", "column"])
def test_fast_fail_discards_sink_on_late_compute_error(sink_kind: str) -> None:
    demand, bindings, targets = _build_demand(chain_depth=1, failing_late=True)
    plan = PlanBuilder(demand).build(targets=targets)

    guardrails = GuardrailsPolicy(enabled=True, mode="fast_fail")
    sink = _make_sink(sink_kind, targets)
    with pytest.raises(ScalimGuardrailViolationError):
        _make_engine(demand, plan, bindings, guardrails=guardrails).run(main_rows=list(_ROWS), sink=sink)

    assert _sink_rows(sink) == []
