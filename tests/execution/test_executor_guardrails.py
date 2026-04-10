from typing import Any, Dict, Hashable, List, Optional, Set, Tuple

import pytest

from scalim.execution.context import BatchContext
from scalim.execution.executor.batch.executor import BatchExecutor
from scalim.execution.executor.operators.load import LoadOperatorExecutor
from scalim.execution.executor.operators.load_ref.executor import LoadRefOperatorExecutor
from scalim.execution.executor.runtime.runtime import ExecutionRuntime
from scalim.execution.guardrails import (
    ScalimGuardrailViolationError as GuardrailViolation,
    GuardrailsLoaderPolicy,
    GuardrailsPolicy,
    GuardrailsRelationsPolicy,
)
from scalim.execution.runtime_bindings import RuntimeBindings
from scalim.hooks import HookManager
from scalim.ob.manager import ObserverManager
from scalim.planning.operators import LoadOperatorIr, LoadRefOperatorIr, OperatorType
from scalim.planning.plan import ExecutionPlan
from scalim.spec.ir import (
    BindingIr,
    FieldIr,
    KeyIr,
    LoaderIr,
    LookupCastSpecIr,
    LookupStepIr,
    MainSourceIr,
    RuntimeHandleIdIr,
    SourceIr,
    ValueOpIr,
)
from scalim.spec.ir.lookup_casts import lookup_cast_id


def _make_main_source(source_id: str = "orders") -> MainSourceIr:
    return MainSourceIr(source_id=source_id, loader_ref=RuntimeHandleIdIr(handle_id="{}.main_loader".format(source_id)))


def _make_runtime(
    plan: ExecutionPlan,
    *,
    main_source: Optional[MainSourceIr],
    sources: Optional[Dict[str, SourceIr]] = None,
    runtime_bindings: Optional[RuntimeBindings] = None,
    guardrails: Optional[GuardrailsPolicy] = None,
) -> ExecutionRuntime:
    resolved_sources: Dict[str, SourceIr] = dict(sources or {})
    resolved_bindings = runtime_bindings or RuntimeBindings()
    if main_source is not None and main_source.source_id not in resolved_bindings.main_source_loaders:
        resolved_bindings.main_source_loaders[str(main_source.source_id)] = lambda: []
    return ExecutionRuntime(
        plan,
        HookManager(),
        ObserverManager(),
        main_source=main_source,
        sources=resolved_sources,
        runtime_bindings=resolved_bindings,
        guardrails=guardrails,
    )


def _raise_value_error(_value: Any) -> Any:
    raise ValueError("bad")


def _make_load_binding() -> BindingIr:
    return BindingIr(
        key_field="order_id",
        params_builder_ref=RuntimeHandleIdIr(handle_id="orders.params_builder.order_id"),
        param_name="order_ids",
    )


def _make_load_ref_binding() -> BindingIr:
    return BindingIr(
        key_field="target_id",
        params_builder_ref=RuntimeHandleIdIr(handle_id="targets.params_builder.target_id"),
        param_name="target_ids",
    )


def _orders_params_builder(ctx) -> Tuple[Tuple[object, ...], Dict[str, object]]:  # type: ignore[no-untyped-def]
    return (), {"order_ids": list(ctx.batch_row_nth)}


def _targets_params_builder(ctx) -> Tuple[Tuple[object, ...], Dict[str, object]]:  # type: ignore[no-untyped-def]
    keys = ctx.lookup_keys_list
    if keys is None:
        keys = list(ctx.lookup_keys or [])
    return (), {"target_ids": list(keys)}


def _make_orders_source(*, loader: Any, extractor: Optional[Any] = None) -> SourceIr:
    _ = loader
    binding = _make_load_binding()
    return SourceIr(
        source_id="orders",
        key=KeyIr(key="order_id"),
        loader_spec=LoaderIr(
            callable_ref=RuntimeHandleIdIr(handle_id="orders.loader"),
            extractor_ref=RuntimeHandleIdIr(handle_id="orders.extractor") if extractor is not None else None,
            bindings={"order_id": binding},
        ),
    )


