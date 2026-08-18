from types import SimpleNamespace
from typing import List

from scalim.planning import PlanBuilder
from scalim.planning.loader_ordering.sequences import build_loader_sequences
from scalim.planning.operators import LoadOperatorIr
from scalim.planning.operators import LoadRefOperatorIr
from scalim.spec.ir import DemandIr
from scalim.spec.ir import FieldIr
from scalim.spec.ir import LookupStepIr

from tests.fixtures.planning_fixtures import build_relation_model, make_main_source, make_source


def test_ref_loader_sequence_contains_field() -> None:
    demand = build_relation_model()
    plan = PlanBuilder(demand).build(targets=["customer_name"])

    all_ref_fields: List[str] = []
    for _, ref_fields in plan.ref_loader_sequence:
        for field_key, _ in ref_fields:
            all_ref_fields.append(field_key)

    assert "customer_name" in all_ref_fields


def test_ref_loader_sequence_cross_source_dependency_ordering() -> None:
    orders_source = make_main_source("orders")
    customers_source = make_source("zz_customers", key_field="customer_id")
    regions_source = make_source("mm_regions", key_field="region_id")
    countries_source = make_source("aa_countries", key_field="country_id")

    fields = [
        FieldIr(field_id="order_id", name="订单ID", source_id=orders_source.source_id, is_primary=True),
        FieldIr(field_id="customer_id", name="客户ID", source_id=orders_source.source_id),
        FieldIr(
            field_id="region_id",
            name="地区ID",
            source_id=customers_source.source_id,
            lookup_steps=(LookupStepIr(from_field="customer_id", to_source_id=customers_source.source_id),),
        ),
        FieldIr(
            field_id="country_id",
            name="国家ID",
            source_id=regions_source.source_id,
            lookup_steps=(LookupStepIr(from_field="region_id", to_source_id=regions_source.source_id),),
        ),
        FieldIr(
            field_id="country_name",
            name="国家名称",
            source_id=countries_source.source_id,
            lookup_steps=(LookupStepIr(from_field="country_id", to_source_id=countries_source.source_id),),
        ),
    ]

    demand = DemandIr.from_irs(
        sources=[customers_source, regions_source, countries_source],
        fields=fields,
        main_source=orders_source,
    )

    plan = PlanBuilder(demand).build(targets=["country_name"])
    assert [src.source_id for src, _ in plan.ref_loader_sequence] == ["zz_customers", "mm_regions", "aa_countries"]

    load_ref_ops = [op for op in plan.operators if isinstance(op, LoadRefOperatorIr)]
    assert [(op.source_id, op.field_key) for op in load_ref_ops] == [
        ("zz_customers", "region_id"),
        ("mm_regions", "country_id"),
        ("aa_countries", "country_name"),
    ]


def test_loader_sequences_group_primary_and_non_relation_fields() -> None:
    main_source = make_main_source("orders")
    customers_source = make_source("customers", key_field="customer_id")

    fields = [
        FieldIr(field_id="order_id", name="订单ID", source_id=main_source.source_id, is_primary=True),
        FieldIr(field_id="customer_id", name="客户ID", source_id=customers_source.source_id, is_primary=True),
        FieldIr(field_id="status", name="状态", source_id=customers_source.source_id),
    ]
    demand = DemandIr.from_irs(sources=[customers_source], fields=fields, main_source=main_source)

    plan = PlanBuilder(demand).build(targets=["customer_id", "status"])
    load_ops = [op for op in plan.operators if isinstance(op, LoadOperatorIr)]

    assert load_ops
    assert load_ops[0].is_primary is True
    assert set(load_ops[0].field_keys) == {"customer_id", "status"}

    for required_fields, expected_fields in (
        ({"customer_id"}, ["customer_id"]),
        ({"status"}, ["status"]),
    ):
        loader_sequence, _ = build_loader_sequences(demand, required_fields=required_fields)
        assert loader_sequence
        assert loader_sequence[0][1] == expected_fields


def test_skips_non_source_ir_fields_in_sequences() -> None:
    class _FakeSource:
        def __init__(self, source_id: str) -> None:
            self.source_id = source_id

    main_source = make_main_source("orders")
    real_source = make_source("fake", key_field="fake_id")
    fake_source = _FakeSource("fake")
    relation = main_source["order_id"].join(real_source["fake_id"])

    demand = DemandIr.from_irs(
        sources=[real_source],
        fields=[FieldIr(field_id="fake_field", name="Fake", source_id=main_source.source_id, relation=relation)],
        main_source=main_source,
    )

    loader_sequence, ref_loader_sequence = build_loader_sequences(demand, required_fields={"fake_field"})
    assert loader_sequence == []
    assert ref_loader_sequence == []

    plan = PlanBuilder(demand).build(targets=["fake_field"])
    assert plan.key_fields == frozenset()
    assert plan.operators == ()


def test_build_loader_sequences_skips_field_missing_catalog_source() -> None:
    main_source = make_main_source("orders")
    ghost = FieldIr(field_id="ghost_name", name="Ghost", source_id="ghost")
    demand = SimpleNamespace(
        main_source=main_source,
        sources={},
        fields={"ghost_name": ghost},
    )
    loader_sequence, ref_loader_sequence = build_loader_sequences(demand, required_fields={"ghost_name"})
    assert loader_sequence == []
    assert ref_loader_sequence == []
