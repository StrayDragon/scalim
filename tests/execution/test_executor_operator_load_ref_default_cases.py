"""Executor operator tests: load_ref default cases."""

from typing import Any, Dict, Hashable

import pytest

from scalim.execution.context import BatchContext
from scalim.execution.guardrails import GuardrailsPolicy
from scalim.execution.runtime_bindings import RuntimeBindings
from scalim.execution.executor.operators.load_ref.executor import LoadRefOperatorExecutor
from scalim.execution.executor.operators.load_ref.flow import (
    _resolve_ref_default_value_on_relation_miss,
    _write_relation_miss_field_value,
)
from scalim.execution.executor.operators.load_ref.context import LoadRefExecutionContext
from scalim.planning.operators import LoadRefOperatorIr, OperatorType
from scalim.planning.plan import ExecutionPlan
from scalim.spec.ir import CallBySpecIr, FieldIr, KeyIr, LookupStepIr, SourceIr, ValueOpIr
from scalim.spec.ir._fields import FieldDefaultCaseIr
from scalim.spec.ir.binding import BindingIr, LoaderIr
from scalim.spec.ir.callable_refs import RuntimeHandleIdIr

from tests.fixtures.executor_operator_fixtures import _make_main_source, _make_runtime
from scalim.utils.relation_signature import build_relation_signature


def _bind_source_loader(runtime_bindings: RuntimeBindings, source_id: str, loader_fn) -> None:  # type: ignore[no-untyped-def]
    runtime_bindings.source_loaders[str(source_id)] = loader_fn


def _bind_params_builder(
    runtime_bindings: RuntimeBindings,
    source_id: str,
    key_field: str,
    params_builder_fn,  # type: ignore[no-untyped-def]
) -> BindingIr:
    runtime_bindings.params_builders[(str(source_id), str(key_field))] = params_builder_fn
    return BindingIr(key_field=str(key_field), params_builder_ref=RuntimeHandleIdIr("params_builder:{}:{}".format(source_id, key_field)))


def _make_single_step_operator(*, field_key: str, source: SourceIr, step: LookupStepIr) -> LoadRefOperatorIr:
    return LoadRefOperatorIr(
        operator_id="load_ref",
        operator_type=OperatorType.LOAD_REF.value,
        source_id=str(source.source_id),
        field_key=str(field_key),
        lookup_steps=(step,),
    )


def _make_single_step_plan(*, field_key: str, field_spec: FieldIr, operator: LoadRefOperatorIr) -> ExecutionPlan:
    return ExecutionPlan(field_specs={str(field_key): field_spec}, operators=(operator,))


def test_load_ref_relation_miss_applies_default_literal_and_value_cast() -> None:
    runtime_bindings = RuntimeBindings()

    def _params_builder(ctx):  # type: ignore[no-untyped-def]
        return (), {"target_ids": list(ctx.lookup_keys or [])}

    def _loader(target_ids):  # type: ignore[no-untyped-def]
        _ = target_ids
        return {}

    main_source = _make_main_source()
    target_source = SourceIr(
        source_id="targets",
        key=KeyIr(key="target_id"),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr("source_loader:targets")),
    )
    _bind_source_loader(runtime_bindings, "targets", _loader)
    binding = _bind_params_builder(runtime_bindings, "targets", "target_id", _params_builder)
    step = LookupStepIr(from_field="fk_id", to_source=target_source, bind=binding)

    field_spec = FieldIr(
        field_id="amount",
        name="Amount",
        source=target_source,
        data_key="amount",
        value_ops=(ValueOpIr(kind="cast", to="int"),),
        default_cases=(FieldDefaultCaseIr(when="relation_miss", kind="literal", literal="0"),),
    )
    runtime_bindings.value_transforms["amount"] = lambda v: int(v) if v is not None else None  # type: ignore[no-any-return]

    operator = _make_single_step_operator(field_key="amount", source=target_source, step=step)
    plan = _make_single_step_plan(field_key="amount", field_spec=field_spec, operator=operator)
    runtime = _make_runtime(plan, main_source, sources={str(target_source.source_id): target_source}, runtime_bindings=runtime_bindings)

    context = BatchContext()
    context.set_field_value("fk_id", 1, 1)

    LoadRefOperatorExecutor().execute(operator, context, [1], runtime)
    assert context.get_field_value("amount", 1) == 0


