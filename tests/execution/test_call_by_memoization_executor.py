import pytest

from scalim.execution.context import BatchContext, DenseBatchContext
from scalim.execution.executor.operators.compute.executor import ComputeOperatorExecutor
from scalim.execution.runtime_bindings import RuntimeBindings
from scalim.planning.operators import ComputeOperatorIr, OperatorType
from scalim.planning.plan import ExecutionPlan
from scalim.spec.ir import CallBySpecIr, CallByValueIr, DerivedFieldIr, RuntimeHandleIdIr

from tests.fixtures.executor_operator_fixtures import _make_runtime


def _make_call_by_field(field_id: str, *, deps) -> DerivedFieldIr:  # type: ignore[no-untyped-def]
    return DerivedFieldIr(
        field_id=field_id,
        name=field_id,
        dependencies=tuple(deps),
        call_by=CallBySpecIr(
            reference=RuntimeHandleIdIr(handle_id="derived.{}".format(field_id)),
            args=tuple(CallByValueIr(kind="field", value=dep) for dep in tuple(deps)),
            field_names=tuple(deps),
        ),
    )


def _make_compute_op(field_id: str, *, deps) -> ComputeOperatorIr:  # type: ignore[no-untyped-def]
    return ComputeOperatorIr(
        operator_id="compute_{}".format(field_id),
        operator_type=OperatorType.COMPUTE.value,
        field_key=field_id,
        input_fields=tuple(deps),
    )