def _make_targets_source(*, loader: Any, extractor: Optional[Any] = None, lookup_chunk_size: int = 0) -> Tuple[SourceIr, BindingIr]:
    _ = loader
    binding = _make_load_ref_binding()
    source = SourceIr(
        source_id="targets",
        key=KeyIr(key="target_id"),
        loader_spec=LoaderIr(
            callable_ref=RuntimeHandleIdIr(handle_id="targets.loader"),
            extractor_ref=RuntimeHandleIdIr(handle_id="targets.extractor") if extractor is not None else None,
            bindings={"target_id": binding},
        ),
    )
    if lookup_chunk_size:
        source = SourceIr(
            source_id=source.source_id,
            key=source.key,
            loader_spec=source.loader_spec,
            lookup_chunk_size=lookup_chunk_size,
        )
    return source, binding


def _guardrail_logged_required_field_missing(source_id: str, field_key: str) -> Set[Tuple[str, ...]]:
    return {("loader_required_field_missing", source_id, field_key)}


def test_guardrails_validate_result_contract_fast_fails_for_load_and_load_ref() -> None:
    def _bad_loader(order_ids: List[int]) -> Any:  # noqa: ARG001
        _ = order_ids
        return [{"amount": 1}]

    source = _make_orders_source(loader=_bad_loader)
    operator = LoadOperatorIr(
        operator_id="load_orders",
        operator_type=OperatorType.LOAD.value,
        source_id=source.source_id,
        field_keys=("amount",),
    )
    plan = ExecutionPlan(operators=(operator,), field_specs={}, target_fields=["amount"])
    guardrails = GuardrailsPolicy(enabled=True, mode="quiet", loader=GuardrailsLoaderPolicy(validate_result=True))
    runtime_bindings = RuntimeBindings(
        source_loaders={"orders": _bad_loader},
        params_builders={("orders", "order_id"): _orders_params_builder},
    )
    runtime = _make_runtime(
        plan,
        main_source=_make_main_source(),
        sources={"orders": source},
        runtime_bindings=runtime_bindings,
        guardrails=guardrails,
    )

    with pytest.raises(GuardrailViolation) as exc_info:
        LoadOperatorExecutor().execute(operator, BatchContext(), [1], runtime)

    assert exc_info.value.code == "loader_result_not_mapping"

    def _bad_ref_loader(target_ids: List[int]) -> Any:  # noqa: ARG001
        _ = target_ids
        return [{"name": "Alpha"}]

    ref_source, ref_binding = _make_targets_source(loader=_bad_ref_loader, lookup_chunk_size=1)
    ref_field_spec = FieldIr(field_id="target_name", name="Target", source=ref_source, data_key="name")
    step = LookupStepIr(from_field="fk_id", to_source=ref_source, bind=ref_binding)
    ref_operator = LoadRefOperatorIr(
        operator_id="load_ref",
        operator_type=OperatorType.LOAD_REF.value,
        source_id=ref_source.source_id,
        field_key="target_name",
        lookup_steps=(step,),
    )
    ref_plan = ExecutionPlan(operators=(ref_operator,), field_specs={"target_name": ref_field_spec}, target_fields=["target_name"])
    ref_runtime_bindings = RuntimeBindings(
        source_loaders={"targets": _bad_ref_loader},
        params_builders={("targets", "target_id"): _targets_params_builder},
    )
    ref_runtime = _make_runtime(
        ref_plan,
        main_source=_make_main_source(),
        sources={"targets": ref_source},
        runtime_bindings=ref_runtime_bindings,
        guardrails=guardrails,
    )
    context = BatchContext()
    context.set_field_value("fk_id", 1, 1)
    context.set_field_value("fk_id", 2, 2)

    with pytest.raises(GuardrailViolation) as exc_info:
        LoadRefOperatorExecutor().execute(ref_operator, context, [1, 2], ref_runtime)

    assert exc_info.value.code == "loader_result_not_mapping"