def test_load_ref_relation_miss_applies_default_call_by() -> None:
    runtime_bindings = RuntimeBindings()

    def _params_builder(ctx):  # type: ignore[no-untyped-def]
        return (), {"target_ids": list(ctx.lookup_keys or [])}

    def _loader(target_ids):  # type: ignore[no-untyped-def]
        _ = target_ids
        return {}

    def _default_calc(*_dep_args: object, **_kwargs: object) -> str:
        return "6"

    main_source = _make_main_source()
    target_source = SourceIr(
        source_id="targets",
        key=KeyIr(key="target_id"),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr("source_loader:targets")),
    )
    _bind_source_loader(runtime_bindings, "targets", _loader)
    binding = _bind_params_builder(runtime_bindings, "targets", "target_id", _params_builder)
    step = LookupStepIr(from_field="fk_id", to_source=target_source, bind=binding)

    field_spec = FieldIr(
        field_id="amount",
        name="Amount",
        source=target_source,
        data_key="amount",
        value_ops=(ValueOpIr(kind="cast", to="int"),),
        default_cases=(
            FieldDefaultCaseIr(
                when="relation_miss",
                kind="call_by",
                call_by=CallBySpecIr(reference=RuntimeHandleIdIr(handle_id="default:amount")),
            ),
        ),
    )
    runtime_bindings.ref_default_calculators[("amount", 0)] = _default_calc
    runtime_bindings.value_transforms["amount"] = lambda v: int(v) if v is not None else None  # type: ignore[no-any-return]

    operator = _make_single_step_operator(field_key="amount", source=target_source, step=step)
    plan = _make_single_step_plan(field_key="amount", field_spec=field_spec, operator=operator)
    runtime = _make_runtime(plan, main_source, sources={str(target_source.source_id): target_source}, runtime_bindings=runtime_bindings)

    context = BatchContext()
    context.set_field_value("fk_id", 1, 1)

    LoadRefOperatorExecutor().execute(operator, context, [1], runtime)
    assert context.get_field_value("amount", 1) == 6


def test_load_ref_relation_hit_does_not_apply_default_even_if_value_is_none() -> None:
    runtime_bindings = RuntimeBindings()

    def _params_builder(ctx):  # type: ignore[no-untyped-def]
        return (), {"target_ids": list(ctx.lookup_keys or [])}

    def _loader(target_ids):  # type: ignore[no-untyped-def]
        return {key: {"amount": None} for key in target_ids}

    main_source = _make_main_source()
    target_source = SourceIr(
        source_id="targets",
        key=KeyIr(key="target_id"),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr("source_loader:targets")),
    )
    _bind_source_loader(runtime_bindings, "targets", _loader)
    binding = _bind_params_builder(runtime_bindings, "targets", "target_id", _params_builder)
    step = LookupStepIr(from_field="fk_id", to_source=target_source, bind=binding)

    field_spec = FieldIr(
        field_id="amount",
        name="Amount",
        source=target_source,
        data_key="amount",
        value_ops=(ValueOpIr(kind="cast", to="int"),),
        default_cases=(FieldDefaultCaseIr(when="relation_miss", kind="literal", literal=0),),
    )
    runtime_bindings.value_transforms["amount"] = lambda v: int(v) if v is not None else None  # type: ignore[no-any-return]

    operator = _make_single_step_operator(field_key="amount", source=target_source, step=step)
    plan = _make_single_step_plan(field_key="amount", field_spec=field_spec, operator=operator)
    runtime = _make_runtime(plan, main_source, sources={str(target_source.source_id): target_source}, runtime_bindings=runtime_bindings)

    context = BatchContext()
    context.set_field_value("fk_id", 1, 1)

    LoadRefOperatorExecutor().execute(operator, context, [1], runtime)
    assert context.get_field_value("amount", 1) is None