def test_call_by_memoization_reuses_ctx_free_results_dense(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCALIM_EXP_CALL_BY_MEMOIZE_MAX_ENTRIES", "16")

    calls = {"n": 0}

    def _calc(amount):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        return amount * 2

    field_spec = _make_call_by_field("score", deps=("amount",))
    operator = _make_compute_op("score", deps=("amount",))

    runtime_bindings = RuntimeBindings(derived_calculators={"score": _calc})
    runtime = _make_runtime(ExecutionPlan(field_specs={"score": field_spec}), None, runtime_bindings=runtime_bindings)

    context = DenseBatchContext(base_row_id=1, row_count=4)
    for row_id in (1, 2, 3, 4):
        context.set_field_value("amount", row_id, 10)

    ComputeOperatorExecutor().execute(operator, context, [1, 2, 3, 4], runtime)
    assert calls["n"] == 1
    assert context.get_field_value("score", 1) == 20
    assert context.get_field_value("score", 4) == 20


def test_call_by_memoization_deny_filter_disables_field(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCALIM_EXP_CALL_BY_MEMOIZE_MAX_ENTRIES", "16")
    monkeypatch.setenv("SCALIM_EXP_CALL_BY_MEMOIZE_DENY", "score")

    calls = {"n": 0}

    def _calc(amount):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        return amount * 2

    field_spec = _make_call_by_field("score", deps=("amount",))
    operator = _make_compute_op("score", deps=("amount",))
    runtime_bindings = RuntimeBindings(derived_calculators={"score": _calc})
    runtime = _make_runtime(ExecutionPlan(field_specs={"score": field_spec}), None, runtime_bindings=runtime_bindings)

    context = DenseBatchContext(base_row_id=1, row_count=4)
    for row_id in (1, 2, 3, 4):
        context.set_field_value("amount", row_id, 10)

    ComputeOperatorExecutor().execute(operator, context, [1, 2, 3, 4], runtime)
    assert calls["n"] == 4


def test_call_by_memoization_protection_disables_low_hit_rate_field(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCALIM_EXP_CALL_BY_MEMOIZE_MAX_ENTRIES", "2")

    calls = {"n": 0}

    def _calc(amount):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        return amount * 2

    field_spec = _make_call_by_field("score", deps=("amount",))
    operator = _make_compute_op("score", deps=("amount",))
    runtime_bindings = RuntimeBindings(derived_calculators={"score": _calc})
    runtime = _make_runtime(ExecutionPlan(field_specs={"score": field_spec}), None, runtime_bindings=runtime_bindings)

    context = DenseBatchContext(base_row_id=1, row_count=12)
    row_ids = list(range(1, 13))
    for row_id in row_ids:
        context.set_field_value("amount", row_id, row_id)  # unique per row

    ComputeOperatorExecutor().execute(operator, context, row_ids, runtime)

    memo = runtime.call_by_memoization
    assert memo is not None
    cache = memo.get_or_create_field_cache("score")
    assert cache.disabled_reason == "low_hit_rate"
    assert calls["n"] == 12


def test_call_by_memoization_log_stats_is_opt_in(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    monkeypatch.setenv("SCALIM_EXP_CALL_BY_MEMOIZE_MAX_ENTRIES", "16")
    monkeypatch.setenv("SCALIM_EXP_CALL_BY_MEMOIZE_LOG_STATS", "1")

    def _calc(amount):  # type: ignore[no-untyped-def]
        return amount * 2

    field_spec = _make_call_by_field("score", deps=("amount",))
    operator = _make_compute_op("score", deps=("amount",))
    runtime_bindings = RuntimeBindings(derived_calculators={"score": _calc})
    runtime = _make_runtime(ExecutionPlan(field_specs={"score": field_spec}), None, runtime_bindings=runtime_bindings)

    context = DenseBatchContext(base_row_id=1, row_count=4)
    for row_id in (1, 2, 3, 4):
        context.set_field_value("amount", row_id, 10)

    ComputeOperatorExecutor().execute(operator, context, [1, 2, 3, 4], runtime)

    caplog.set_level("INFO", logger="scalim.performance")
    runtime.maybe_log_call_by_memoization_summary()

    assert any("记忆化摘要" in rec.message for rec in caplog.records)
    assert any("score" in rec.message for rec in caplog.records)


def test_call_by_memoization_log_stats_disabled_emits_nothing(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    monkeypatch.setenv("SCALIM_EXP_CALL_BY_MEMOIZE_MAX_ENTRIES", "16")

    def _calc(amount):  # type: ignore[no-untyped-def]
        return amount * 2

    field_spec = _make_call_by_field("score", deps=("amount",))
    operator = _make_compute_op("score", deps=("amount",))
    runtime_bindings = RuntimeBindings(derived_calculators={"score": _calc})
    runtime = _make_runtime(ExecutionPlan(field_specs={"score": field_spec}), None, runtime_bindings=runtime_bindings)

    context = DenseBatchContext(base_row_id=1, row_count=2)
    context.set_field_value("amount", 1, 10)
    context.set_field_value("amount", 2, 10)
    ComputeOperatorExecutor().execute(operator, context, [1, 2], runtime)

    caplog.set_level("INFO", logger="scalim.performance")
    runtime.maybe_log_call_by_memoization_summary()
    assert not any("记忆化摘要" in rec.message for rec in caplog.records)


def test_call_by_memoization_reuses_ctx_free_results_dense_two_deps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCALIM_EXP_CALL_BY_MEMOIZE_MAX_ENTRIES", "16")

    calls = {"n": 0}

    def _calc(a, b):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        return (a or 0) + (b or 0)

    field_spec = _make_call_by_field("sum2", deps=("a", "b"))
    operator = _make_compute_op("sum2", deps=("a", "b"))
    runtime_bindings = RuntimeBindings(derived_calculators={"sum2": _calc})
    runtime = _make_runtime(ExecutionPlan(field_specs={"sum2": field_spec}), None, runtime_bindings=runtime_bindings)

    context = DenseBatchContext(base_row_id=1, row_count=4)
    for row_id in (1, 2, 3, 4):
        context.set_field_value("a", row_id, 1)
        context.set_field_value("b", row_id, 2)

    ComputeOperatorExecutor().execute(operator, context, [1, 2, 3, 4], runtime)
    assert calls["n"] == 1
    assert context.get_field_value("sum2", 1) == 3


def test_call_by_memoization_dense_two_deps_unhashable_key_does_not_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCALIM_EXP_CALL_BY_MEMOIZE_MAX_ENTRIES", "16")

    calls = {"n": 0}

    def _calc(a, b):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        return 1

    field_spec = _make_call_by_field("sum2", deps=("a", "b"))
    operator = _make_compute_op("sum2", deps=("a", "b"))
    runtime_bindings = RuntimeBindings(derived_calculators={"sum2": _calc})
    runtime = _make_runtime(ExecutionPlan(field_specs={"sum2": field_spec}), None, runtime_bindings=runtime_bindings)

    context = DenseBatchContext(base_row_id=1, row_count=4)
    for row_id in (1, 2, 3, 4):
        context.set_field_value("a", row_id, {"k": "v"})
        context.set_field_value("b", row_id, 2)

    ComputeOperatorExecutor().execute(operator, context, [1, 2, 3, 4], runtime)
    assert calls["n"] == 4
    assert context.get_field_value("sum2", 1) == 1


def test_call_by_memoization_reuses_ctx_free_results_dense_three_deps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCALIM_EXP_CALL_BY_MEMOIZE_MAX_ENTRIES", "16")

    calls = {"n": 0}

    def _calc(a, b, c):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        return (a or 0) + (b or 0) + (c or 0)

    field_spec = _make_call_by_field("sum3", deps=("a", "b", "c"))
    operator = _make_compute_op("sum3", deps=("a", "b", "c"))
    runtime_bindings = RuntimeBindings(derived_calculators={"sum3": _calc})
    runtime = _make_runtime(ExecutionPlan(field_specs={"sum3": field_spec}), None, runtime_bindings=runtime_bindings)

    context = DenseBatchContext(base_row_id=1, row_count=4)
    for row_id in (1, 2, 3, 4):
        context.set_field_value("a", row_id, 1)
        context.set_field_value("b", row_id, 2)
        context.set_field_value("c", row_id, 3)

    ComputeOperatorExecutor().execute(operator, context, [1, 2, 3, 4], runtime)
    assert calls["n"] == 1
    assert context.get_field_value("sum3", 1) == 6


def test_call_by_memoization_dense_three_deps_unhashable_key_does_not_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCALIM_EXP_CALL_BY_MEMOIZE_MAX_ENTRIES", "16")

    calls = {"n": 0}

    def _calc(a, b, c):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        return 1

    field_spec = _make_call_by_field("sum3", deps=("a", "b", "c"))
    operator = _make_compute_op("sum3", deps=("a", "b", "c"))
    runtime_bindings = RuntimeBindings(derived_calculators={"sum3": _calc})
    runtime = _make_runtime(ExecutionPlan(field_specs={"sum3": field_spec}), None, runtime_bindings=runtime_bindings)

    context = DenseBatchContext(base_row_id=1, row_count=4)
    for row_id in (1, 2, 3, 4):
        context.set_field_value("a", row_id, {"k": "v"})
        context.set_field_value("b", row_id, 2)
        context.set_field_value("c", row_id, 3)

    ComputeOperatorExecutor().execute(operator, context, [1, 2, 3, 4], runtime)
    assert calls["n"] == 4
    assert context.get_field_value("sum3", 1) == 1


def test_call_by_memoization_reuses_ctx_free_results_dense_many_deps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCALIM_EXP_CALL_BY_MEMOIZE_MAX_ENTRIES", "16")

    calls = {"n": 0}

    def _calc(a, b, c, d):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        return (a or 0) + (b or 0) + (c or 0) + (d or 0)

    field_spec = _make_call_by_field("sum4", deps=("a", "b", "c", "d"))
    operator = _make_compute_op("sum4", deps=("a", "b", "c", "d"))
    runtime_bindings = RuntimeBindings(derived_calculators={"sum4": _calc})
    runtime = _make_runtime(ExecutionPlan(field_specs={"sum4": field_spec}), None, runtime_bindings=runtime_bindings)

    context = DenseBatchContext(base_row_id=1, row_count=4)
    for row_id in (1, 2, 3, 4):
        context.set_field_value("a", row_id, 1)
        context.set_field_value("b", row_id, 2)
        context.set_field_value("c", row_id, 3)
        context.set_field_value("d", row_id, 4)

    ComputeOperatorExecutor().execute(operator, context, [1, 2, 3, 4], runtime)
    assert calls["n"] == 1
    assert context.get_field_value("sum4", 1) == 10


def test_call_by_memoization_dense_many_deps_unhashable_key_does_not_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCALIM_EXP_CALL_BY_MEMOIZE_MAX_ENTRIES", "16")

    calls = {"n": 0}

    def _calc(a, b, c, d):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        return 1

    field_spec = _make_call_by_field("sum4", deps=("a", "b", "c", "d"))
    operator = _make_compute_op("sum4", deps=("a", "b", "c", "d"))
    runtime_bindings = RuntimeBindings(derived_calculators={"sum4": _calc})
    runtime = _make_runtime(ExecutionPlan(field_specs={"sum4": field_spec}), None, runtime_bindings=runtime_bindings)

    context = DenseBatchContext(base_row_id=1, row_count=4)
    for row_id in (1, 2, 3, 4):
        context.set_field_value("a", row_id, {"k": "v"})
        context.set_field_value("b", row_id, 2)
        context.set_field_value("c", row_id, 3)
        context.set_field_value("d", row_id, 4)

    ComputeOperatorExecutor().execute(operator, context, [1, 2, 3, 4], runtime)
    assert calls["n"] == 4
    assert context.get_field_value("sum4", 1) == 1


def test_call_by_memoization_reuses_ctx_free_results_generic_context(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCALIM_EXP_CALL_BY_MEMOIZE_MAX_ENTRIES", "16")

    calls = {"n": 0}

    def _calc(amount):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        return amount * 2

    field_spec = _make_call_by_field("score", deps=("amount",))
    operator = _make_compute_op("score", deps=("amount",))

    runtime_bindings = RuntimeBindings(derived_calculators={"score": _calc})
    runtime = _make_runtime(ExecutionPlan(field_specs={"score": field_spec}), None, runtime_bindings=runtime_bindings)

    context = BatchContext()
    for row_id in (1, 2, 3, 4):
        context.set_field_value("amount", row_id, 10)

    ComputeOperatorExecutor().execute(operator, context, [1, 2, 3, 4], runtime)
    assert calls["n"] == 1


def test_call_by_memoization_generic_context_unhashable_key_does_not_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCALIM_EXP_CALL_BY_MEMOIZE_MAX_ENTRIES", "16")

    calls = {"n": 0}

    def _calc(amount):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        return 1

    field_spec = _make_call_by_field("score", deps=("amount",))
    operator = _make_compute_op("score", deps=("amount",))

    runtime_bindings = RuntimeBindings(derived_calculators={"score": _calc})
    runtime = _make_runtime(ExecutionPlan(field_specs={"score": field_spec}), None, runtime_bindings=runtime_bindings)

    context = BatchContext()
    for row_id in (1, 2, 3, 4):
        context.set_field_value("amount", row_id, {"k": row_id})

    ComputeOperatorExecutor().execute(operator, context, [1, 2, 3, 4], runtime)
    assert calls["n"] == 4