def test_guardrails_load_operator_required_fields_missing_row_and_value() -> None:
    def _empty_loader(order_ids: List[int]) -> Dict[Hashable, Any]:  # noqa: ARG001
        _ = order_ids
        return {}

    source = _make_orders_source(loader=_empty_loader)
    operator = LoadOperatorIr(
        operator_id="load_orders",
        operator_type=OperatorType.LOAD.value,
        source_id=source.source_id,
        field_keys=("amount",),
        is_primary=True,
    )
    plan = ExecutionPlan(operators=(operator,), field_specs={}, target_fields=["amount"])

    quiet = GuardrailsPolicy(enabled=True, mode="quiet", loader=GuardrailsLoaderPolicy(required_fields=("amount",)))
    runtime_bindings = RuntimeBindings(
        source_loaders={"orders": _empty_loader},
        params_builders={("orders", "order_id"): _orders_params_builder},
    )
    runtime = _make_runtime(
        plan,
        main_source=_make_main_source(),
        sources={"orders": source},
        runtime_bindings=runtime_bindings,
        guardrails=quiet,
    )
    context = BatchContext()
    LoadOperatorExecutor().execute(operator, context, [1, 2], runtime)
    assert context.get_field_value("amount", 1) is None
    assert context.get_field_value("amount", 2) is None
    assert runtime.guardrail_logged == _guardrail_logged_required_field_missing("orders", "amount")

    fast_fail = GuardrailsPolicy(enabled=True, mode="fast_fail", loader=GuardrailsLoaderPolicy(required_fields=("amount",)))
    runtime = _make_runtime(
        plan,
        main_source=_make_main_source(),
        sources={"orders": source},
        runtime_bindings=runtime_bindings,
        guardrails=fast_fail,
    )
    with pytest.raises(GuardrailViolation, match="Required field") as exc_info:
        LoadOperatorExecutor().execute(operator, BatchContext(), [1], runtime)
    assert exc_info.value.code == "loader_required_field_missing"

    def _none_value_loader(order_ids: List[int]) -> Dict[Hashable, Any]:  # noqa: ARG001
        _ = order_ids
        return {1: {"amount": None}}

    source = _make_orders_source(loader=_none_value_loader)
    field_spec = FieldIr(field_id="amount", name="Amount", source=source)
    operator = LoadOperatorIr(
        operator_id="load_orders",
        operator_type=OperatorType.LOAD.value,
        source_id=source.source_id,
        field_keys=("amount",),
        is_primary=True,
    )
    plan = ExecutionPlan(operators=(operator,), field_specs={"amount": field_spec}, target_fields=["amount"])
    runtime_bindings = RuntimeBindings(
        source_loaders={"orders": _none_value_loader},
        params_builders={("orders", "order_id"): _orders_params_builder},
    )

    runtime = _make_runtime(
        plan,
        main_source=_make_main_source(),
        sources={"orders": source},
        runtime_bindings=runtime_bindings,
        guardrails=quiet,
    )
    context = BatchContext()
    LoadOperatorExecutor().execute(operator, context, [1], runtime)
    assert context.get_field_value("amount", 1) is None
    assert runtime.guardrail_logged == _guardrail_logged_required_field_missing("orders", "amount")

    runtime = _make_runtime(
        plan,
        main_source=_make_main_source(),
        sources={"orders": source},
        runtime_bindings=runtime_bindings,
        guardrails=fast_fail,
    )
    with pytest.raises(GuardrailViolation) as exc_info:
        LoadOperatorExecutor().execute(operator, BatchContext(), [1], runtime)
    assert exc_info.value.code == "loader_required_field_missing"