def test_load_ref_null_fk_applies_default_without_calling_loader() -> None:
    runtime_bindings = RuntimeBindings()

    def _params_builder(ctx):  # type: ignore[no-untyped-def]
        return (), {"target_ids": list(ctx.lookup_keys or [])}

    def _loader(*_args: object, **_kwargs: object) -> Dict[Hashable, Dict[str, Any]]:
        raise AssertionError("loader should not be called when fk is None")

    main_source = _make_main_source()
    target_source = SourceIr(
        source_id="targets",
        key=KeyIr(key="target_id"),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr("source_loader:targets")),
    )
    _bind_source_loader(runtime_bindings, "targets", _loader)
    binding = _bind_params_builder(runtime_bindings, "targets", "target_id", _params_builder)
    step = LookupStepIr(from_field="fk_id", to_source=target_source, bind=binding)

    field_spec = FieldIr(
        field_id="amount",
        name="Amount",
        source=target_source,
        data_key="amount",
        value_ops=(ValueOpIr(kind="cast", to="int"),),
        default_cases=(FieldDefaultCaseIr(when="relation_miss", kind="literal", literal=0),),
    )
    runtime_bindings.value_transforms["amount"] = lambda v: int(v) if v is not None else None  # type: ignore[no-any-return]

    operator = _make_single_step_operator(field_key="amount", source=target_source, step=step)
    plan = _make_single_step_plan(field_key="amount", field_spec=field_spec, operator=operator)
    runtime = _make_runtime(plan, main_source, sources={str(target_source.source_id): target_source}, runtime_bindings=runtime_bindings)

    context = BatchContext()
    context.set_field_value("fk_id", 1, None)

    LoadRefOperatorExecutor().execute(operator, context, [1], runtime)
    assert context.get_field_value("amount", 1) == 0


def test_load_ref_relation_miss_call_by_default_requires_bound_calculator() -> None:
    runtime_bindings = RuntimeBindings()

    def _params_builder(ctx):  # type: ignore[no-untyped-def]
        return (), {"target_ids": list(ctx.lookup_keys or [])}

    def _loader(target_ids):  # type: ignore[no-untyped-def]
        _ = target_ids
        return {}

    main_source = _make_main_source()
    target_source = SourceIr(
        source_id="targets",
        key=KeyIr(key="target_id"),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr("source_loader:targets")),
    )
    _bind_source_loader(runtime_bindings, "targets", _loader)
    binding = _bind_params_builder(runtime_bindings, "targets", "target_id", _params_builder)
    step = LookupStepIr(from_field="fk_id", to_source=target_source, bind=binding)

    field_spec = FieldIr(
        field_id="amount",
        name="Amount",
        source=target_source,
        data_key="amount",
        value_ops=(ValueOpIr(kind="cast", to="int"),),
        default_cases=(
            FieldDefaultCaseIr(
                when="relation_miss",
                kind="call_by",
                call_by=CallBySpecIr(reference=RuntimeHandleIdIr(handle_id="default:amount")),
            ),
        ),
    )
    runtime_bindings.value_transforms["amount"] = lambda v: int(v) if v is not None else None  # type: ignore[no-any-return]

    operator = _make_single_step_operator(field_key="amount", source=target_source, step=step)
    plan = _make_single_step_plan(field_key="amount", field_spec=field_spec, operator=operator)
    runtime = _make_runtime(plan, main_source, sources={str(target_source.source_id): target_source}, runtime_bindings=runtime_bindings)

    context = BatchContext()
    context.set_field_value("fk_id", 1, 1)

    with pytest.raises(KeyError, match=r"Missing runtime ref default calculator"):
        LoadRefOperatorExecutor().execute(operator, context, [1], runtime)


