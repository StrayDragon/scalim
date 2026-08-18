import pytest

from scalim.spec.ir.binding import BindingIr, LoaderCallContextIr, LoaderIr
from scalim.spec.ir import BuiltinCallableIdIr, CallBySpecIr, CallByValueIr, DemandIr, DerivedFieldIr, FieldIr, SourceNormalizeIr, ValueOpIr
from scalim.spec.ir.callable_refs import describe_callable_ref
from scalim.spec.ir._helpers import call_loader_with_binding, extract_from_fields, infer_lookup_steps
from scalim.spec.ir import JoinConditionIr, LookupStepIr, RelationIr
from scalim.spec.ir import KeyIr, MainSourceIr, RuntimeHandleIdIr, SourceIr


def _make_source(source_id: str, pk_key: object = "id") -> SourceIr:
    return SourceIr(
        source_id=source_id,
        key=KeyIr(key=pk_key),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr(handle_id="{}.loader".format(source_id))),
    )


def _make_main_source(source_id: str) -> MainSourceIr:
    return MainSourceIr(
        source_id=source_id,
        loader_ref=RuntimeHandleIdIr(handle_id="{}.loader".format(source_id)),
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
    field = FieldIr(field_id="order_id", name="订单ID", source_id=orders.source_id)
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
        LookupStepIr(from_field=("a", "b"), to_source_id=source.source_id, to_field="a")

    with pytest.raises(ValueError, match="same length"):
        LookupStepIr(from_field=("a", "b"), to_source_id=source.source_id, to_field=("a",))

    step = LookupStepIr(from_field="a", to_source_id=source.source_id)
    assert step.get_to_fields_or_source_key(source) == ("a", "b")
    assert step.get_to_key_or_source_key(source) == ("a", "b")

    other_source = _make_source("other", pk_key="id")
    step2 = LookupStepIr(from_field=("id", "id2"), to_source_id=other_source.source_id, to_field=["x", "y"])
    assert step2.get_to_fields_or_source_key(source) == ("x", "y")
    assert step2.get_to_key_or_source_key(source) == ["x", "y"]


def test_lookup_step_to_field_and_pk_single() -> None:
    source = _make_source("orders", pk_key="order_id")

    step = LookupStepIr(from_field="a", to_source_id=source.source_id, to_field="id")
    assert step.get_to_fields_or_source_key(source) == ("id",)

    step_pk = LookupStepIr(from_field="a", to_source_id=source.source_id)
    assert step_pk.get_to_fields_or_source_key(source) == ("order_id",)


def test_field_and_derived_field_value_ops_and_call_by_contracts() -> None:
    source = _make_source("orders", pk_key="order_id")

    field = FieldIr(field_id="amount", name="Amount", source_id=source.source_id, value_ops=(ValueOpIr(kind="cast", to="decimal"),))
    assert field.value_ops[0].kind == "cast"

    with pytest.raises(ValueError, match="requires non-empty to"):
        ValueOpIr(kind="cast")  # pyright: ignore[reportUnusedCallResult]

    with pytest.raises(ValueError, match="requires callable_ref"):
        ValueOpIr(kind="transform")  # pyright: ignore[reportUnusedCallResult]

    with pytest.raises(ValueError, match="必须声明 compute_expr 或 call_by"):
        DerivedFieldIr(field_id="bad", name="Bad", dependencies=("amount",))

    derived = DerivedFieldIr(
        field_id="profit",
        name="Profit",
        dependencies=("amount",),
        call_by=CallBySpecIr(
            reference=RuntimeHandleIdIr(handle_id="profit.calculator"),
            kwargs=(("amount", CallByValueIr(kind="field", value="amount")),),
            field_names=("amount",),
        ),
        value_ops=(ValueOpIr(kind="cast", to="int"),),
    )
    assert derived.get_dependencies() == ("amount",)


def test_derived_field_constant_compute_rejects_dependencies() -> None:
    with pytest.raises(ValueError, match="必须不声明 dependencies"):
        DerivedFieldIr(
            field_id="bad",
            name="Bad",
            dependencies=("amount",),
            compute_expr="1",
            is_constant_compute=True,
        )


def test_derived_field_constant_compute_rejects_call_ctx_key() -> None:
    with pytest.raises(ValueError, match="不允许 call_by 上下文"):
        DerivedFieldIr(
            field_id="bad",
            name="Bad",
            dependencies=(),
            compute_expr="1",
            call_ctx_key="$ctx",
            is_constant_compute=True,
        )


def test_field_get_dependencies_from_relations() -> None:
    left = _make_source("left", pk_key="left_id")
    right = _make_source("right", pk_key="right_id")

    join = left["left_fk"].join(right["right_id"])
    field = FieldIr(field_id="left_fk", name="Left FK", source_id=right.source_id, relation=join)
    assert set(field.get_dependencies()) == {"left_fk"}

    relation = join.and_(left["other_fk"].join(right["other_id"]))
    field_multi = FieldIr(field_id="other_fk", name="Other FK", source_id=right.source_id, relation=relation)
    assert set(field_multi.get_dependencies()) == {"left_fk", "other_fk"}


def test_field_get_dependencies_prefers_lookup_steps_and_supports_empty() -> None:
    source = _make_source("customers", pk_key="customer_id")
    steps = (
        LookupStepIr(from_field="customer_id", to_source_id=source.source_id, to_field="customer_id"),
        LookupStepIr(from_field="region_id", to_source_id=source.source_id, to_field="region_id"),
    )
    field = FieldIr(
        field_id="customer_name",
        name="Customer Name",
        source_id=source.source_id,
        lookup_steps=steps,
    )
    assert set(field.get_dependencies()) == {"customer_id", "region_id"}

    no_deps = FieldIr(field_id="order_id", name="Order ID", source_id=source.source_id)
    assert no_deps.get_dependencies() == ()


def test_demand_ir_validation_and_duplicates() -> None:
    main_source = _make_main_source("orders")
    source = _make_source("customers", pk_key="customer_id")
    bad_source = _make_source("missing", pk_key="id")
    field = FieldIr(field_id="order_id", name="Order", source_id=main_source.source_id, is_primary=True)

    with pytest.raises(ValueError, match="主数据源"):
        DemandIr(
            sources={"orders": _make_source("orders", pk_key="order_id")},
            fields={"order_id": field},
            main_source=main_source,
        )

    with pytest.raises(ValueError, match="字段 'order_id' 引用的数据源"):
        DemandIr(
            sources={"customers": source},
            fields={"order_id": FieldIr(field_id="order_id", name="Order", source_id=bad_source.source_id)},
            main_source=main_source,
        )

    with pytest.raises(ValueError, match="lookup 引用数据源"):
        DemandIr(
            sources={"customers": source},
            fields={
                "customer_name": FieldIr(
                    field_id="customer_name",
                    name="Customer",
                    source_id=source.source_id,
                    lookup_steps=(LookupStepIr(from_field="customer_id", to_source_id="missing"),),
                )
            },
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
        fields=[FieldIr(field_id="amount", name="Amount", source_id=main_source.source_id)],
        main_source=main_source,
    )
    assert demand_no_primary.get_primary_field() is None


def test_demand_ir_keeps_mapping_proxy_inputs() -> None:
    from types import MappingProxyType

    main_source = _make_main_source("orders")
    demand = DemandIr(
        sources=MappingProxyType({}),
        fields=MappingProxyType({}),
        main_source=main_source,
    )

    assert isinstance(demand.sources, MappingProxyType)
    assert isinstance(demand.fields, MappingProxyType)


def test_demand_ir_freezes_non_dict_mappings_and_rejects_invalid_inputs() -> None:
    from collections import ChainMap
    from types import MappingProxyType

    main_source = _make_main_source("orders")
    demand = DemandIr(
        sources=ChainMap({}),
        fields=ChainMap({}),
        main_source=main_source,
    )
    assert isinstance(demand.sources, MappingProxyType)
    assert isinstance(demand.fields, MappingProxyType)

    with pytest.raises(TypeError, match="DemandIr.sources must be a mapping"):
        _ = DemandIr(  # type: ignore[arg-type]
            sources=[],
            fields={},
            main_source=main_source,
        )

    with pytest.raises(TypeError, match="DemandIr.fields must be a mapping"):
        _ = DemandIr(  # type: ignore[arg-type]
            sources={},
            fields=[],
            main_source=main_source,
        )


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
        params_builder_ref=RuntimeHandleIdIr(handle_id="order_id.params_builder"),
    )
    loader_ir = LoaderIr(
        callable_ref=RuntimeHandleIdIr(handle_id="orders.loader"),
        bindings={"order_id": binding},
    )

    assert loader_ir.get_binding("order_id") == binding
    assert loader_ir.get_binding("missing") is None

    with pytest.raises(TypeError):
        loader_ir.bindings["new_key"] = binding  # type: ignore[index]