def test_guardrails_load_operator_extractor_and_transform_error_modes() -> None:
    def _loader(order_ids: List[int]) -> Dict[Hashable, Any]:  # noqa: ARG001
        _ = order_ids
        return {1: {"amount": 1}}

    def _extract(_pk: Hashable, _result: Any) -> Any:
        raise ValueError("boom")

    source = _make_orders_source(loader=_loader, extractor=_extract)
    operator = LoadOperatorIr(
        operator_id="load_orders",
        operator_type=OperatorType.LOAD.value,
        source_id=source.source_id,
        field_keys=("amount",),
    )
    plan = ExecutionPlan(operators=(operator,), field_specs={}, target_fields=["amount"])

    runtime_bindings = RuntimeBindings(
        source_loaders={"orders": _loader},
        params_builders={("orders", "order_id"): _orders_params_builder},
        loader_extractors={"orders": _extract},
    )
    runtime = _make_runtime(plan, main_source=_make_main_source(), sources={"orders": source}, runtime_bindings=runtime_bindings)
    with pytest.raises(ValueError, match="boom"):
        LoadOperatorExecutor().execute(operator, BatchContext(), [1], runtime)

    quiet = GuardrailsPolicy(enabled=True, mode="quiet", loader=GuardrailsLoaderPolicy(on_transform_error="quiet"))
    runtime = _make_runtime(
        plan,
        main_source=_make_main_source(),
        sources={"orders": source},
        runtime_bindings=runtime_bindings,
        guardrails=quiet,
    )
    context = BatchContext()
    LoadOperatorExecutor().execute(operator, context, [1], runtime)
    assert context.get_field_value("amount", 1) is None

    fast_fail = GuardrailsPolicy(enabled=True, mode="fast_fail", loader=GuardrailsLoaderPolicy(on_transform_error="fast_fail"))
    runtime = _make_runtime(
        plan,
        main_source=_make_main_source(),
        sources={"orders": source},
        runtime_bindings=runtime_bindings,
        guardrails=fast_fail,
    )
    with pytest.raises(GuardrailViolation) as exc_info:
        LoadOperatorExecutor().execute(operator, BatchContext(), [1], runtime)
    assert exc_info.value.code == "loader_extractor_error"

    source = _make_orders_source(loader=_loader)
    field_spec = FieldIr(
        field_id="amount",
        name="Amount",
        source=source,
        value_ops=(ValueOpIr(kind="transform", callable_ref=RuntimeHandleIdIr(handle_id="fields.amount.transform")),),
    )
    operator = LoadOperatorIr(
        operator_id="load_orders",
        operator_type=OperatorType.LOAD.value,
        source_id=source.source_id,
        field_keys=("amount",),
        is_primary=True,
    )
    plan = ExecutionPlan(operators=(operator,), field_specs={"amount": field_spec}, target_fields=["amount"])

    runtime_bindings = RuntimeBindings(
        source_loaders={"orders": _loader},
        params_builders={("orders", "order_id"): _orders_params_builder},
        value_transforms={"amount": _raise_value_error},
    )
    runtime = _make_runtime(plan, main_source=_make_main_source(), sources={"orders": source}, runtime_bindings=runtime_bindings)
    with pytest.raises(ValueError, match="bad"):
        LoadOperatorExecutor().execute(operator, BatchContext(), [1], runtime)

    runtime = _make_runtime(
        plan,
        main_source=_make_main_source(),
        sources={"orders": source},
        runtime_bindings=runtime_bindings,
        guardrails=quiet,
    )
    context = BatchContext()
    LoadOperatorExecutor().execute(operator, context, [1], runtime)
    assert context.get_field_value("amount", 1) is None

    runtime = _make_runtime(
        plan,
        main_source=_make_main_source(),
        sources={"orders": source},
        runtime_bindings=runtime_bindings,
        guardrails=fast_fail,
    )
    with pytest.raises(GuardrailViolation) as exc_info:
        LoadOperatorExecutor().execute(operator, BatchContext(), [1], runtime)
    assert exc_info.value.code == "loader_transform_error"


def _make_load_ref_operator(
    *,
    field_key: str,
    field_spec: FieldIr,
    loader: Any,
    extractor: Optional[Any] = None,
) -> Tuple[LoadRefOperatorIr, ExecutionPlan, BindingIr]:
    source, binding = _make_targets_source(loader=loader, extractor=extractor)
    step = LookupStepIr(from_field="fk_id", to_source=source, bind=binding)
    operator = LoadRefOperatorIr(
        operator_id="load_ref",
        operator_type=OperatorType.LOAD_REF.value,
        source_id=source.source_id,
        field_key=field_key,
        lookup_steps=(step,),
    )
    plan = ExecutionPlan(operators=(operator,), field_specs={field_key: field_spec}, target_fields=[field_key])
    return operator, plan, binding