def test_load_ref_relation_miss_call_by_default_passes_dependencies() -> None:
    runtime_bindings = RuntimeBindings()

    def _params_builder(ctx):  # type: ignore[no-untyped-def]
        return (), {"target_ids": list(ctx.lookup_keys or [])}

    def _loader(target_ids):  # type: ignore[no-untyped-def]
        _ = target_ids
        return {}

    captured = {}

    def _default_calc(*dep_args: object, **kwargs: object) -> str:
        captured["dep_args"] = tuple(dep_args)
        ctx = kwargs.get("ctx")
        assert ctx is not None
        captured["ctx_values"] = dict(getattr(ctx, "values", {}))
        return "6"

    main_source = _make_main_source()
    target_source = SourceIr(
        source_id="targets",
        key=KeyIr(key="target_id"),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr("source_loader:targets")),
    )
    _bind_source_loader(runtime_bindings, "targets", _loader)
    binding = _bind_params_builder(runtime_bindings, "targets", "target_id", _params_builder)
    step = LookupStepIr(from_field="fk_id", to_source=target_source, bind=binding)

    field_spec = FieldIr(
        field_id="amount",
        name="Amount",
        source=target_source,
        data_key="amount",
        value_ops=(ValueOpIr(kind="cast", to="int"),),
        default_cases=(
            FieldDefaultCaseIr(
                when="relation_miss",
                kind="call_by",
                call_by=CallBySpecIr(
                    reference=RuntimeHandleIdIr(handle_id="default:amount"),
                    field_names=("fk_id",),
                ),
            ),
        ),
    )
    runtime_bindings.ref_default_calculators[("amount", 0)] = _default_calc
    runtime_bindings.value_transforms["amount"] = lambda v: int(v) if v is not None else None  # type: ignore[no-any-return]

    operator = _make_single_step_operator(field_key="amount", source=target_source, step=step)
    plan = _make_single_step_plan(field_key="amount", field_spec=field_spec, operator=operator)
    runtime = _make_runtime(plan, main_source, sources={str(target_source.source_id): target_source}, runtime_bindings=runtime_bindings)

    context = BatchContext()
    context.set_field_value("fk_id", 1, 1)

    LoadRefOperatorExecutor().execute(operator, context, [1], runtime)
    assert context.get_field_value("amount", 1) == 6
    assert captured["dep_args"] == (1,)
    assert captured["ctx_values"] == {"fk_id": 1}


def test_flow_resolve_default_returns_noop_when_field_spec_not_field_ir() -> None:
    runtime = _make_runtime(ExecutionPlan(field_specs={"x": object()}, operators=()), _make_main_source(), sources={})
    ctx = LoadRefExecutionContext(
        runtime,
        BatchContext(),
        [1],
        field_key="x",
        relation_signature=build_relation_signature(()),
    )
    assert _resolve_ref_default_value_on_relation_miss(ctx, 1, field_key="x") == (None, False)


def test_flow_resolve_default_skips_unsupported_when() -> None:
    runtime = _make_runtime(
        ExecutionPlan(
            field_specs={
                "x": FieldIr(
                    field_id="x",
                    name="X",
                    source=SourceIr(
                        source_id="s1",
                        key=KeyIr(key="id"),
                        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr("loader:s1")),
                    ),
                    default_cases=(FieldDefaultCaseIr(when="hit_null", kind="literal", literal=1),),
                )
            },
            operators=(),
        ),
        _make_main_source(),
        sources={},
    )
    ctx = LoadRefExecutionContext(
        runtime,
        BatchContext(),
        [1],
        field_key="x",
        relation_signature=build_relation_signature(()),
    )
    assert _resolve_ref_default_value_on_relation_miss(ctx, 1, field_key="x") == (None, False)


def test_flow_resolve_default_handles_corrupted_call_by_case() -> None:
    class _BadCase:
        when = "relation_miss"
        kind = "call_by"
        call_by = None

    field = FieldIr(
        field_id="x",
        name="X",
        source=SourceIr(
            source_id="s1",
            key=KeyIr(key="id"),
            loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr("loader:s1")),
        ),
        default_cases=(_BadCase(),),  # type: ignore[arg-type] internal tests: corrupted case instance
    )
    runtime = _make_runtime(ExecutionPlan(field_specs={"x": field}, operators=()), _make_main_source(), sources={})
    ctx = LoadRefExecutionContext(
        runtime,
        BatchContext(),
        [1],
        field_key="x",
        relation_signature=build_relation_signature(()),
    )
    assert _resolve_ref_default_value_on_relation_miss(ctx, 1, field_key="x") == (None, True)


def test_flow_resolve_default_handles_corrupted_kind_case() -> None:
    class _BadCase:
        when = "relation_miss"
        kind = "bad_kind"
        literal = None
        call_by = None

    field = FieldIr(
        field_id="x",
        name="X",
        source=SourceIr(
            source_id="s1",
            key=KeyIr(key="id"),
            loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr("loader:s1")),
        ),
        default_cases=(_BadCase(),),  # type: ignore[arg-type] internal tests: corrupted case instance
    )
    runtime = _make_runtime(ExecutionPlan(field_specs={"x": field}, operators=()), _make_main_source(), sources={})
    ctx = LoadRefExecutionContext(
        runtime,
        BatchContext(),
        [1],
        field_key="x",
        relation_signature=build_relation_signature(()),
    )
    assert _resolve_ref_default_value_on_relation_miss(ctx, 1, field_key="x") == (None, True)


