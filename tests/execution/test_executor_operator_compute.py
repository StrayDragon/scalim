"""Executor operator tests: compute."""

from typing import Any, Optional

import pytest

from scalim.dsl.yaml_dsl._internal.config_parsing.security import SecureComputeEngine
from scalim.execution.context import BatchContext
from scalim.execution.guardrails import ScalimGuardrailViolationError as GuardrailViolation, GuardrailsComputePolicy, GuardrailsPolicy
from scalim.execution.executor.operators.compute.executor import ComputeOperatorExecutor
from scalim.execution.runtime_bindings import RuntimeBindings
from scalim.hooks import HookManager
from scalim.planning.operators import ComputeOperatorIr, OperatorType
from scalim.planning.plan import ExecutionPlan
from scalim.spec.ir import CallBySpecIr, CallByValueIr, DerivedFieldIr, RuntimeHandleIdIr, ValueOpIr

from tests.fixtures.executor_operator_fixtures import _CaptureHook, _make_runtime


def _make_runtime_with_hook(
    plan: ExecutionPlan,
    *,
    guardrails: Optional[GuardrailsPolicy] = None,
    runtime_bindings: Optional[RuntimeBindings] = None,
):
    hook = _CaptureHook()
    hook_manager = HookManager()
    hook_manager.register(hook)
    runtime = _make_runtime(plan, None, hook_manager=hook_manager, guardrails=guardrails, runtime_bindings=runtime_bindings)
    return runtime, hook


def test_compute_operator_emits_errors_and_success() -> None:
    def _compute(amount):  # type: ignore[no-untyped-def]
        if amount == 0:
            return amount / 0
        if amount < 0:
            raise RuntimeError("boom")
        return amount * 2

    field_spec = DerivedFieldIr(
        field_id="score",
        name="Score",
        dependencies=("amount",),
        call_by=CallBySpecIr(
            reference=RuntimeHandleIdIr(handle_id="derived.score"),
            args=(CallByValueIr(kind="field", value="amount"),),
            field_names=("amount",),
        ),
    )
    operator = ComputeOperatorIr(
        operator_id="compute_score",
        operator_type=OperatorType.COMPUTE.value,
        field_key="score",
        input_fields=("amount",),
    )

    hook = _CaptureHook()
    hook_manager = HookManager()
    hook_manager.register(hook)
    runtime_bindings = RuntimeBindings(derived_calculators={"score": _compute})
    runtime = _make_runtime(
        ExecutionPlan(field_specs={"score": field_spec}),
        None,
        hook_manager=hook_manager,
        runtime_bindings=runtime_bindings,
    )

    context = BatchContext()
    context.set_field_value("amount", 1, 0)
    context.set_field_value("amount", 2, -1)
    context.set_field_value("amount", 3, 3)

    ComputeOperatorExecutor().execute(operator, context, [1, 2, 3], runtime)

    assert context.get_field_value("score", 1) is None
    assert context.get_field_value("score", 2) is None
    assert context.get_field_value("score", 3) == 6
    assert len(hook.errors) == 2
    assert len(hook.field_computed) == 1
    assert any(getattr(event, "context", {}).get("unexpected") for event in hook.errors)


