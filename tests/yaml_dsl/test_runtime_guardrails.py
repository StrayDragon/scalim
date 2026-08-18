from collections import UserDict
from types import MappingProxyType, SimpleNamespace
from typing import Any, Dict, Hashable, List, Optional, Set

import pytest

from scalim.execution.engine import ScalimEngine
from scalim.execution.guardrails import (
    ScalimGuardrailViolationError as GuardrailViolation,
    GuardrailsComputePolicy,
    GuardrailsLoaderPolicy,
    GuardrailsPolicy,
    GuardrailsRelationsPolicy,
)
from scalim.execution.executor.helpers.field_access import extract_field
from scalim.execution.runtime_bindings import RuntimeBindings
from scalim.planning import PlanBuilder
from scalim.spec.ir.binding import BindingIr, LoaderIr
from scalim.spec.ir import DemandIr
from scalim.spec.ir import DerivedFieldIr, FieldIr
from scalim.spec.ir import KeyIr, LookupCastSpecIr, MainSourceIr, RuntimeHandleIdIr, SourceIr, ValueOpIr
from scalim.spec.ir.lookup_casts import lookup_cast_id


def test_extract_field_rowlike_precedence() -> None:
    assert extract_field({"a": 1}, "a") == 1
    assert extract_field(UserDict({"a": 1}), "a") == 1
    assert extract_field(MappingProxyType({"a": 1}), "a") == 1

    assert extract_field(SimpleNamespace(a=1), "a") == 1

    class _GetItemOnly:
        def __init__(self) -> None:
            self._data = {"a": 1}

        def __getitem__(self, key: str) -> Any:
            return self._data[key]

    assert extract_field(_GetItemOnly(), "a") == 1

    from collections.abc import Mapping as _Mapping  # noqa: PLC0415

    class _AttrMapping(_Mapping):
        def __init__(self) -> None:
            self._data = {"a": 1}

        def __getitem__(self, key: str) -> Any:
            return self._data[key]

        def __iter__(self):  # type: ignore[no-untyped-def]
            return iter(self._data)

        def __len__(self) -> int:
            return len(self._data)

        @property
        def a(self) -> int:
            return 999

    assert extract_field(_AttrMapping(), "a") == 1


def _build_relation_demand(
    *,
    main_rows: List[Dict[str, Any]],
    customer_loader_result: Any,
    customer_key_cast: Optional[LookupCastSpecIr] = None,
    customer_transform: Optional[Any] = None,
) -> Any:
    def _main_loader() -> List[Dict[str, Any]]:
        return list(main_rows)

    def _customer_loader(customer_ids_set: Optional[Set[Hashable]] = None) -> Any:  # noqa: ARG001
        return customer_loader_result

    runtime_bindings = RuntimeBindings(
        main_source_loaders={"orders": _main_loader},
        source_loaders={"customers": _customer_loader},
        params_builders={
            ("customers", "customer_id"): lambda ctx: ((), {"customer_ids_set": ctx.lookup_keys}),
        },
    )
    if customer_transform is not None:
        runtime_bindings.value_transforms["customer_name"] = customer_transform

    if customer_key_cast is not None:
        from scalim.dsl.yaml_dsl.runtime.conversion import LookupCastRegistry

        registry = LookupCastRegistry()
        cast_key = lookup_cast_id(customer_key_cast, is_multi=False)
        runtime_bindings.lookup_key_casts[cast_key] = registry.build(customer_key_cast, is_multi=False)

    customers_loader = LoaderIr(
        callable_ref=RuntimeHandleIdIr(handle_id="customers.loader"),
        bindings={
            "customer_id": BindingIr(
                key_field="customer_id",
                params_builder_ref=RuntimeHandleIdIr(handle_id="customers.customer_id.params_builder"),
            ),
        },
    )

    orders_source = MainSourceIr(source_id="orders", loader_ref=RuntimeHandleIdIr(handle_id="orders.loader"))
    customers_source = SourceIr(
        source_id="customers",
        key=KeyIr(key="customer_id", cast=customer_key_cast),
        loader_spec=customers_loader,
    )

    orders_to_customers = orders_source["customer_id"].join(customers_source["customer_id"])

    customer_field = FieldIr(
        field_id="customer_name",
        name="Customer Name",
        source_id=customers_source.source_id,
        data_key="customer_name",
        relation=orders_to_customers,
        value_ops=(
            (ValueOpIr(kind="transform", callable_ref=RuntimeHandleIdIr(handle_id="customer_name.transform")),)
            if customer_transform is not None
            else ()
        ),
    )

    demand = DemandIr.from_irs(
        sources=[customers_source],
        fields=[
            FieldIr(field_id="order_id", name="Order ID", source_id=orders_source.source_id, is_primary=True),
            customer_field,
        ],
        main_source=orders_source,
    )
    return demand, runtime_bindings