def test_guardrails_load_ref_required_field_missing_variants() -> None:
    quiet = GuardrailsPolicy(enabled=True, mode="quiet", loader=GuardrailsLoaderPolicy(required_fields=("target_name",)))
    fast_fail = GuardrailsPolicy(enabled=True, mode="fast_fail", loader=GuardrailsLoaderPolicy(required_fields=("target_name",)))

    def _missing_lookup_key_loader(target_ids: List[int]) -> Dict[Hashable, Any]:  # noqa: ARG001
        _ = target_ids
        return {}

    source, binding = _make_targets_source(loader=_missing_lookup_key_loader)
    runtime_bindings = RuntimeBindings(
        source_loaders={"targets": _missing_lookup_key_loader},
        params_builders={("targets", "target_id"): _targets_params_builder},
    )
    field_spec = FieldIr(field_id="target_name", name="Target", source=source, data_key="name")
    step = LookupStepIr(from_field="fk_id", to_source=source, bind=binding)
    operator = LoadRefOperatorIr(
        operator_id="load_ref",
        operator_type=OperatorType.LOAD_REF.value,
        source_id=source.source_id,
        field_key="target_name",
        lookup_steps=(step,),
    )
    plan = ExecutionPlan(operators=(operator,), field_specs={"target_name": field_spec}, target_fields=["target_name"])

    runtime = _make_runtime(
        plan,
        main_source=_make_main_source(),
        sources={"targets": source},
        runtime_bindings=runtime_bindings,
        guardrails=quiet,
    )
    context = BatchContext()
    context.set_field_value("fk_id", 1, 1)
    context.set_field_value("fk_id", 2, 2)
    LoadRefOperatorExecutor().execute(operator, context, [1, 2], runtime)
    assert context.get_field_value("target_name", 1) is None
    assert context.get_field_value("target_name", 2) is None
    assert runtime.guardrail_logged == _guardrail_logged_required_field_missing("targets", "target_name")

    runtime = _make_runtime(
        plan,
        main_source=_make_main_source(),
        sources={"targets": source},
        runtime_bindings=runtime_bindings,
        guardrails=fast_fail,
    )
    context = BatchContext()
    context.set_field_value("fk_id", 1, 1)
    with pytest.raises(GuardrailViolation) as exc_info:
        LoadRefOperatorExecutor().execute(operator, context, [1], runtime)
    assert exc_info.value.code == "loader_required_field_missing"

    def _missing_field_value_loader(target_ids: List[int]) -> Dict[Hashable, Any]:  # noqa: ARG001
        _ = target_ids
        return {1: {}}

    source, binding = _make_targets_source(loader=_missing_field_value_loader)
    runtime_bindings = RuntimeBindings(
        source_loaders={"targets": _missing_field_value_loader},
        params_builders={("targets", "target_id"): _targets_params_builder},
    )
    field_spec = FieldIr(field_id="target_name", name="Target", source=source, data_key="name")
    step = LookupStepIr(from_field="fk_id", to_source=source, bind=binding)
    operator = LoadRefOperatorIr(
        operator_id="load_ref",
        operator_type=OperatorType.LOAD_REF.value,
        source_id=source.source_id,
        field_key="target_name",
        lookup_steps=(step,),
    )
    plan = ExecutionPlan(operators=(operator,), field_specs={"target_name": field_spec}, target_fields=["target_name"])

    runtime = _make_runtime(
        plan,
        main_source=_make_main_source(),
        sources={"targets": source},
        runtime_bindings=runtime_bindings,
        guardrails=quiet,
    )
    context = BatchContext()
    context.set_field_value("fk_id", 1, 1)
    LoadRefOperatorExecutor().execute(operator, context, [1], runtime)
    assert context.get_field_value("target_name", 1) is None
    assert runtime.guardrail_logged == _guardrail_logged_required_field_missing("targets", "target_name")

    runtime = _make_runtime(
        plan,
        main_source=_make_main_source(),
        sources={"targets": source},
        runtime_bindings=runtime_bindings,
        guardrails=fast_fail,
    )
    context = BatchContext()
    context.set_field_value("fk_id", 1, 1)
    with pytest.raises(GuardrailViolation) as exc_info:
        LoadRefOperatorExecutor().execute(operator, context, [1], runtime)
    assert exc_info.value.code == "loader_required_field_missing"

    def _missing_field_spec_loader(target_ids: List[int]) -> Dict[Hashable, Any]:  # noqa: ARG001
        _ = target_ids
        return {1: {}}

    source, binding = _make_targets_source(loader=_missing_field_spec_loader)
    runtime_bindings = RuntimeBindings(
        source_loaders={"targets": _missing_field_spec_loader},
        params_builders={("targets", "target_id"): _targets_params_builder},
    )
    value_spec = FieldIr(field_id="value", name="Value", source=source)
    step = LookupStepIr(from_field="fk_id", to_source=source, bind=binding)
    operator = LoadRefOperatorIr(
        operator_id="load_ref",
        operator_type=OperatorType.LOAD_REF.value,
        source_id=source.source_id,
        field_key="value",
        lookup_steps=(step,),
    )
    plan = ExecutionPlan(operators=(operator,), field_specs={}, target_fields=["value"])

    quiet_value = GuardrailsPolicy(enabled=True, mode="quiet", loader=GuardrailsLoaderPolicy(required_fields=("value",)))
    fast_fail_value = GuardrailsPolicy(enabled=True, mode="fast_fail", loader=GuardrailsLoaderPolicy(required_fields=("value",)))

    runtime = _make_runtime(
        plan,
        main_source=_make_main_source(),
        sources={"targets": source},
        runtime_bindings=runtime_bindings,
        guardrails=quiet_value,
    )
    context = BatchContext()
    context.set_field_value("fk_id", 1, 1)
    LoadRefOperatorExecutor().execute(operator, context, [1], runtime)
    assert context.get_field_value("value", 1) is None
    assert runtime.guardrail_logged == _guardrail_logged_required_field_missing("targets", "value")

    runtime = _make_runtime(
        plan,
        main_source=_make_main_source(),
        sources={"targets": source},
        runtime_bindings=runtime_bindings,
        guardrails=fast_fail_value,
    )
    context = BatchContext()
    context.set_field_value("fk_id", 1, 1)
    with pytest.raises(GuardrailViolation) as exc_info:
        LoadRefOperatorExecutor().execute(operator, context, [1], runtime)
    assert exc_info.value.code == "loader_required_field_missing"


