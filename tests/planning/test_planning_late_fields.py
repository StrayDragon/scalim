"""`ExecutionPlan.late_fields`(write-precompute)推导契约.

对应 specs: `execution-hotpath-fastpaths` r950 / r951.
"""

from typing import Any, Dict, List, Tuple

from scalim.planning import PlanBuilder
from scalim.planning.builder_helpers.late_fields import derive_late_fields
from scalim.spec.ir import (
    CallBySpecIr,
    CallByValueIr,
    DemandIr,
    DerivedFieldIr,
    FieldIr,
    MainSourceIr,
    OrderByKeyIr,
    RuntimeHandleIdIr,
)

from tests.fixtures.planning_fixtures import make_main_source, make_source


def _call_by(handle_suffix: str, dep_fields: List[str]) -> CallBySpecIr:
    return CallBySpecIr(
        reference=RuntimeHandleIdIr(handle_id="derived.{}".format(handle_suffix)),
        args=tuple(CallByValueIr(kind="field", value=dep) for dep in dep_fields),
        field_names=tuple(dep_fields),
    )


def test_output_only_derived_is_late() -> None:
    main = make_main_source("orders")
    fields: List[Any] = [
        FieldIr(field_id="order_id", name="订单ID", source=main, is_primary=True),
        FieldIr(field_id="amount", name="金额", source=main),
        DerivedFieldIr(field_id="doubled", name="双倍", dependencies=("amount",), compute_expr="amount * 2"),
    ]
    demand = DemandIr.from_irs(sources=[], fields=fields, main_source=main)

    plan = PlanBuilder(demand).build(targets=["order_id", "amount", "doubled"])

    assert plan.late_fields == ("doubled",)


def test_derived_consumed_by_another_eager_derived_is_not_late() -> None:
    main = make_main_source("orders")
    fields: List[Any] = [
        FieldIr(field_id="order_id", name="订单ID", source=main, is_primary=True),
        FieldIr(field_id="amount", name="金额", source=main),
        DerivedFieldIr(field_id="base", name="基数", dependencies=("amount",), compute_expr="amount * 2"),
        # 含 `$ctx` 的 `call_by` 永远早算,因此其依赖 `base` 也存在“子图外消费者”.
        DerivedFieldIr(
            field_id="with_ctx",
            name="带上下文",
            dependencies=("base",),
            call_by=_call_by("with_ctx", ["base"]),
            call_ctx_key="ctx",
        ),
    ]
    demand = DemandIr.from_irs(sources=[], fields=fields, main_source=main)

    plan = PlanBuilder(demand).build(targets=["order_id", "amount", "base", "with_ctx"])

    assert plan.late_fields == ()


def test_derived_consumed_by_load_ref_from_field_is_not_late() -> None:
    orders = make_main_source("orders")
    regions = make_source("regions", key_field="region_key")

    fields: List[Any] = [
        FieldIr(field_id="order_id", name="订单ID", source=orders, is_primary=True),
        FieldIr(field_id="region_code", name="地区码", source=orders),
        DerivedFieldIr(
            field_id="region_key",
            name="地区键",
            dependencies=("region_code",),
            compute_expr="region_code",
        ),
        FieldIr(
            field_id="region_name",
            name="地区名",
            source=regions,
            data_key="region_name",
            relation=orders["region_key"].join(regions["region_key"]),
        ),
    ]
    demand = DemandIr.from_irs(sources=[regions], fields=fields, main_source=orders)

    plan = PlanBuilder(demand).build(targets=["order_id", "region_key", "region_name"])

    assert "region_key" not in plan.late_fields


def test_ctx_call_by_is_never_late() -> None:
    main = make_main_source("orders")
    fields: List[Any] = [
        FieldIr(field_id="order_id", name="订单ID", source=main, is_primary=True),
        FieldIr(field_id="amount", name="金额", source=main),
        DerivedFieldIr(
            field_id="tagged",
            name="带标记",
            dependencies=("amount",),
            call_by=_call_by("tagged", ["amount"]),
            call_ctx_key="ctx",
        ),
        DerivedFieldIr(
            field_id="plain",
            name="无上下文",
            dependencies=("amount",),
            call_by=_call_by("plain", ["amount"]),
        ),
    ]
    demand = DemandIr.from_irs(sources=[], fields=fields, main_source=main)

    plan = PlanBuilder(demand).build(targets=["order_id", "amount", "tagged", "plain"])

    assert "tagged" not in plan.late_fields
    assert "plain" in plan.late_fields