class _Template:
    def render_kwargs(self, _ctx: object, *, path: str):  # type: ignore[no-untyped-def]
        return {"path": path}


def test_binding_ir_build_params_enforces_runtime_linking_boundary() -> None:
    ctx = LoaderCallContextIr()

    with pytest.raises(ValueError, match="must not set both"):
        _ = BindingIr(
            key_field="id",
            params_template=_Template(),
            params_builder_ref=BuiltinCallableIdIr(callable_id="demo.builder"),
        )

    binding_ref = BindingIr(key_field="id", params_builder_ref=BuiltinCallableIdIr(callable_id="demo.builder"))
    with pytest.raises(TypeError, match="requires runtime linking"):
        binding_ref.build_params(ctx)

    binding_empty = BindingIr(key_field="id")
    assert binding_empty.build_params(ctx) == ((), {})

    binding_bad_template = BindingIr(key_field="id", params_template=object())
    with pytest.raises(TypeError, match="render_kwargs"):
        binding_bad_template.build_params(ctx)

    binding_template = BindingIr(key_field="id", params_template=_Template(), template_path="sources.demo.bind")
    args, kwargs = binding_template.build_params(ctx)
    assert args == ()
    assert kwargs["path"] == "sources.demo.bind"


def test_call_loader_with_binding_supports_template_and_none() -> None:
    ctx = LoaderCallContextIr()

    def _loader_fn(*args, **kwargs):  # type: ignore[no-untyped-def]
        return {"args": args, "kwargs": kwargs}

    assert call_loader_with_binding(None, ctx, _loader_fn) == {"args": (), "kwargs": {}}

    binding = BindingIr(key_field="id", params_template=_Template(), template_path="demo")
    assert call_loader_with_binding(binding, ctx, _loader_fn) == {"args": (), "kwargs": {"path": "demo"}}