def test_compute_operator_secure_compute_wants_gated_dependencies_payload(monkeypatch) -> None:
    import scalim.execution.executor.operators.compute.executor as impl_module

    def _raise_payload(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("dependencies payload should be wants-gated")

    monkeypatch.setattr(impl_module, "build_field_compute_dependencies_payload", _raise_payload)

    engine = SecureComputeEngine()
    calculator = engine.compile("a + b", ("a", "b"))
    field_spec = DerivedFieldIr(
        field_id="sum",
        name="Sum",
        dependencies=("a", "b"),
        call_by=CallBySpecIr(
            reference=RuntimeHandleIdIr(handle_id="derived.sum"),
            args=(CallByValueIr(kind="field", value="a"), CallByValueIr(kind="field", value="b")),
            field_names=("a", "b"),
        ),
    )
    operator = ComputeOperatorIr(
        operator_id="compute_sum",
        operator_type=OperatorType.COMPUTE.value,
        field_key="sum",
        input_fields=("a", "b"),
    )

    runtime_bindings = RuntimeBindings(derived_calculators={"sum": calculator})
    runtime = _make_runtime(ExecutionPlan(field_specs={"sum": field_spec}), None, runtime_bindings=runtime_bindings)

    context = BatchContext()
    context.set_field_value("a", 1, 1)
    context.set_field_value("b", 1, 2)
    context.set_field_value("a", 2, 3)
    context.set_field_value("b", 2, 4)

    ComputeOperatorExecutor().execute(operator, context, [1, 2], runtime)

    assert context.get_field_value("sum", 1) == 3
    assert context.get_field_value("sum", 2) == 7


def test_compute_operator_secure_compute_emits_field_compute_and_formats_value() -> None:
    engine = SecureComputeEngine()
    calculator = engine.compile("a + b", ("a", "b"))

    field_spec = DerivedFieldIr(
        field_id="sum",
        name="Sum",
        dependencies=("a", "b"),
        call_by=CallBySpecIr(
            reference=RuntimeHandleIdIr(handle_id="derived.sum"),
            args=(CallByValueIr(kind="field", value="a"), CallByValueIr(kind="field", value="b")),
            field_names=("a", "b"),
        ),
        value_ops=(ValueOpIr(kind="format", callable_ref=RuntimeHandleIdIr(handle_id="format.sum")),),
    )
    operator = ComputeOperatorIr(
        operator_id="compute_sum",
        operator_type=OperatorType.COMPUTE.value,
        field_key="sum",
        input_fields=("a", "b"),
    )

    hook = _CaptureHook()
    hook_manager = HookManager()
    hook_manager.register(hook)
    runtime_bindings = RuntimeBindings(
        derived_calculators={"sum": calculator},
        value_transforms={"sum": (lambda value: value * 10)},
    )
    runtime = _make_runtime(
        ExecutionPlan(field_specs={"sum": field_spec}),
        None,
        hook_manager=hook_manager,
        runtime_bindings=runtime_bindings,
    )

    context = BatchContext()
    context.set_field_value("a", 1, 1)
    context.set_field_value("b", 1, 2)
    context.set_field_value("a", 2, 3)
    context.set_field_value("b", 2, 4)

    ComputeOperatorExecutor().execute(operator, context, [1, 2], runtime)

    assert context.get_field_value("sum", 1) == 30
    assert context.get_field_value("sum", 2) == 70
    assert len(hook.field_computed) == 2
    assert hook.field_computed[0].dependencies == {"a": 1, "b": 2}
    assert hook.field_computed[1].dependencies == {"a": 3, "b": 4}


@pytest.mark.parametrize(
    ("guardrails", "should_raise"),
    [
        (None, False),
        (GuardrailsPolicy(enabled=True, compute=GuardrailsComputePolicy(on_error="quiet")), False),
        (GuardrailsPolicy(enabled=True, mode="fast_fail"), True),
    ],
    ids=[
        "no_guardrails",
        "guardrails_quiet",
        "guardrails_fast_fail",
    ],
)
def test_compute_operator_secure_compute_expected_error_variants(
    guardrails: Optional[GuardrailsPolicy],
    should_raise: bool,
) -> None:
    engine = SecureComputeEngine()
    calculator = engine.compile("a + 1", ("a",))
    field_spec = DerivedFieldIr(
        field_id="sum",
        name="Sum",
        dependencies=("a", "b"),
        call_by=CallBySpecIr(
            reference=RuntimeHandleIdIr(handle_id="derived.sum"),
            args=(CallByValueIr(kind="field", value="a"), CallByValueIr(kind="field", value="b")),
            field_names=("a", "b"),
        ),
    )
    operator = ComputeOperatorIr(
        operator_id="compute_sum",
        operator_type=OperatorType.COMPUTE.value,
        field_key="sum",
        input_fields=("a", "b"),
    )

    runtime_bindings = RuntimeBindings(derived_calculators={"sum": calculator})
    runtime, hook = _make_runtime_with_hook(
        ExecutionPlan(field_specs={"sum": field_spec}),
        guardrails=guardrails,
        runtime_bindings=runtime_bindings,
    )

    context = BatchContext()
    context.set_field_value("a", 1, 1)
    context.set_field_value("b", 1, 2)

    if should_raise:
        with pytest.raises(GuardrailViolation):
            ComputeOperatorExecutor().execute(operator, context, [1], runtime)
    else:
        ComputeOperatorExecutor().execute(operator, context, [1], runtime)

    assert context.get_field_value("sum", 1) is None
    assert len(hook.errors) == 1

    if guardrails is None:
        assert hook.errors[0].context["dependencies"] == {"a": 1, "b": 2}
        assert hook.errors[0].context.get("guardrail") is None
        assert hook.errors[0].context.get("unexpected") is None
    else:
        assert isinstance(hook.errors[0].error, GuardrailViolation)
        assert hook.errors[0].context.get("guardrail") is True
        assert hook.errors[0].context.get("unexpected") is None


@pytest.mark.parametrize(
    ("guardrails", "should_raise"),
    [
        (None, False),
        (GuardrailsPolicy(enabled=True, compute=GuardrailsComputePolicy(on_error="quiet")), False),
        (GuardrailsPolicy(enabled=True, mode="fast_fail"), True),
    ],
    ids=[
        "no_guardrails",
        "guardrails_quiet",
        "guardrails_fast_fail",
    ],
)
def test_compute_operator_secure_compute_unexpected_error_variants(
    guardrails: Optional[GuardrailsPolicy],
    should_raise: bool,
) -> None:
    engine = SecureComputeEngine()
    calculator = engine.compile("a / b", ("a", "b"))
    field_spec = DerivedFieldIr(
        field_id="div",
        name="Div",
        dependencies=("a", "b"),
        call_by=CallBySpecIr(
            reference=RuntimeHandleIdIr(handle_id="derived.div"),
            args=(CallByValueIr(kind="field", value="a"), CallByValueIr(kind="field", value="b")),
            field_names=("a", "b"),
        ),
    )
    operator = ComputeOperatorIr(
        operator_id="compute_div",
        operator_type=OperatorType.COMPUTE.value,
        field_key="div",
        input_fields=("a", "b"),
    )

    runtime_bindings = RuntimeBindings(derived_calculators={"div": calculator})
    runtime, hook = _make_runtime_with_hook(
        ExecutionPlan(field_specs={"div": field_spec}),
        guardrails=guardrails,
        runtime_bindings=runtime_bindings,
    )

    context = BatchContext()
    context.set_field_value("a", 1, 1)
    context.set_field_value("b", 1, 0)

    if should_raise:
        with pytest.raises(GuardrailViolation):
            ComputeOperatorExecutor().execute(operator, context, [1], runtime)
    else:
        ComputeOperatorExecutor().execute(operator, context, [1], runtime)

    assert context.get_field_value("div", 1) is None
    assert len(hook.errors) == 1
    assert hook.errors[0].context.get("unexpected") is True

    if guardrails is None:
        assert hook.errors[0].context["dependencies"] == {"a": 1, "b": 0}
        assert hook.errors[0].context.get("guardrail") is None
    else:
        assert isinstance(hook.errors[0].error, GuardrailViolation)
        assert hook.errors[0].context.get("guardrail") is True


def test_compute_operator_injects_ctx_when_configured_and_emits_deps_without_ctx() -> None:
    def _calc(amount, **kwargs):  # type: ignore[no-untyped-def]
        _ = amount
        ctx = kwargs["ctx"]
        return "{}:{}".format(ctx.row_id, ctx.batch_num)

    field_spec = DerivedFieldIr(
        field_id="score",
        name="Score",
        dependencies=("amount",),
        call_by=CallBySpecIr(
            reference=RuntimeHandleIdIr(handle_id="derived.score"),
            args=(CallByValueIr(kind="field", value="amount"),),
            field_names=("amount",),
        ),
        call_ctx_key="ctx",
    )
    operator = ComputeOperatorIr(
        operator_id="compute_score",
        operator_type=OperatorType.COMPUTE.value,
        field_key="score",
        input_fields=("amount",),
    )

    hook = _CaptureHook()
    hook_manager = HookManager()
    hook_manager.register(hook)
    runtime_bindings = RuntimeBindings(derived_calculators={"score": _calc})
    runtime = _make_runtime(
        ExecutionPlan(field_specs={"score": field_spec}, target_fields=["score"]),
        None,
        hook_manager=hook_manager,
        runtime_bindings=runtime_bindings,
    )
    runtime.batch_num = 7

    context = BatchContext()
    context.set_field_value("amount", 1, 100)
    context.set_field_value("amount", 2, 200)

    ComputeOperatorExecutor().execute(operator, context, [1, 2], runtime)

    assert context.get_field_value("score", 1) == "1:7"
    assert context.get_field_value("score", 2) == "2:7"
    assert len(hook.field_computed) == 2
    assert hook.field_computed[0].dependencies == {"amount": 100}
    assert hook.field_computed[1].dependencies == {"amount": 200}


def test_compute_operator_general_compute_guardrails_quiet_records_expected_and_unexpected_errors() -> None:
    def _expected(x: Any) -> Any:
        _ = x
        return 1 / 0

    def _unexpected(x: Any) -> Any:
        _ = x
        raise RuntimeError("boom")

    expected = DerivedFieldIr(
        field_id="expected",
        name="Expected",
        dependencies=("x",),
        call_by=CallBySpecIr(
            reference=RuntimeHandleIdIr(handle_id="derived.expected"),
            args=(CallByValueIr(kind="field", value="x"),),
            field_names=("x",),
        ),
    )
    unexpected = DerivedFieldIr(
        field_id="unexpected",
        name="Unexpected",
        dependencies=("x",),
        call_by=CallBySpecIr(
            reference=RuntimeHandleIdIr(handle_id="derived.unexpected"),
            args=(CallByValueIr(kind="field", value="x"),),
            field_names=("x",),
        ),
    )

    op_expected = ComputeOperatorIr(
        operator_id="compute_expected",
        operator_type=OperatorType.COMPUTE.value,
        field_key="expected",
        input_fields=("x",),
    )
    op_unexpected = ComputeOperatorIr(
        operator_id="compute_unexpected",
        operator_type=OperatorType.COMPUTE.value,
        field_key="unexpected",
        input_fields=("x",),
    )

    hook = _CaptureHook()
    hook_manager = HookManager()
    hook_manager.register(hook)
    plan = ExecutionPlan(field_specs={"expected": expected, "unexpected": unexpected})
    runtime_bindings = RuntimeBindings(derived_calculators={"expected": _expected, "unexpected": _unexpected})
    runtime = _make_runtime(
        plan,
        None,
        hook_manager=hook_manager,
        runtime_bindings=runtime_bindings,
        guardrails=GuardrailsPolicy(enabled=True, mode="quiet"),
    )
    context = BatchContext()
    context.set_field_value("x", 1, 1)

    ComputeOperatorExecutor().execute(op_expected, context, [1], runtime)
    ComputeOperatorExecutor().execute(op_unexpected, context, [1], runtime)

    assert context.get_field_value("expected", 1) is None
    assert context.get_field_value("unexpected", 1) is None
    assert len(hook.errors) == 2

    runtime = _make_runtime(
        plan,
        None,
        hook_manager=hook_manager,
        runtime_bindings=runtime_bindings,
        guardrails=GuardrailsPolicy(enabled=True, mode="fast_fail"),
    )
    context = BatchContext()
    context.set_field_value("x", 1, 1)
    with pytest.raises(GuardrailViolation) as exc_info:
        ComputeOperatorExecutor().execute(op_unexpected, context, [1], runtime)
    assert exc_info.value.code == "compute_error"
    assert exc_info.value.context.get("unexpected") is True


def test_compute_operator_constant_compute_caches_result_and_emits_per_row() -> None:
    calls = {"count": 0}

    def _compute(**_kwargs):  # type: ignore[no-untyped-def]
        calls["count"] += 1
        return 3

    field_spec = DerivedFieldIr(
        field_id="const",
        name="Const",
        dependencies=(),
        call_by=CallBySpecIr(reference=RuntimeHandleIdIr(handle_id="derived.const")),
        is_constant_compute=True,
    )
    operator = ComputeOperatorIr(
        operator_id="compute_const",
        operator_type=OperatorType.COMPUTE.value,
        field_key="const",
        input_fields=(),
    )

    hook = _CaptureHook()
    hook_manager = HookManager()
    hook_manager.register(hook)
    runtime_bindings = RuntimeBindings(derived_calculators={"const": _compute})
    runtime = _make_runtime(
        ExecutionPlan(field_specs={"const": field_spec}),
        None,
        hook_manager=hook_manager,
        runtime_bindings=runtime_bindings,
    )

    context = BatchContext()
    ComputeOperatorExecutor().execute(operator, context, [1, 2, 3], runtime)

    assert calls["count"] == 1
    assert context.get_field_value("const", 1) == 3
    assert context.get_field_value("const", 2) == 3
    assert context.get_field_value("const", 3) == 3
    assert len(hook.field_computed) == 3


def test_compute_operator_constant_compute_applies_value_transform() -> None:
    def _compute(**_kwargs):  # type: ignore[no-untyped-def]
        return 3

    field_spec = DerivedFieldIr(
        field_id="const",
        name="Const",
        dependencies=(),
        call_by=CallBySpecIr(reference=RuntimeHandleIdIr(handle_id="derived.const")),
        is_constant_compute=True,
    )
    operator = ComputeOperatorIr(
        operator_id="compute_const",
        operator_type=OperatorType.COMPUTE.value,
        field_key="const",
        input_fields=(),
    )

    runtime_bindings = RuntimeBindings(
        derived_calculators={"const": _compute},
        value_transforms={"const": (lambda v: v + 1)},  # type: ignore[no-any-return]
    )
    runtime, _hook = _make_runtime_with_hook(ExecutionPlan(field_specs={"const": field_spec}), runtime_bindings=runtime_bindings)

    context = BatchContext()
    ComputeOperatorExecutor().execute(operator, context, [1, 2, 3], runtime)
    assert context.get_field_value("const", 1) == 4


def test_compute_operator_returns_early_when_field_is_not_derived() -> None:
    operator = ComputeOperatorIr(
        operator_id="compute_missing",
        operator_type=OperatorType.COMPUTE.value,
        field_key="missing",
        input_fields=(),
    )
    runtime, _hook = _make_runtime_with_hook(ExecutionPlan(field_specs={}), runtime_bindings=RuntimeBindings())
    ComputeOperatorExecutor().execute(operator, BatchContext(), [1], runtime)


@pytest.mark.parametrize(
    ("kind", "unexpected"),
    [
        ("expected", False),
        ("unexpected", True),
    ],
    ids=[
        "expected_error",
        "unexpected_error",
    ],
)
def test_compute_operator_constant_compute_errors_emit_per_row_and_compute_once(kind: str, unexpected: bool) -> None:
    calls = {"count": 0}

    def _compute(**_kwargs):  # type: ignore[no-untyped-def]
        calls["count"] += 1
        if kind == "expected":
            return 1 / 0
        raise RuntimeError("boom")

    field_spec = DerivedFieldIr(
        field_id="const",
        name="Const",
        dependencies=(),
        call_by=CallBySpecIr(reference=RuntimeHandleIdIr(handle_id="derived.const")),
        is_constant_compute=True,
    )
    operator = ComputeOperatorIr(
        operator_id="compute_const",
        operator_type=OperatorType.COMPUTE.value,
        field_key="const",
        input_fields=(),
    )

    runtime_bindings = RuntimeBindings(derived_calculators={"const": _compute})
    runtime, hook = _make_runtime_with_hook(ExecutionPlan(field_specs={"const": field_spec}), runtime_bindings=runtime_bindings)

    context = BatchContext()
    ComputeOperatorExecutor().execute(operator, context, [1, 2, 3], runtime)

    assert calls["count"] == 1
    assert context.get_field_value("const", 1) is None
    assert context.get_field_value("const", 2) is None
    assert context.get_field_value("const", 3) is None
    assert len(hook.errors) == 3
    if unexpected:
        assert all(getattr(event, "context", {}).get("unexpected") for event in hook.errors)
    else:
        assert all(getattr(event, "context", {}).get("unexpected") is None for event in hook.errors)


@pytest.mark.parametrize(
    ("kind", "unexpected"),
    [
        ("expected", False),
        ("unexpected", True),
    ],
    ids=[
        "expected_error",
        "unexpected_error",
    ],
)
@pytest.mark.parametrize(
    ("mode", "should_raise"),
    [
        ("quiet", False),
        ("fast_fail", True),
    ],
    ids=[
        "guardrails_quiet",
        "guardrails_fast_fail",
    ],
)
def test_compute_operator_constant_compute_errors_guardrails_variants(
    kind: str,
    unexpected: bool,
    mode: str,
    should_raise: bool,
) -> None:
    calls = {"count": 0}

    def _compute(**_kwargs):  # type: ignore[no-untyped-def]
        calls["count"] += 1
        if kind == "expected":
            return 1 / 0
        raise RuntimeError("boom")

    field_spec = DerivedFieldIr(
        field_id="const",
        name="Const",
        dependencies=(),
        call_by=CallBySpecIr(reference=RuntimeHandleIdIr(handle_id="derived.const")),
        is_constant_compute=True,
    )
    operator = ComputeOperatorIr(
        operator_id="compute_const",
        operator_type=OperatorType.COMPUTE.value,
        field_key="const",
        input_fields=(),
    )

    hook = _CaptureHook()
    hook_manager = HookManager()
    hook_manager.register(hook)
    runtime_bindings = RuntimeBindings(derived_calculators={"const": _compute})
    runtime = _make_runtime(
        ExecutionPlan(field_specs={"const": field_spec}),
        None,
        hook_manager=hook_manager,
        runtime_bindings=runtime_bindings,
        guardrails=GuardrailsPolicy(enabled=True, mode=mode),  # type: ignore[arg-type]
    )

    context = BatchContext()
    if should_raise:
        with pytest.raises(GuardrailViolation) as exc_info:
            ComputeOperatorExecutor().execute(operator, context, [1, 2, 3], runtime)
        assert len(hook.errors) == 1
        if unexpected:
            assert exc_info.value.context.get("unexpected") is True
        else:
            assert exc_info.value.context.get("unexpected") is None
    else:
        ComputeOperatorExecutor().execute(operator, context, [1, 2, 3], runtime)
        assert len(hook.errors) == 3
        assert all(getattr(event, "context", {}).get("guardrail") for event in hook.errors)
        if unexpected:
            assert all(getattr(event, "context", {}).get("unexpected") for event in hook.errors)
        else:
            assert all(getattr(event, "context", {}).get("unexpected") is None for event in hook.errors)

    assert calls["count"] == 1
    assert context.get_field_value("const", 1) is None
    assert context.get_field_value("const", 2) is None
    assert context.get_field_value("const", 3) is None


def test_compute_operator_non_constant_compute_is_not_cached() -> None:
    calls = {"count": 0}

    def _compute(amount):  # type: ignore[no-untyped-def]
        calls["count"] += 1
        return amount + 1

    field_spec = DerivedFieldIr(
        field_id="score",
        name="Score",
        dependencies=("amount",),
        call_by=CallBySpecIr(
            reference=RuntimeHandleIdIr(handle_id="derived.score"),
            args=(CallByValueIr(kind="field", value="amount"),),
            field_names=("amount",),
        ),
    )
    operator = ComputeOperatorIr(
        operator_id="compute_score",
        operator_type=OperatorType.COMPUTE.value,
        field_key="score",
        input_fields=("amount",),
    )

    runtime_bindings = RuntimeBindings(derived_calculators={"score": _compute})
    runtime = _make_runtime(ExecutionPlan(field_specs={"score": field_spec}), None, runtime_bindings=runtime_bindings)
    context = BatchContext()
    context.set_field_value("amount", 1, 10)
    context.set_field_value("amount", 2, 20)
    context.set_field_value("amount", 3, 30)

    ComputeOperatorExecutor().execute(operator, context, [1, 2, 3], runtime)

    assert calls["count"] == 3
    assert context.get_field_value("score", 1) == 11
    assert context.get_field_value("score", 2) == 21
    assert context.get_field_value("score", 3) == 31
