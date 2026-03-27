import pytest

from scalim.execution import ScalimEngine
from scalim.planning import PlanBuilder
from scalim.planning.builder_helpers.operators import derive_pre_ref_available_field_keys
from scalim.planning.operators import ComputeOperatorIr, LoadRefOperatorIr
from scalim.spec.ir.binding import BindingIr, LoaderIr
from scalim.spec.ir.demand import DemandIr
from scalim.spec.ir.fields import DerivedFieldIr, FieldIr
from scalim.spec.ir.sources import KeyIr, MainSourceIr, SourceIr
from scalim.utils.graph import ScalimCyclicDependencyError


def test_relation_from_allows_constant_derived_join_key_and_executes_before_loadref() -> None:
    orders_source = MainSourceIr(source_id="orders", loader=lambda: [])

    def load_customers(*_args: object, **_kwargs: object) -> object:
        return {"k": {"customer_name": "customer_k"}}

    customers_source = SourceIr(
        source_id="customers",
        key=KeyIr(key="customer_id"),
        loader_spec=LoaderIr(
            callable=load_customers,
            bindings={
                "customer_id": BindingIr(
                    key_field="customer_id",
                    params_builder=lambda _ctx: ((), {}),
                )
            },
        ),
    )

    orders_to_customers = orders_source["broadcast_key"].join(customers_source["customer_id"])

    demand = DemandIr.from_irs(
        sources=[customers_source],
        fields=[
            FieldIr(field_id="order_id", name="订单ID", source=orders_source, is_primary=True),
            DerivedFieldIr(
                field_id="broadcast_key",
                name="Broadcast Key",
                dependencies=(),
                calculator=lambda: "k",
                is_constant_compute=True,
            ),
            FieldIr(
                field_id="customer_name",
                name="客户名称",
                source=customers_source,
                data_key="customer_name",
                relation=orders_to_customers,
            ),
        ],
        main_source=orders_source,
    )

    plan = PlanBuilder(demand).build(targets=["order_id", "customer_name"])

    compute_idx = next(
        idx for idx, op in enumerate(plan.operators) if isinstance(op, ComputeOperatorIr) and op.field_spec.field_id == "broadcast_key"
    )
    load_ref_idx = next(
        idx for idx, op in enumerate(plan.operators) if isinstance(op, LoadRefOperatorIr) and op.field_key == "customer_name"
    )
    assert compute_idx < load_ref_idx

    results = ScalimEngine(demand=demand, plan=plan, batch_size=10).run(
        main_rows=[
            {"order_id": 1},
            {"order_id": 2},
        ]
    )
    assert [row.get("customer_name") for row in results] == ["customer_k", "customer_k"]


def test_plan_builder_cycle_error_mentions_pre_relation_hint_for_derived_ref_cycle() -> None:
    orders_source = MainSourceIr(source_id="orders", loader=lambda: [])

    customers_source = SourceIr(
        source_id="customers",
        key=KeyIr(key="customer_id"),
        loader_spec=LoaderIr(
            callable=lambda *_args, **_kwargs: {},
            bindings={
                "customer_id": BindingIr(
                    key_field="customer_id",
                    params_builder=lambda _ctx: ((), {}),
                )
            },
        ),
    )

    orders_to_customers = orders_source["broadcast_key"].join(customers_source["customer_id"])

    demand = DemandIr.from_irs(
        sources=[customers_source],
        fields=[
            FieldIr(field_id="order_id", name="订单ID", source=orders_source, is_primary=True),
            FieldIr(
                field_id="customer_name",
                name="客户名称",
                source=customers_source,
                data_key="customer_name",
                relation=orders_to_customers,
            ),
            DerivedFieldIr(
                field_id="broadcast_key",
                name="Broadcast Key",
                dependencies=("customer_name",),
                calculator=lambda customer_name: customer_name,
            ),
        ],
        main_source=orders_source,
    )

    with pytest.raises(
        ScalimCyclicDependencyError, match=r"Hint: this may be caused by derived fields participating in relation join keys"
    ):
        _ = PlanBuilder(demand).build(targets=["customer_name"])