def test_guardrails_validate_result_contract_always_fast_fail_even_in_quiet_mode() -> None:
    demand, runtime_bindings = _build_relation_demand(
        main_rows=[{"order_id": 1, "customer_id": 100}],
        customer_loader_result=[{"customer_id": 100, "customer_name": "Alice"}],
    )
    plan = PlanBuilder(demand).build(targets=["customer_name"])

    guardrails = GuardrailsPolicy(
        enabled=True,
        mode="quiet",
        loader=GuardrailsLoaderPolicy(validate_result=True),
    )
    engine = ScalimEngine(demand=demand, plan=plan, runtime_bindings=runtime_bindings, batch_size=1, guardrails=guardrails)

    with pytest.raises(GuardrailViolation) as exc_info:
        _ = engine.run()

    assert exc_info.value.code == "loader_result_not_mapping"


def test_guardrails_loader_transform_error_quiet_writes_none_and_continues() -> None:
    def _boom(_value: Any) -> Any:
        raise ValueError("boom")

    demand, runtime_bindings = _build_relation_demand(
        main_rows=[{"order_id": 1, "customer_id": 100}],
        customer_loader_result={100: {"customer_id": 100, "customer_name": "Alice"}},
        customer_transform=_boom,
    )
    plan = PlanBuilder(demand).build(targets=["customer_name"])

    guardrails = GuardrailsPolicy(
        enabled=True,
        mode="quiet",
        loader=GuardrailsLoaderPolicy(on_transform_error="quiet"),
    )
    engine = ScalimEngine(demand=demand, plan=plan, runtime_bindings=runtime_bindings, batch_size=1, guardrails=guardrails)

    results = engine.run()
    assert results and results[0]["customer_name"] is None


def test_guardrails_loader_transform_error_fast_fail_aborts() -> None:
    def _boom(_value: Any) -> Any:
        raise ValueError("boom")

    demand, runtime_bindings = _build_relation_demand(
        main_rows=[{"order_id": 1, "customer_id": 100}],
        customer_loader_result={100: {"customer_id": 100, "customer_name": "Alice"}},
        customer_transform=_boom,
    )
    plan = PlanBuilder(demand).build(targets=["customer_name"])

    guardrails = GuardrailsPolicy(
        enabled=True,
        mode="fast_fail",
        loader=GuardrailsLoaderPolicy(on_transform_error="fast_fail"),
    )
    engine = ScalimEngine(demand=demand, plan=plan, runtime_bindings=runtime_bindings, batch_size=1, guardrails=guardrails)

    with pytest.raises(GuardrailViolation) as exc_info:
        _ = engine.run()

    assert exc_info.value.code == "loader_transform_error"


def test_guardrails_relations_null_key_max_rate_fast_fail() -> None:
    demand, runtime_bindings = _build_relation_demand(
        main_rows=[
            {"order_id": 1, "customer_id": None},
        ],
        customer_loader_result={},
    )
    plan = PlanBuilder(demand).build(targets=["customer_name"])

    guardrails = GuardrailsPolicy(
        enabled=True,
        mode="fast_fail",
        relations=GuardrailsRelationsPolicy(null_key_max_rate=0.0),
    )
    engine = ScalimEngine(demand=demand, plan=plan, runtime_bindings=runtime_bindings, batch_size=1, guardrails=guardrails)

    with pytest.raises(GuardrailViolation) as exc_info:
        _ = engine.run()

    assert exc_info.value.code == "relation_null_key_rate_exceeded"


def test_guardrails_relations_type_error_max_rate_fast_fail() -> None:
    demand, runtime_bindings = _build_relation_demand(
        main_rows=[
            {"order_id": 1, "customer_id": "not-an-int"},
        ],
        customer_loader_result={},
        customer_key_cast=LookupCastSpecIr(name="int"),
    )
    plan = PlanBuilder(demand).build(targets=["customer_name"])

    guardrails = GuardrailsPolicy(
        enabled=True,
        mode="fast_fail",
        relations=GuardrailsRelationsPolicy(type_error_max_rate=0.0),
    )
    engine = ScalimEngine(demand=demand, plan=plan, runtime_bindings=runtime_bindings, batch_size=1, guardrails=guardrails)

    with pytest.raises(GuardrailViolation) as exc_info:
        _ = engine.run()

    assert exc_info.value.code == "relation_type_error_rate_exceeded"


def test_guardrails_compute_fast_fail_aborts() -> None:
    def _main_loader() -> List[Dict[str, Any]]:
        return [{"x": 1}]

    main_source = MainSourceIr(source_id="orders", loader_ref=RuntimeHandleIdIr(handle_id="orders.loader"))
    runtime_bindings = RuntimeBindings(
        main_source_loaders={"orders": _main_loader},
        derived_calculators={"boom": lambda x: 1 / 0},
    )
    demand = DemandIr.from_irs(
        sources=[],
        fields=[
            FieldIr(field_id="x", name="x", source_id=main_source.source_id, is_primary=True),
            DerivedFieldIr(field_id="boom", name="boom", dependencies=("x",), compute_expr="x / 0"),
        ],
        main_source=main_source,
    )
    plan = PlanBuilder(demand).build(targets=["boom"])

    guardrails = GuardrailsPolicy(
        enabled=True,
        mode="fast_fail",
        compute=GuardrailsComputePolicy(on_error="fast_fail"),
    )
    engine = ScalimEngine(demand=demand, plan=plan, runtime_bindings=runtime_bindings, batch_size=1, guardrails=guardrails)

    with pytest.raises(GuardrailViolation) as exc_info:
        _ = engine.run()

    assert exc_info.value.code == "compute_error"