def test_guardrails_load_ref_extractor_and_transform_error_modes() -> None:
    def _loader(target_ids: List[int]) -> Dict[Hashable, Any]:  # noqa: ARG001
        _ = target_ids
        return {1: {"name": "Alpha"}}

    def _extract(_pk: Hashable, _result: Any) -> Any:
        raise ValueError("boom")

    source, binding = _make_targets_source(loader=_loader, extractor=_extract)
    field_spec = FieldIr(field_id="target_name", name="Target", source=source, data_key="name")
    step = LookupStepIr(from_field="fk_id", to_source=source, bind=binding)
    operator = LoadRefOperatorIr(
        operator_id="load_ref",
        operator_type=OperatorType.LOAD_REF.value,
        source_id=source.source_id,
        field_key="target_name",
        lookup_steps=(step,),
    )
    plan = ExecutionPlan(operators=(operator,), field_specs={"target_name": field_spec}, target_fields=["target_name"])

    runtime_bindings = RuntimeBindings(
        source_loaders={"targets": _loader},
        params_builders={("targets", "target_id"): _targets_params_builder},
        loader_extractors={"targets": _extract},
    )
    runtime = _make_runtime(plan, main_source=_make_main_source(), sources={"targets": source}, runtime_bindings=runtime_bindings)
    context = BatchContext()
    context.set_field_value("fk_id", 1, 1)
    with pytest.raises(ValueError, match="boom"):
        LoadRefOperatorExecutor().execute(operator, context, [1], runtime)

    quiet = GuardrailsPolicy(enabled=True, mode="quiet", loader=GuardrailsLoaderPolicy(on_transform_error="quiet"))
    runtime = _make_runtime(
        plan,
        main_source=_make_main_source(),
        sources={"targets": source},
        runtime_bindings=runtime_bindings,
        guardrails=quiet,
    )
    context = BatchContext()
    context.set_field_value("fk_id", 1, 1)
    LoadRefOperatorExecutor().execute(operator, context, [1], runtime)
    assert context.get_field_value("target_name", 1) is None

    fast_fail = GuardrailsPolicy(enabled=True, mode="fast_fail", loader=GuardrailsLoaderPolicy(on_transform_error="fast_fail"))
    runtime = _make_runtime(
        plan,
        main_source=_make_main_source(),
        sources={"targets": source},
        runtime_bindings=runtime_bindings,
        guardrails=fast_fail,
    )
    context = BatchContext()
    context.set_field_value("fk_id", 1, 1)
    with pytest.raises(GuardrailViolation) as exc_info:
        LoadRefOperatorExecutor().execute(operator, context, [1], runtime)
    assert exc_info.value.code == "loader_extractor_error"

    source, binding = _make_targets_source(loader=_loader)
    field_spec = FieldIr(
        field_id="target_name",
        name="Target",
        source=source,
        data_key="name",
        value_ops=(ValueOpIr(kind="transform", callable_ref=RuntimeHandleIdIr(handle_id="fields.target_name.transform")),),
    )
    step = LookupStepIr(from_field="fk_id", to_source=source, bind=binding)
    operator = LoadRefOperatorIr(
        operator_id="load_ref",
        operator_type=OperatorType.LOAD_REF.value,
        source_id=source.source_id,
        field_key="target_name",
        lookup_steps=(step,),
    )
    plan = ExecutionPlan(operators=(operator,), field_specs={"target_name": field_spec}, target_fields=["target_name"])

    runtime_bindings = RuntimeBindings(
        source_loaders={"targets": _loader},
        params_builders={("targets", "target_id"): _targets_params_builder},
        value_transforms={"target_name": _raise_value_error},
    )
    runtime = _make_runtime(plan, main_source=_make_main_source(), sources={"targets": source}, runtime_bindings=runtime_bindings)
    context = BatchContext()
    context.set_field_value("fk_id", 1, 1)
    with pytest.raises(ValueError, match="bad"):
        LoadRefOperatorExecutor().execute(operator, context, [1], runtime)