def test_value_op_ir_validates_configs() -> None:
    with pytest.raises(ValueError, match="must not set callable_ref"):
        _ = ValueOpIr(kind="cast", to="int", callable_ref=BuiltinCallableIdIr(callable_id="demo.cast"))

    with pytest.raises(ValueError, match="must not set to"):
        _ = ValueOpIr(kind="transform", to="int", callable_ref=BuiltinCallableIdIr(callable_id="demo.transform"))

    with pytest.raises(ValueError, match="Unknown ValueOpIr.kind"):
        _ = ValueOpIr(kind="weird")


def test_derived_field_ir_rejects_ambiguous_call_by_and_compute_expr() -> None:
    with pytest.raises(ValueError, match="compute_expr 或 call_by"):
        _ = DerivedFieldIr(
            field_id="x",
            name="X",
            dependencies=("a",),
            compute_expr="1",
            call_by=CallBySpecIr(reference=BuiltinCallableIdIr(callable_id="demo.fn")),
        )

    with pytest.raises(ValueError, match="至少有一个依赖"):
        _ = DerivedFieldIr(field_id="x", name="X", dependencies=(), compute_expr="1")


def test_describe_callable_ref_formats_builtin_ids() -> None:
    assert describe_callable_ref(BuiltinCallableIdIr(callable_id="demo")) == "^demo"


def test_source_normalize_ir_requires_runtime_resolved_callable_when_call_by_ref_set() -> None:
    normalize = SourceNormalizeIr(kind="take_first", call_by_ref=BuiltinCallableIdIr(callable_id="demo.normalize"))
    result = {"k": [{"x": 1}]}

    with pytest.raises(ValueError, match="requires runtime resolution"):
        normalize.apply(result, source_id="demo")

    with pytest.raises(TypeError, match="expects callable runtime binding"):
        normalize.apply(result, source_id="demo", call_by=object())
