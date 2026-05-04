from typing import Any, Tuple

import pytest

import scalim.execution.executor.operators.compute.executor as compute_impl
from scalim.execution.context import BatchContext, DenseBatchContext
from scalim.execution.runtime_bindings import RuntimeBindings
from scalim.planning.plan import ExecutionPlan
from scalim.spec.ir import CallBySpecIr, DerivedFieldIr, RuntimeHandleIdIr

from tests.fixtures.executor_operator_fixtures import _make_runtime


def _make_call_by_field(*, field_id: str, deps: Tuple[str, ...]) -> DerivedFieldIr:
    return DerivedFieldIr(
        field_id=field_id,
        name="Out",
        dependencies=deps,
        call_by=CallBySpecIr(reference=RuntimeHandleIdIr("noop")),
    )


@pytest.mark.parametrize(
    ("deps", "values"),
    [
        (("a",), (1,)),
        (("a", "b"), (1, 2)),
        (("a", "b", "c"), (1, 2, 3)),
        (("a", "b", "c", "d"), (1, 2, 3, 4)),
    ],
)
def test_execute_row_compute_dense_records_dep_cardinality_for_call_by(
    monkeypatch: pytest.MonkeyPatch,
    deps: Tuple[str, ...],
    values: Tuple[Any, ...],
) -> None:
    monkeypatch.setenv("SCALIM_PROBE_CALL_BY_DEP_CARDINALITY", "16")

    field_spec = _make_call_by_field(field_id="out", deps=deps)
    plan = ExecutionPlan(field_specs={field_spec.field_id: field_spec})
    runtime = _make_runtime(plan, None, runtime_bindings=RuntimeBindings(derived_calculators={"out": (lambda *_args, **_kwargs: "x")}))
    runtime.batch_num = 7

    ctx = DenseBatchContext(base_row_id=0, row_count=1, required_fields=set(deps) | {"out"})
    for dep_key, dep_value in zip(deps, values):
        ctx.set_field_value(str(dep_key), 0, dep_value)

    ok = compute_impl._execute_row_compute_dense(
        field_spec=field_spec,
        context=ctx,
        batch_row_nth=[0],
        runtime=runtime,
        compute_mode="full",
        wants_field_compute=False,
    )
    assert ok is True

    collector = runtime.call_by_dep_cardinality
    assert collector is not None
    stat = collector.stats_by_field["out"]
    assert stat.call_count == 1
    assert len(stat.unique_hashes) == 1


def test_execute_row_compute_dense_disables_probe_for_non_call_by(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCALIM_PROBE_CALL_BY_DEP_CARDINALITY", "16")

    field_spec = DerivedFieldIr(field_id="out", name="Out", dependencies=("a",), compute_expr="a")
    plan = ExecutionPlan(field_specs={field_spec.field_id: field_spec})
    runtime = _make_runtime(plan, None, runtime_bindings=RuntimeBindings(derived_calculators={"out": (lambda a: a)}))
    runtime.batch_num = 7

    ctx = DenseBatchContext(base_row_id=0, row_count=1, required_fields={"a", "out"})
    ctx.set_field_value("a", 0, 1)

    ok = compute_impl._execute_row_compute_dense(
        field_spec=field_spec,
        context=ctx,
        batch_row_nth=[0],
        runtime=runtime,
        compute_mode="full",
        wants_field_compute=False,
    )
    assert ok is True
    assert ctx.get_field_value("out", 0) == 1
    assert runtime.call_by_dep_cardinality is not None
    assert runtime.call_by_dep_cardinality.stats_by_field == {}


def test_execute_row_compute_records_dep_cardinality_for_call_by(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCALIM_PROBE_CALL_BY_DEP_CARDINALITY", "16")

    field_spec = _make_call_by_field(field_id="out", deps=("a",))
    plan = ExecutionPlan(field_specs={field_spec.field_id: field_spec})
    runtime = _make_runtime(plan, None, runtime_bindings=RuntimeBindings(derived_calculators={"out": (lambda a: int(a or 0) + 1)}))
    runtime.batch_num = 7

    ctx = BatchContext()
    ctx.set_field_value("a", 1, 10)

    compute_impl._execute_row_compute(
        field_spec=field_spec,
        context=ctx,
        batch_row_nth=[1],
        runtime=runtime,
        compute_mode="full",
        wants_field_compute=False,
    )
    assert ctx.get_field_value("out", 1) == 11

    collector = runtime.call_by_dep_cardinality
    assert collector is not None
    assert collector.stats_by_field["out"].call_count == 1


def test_execute_row_compute_disables_probe_for_non_call_by(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCALIM_PROBE_CALL_BY_DEP_CARDINALITY", "16")

    field_spec = DerivedFieldIr(field_id="out", name="Out", dependencies=("a",), compute_expr="a")
    plan = ExecutionPlan(field_specs={field_spec.field_id: field_spec})
    runtime = _make_runtime(plan, None, runtime_bindings=RuntimeBindings(derived_calculators={"out": (lambda a: int(a or 0) + 1)}))
    runtime.batch_num = 7

    ctx = BatchContext()
    ctx.set_field_value("a", 1, 10)

    compute_impl._execute_row_compute(
        field_spec=field_spec,
        context=ctx,
        batch_row_nth=[1],
        runtime=runtime,
        compute_mode="full",
        wants_field_compute=False,
    )
    assert ctx.get_field_value("out", 1) == 11
    assert runtime.call_by_dep_cardinality is not None
    assert runtime.call_by_dep_cardinality.stats_by_field == {}


def test_runtime_maybe_log_call_by_dep_cardinality_summary(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    monkeypatch.setenv("SCALIM_PROBE_CALL_BY_DEP_CARDINALITY", "16")

    field_spec = _make_call_by_field(field_id="out", deps=("a",))
    plan = ExecutionPlan(field_specs={field_spec.field_id: field_spec})
    runtime = _make_runtime(plan, None)

    collector = runtime.call_by_dep_cardinality
    assert collector is not None
    collector.record(field_key="out", dep_args=(1,))

    caplog.set_level("INFO")
    runtime.maybe_log_call_by_dep_cardinality_summary()
    assert "依赖元组去重摘要" in caplog.text


def test_runtime_maybe_log_call_by_dep_cardinality_summary_skips_empty(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("SCALIM_PROBE_CALL_BY_DEP_CARDINALITY", "16")

    field_spec = _make_call_by_field(field_id="out", deps=("a",))
    plan = ExecutionPlan(field_specs={field_spec.field_id: field_spec})
    runtime = _make_runtime(plan, None)

    caplog.set_level("INFO")
    runtime.maybe_log_call_by_dep_cardinality_summary()
    assert "依赖元组去重摘要" not in caplog.text