def test_guardrails_relations_quiet_records_rate_violations_without_raising() -> None:
    int_cast = LookupCastSpecIr(name="int")
    source = SourceIr(
        source_id="targets",
        key=KeyIr(key="id", cast=int_cast),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr(handle_id="targets.loader")),
    )
    step = LookupStepIr(from_field="fk_id", to_source=source)

    plan = ExecutionPlan(field_specs={}, target_fields=[])
    runtime_bindings = RuntimeBindings(lookup_key_casts={lookup_cast_id(int_cast, is_multi=False): int})
    guardrails = GuardrailsPolicy(
        enabled=True,
        mode="quiet",
        relations=GuardrailsRelationsPolicy(null_key_max_rate=0.0, type_error_max_rate=0.0),
    )
    runtime = _make_runtime(plan, main_source=_make_main_source(), runtime_bindings=runtime_bindings, guardrails=guardrails)

    _, status, _ = runtime.normalize_lookup_key_with_status(None, step)
    assert status == "null_key"

    _, status, _ = runtime.normalize_lookup_key_with_status("not-int", step)
    assert status == "type_error"

    assert len(runtime.guardrail_logged) == 2


def test_guardrails_batch_prefill_main_source_fields_variants() -> None:
    main_source = _make_main_source()
    field_spec = FieldIr(
        field_id="amount",
        name="Amount",
        source=main_source,
        value_ops=(ValueOpIr(kind="transform", callable_ref=RuntimeHandleIdIr(handle_id="fields.amount.transform")),),
    )
    runtime_bindings = RuntimeBindings(value_transforms={"amount": _raise_value_error})
    plan = ExecutionPlan(field_specs={"amount": field_spec}, target_fields=["amount"])

    quiet = GuardrailsPolicy(enabled=True, mode="quiet", loader=GuardrailsLoaderPolicy(required_fields=("amount",)))
    runtime = _make_runtime(plan, main_source=main_source, runtime_bindings=runtime_bindings, guardrails=quiet)
    context = BatchContext()
    main_rows = {1: {"amount": 1}, 2: {"amount": 2}}

    BatchExecutor(plan, runtime).prefill_main_source_fields(context, main_rows, required_fields={"amount"})

    assert context.get_field_value("amount", 1) is None
    assert context.get_field_value("amount", 2) is None
    assert runtime.guardrail_logged == _guardrail_logged_required_field_missing("orders", "amount")

    fast_fail = GuardrailsPolicy(enabled=True, mode="fast_fail", loader=GuardrailsLoaderPolicy(on_transform_error="fast_fail"))
    runtime = _make_runtime(plan, main_source=main_source, runtime_bindings=runtime_bindings, guardrails=fast_fail)
    context = BatchContext()
    main_rows = {1: {"amount": 1}}

    with pytest.raises(GuardrailViolation) as exc_info:
        BatchExecutor(plan, runtime).prefill_main_source_fields(context, main_rows, required_fields={"amount"})
    assert exc_info.value.code == "loader_transform_error"

    runtime = _make_runtime(plan, main_source=main_source, runtime_bindings=runtime_bindings)
    context = BatchContext()
    with pytest.raises(ValueError, match="bad"):
        BatchExecutor(plan, runtime).prefill_main_source_fields(context, main_rows, required_fields={"amount"})

    field_spec = FieldIr(field_id="amount", name="Amount", source=main_source)
    plan = ExecutionPlan(field_specs={"amount": field_spec}, target_fields=["amount"])
    missing_required = GuardrailsPolicy(enabled=True, mode="fast_fail", loader=GuardrailsLoaderPolicy(required_fields=("amount",)))
    runtime = _make_runtime(plan, main_source=main_source, guardrails=missing_required)
    context = BatchContext()
    with pytest.raises(GuardrailViolation) as exc_info:
        BatchExecutor(plan, runtime).prefill_main_source_fields(context, {1: {}}, required_fields={"amount"})
    assert exc_info.value.code == "loader_required_field_missing"

    passthrough_plan = ExecutionPlan(field_specs={}, target_fields=["extra"])
    quiet_passthrough = GuardrailsPolicy(enabled=True, mode="quiet", loader=GuardrailsLoaderPolicy(required_fields=("extra",)))
    runtime = _make_runtime(passthrough_plan, main_source=main_source, guardrails=quiet_passthrough)
    context = BatchContext()
    BatchExecutor(passthrough_plan, runtime).prefill_main_source_fields(context, {1: {}, 2: {}}, required_fields={"extra"})
    assert context.get_field_value("extra", 1) is None
    assert context.get_field_value("extra", 2) is None
    assert runtime.guardrail_logged == _guardrail_logged_required_field_missing("orders", "extra")

    fast_fail_passthrough = GuardrailsPolicy(enabled=True, mode="fast_fail", loader=GuardrailsLoaderPolicy(required_fields=("extra",)))
    runtime = _make_runtime(passthrough_plan, main_source=main_source, guardrails=fast_fail_passthrough)
    context = BatchContext()
    with pytest.raises(GuardrailViolation) as exc_info:
        BatchExecutor(passthrough_plan, runtime).prefill_main_source_fields(context, {1: {}}, required_fields={"extra"})
    assert exc_info.value.code == "loader_required_field_missing"