def test_flow_write_relation_miss_field_value_handles_transform_errors_when_guardrails_enabled() -> None:
    runtime_bindings = RuntimeBindings()

    def _raise(_value):  # type: ignore[no-untyped-def]
        raise ValueError("bad")

    target_source = SourceIr(
        source_id="targets",
        key=KeyIr(key="target_id"),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr("source_loader:targets")),
    )
    field_spec = FieldIr(
        field_id="amount",
        name="Amount",
        source=target_source,
        default_cases=(FieldDefaultCaseIr(when="relation_miss", kind="literal", literal=1),),
    )
    runtime_bindings.value_transforms["amount"] = _raise

    plan = ExecutionPlan(field_specs={"amount": field_spec}, operators=())
    runtime = _make_runtime(
        plan,
        _make_main_source(),
        sources={str(target_source.source_id): target_source},
        runtime_bindings=runtime_bindings,
        guardrails=GuardrailsPolicy(enabled=True, mode="quiet"),
    )
    batch_context = BatchContext()
    exec_ctx = LoadRefExecutionContext(
        runtime,
        batch_context,
        [1],
        field_key="amount",
        relation_signature=build_relation_signature(()),
    )

    _write_relation_miss_field_value(
        exec_ctx,
        1,
        field_key="amount",
        required_field_keys=set(),
        required_mode=runtime.guardrails.mode,
        transform_mode=runtime.guardrails.effective_loader_transform_mode(),
        reason="test",
        lookup_key=None,
    )
    assert batch_context.get_field_value("amount", 1) is None


def test_flow_write_relation_miss_field_value_raises_transform_errors_when_guardrails_disabled() -> None:
    runtime_bindings = RuntimeBindings()

    def _raise(_value):  # type: ignore[no-untyped-def]
        raise ValueError("bad")

    target_source = SourceIr(
        source_id="targets",
        key=KeyIr(key="target_id"),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr("source_loader:targets")),
    )
    field_spec = FieldIr(
        field_id="amount",
        name="Amount",
        source=target_source,
        default_cases=(FieldDefaultCaseIr(when="relation_miss", kind="literal", literal=1),),
    )
    runtime_bindings.value_transforms["amount"] = _raise

    plan = ExecutionPlan(field_specs={"amount": field_spec}, operators=())
    runtime = _make_runtime(
        plan,
        _make_main_source(),
        sources={str(target_source.source_id): target_source},
        runtime_bindings=runtime_bindings,
    )
    batch_context = BatchContext()
    exec_ctx = LoadRefExecutionContext(
        runtime,
        batch_context,
        [1],
        field_key="amount",
        relation_signature=build_relation_signature(()),
    )

    with pytest.raises(ValueError, match=r"bad"):
        _write_relation_miss_field_value(
            exec_ctx,
            1,
            field_key="amount",
            required_field_keys=set(),
            required_mode=runtime.guardrails.mode,
            transform_mode=runtime.guardrails.effective_loader_transform_mode(),
            reason="test",
            lookup_key=None,
        )


def test_flow_write_relation_miss_field_value_noops_when_field_spec_is_not_field_ir() -> None:
    batch_context = BatchContext()
    runtime = _make_runtime(ExecutionPlan(field_specs={"x": object()}, operators=()), _make_main_source(), sources={})
    exec_ctx = LoadRefExecutionContext(
        runtime,
        batch_context,
        [1],
        field_key="x",
        relation_signature=build_relation_signature(()),
    )

    _write_relation_miss_field_value(
        exec_ctx,
        1,
        field_key="x",
        required_field_keys=set(),
        required_mode=runtime.guardrails.mode,
        transform_mode=runtime.guardrails.effective_loader_transform_mode(),
        reason="test",
        lookup_key=None,
    )
    assert batch_context.get_field_value("x", 1) is None
