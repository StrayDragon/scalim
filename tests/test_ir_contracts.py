import pytest

from scalim.spec.ir.binding import BindingIr, LoaderCallContextIr, LoaderIr
from scalim.spec.ir.demand import DemandIr
from scalim.spec.ir.fields import DerivedFieldIr, FieldIr
from scalim.spec.ir.helpers import extract_from_fields, infer_lookup_steps
from scalim.spec.ir.relations import JoinConditionIr, LookupStepIr, RelationIr
from scalim.spec.ir.sources import KeyIr, MainSourceIr, SourceIr


def _make_source(source_id: str, pk_key: object = "id") -> SourceIr:
    return SourceIr(
        source_id=source_id,
        key=KeyIr(key=pk_key),
        loader_spec=LoaderIr(callable=lambda: {}),
    )


def _make_main_source(source_id: str) -> MainSourceIr:
    return MainSourceIr(
        source_id=source_id,
        loader=lambda: [],
    )


def test_key_ir_and_loader_context_fields() -> None:
    key = KeyIr(key="order_id")
    assert str(key) == "order_id"
    assert hash(key) == hash("order_id")

    ctx = LoaderCallContextIr(batch_row_nth=[0, 1], lookup_keys={"1", 2}, lookup_keys_list=["1", 2])
    assert ctx.batch_row_nth == [0, 1]
    assert ctx.lookup_keys == {"1", 2}
    assert ctx.lookup_keys_list == ["1", 2]


def test_key_ir_rejects_composite_key_string() -> None:
    with pytest.raises(ValueError, match="Composite key"):
        KeyIr(key="(region_id, institution_id)")  # pyright: ignore[reportUnusedCallResult]


def test_field_ir_data_key_defaults_to_field_id() -> None:
    orders = _make_source("orders", pk_key="order_id")
    field = FieldIr(field_id="order_id", name="订单ID", source=orders)
    assert field.data_key == "order_id"


def test_field_ref_and_relation_composition() -> None:
    orders = _make_source("orders", pk_key="order_id")
    customers = _make_source("customers", pk_key="customer_id")
    payments = _make_source("payments", pk_key="payment_id")

    relation1 = orders["customer_id"].join(customers["customer_id"])
    relation2 = orders["payment_id"].join(payments["payment_id"])

    combined = relation1.and_(relation2)
    assert isinstance(combined, RelationIr)
    assert len(combined.conditions) == 2

    extended = combined.and_(customers["customer_id"].join(orders["customer_id"]))
    assert len(extended.conditions) == 3

    merged = combined.and_(relation1)
    assert len(merged.conditions) == 3

    assert hash(orders) == hash("orders")
    assert hash(orders["order_id"]) == hash(("orders", "order_id"))

    assert orders["order_id"] == orders["order_id"]
    assert orders["order_id"] != customers["customer_id"]

    rel = orders["customer_id"].join(customers["customer_id"])
    merged2 = rel.and_(combined)
    assert len(merged2.conditions) == 3
    with pytest.raises(TypeError, match="and_\\(\\) requires"):
        rel.and_("bad")  # type: ignore[arg-type]


def test_main_source_hash() -> None:
    main_source = _make_main_source("orders")
    assert hash(main_source) == hash("orders")


def test_field_ref_join_and_eq() -> None:
    orders = _make_source("orders", pk_key="order_id")
    customers = _make_source("customers", pk_key="customer_id")

    join = orders["customer_id"].join(customers["customer_id"])
    assert isinstance(join, JoinConditionIr)

    eq = orders["customer_id"].eq(customers["customer_id"])
    assert isinstance(eq, JoinConditionIr)

    with pytest.raises(TypeError, match="join\\(\\) requires"):
        orders["customer_id"].join("bad")  # type: ignore[arg-type]


def test_relation_infer_lookup_path_errors_and_non_pk() -> None:
    orders = _make_source("orders", pk_key="order_id")
    customers = _make_source("customers", pk_key="customer_id")
    mapping = _make_source("mapping", pk_key="pk")

    relation = orders["customer_id"].join(customers["customer_id"]).and_(customers["customer_id"].join(mapping["cust_ref"]))

    with pytest.raises(ValueError, match="不在关联关系"):
        relation.infer_lookup_path(from_source=_make_source("missing"), to_source=customers)

    with pytest.raises(ValueError, match="无法从"):
        relation.infer_lookup_path(from_source=orders, to_source=_make_source("other"))

    steps = relation.infer_lookup_path(from_source=customers, to_source=mapping)
    assert steps[0].to_field == "cust_ref"

    sources = relation.get_involved_sources()
    assert orders in sources
    assert customers in sources