def test_plan_builder_rejects_non_pre_ref_derived_join_key_with_blocking_chain() -> None:
    orders_source = MainSourceIr(source_id="orders", loader=lambda: [])

    customers_source = SourceIr(
        source_id="customers",
        key=KeyIr(key="customer_id"),
        loader_spec=LoaderIr(
            callable=lambda *_args, **_kwargs: {},
            bindings={
                "customer_id": BindingIr(
                    key_field="customer_id",
                    params_builder=lambda _ctx: ((), {}),
                )
            },
        ),
    )

    ref_by_order_id = orders_source["order_id"].join(customers_source["customer_id"])
    ref_by_broadcast_key = orders_source["broadcast_key"].join(customers_source["customer_id"])

    demand = DemandIr.from_irs(
        sources=[customers_source],
        fields=[
            FieldIr(field_id="order_id", name="订单ID", source=orders_source, is_primary=True),
            FieldIr(field_id="ref_value", name="Ref Value", source=customers_source, data_key="ref_value", relation=ref_by_order_id),
            DerivedFieldIr(
                field_id="broadcast_key",
                name="Broadcast Key",
                dependencies=("order_id", "ref_value"),
                calculator=lambda order_id, ref_value: str(order_id) + str(ref_value),
            ),
            FieldIr(
                field_id="customer_name",
                name="客户名称",
                source=customers_source,
                data_key="customer_name",
                relation=ref_by_broadcast_key,
            ),
        ],
        main_source=orders_source,
    )

    with pytest.raises(ValueError, match=r"Blocking dependency chain: broadcast_key -> ref_value"):
        _ = PlanBuilder(demand).build(targets=["customer_name"])


def test_derive_pre_ref_available_field_keys_excludes_main_source_ref_fields() -> None:
    orders_source = MainSourceIr(source_id="orders", loader=lambda: [])
    demand = DemandIr.from_irs(
        sources=[],
        fields=[
            FieldIr(field_id="order_id", name="订单ID", source=orders_source, is_primary=True),
            FieldIr(field_id="ref_like", name="RefLike", source=orders_source, relation="x"),  # type: ignore[arg-type]
        ],
        main_source=orders_source,
    )

    available = derive_pre_ref_available_field_keys(demand=demand)
    assert "order_id" in available
    assert "ref_like" not in available


def test_derive_pre_ref_available_field_keys_returns_empty_when_main_source_id_empty() -> None:
    orders_source = MainSourceIr(source_id="", loader=lambda: [])
    demand = DemandIr.from_irs(
        sources=[],
        fields=[FieldIr(field_id="order_id", name="订单ID", source=orders_source, is_primary=True)],
        main_source=orders_source,
    )
    assert derive_pre_ref_available_field_keys(demand=demand) == set()


def test_plan_builder_find_pre_ref_blocking_chain_branches() -> None:
    class _WeirdField:
        def __init__(self, field_id: str) -> None:
            self.field_id = field_id

    orders_source = MainSourceIr(source_id="orders", loader=lambda: [])

    demand = DemandIr.from_irs(
        sources=[],
        fields=[
            FieldIr(field_id="order_id", name="订单ID", source=orders_source, is_primary=True),
            DerivedFieldIr(field_id="const", name="Const", dependencies=(), calculator=lambda: "x", is_constant_compute=True),
            DerivedFieldIr(field_id="b", name="B", dependencies=("order_id",), calculator=lambda order_id: order_id),
            DerivedFieldIr(field_id="a", name="A", dependencies=("b", "b"), calculator=lambda b: b),
            DerivedFieldIr(field_id="missing_dep", name="Missing Dep", dependencies=("missing",), calculator=lambda missing: missing),
            _WeirdField(field_id="weird"),
            DerivedFieldIr(field_id="needs_weird", name="Needs Weird", dependencies=("weird",), calculator=lambda weird: weird),
        ],
        main_source=orders_source,
    )

    builder = PlanBuilder(demand)

    assert builder._find_pre_ref_blocking_chain(start="order_id", pre_ref_available=set(), pre_ref_derived=set()) == ["order_id"]
    assert builder._find_pre_ref_blocking_chain(start="const", pre_ref_available=set(), pre_ref_derived=set()) == ["const"]
    assert builder._find_pre_ref_blocking_chain(start="missing_dep", pre_ref_available=set(), pre_ref_derived=set()) == [
        "missing_dep",
        "missing",
    ]
    assert builder._find_pre_ref_blocking_chain(start="needs_weird", pre_ref_available=set(), pre_ref_derived=set()) == [
        "needs_weird",
        "weird",
    ]
    assert builder._find_pre_ref_blocking_chain(start="b", pre_ref_available=set(), pre_ref_derived=set()) == ["b", "order_id"]
    assert builder._find_pre_ref_blocking_chain(start="a", pre_ref_available={"order_id"}, pre_ref_derived=set()) == ["a"]
