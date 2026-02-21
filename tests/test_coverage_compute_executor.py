from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, Set

import pytest

from scalim.events.catalog import EVENT_ERROR, EVENT_FIELD_COMPUTE
from scalim.execution.context import BatchContext
from scalim.execution.executor.operators.compute.errors import handle_compute_error
from scalim.execution.executor.operators.compute.executor import ComputeOperatorExecutor
from scalim.execution.guardrails import GuardrailViolation, GuardrailsComputePolicy, GuardrailsPolicy
from scalim.hooks.base import HookManager
from scalim.ob.manager import ObserverManager
from scalim.ob.observer import Observer
from scalim.planning.operators import ComputeOperatorIr
from scalim.planning.plan import ExecutionPlan
from scalim.spec.ir.fields import DerivedFieldIr
from scalim.execution.executor.runtime.runtime import ExecutionRuntime


class _CaptureObserver(Observer):
    def __init__(self, event_types: Optional[Set[str]] = None) -> None:
        self.event_types = event_types
        self.events = []

    def on_event(self, event) -> None:  # type: ignore[override]
        self.events.append(event)


def _make_runtime(
    *,
    field_specs: Dict[str, Any],
    field_dependencies: Optional[Dict[str, tuple[str, ...]]] = None,
    guardrails: Optional[GuardrailsPolicy] = None,
    observer_event_types: Optional[Iterable[str]] = None,
) -> tuple[ExecutionRuntime, Optional[_CaptureObserver]]:
    plan = ExecutionPlan(
        operators=(),
        field_specs=dict(field_specs),
        field_dependencies=dict(field_dependencies or {}),
        target_fields=list(field_specs.keys()),
    )
    hook_manager = HookManager()
    observer_manager = ObserverManager()
    observer: Optional[_CaptureObserver] = None
    if observer_event_types is not None:
        observer = _CaptureObserver(event_types=set(observer_event_types))
        observer_manager.register(observer)
    runtime = ExecutionRuntime(plan, hook_manager, observer_manager, main_source=None, guardrails=guardrails)
    runtime.batch_num = 3
    return runtime, observer


def test_compute_executor_constant_compute_success_emits_when_wanted() -> None:
    field_spec = DerivedFieldIr(
        field_id="const",
        name="Const",
        dependencies=(),
        calculator=lambda: 7,
        is_constant_compute=True,
    )
    runtime, observer = _make_runtime(
        field_specs={"const": field_spec},
        field_dependencies={"const": ()},
        guardrails=GuardrailsPolicy.disabled(),
        observer_event_types=[EVENT_FIELD_COMPUTE],
    )
    assert observer is not None

    context = BatchContext()
    op = ComputeOperatorIr(
        operator_id="compute:const",
        operator_type="compute",
        field_spec=field_spec,
        input_fields=(),
    )

    ComputeOperatorExecutor().execute(op, context, batch_row_nth=[0, 1], runtime=runtime)

    assert context.get_field_value("const", 0) == 7
    assert context.get_field_value("const", 1) == 7
    assert len(observer.events) == 2


def test_compute_executor_constant_compute_unexpected_error_quiet_guardrail_sets_none() -> None:
    def boom() -> int:
        raise RuntimeError("boom")

    field_spec = DerivedFieldIr(
        field_id="const",
        name="Const",
        dependencies=(),
        calculator=boom,
        is_constant_compute=True,
    )
    runtime, _ = _make_runtime(
        field_specs={"const": field_spec},
        field_dependencies={"const": ()},
        guardrails=GuardrailsPolicy(enabled=True, compute=GuardrailsComputePolicy(on_error="quiet")),
    )

    context = BatchContext()
    op = ComputeOperatorIr(
        operator_id="compute:const",
        operator_type="compute",
        field_spec=field_spec,
        input_fields=(),
    )

    ComputeOperatorExecutor().execute(op, context, batch_row_nth=[0, 1], runtime=runtime)

    assert context.get_field_value("const", 0) is None
    assert context.get_field_value("const", 1) is None