def test_relation_build_lookup_steps_rejects_main_source_target() -> None:
    main_source = _make_main_source("orders")
    relation = RelationIr(conditions=())

    with pytest.raises(TypeError, match="主数据源"):
        relation._build_lookup_steps([("order_id", main_source, "order_id")])


def test_relation_and_relation_and_notimplemented() -> None:
    orders = _make_source("orders", pk_key="order_id")
    customers = _make_source("customers", pk_key="customer_id")

    relation1 = RelationIr(conditions=(orders["customer_id"].join(customers["customer_id"]),))
    relation2 = RelationIr(conditions=(customers["customer_id"].join(orders["customer_id"]),))

    merged = relation1.and_(relation2)
    assert len(merged.conditions) == 2
    with pytest.raises(TypeError, match="and_\\(\\) requires"):
        relation1.and_("bad")  # type: ignore[arg-type]


def test_infer_multi_field_lookup_path_reverse_and_non_pk() -> None:
    orders = _make_source("orders", pk_key="order_id")
    customers = _make_source("customers", pk_key="customer_id")

    reverse_relation = customers["customer_id"].join(orders["customer_id"])
    relation = RelationIr(conditions=(reverse_relation,))
    steps = relation.infer_multi_field_lookup_path(from_source=orders, to_source=customers)
    assert steps[0].from_field == "customer_id"

    alt_relation = orders["customer_id"].join(customers["alt_id"])
    relation_alt = RelationIr(conditions=(alt_relation,))
    steps_alt = relation_alt.infer_multi_field_lookup_path(from_source=orders, to_source=customers)
    assert steps_alt[0].to_field == "alt_id"


def test_lookup_step_validation_and_fields() -> None:
    source = _make_source("orders", pk_key=("a", "b"))

    with pytest.raises(ValueError, match="both be single"):
        LookupStepIr(from_field=("a", "b"), to_source=source, to_field="a")

    with pytest.raises(ValueError, match="same length"):
        LookupStepIr(from_field=("a", "b"), to_source=source, to_field=("a",))

    step = LookupStepIr(from_field="a", to_source=source)
    assert step.get_to_fields_or_source_key() == ("a", "b")
    assert step.get_to_key_or_source_key() == ("a", "b")

    other_source = _make_source("other", pk_key="id")
    step2 = LookupStepIr(from_field=("id", "id2"), to_source=other_source, to_field=["x", "y"])
    assert step2.get_to_fields_or_source_key() == ("x", "y")
    assert step2.get_to_key_or_source_key() == ["x", "y"]


def test_lookup_step_to_field_and_pk_single() -> None:
    source = _make_source("orders", pk_key="order_id")

    step = LookupStepIr(from_field="a", to_source=source, to_field="id")
    assert step.get_to_fields_or_source_key() == ("id",)

    step_pk = LookupStepIr(from_field="a", to_source=source)
    assert step_pk.get_to_fields_or_source_key() == ("order_id",)


def test_field_and_derived_field_transforms() -> None:
    source = _make_source("orders", pk_key="order_id")

    field = FieldIr(
        field_id="amount",
        name="Amount",
        source=source,
        transform=lambda v: v * 2,
        value_formatter=lambda v: "{:d}".format(v),
    )
    assert field.apply_transform(5) == "10"

    with pytest.raises(ValueError, match="必须至少有一个依赖"):
        DerivedFieldIr(field_id="bad", name="Bad", dependencies=(), calculator=lambda: 0)

    derived = DerivedFieldIr(
        field_id="profit",
        name="Profit",
        dependencies=("amount",),
        calculator=lambda amount: amount + 1,
        value_formatter=lambda v: "{}".format(v),
    )
    assert derived.get_dependencies() == ("amount",)
    assert derived.compute(amount=1) == "2"


def test_derived_field_constant_compute_rejects_dependencies() -> None:
    with pytest.raises(ValueError, match="必须不声明 dependencies"):
        DerivedFieldIr(
            field_id="bad",
            name="Bad",
            dependencies=("amount",),
            calculator=lambda amount: amount,  # type: ignore[no-untyped-def]
            is_constant_compute=True,
        )