def test_late_chain_is_topologically_ordered() -> None:
    main = make_main_source("orders")
    fields: List[Any] = [
        FieldIr(field_id="order_id", name="订单ID", source=main, is_primary=True),
        FieldIr(field_id="amount", name="金额", source=main),
        DerivedFieldIr(field_id="c0", name="c0", dependencies=("amount",), compute_expr="amount + 1"),
        DerivedFieldIr(field_id="c1", name="c1", dependencies=("c0",), compute_expr="c0 + 1"),
        DerivedFieldIr(field_id="c2", name="c2", dependencies=("c1",), compute_expr="c1 + 1"),
    ]
    demand = DemandIr.from_irs(sources=[], fields=fields, main_source=main)

    plan = PlanBuilder(demand).build(targets=["order_id", "amount", "c0", "c1", "c2"])

    assert plan.late_fields == ("c0", "c1", "c2")


def test_intermediate_derived_outside_targets_blocks_late() -> None:
    main = make_main_source("orders")
    fields: List[Any] = [
        FieldIr(field_id="order_id", name="订单ID", source=main, is_primary=True),
        FieldIr(field_id="amount", name="金额", source=main),
        DerivedFieldIr(field_id="c0", name="c0", dependencies=("amount",), compute_expr="amount + 1"),
        DerivedFieldIr(field_id="c1", name="c1", dependencies=("c0",), compute_expr="c0 + 1"),
    ]
    demand = DemandIr.from_irs(sources=[], fields=fields, main_source=main)

    plan = PlanBuilder(demand).build(targets=["order_id", "c1"])

    # `c0` 不是写出目标(不可 late),`c1` 的依赖因此不满足“写出点可得”.
    assert plan.late_fields == ()


def test_order_by_key_is_not_late() -> None:
    main = MainSourceIr(
        source_id="orders",
        loader_ref=RuntimeHandleIdIr(handle_id="orders.main_loader"),
        order_by=(OrderByKeyIr(field_key="sort_key", direction="asc"),),
    )
    fields: List[Any] = [
        FieldIr(field_id="order_id", name="订单ID", source=main, is_primary=True),
        FieldIr(field_id="amount", name="金额", source=main),
        DerivedFieldIr(field_id="sort_key", name="排序键", dependencies=("amount",), compute_expr="amount * -1"),
    ]
    demand = DemandIr.from_irs(sources=[], fields=fields, main_source=main)

    plan = PlanBuilder(demand).build(targets=["order_id", "amount", "sort_key"])

    assert plan.late_fields == ()


def test_undeclared_dependency_stays_available_at_write() -> None:
    """未声明规格的依赖走主行透传提取,与主源字段同批预填充,不阻止 `late`."""
    spec = DerivedFieldIr(field_id="tag", name="标记", dependencies=("ghost",), compute_expr="ghost")

    late = derive_late_fields(
        field_specs={"tag": spec},
        field_dependencies={"tag": ("ghost",)},
        target_fields=["tag"],
        key_fields=set(),
        protected_fields=set(),
        main_source_id="orders",
    )

    assert late == ("tag",)


def test_rejected_candidate_requeues_its_late_consumers() -> None:
    """候选被踢出后必须复查它的候选消费者(工作表收缩到不动点)."""
    field_specs: Dict[str, Any] = {
        # 别源直取字段: 写出点不可得,导致 `blocked` 退回早算.
        "ext": FieldIr(field_id="ext", name="外部字段", source=make_source("regions")),
        "blocked": DerivedFieldIr(field_id="blocked", name="blocked", dependencies=("ext",), compute_expr="ext"),
        "chained": DerivedFieldIr(field_id="chained", name="chained", dependencies=("blocked",), compute_expr="blocked + 1"),
    }
    field_dependencies: Dict[str, Tuple[str, ...]] = {"ext": (), "blocked": ("ext",), "chained": ("blocked",)}

    late = derive_late_fields(
        field_specs=field_specs,
        field_dependencies=field_dependencies,
        target_fields=["blocked", "chained"],
        key_fields=set(),
        protected_fields=set(),
        main_source_id="orders",
    )

    # `blocked` 退回早算后仍是写出目标,因此 `chained` 依旧可以 `late`.
    assert late == ("chained",)


def test_constant_compute_is_not_late() -> None:
    main = make_main_source("orders")
    fields: List[Any] = [
        FieldIr(field_id="order_id", name="订单ID", source=main, is_primary=True),
        DerivedFieldIr(
            field_id="const",
            name="常量",
            dependencies=(),
            call_by=_call_by("const", []),
            is_constant_compute=True,
        ),
    ]
    demand = DemandIr.from_irs(sources=[], fields=fields, main_source=main)

    plan = PlanBuilder(demand).build(targets=["order_id", "const"])

    assert plan.late_fields == ()