def test_compute_executor_constant_compute_expected_error_sets_none() -> None:
    def boom() -> int:
        raise ValueError("bad")

    field_spec = DerivedFieldIr(
        field_id="const",
        name="Const",
        dependencies=(),
        calculator=boom,
        is_constant_compute=True,
    )
    runtime, _ = _make_runtime(
        field_specs={"const": field_spec},
        field_dependencies={"const": ()},
        guardrails=GuardrailsPolicy.disabled(),
    )

    context = BatchContext()
    op = ComputeOperatorIr(
        operator_id="compute:const",
        operator_type="compute",
        field_spec=field_spec,
        input_fields=(),
    )

    ComputeOperatorExecutor().execute(op, context, batch_row_nth=[0, 1], runtime=runtime)

    assert context.get_field_value("const", 0) is None
    assert context.get_field_value("const", 1) is None


def test_handle_compute_error_without_guardrails_includes_unexpected_flag() -> None:
    runtime, _ = _make_runtime(
        field_specs={},
        guardrails=GuardrailsPolicy.disabled(),
        observer_event_types=[EVENT_ERROR],
    )
    context = BatchContext()

    handle_compute_error(
        runtime,
        context,
        field_key="profit",
        row_id=0,
        dependencies={"amount": 1},
        dependency_names=("amount",),
        exc=ValueError("bad"),
        compute_mode="fast_fail",
        unexpected=True,
    )

    assert context.get_field_value("profit", 0) is None


def test_handle_compute_error_fast_fail_raises_guardrail_violation() -> None:
    runtime, _ = _make_runtime(
        field_specs={},
        guardrails=GuardrailsPolicy(enabled=True, mode="fast_fail"),
        observer_event_types=[EVENT_ERROR],
    )
    context = BatchContext()

    with pytest.raises(GuardrailViolation):
        handle_compute_error(
            runtime,
            context,
            field_key="profit",
            row_id=0,
            dependencies={"amount": 1},
            dependency_names=("amount",),
            exc=ValueError("bad"),
            compute_mode="fast_fail",
            unexpected=False,
        )

    assert context.get_field_value("profit", 0) is None


def test_compute_executor_secure_compute_success_and_expected_error_payload_rules() -> None:
    def secure_add(a: int, b: int) -> int:
        return a + b

    secure_add._scalim_secure_compute = True  # type: ignore[attr-defined]

    def secure_div(a: int, b: int) -> float:
        return a / b

    secure_div._scalim_secure_compute = True  # type: ignore[attr-defined]

    field_ok = DerivedFieldIr(
        field_id="sum",
        name="Sum",
        dependencies=("a", "b"),
        calculator=secure_add,
        value_formatter=str,
    )
    field_err = DerivedFieldIr(
        field_id="ratio",
        name="Ratio",
        dependencies=("a", "b"),
        calculator=secure_div,
        value_formatter=None,
    )

    runtime_ok, _ = _make_runtime(
        field_specs={"sum": field_ok},
        field_dependencies={"sum": ("a", "b")},
        guardrails=GuardrailsPolicy.disabled(),
        observer_event_types=[EVENT_FIELD_COMPUTE],
    )

    context_ok = BatchContext()
    context_ok.set_field_value("a", 0, 2)
    context_ok.set_field_value("b", 0, 3)
    op_ok = ComputeOperatorIr(operator_id="compute:sum", operator_type="compute", field_spec=field_ok, input_fields=("a", "b"))
    ComputeOperatorExecutor().execute(op_ok, context_ok, batch_row_nth=[0], runtime=runtime_ok)
    assert context_ok.get_field_value("sum", 0) == "5"

    # Guardrails disabled => error payload includes dependency values (built by build_field_compute_dependencies_payload)
    runtime_err, _ = _make_runtime(
        field_specs={"ratio": field_err},
        field_dependencies={"ratio": ("a", "b")},
        guardrails=GuardrailsPolicy.disabled(),
    )
    context_err = BatchContext()
    context_err.set_field_value("a", 0, 1)
    context_err.set_field_value("b", 0, 0)
    op_err = ComputeOperatorIr(
        operator_id="compute:ratio",
        operator_type="compute",
        field_spec=field_err,
        input_fields=("a", "b"),
    )
    ComputeOperatorExecutor().execute(op_err, context_err, batch_row_nth=[0], runtime=runtime_err)
    assert context_err.get_field_value("ratio", 0) is None

    # Guardrails enabled (quiet) => error payload suppresses dependency values (deps_payload stays empty)
    runtime_guarded, _ = _make_runtime(
        field_specs={"ratio": field_err},
        field_dependencies={"ratio": ("a", "b")},
        guardrails=GuardrailsPolicy(enabled=True, compute=GuardrailsComputePolicy(on_error="quiet")),
    )
    context_guarded = BatchContext()
    context_guarded.set_field_value("a", 0, 1)
    context_guarded.set_field_value("b", 0, 0)
    ComputeOperatorExecutor().execute(op_err, context_guarded, batch_row_nth=[0], runtime=runtime_guarded)
    assert context_guarded.get_field_value("ratio", 0) is None


