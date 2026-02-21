from typing import List

import pytest

from scalim.planning.builder_helpers.dep_graph import build_dependency_graph
from scalim.planning.builder_helpers.key_fields import compute_key_fields
from scalim.planning.builder_helpers.operators import build_plan_operators
from scalim.planning.builder_helpers.resolver import LookupStepsResolver, extract_relation_dependency_keys
from scalim.spec.ir.demand import DemandIr
from scalim.spec.ir.fields import DerivedFieldIr, FieldIr

from .fixtures.planning_fixtures import make_main_source, make_source


def test_build_dependency_graph_includes_unknown_field() -> None:
    main_source = make_main_source("orders")
    fields = [
        FieldIr(field_id="order_id", name="订单ID", source=main_source, is_primary=True),
        FieldIr(field_id="amount", name="金额", source=main_source),
    ]
    demand = DemandIr.from_irs(sources=[], fields=fields, main_source=main_source)
    demand.fields["unknown"] = object()  # type: ignore[assignment]

    dep_graph = build_dependency_graph(demand=demand, resolver=LookupStepsResolver())
    assert "unknown" in dep_graph.nodes()


@pytest.mark.parametrize(
    ("field_factory", "expected"),
    [
        (
            lambda demand, main_source, customers: (
                FieldIr(field_id="amount", name="金额", source=main_source),
                "amount",
            ),
            [],
        ),
        (
            lambda demand, main_source, customers: (
                FieldIr(
                    field_id="customer_name",
                    name="客户名",
                    source=customers,
                    relation=main_source["customer_id"].join(customers["customer_id"]),
                ),
                "customer_name",
            ),
            ["customer_id"],
        ),
    ],
    ids=["no-relation", "relation"],
)
def test_extract_relation_dependency_keys_basic(field_factory, expected: List[str]) -> None:  # type: ignore[no-untyped-def]
    main_source = make_main_source("orders")
    customers = make_source("customers", key_field="customer_id")

    demand = DemandIr.from_irs(
        sources=[customers],
        fields=[FieldIr(field_id="customer_id", name="客户ID", source=main_source)],
        main_source=main_source,
    )

    resolver = LookupStepsResolver()
    field, field_key = field_factory(demand, main_source, customers)
    deps = extract_relation_dependency_keys(demand=demand, field_spec=field, resolver=resolver, field_key=field_key)
    assert deps == expected


def test_extract_relation_dependency_keys_handles_empty_paths() -> None:
    main_source = make_main_source("orders")
    customers = make_source("customers", key_field="customer_id")
    relation = main_source["customer_id"].join(customers["customer_id"])

    field = FieldIr(field_id="customer_name", name="客户名", source=customers, relation=relation)
    demand = DemandIr.from_irs(sources=[customers], fields=[field], main_source=main_source)

    object.__setattr__(demand, "main_source", None)
    deps = extract_relation_dependency_keys(demand=demand, field_spec=field, resolver=LookupStepsResolver(), field_key="customer_name")
    assert deps == []


def test_extract_relation_dependency_keys_skips_non_source_ir_fields() -> None:
    class _FakeSource:
        def __init__(self, source_id: str) -> None:
            self.source_id = source_id

    main_source = make_main_source("orders")
    real_source = make_source("customers", key_field="customer_id")
    relation = main_source["order_id"].join(real_source["customer_id"])

    field = FieldIr(field_id="fake_field", name="Fake", source=_FakeSource("customers"), relation=relation)
    demand = DemandIr.from_irs(sources=[real_source], fields=[field], main_source=main_source)

    deps = extract_relation_dependency_keys(demand=demand, field_spec=field, resolver=LookupStepsResolver(), field_key="fake_field")
    assert deps == []


def test_build_plan_operators_skips_invalid_ref_loader_fields() -> None:
    def _no_steps(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        return ()

    main_source = make_main_source("orders")
    source = make_source("dummy", key_field="id")
    demand = DemandIr.from_irs(
        sources=[source],
        fields=[FieldIr(field_id="order_id", name="订单ID", source=main_source, is_primary=True)],
        main_source=main_source,
    )

    derived = DerivedFieldIr(field_id="derived", name="Derived", dependencies=("order_id",), calculator=lambda v: v)
    demand.fields["derived"] = derived

    # 1) not FieldIr -> skipped
    ops = build_plan_operators(
        demand=demand,
        resolver=LookupStepsResolver(),
        required_fields=set(),
        field_order=(),
        loader_sequence=[],
        ref_loader_sequence=[(source, [("derived", "")])],
    )
    assert ops == ()

    # 2) missing main_source -> skipped
    relation_field = FieldIr(
        field_id="ref",
        name="Ref",
        source=source,
        relation=main_source["order_id"].join(source["id"]),
    )
    demand.fields["ref"] = relation_field
    object.__setattr__(demand, "main_source", None)
    ops = build_plan_operators(
        demand=demand,
        resolver=LookupStepsResolver(),
        required_fields=set(),
        field_order=(),
        loader_sequence=[],
        ref_loader_sequence=[(source, [("ref", "")])],
    )
    assert ops == ()

    # 3) no inferred steps -> skipped
    object.__setattr__(demand, "main_source", main_source)
    resolver = LookupStepsResolver(infer_lookup_steps_fn=_no_steps)
    ops = build_plan_operators(
        demand=demand,
        resolver=resolver,
        required_fields=set(),
        field_order=(),
        loader_sequence=[],
        ref_loader_sequence=[(source, [("ref", "")])],
    )
    assert ops == ()

    # 4) field_spec.source is not SourceIr -> skipped
    class _FakeSource:
        def __init__(self, source_id: str) -> None:
            self.source_id = source_id

    fake_relation_field = FieldIr(
        field_id="fake_ref",
        name="FakeRef",
        source=_FakeSource("dummy"),
        relation=main_source["order_id"].join(source["id"]),
    )
    demand.fields["fake_ref"] = fake_relation_field
    ops = build_plan_operators(
        demand=demand,
        resolver=LookupStepsResolver(),
        required_fields=set(),
        field_order=(),
        loader_sequence=[],
        ref_loader_sequence=[(source, [("fake_ref", "")])],
    )
    assert ops == ()


def test_compute_key_fields_returns_empty_when_main_source_missing() -> None:
    main_source = make_main_source("orders")
    customers = make_source("customers", key_field="customer_id")
    relation = main_source["customer_id"].join(customers["customer_id"])
    field = FieldIr(field_id="customer_name", name="客户名", source=customers, relation=relation)
    demand = DemandIr.from_irs(sources=[customers], fields=[field], main_source=main_source)

    object.__setattr__(demand, "main_source", None)
    key_fields = compute_key_fields(demand=demand, resolver=LookupStepsResolver(), required_fields={"customer_name"})
    assert key_fields == frozenset()


def test_build_plan_operators_skips_compute_when_field_not_required() -> None:
    main_source = make_main_source("orders")
    order_id = FieldIr(field_id="order_id", name="订单ID", source=main_source, is_primary=True)
    derived = DerivedFieldIr(
        field_id="derived",
        name="Derived",
        dependencies=("order_id",),
        calculator=lambda v: v,
    )

    demand = DemandIr.from_irs(sources=[], fields=[order_id, derived], main_source=main_source)
    ops = build_plan_operators(
        demand=demand,
        resolver=LookupStepsResolver(),
        required_fields=set(),
        field_order=("derived",),
        loader_sequence=[],
        ref_loader_sequence=[],
    )
    assert ops == ()
