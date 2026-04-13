from dataclasses import dataclass

import pytest

from scalim.planning import ComputeOperatorIr, ExecutionPlan, LoadOperatorIr, LoadRefOperatorIr, OperatorType
from scalim.planning.snapshots import execution_deps_snapshot, execution_plan_snapshot, operator_snapshot
from scalim.spec.ir import BindingIr, BuiltinCallableIdIr, LookupCastSpecIr, LookupStepIr


@dataclass(frozen=True)
class _DummySource:
    source_id: str


class _Template:
    def top_level_mapping_string_keys(self):
        return ("alpha", "beta")


class _TemplateWithNonCallableKeys:
    top_level_mapping_string_keys = "not-callable"


def test_operator_snapshot_for_all_core_operator_types() -> None:
    load = LoadOperatorIr(
        operator_id="load.orders",
        operator_type=str(OperatorType.LOAD),
        source_id="orders",
        field_keys=("order_id",),
        depends_on=(),
        is_primary=True,
    )
    assert operator_snapshot(load)["operator_type"] == str(OperatorType.LOAD)

    compute = ComputeOperatorIr(
        operator_id="compute.total",
        operator_type=str(OperatorType.COMPUTE),
        field_key="total",
        input_fields=("amount", "cost"),
        depends_on=("amount", "cost"),
    )
    assert operator_snapshot(compute)["operator_type"] == str(OperatorType.COMPUTE)

    lookup_cast = LookupCastSpecIr(name="sep_first", sep="|")
    lookup_cast_without_sep = LookupCastSpecIr(name="sep_first", sep=None)
    binding_template = BindingIr(key_field="order_id", params_template=_Template())
    binding_template_without_callable_keys = BindingIr(key_field="order_id", params_template=_TemplateWithNonCallableKeys())
    binding_builder = BindingIr(key_field="order_id", params_builder_ref=BuiltinCallableIdIr(callable_id="demo.builder"))

    customer_source = _DummySource(source_id="customers")
    steps = (
        LookupStepIr(
            from_field=("customer_id", "tenant_id"),
            to_source=customer_source,
            to_field=("customer_id", "tenant_id"),
            lookup_cast=lookup_cast,
        ),
        LookupStepIr(from_field="customer_id", to_source=customer_source, to_field="customer_id", lookup_cast=lookup_cast_without_sep),
        LookupStepIr(from_field="customer_id", to_source=customer_source, lookup_cast=lookup_cast, bind=binding_template),
        LookupStepIr(from_field="customer_id", to_source=customer_source, bind=binding_template_without_callable_keys),
        LookupStepIr(from_field="customer_id", to_source=customer_source, bind=binding_builder),
        LookupStepIr(from_field="customer_id", to_source=customer_source),
    )
    load_ref = LoadRefOperatorIr(
        operator_id="load_ref.customer_name",
        operator_type=str(OperatorType.LOAD_REF),
        source_id="customers",
        field_key="customer_name",
        lookup_steps=steps,
        depends_on=("customer_id",),
        use_cache=True,
    )
    payload = operator_snapshot(load_ref)
    assert payload["operator_type"] == str(OperatorType.LOAD_REF)
    assert payload["use_cache"] is True
    assert payload["lookup_steps"][0]["from_field"] == ["customer_id", "tenant_id"]
    assert payload["lookup_steps"][0]["to_field"] == ["customer_id", "tenant_id"]
    assert payload["lookup_steps"][1]["to_field"] == "customer_id"
    assert payload["lookup_steps"][1]["lookup_cast"]["name"] == "sep_first"
    assert "sep" not in payload["lookup_steps"][1]["lookup_cast"]
    assert payload["lookup_steps"][2]["lookup_cast"]["sep"] == "|"
    assert "template_top_level_keys" not in payload["lookup_steps"][3]["bind"]
    assert payload["lookup_steps"][4]["bind"]["params_builder_ref"]


def test_operator_snapshot_rejects_unknown_operator_type() -> None:
    with pytest.raises(TypeError):
        operator_snapshot(object())


def test_execution_plan_snapshot_and_deps_snapshot_are_stable() -> None:
    plan = ExecutionPlan(
        operators=(
            LoadOperatorIr(
                operator_id="load.orders",
                operator_type=str(OperatorType.LOAD),
                source_id="orders",
                field_keys=("order_id",),
                depends_on=(),
                is_primary=True,
            ),
            ComputeOperatorIr(
                operator_id="compute.total",
                operator_type=str(OperatorType.COMPUTE),
                field_key="total",
                input_fields=("amount", "cost"),
                depends_on=("amount", "cost"),
            ),
        ),
        field_order=["amount", "cost", "total"],
        target_fields=["total"],
        primary_field="order_id",
        key_fields=frozenset({"tenant_id", "order_id"}),
        field_dependencies={
            "total": ("cost", "amount"),
            "cost": (),
            "amount": (),
        },
    )

    plan_snapshot = execution_plan_snapshot(plan)
    assert plan_snapshot["schema_version"] == "execution_plan/v1"
    assert plan_snapshot["key_fields"] == ["order_id", "tenant_id"]

    deps_snapshot = execution_deps_snapshot(plan)
    assert deps_snapshot["schema_version"] == "execution_deps/v1"
    assert deps_snapshot["edges"] == [
        {"from": "amount", "to": "total"},
        {"from": "cost", "to": "total"},
    ]
    assert deps_snapshot["dependencies_by_field"]["total"] == ["cost", "amount"]