def test_compute_executor_secure_compute_unexpected_exception_builds_deps_payload() -> None:
    def secure_boom(_a: int, _b: int) -> int:
        raise RuntimeError("boom")

    secure_boom._scalim_secure_compute = True  # type: ignore[attr-defined]

    field_spec = DerivedFieldIr(
        field_id="secure_boom",
        name="SecureBoom",
        dependencies=("a", "b"),
        calculator=secure_boom,
    )

    runtime, _ = _make_runtime(
        field_specs={"secure_boom": field_spec},
        field_dependencies={"secure_boom": ("a", "b")},
        guardrails=GuardrailsPolicy.disabled(),
    )

    context = BatchContext()
    context.set_field_value("a", 0, 1)
    context.set_field_value("b", 0, 2)
    op = ComputeOperatorIr(
        operator_id="compute:secure_boom",
        operator_type="compute",
        field_spec=field_spec,
        input_fields=("a", "b"),
    )

    ComputeOperatorExecutor().execute(op, context, batch_row_nth=[0], runtime=runtime)
    assert context.get_field_value("secure_boom", 0) is None


def test_compute_executor_general_compute_injects_call_context_both_modes_and_handles_unexpected() -> None:
    def calc_with_ctx(x: int, ctx) -> int:  # type: ignore[no-untyped-def]
        return x + int(ctx.batch_num)

    with_ctx = DerivedFieldIr(
        field_id="with_ctx",
        name="WithCtx",
        dependencies=("x",),
        calculator=calc_with_ctx,
        call_ctx_key="ctx",
    )
    runtime_wanted, _ = _make_runtime(
        field_specs={"with_ctx": with_ctx},
        field_dependencies={"with_ctx": ("x",)},
        guardrails=GuardrailsPolicy.disabled(),
        observer_event_types=[EVENT_FIELD_COMPUTE],
    )
    context_wanted = BatchContext()
    context_wanted.set_field_value("x", 0, 1)
    op = ComputeOperatorIr(
        operator_id="compute:with_ctx",
        operator_type="compute",
        field_spec=with_ctx,
        input_fields=("x",),
    )
    ComputeOperatorExecutor().execute(op, context_wanted, batch_row_nth=[0], runtime=runtime_wanted)
    assert context_wanted.get_field_value("with_ctx", 0) == 4

    runtime_not_wanted, _ = _make_runtime(
        field_specs={"with_ctx": with_ctx},
        field_dependencies={"with_ctx": ("x",)},
        guardrails=GuardrailsPolicy.disabled(),
    )
    context_not_wanted = BatchContext()
    context_not_wanted.set_field_value("x", 0, 1)
    ComputeOperatorExecutor().execute(op, context_not_wanted, batch_row_nth=[0], runtime=runtime_not_wanted)
    assert context_not_wanted.get_field_value("with_ctx", 0) == 4

    def boom_compute(**_kwargs) -> int:  # type: ignore[no-untyped-def]
        raise RuntimeError("boom")

    boom_field = DerivedFieldIr(
        field_id="boom",
        name="Boom",
        dependencies=("x",),
        calculator=boom_compute,
    )
    runtime_boom, _ = _make_runtime(
        field_specs={"boom": boom_field},
        field_dependencies={"boom": ("x",)},
        guardrails=GuardrailsPolicy.disabled(),
    )
    context_boom = BatchContext()
    context_boom.set_field_value("x", 0, 1)
    op_boom = ComputeOperatorIr(operator_id="compute:boom", operator_type="compute", field_spec=boom_field, input_fields=("x",))
    ComputeOperatorExecutor().execute(op_boom, context_boom, batch_row_nth=[0], runtime=runtime_boom)
    assert context_boom.get_field_value("boom", 0) is None