def test_derived_field_constant_compute_rejects_call_ctx_key() -> None:
    with pytest.raises(ValueError, match="不允许 call_by 上下文"):
        DerivedFieldIr(
            field_id="bad",
            name="Bad",
            dependencies=(),
            calculator=lambda: 0,  # type: ignore[no-untyped-def]
            call_ctx_key="$ctx",
            is_constant_compute=True,
        )


def test_field_get_dependencies_from_relations() -> None:
    left = _make_source("left", pk_key="left_id")
    right = _make_source("right", pk_key="right_id")

    join = left["left_fk"].join(right["right_id"])
    field = FieldIr(field_id="left_fk", name="Left FK", source=right, relation=join)
    assert set(field.get_dependencies()) == {"left_fk"}

    relation = join.and_(left["other_fk"].join(right["other_id"]))
    field_multi = FieldIr(field_id="other_fk", name="Other FK", source=right, relation=relation)
    assert set(field_multi.get_dependencies()) == {"left_fk", "other_fk"}


def test_field_get_dependencies_prefers_lookup_steps_and_supports_empty() -> None:
    source = _make_source("customers", pk_key="customer_id")
    steps = (
        LookupStepIr(from_field="customer_id", to_source=source, to_field="customer_id"),
        LookupStepIr(from_field="region_id", to_source=source, to_field="region_id"),
    )
    field = FieldIr(
        field_id="customer_name",
        name="Customer Name",
        source=source,
        lookup_steps=steps,
    )
    assert set(field.get_dependencies()) == {"customer_id", "region_id"}

    no_deps = FieldIr(field_id="order_id", name="Order ID", source=source)
    assert no_deps.get_dependencies() == ()


def test_demand_ir_validation_and_duplicates() -> None:
    main_source = _make_main_source("orders")
    source = _make_source("customers", pk_key="customer_id")
    bad_source = _make_source("missing", pk_key="id")
    field = FieldIr(field_id="order_id", name="Order", source=main_source, is_primary=True)

    with pytest.raises(ValueError, match="主数据源"):
        DemandIr(
            sources={"orders": _make_source("orders", pk_key="order_id")},
            fields={"order_id": field},
            main_source=main_source,
        )

    with pytest.raises(ValueError, match="字段 'order_id' 引用的数据源"):
        DemandIr(
            sources={"customers": source},
            fields={"order_id": FieldIr(field_id="order_id", name="Order", source=bad_source)},
            main_source=main_source,
        )

    with pytest.raises(ValueError, match="数据源标识重复"):
        DemandIr.from_irs(sources=[source, source], fields=[field], main_source=main_source)

    with pytest.raises(ValueError, match="字段键名重复"):
        DemandIr.from_irs(sources=[source], fields=[field, field], main_source=main_source)

    demand = DemandIr.from_irs(sources=[source], fields=[field], main_source=main_source)
    assert demand.get_primary_field() == field

    demand_no_primary = DemandIr.from_irs(
        sources=[source],
        fields=[FieldIr(field_id="amount", name="Amount", source=main_source)],
        main_source=main_source,
    )
    assert demand_no_primary.get_primary_field() is None


def test_infer_lookup_steps_and_extract_fields() -> None:
    orders = _make_source("orders", pk_key="order_id")
    customers = _make_source("customers", pk_key="customer_id")

    relation = orders["customer_id"].join(customers["customer_id"])

    steps = infer_lookup_steps(relation, orders, customers)
    assert steps is not None
    assert extract_from_fields(steps) == ("customer_id",)

    unreachable = infer_lookup_steps(relation, orders, _make_source("other"))
    assert unreachable is None

    unknown = infer_lookup_steps("bad", orders, customers)  # type: ignore[arg-type]
    assert unknown is None


def test_loader_ir_bindings_immutable() -> None:
    binding = BindingIr(
        key_field="order_id",
        params_builder=lambda ctx: ((), {"ids": list(ctx.lookup_keys or [])}),
    )
    loader_ir = LoaderIr(
        callable=lambda: {},
        bindings={"order_id": binding},
    )

    assert loader_ir.get_binding("order_id") == binding
    assert loader_ir.get_binding("missing") is None

    with pytest.raises(TypeError):
        loader_ir.bindings["new_key"] = binding  # type: ignore[index]
