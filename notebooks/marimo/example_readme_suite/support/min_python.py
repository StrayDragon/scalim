"""最小可跑 Python 示例（假数据闭环）。"""

from __future__ import annotations

from typing import Any, Dict, List

from scalim.execution.engine import ScalimEngine
from scalim.execution.runtime_bindings import RuntimeBindings
from scalim.planning import PlanBuilder
from scalim.sinks.memory import InMemoryRowDataSink
from scalim.spec.ir import CallBySpecIr, CallByValueIr, DemandIr, DerivedFieldIr, FieldIr, MainSourceIr, RuntimeHandleIdIr


def load_orders(**_kwargs: Any) -> List[Dict[str, Any]]:
    return [
        {"order_id": 1, "amount": 10.0},
        {"order_id": 2, "amount": 20.5},
        {"order_id": 3, "amount": 7.0},
    ]


def calc_amount_x2(amount: Any) -> Any:
    return float(amount) * 2


def build_min_demand() -> DemandIr:
    orders = MainSourceIr(source_id="orders", loader_ref=RuntimeHandleIdIr(handle_id="orders.loader"))
    return DemandIr.from_irs(
        sources=[],
        main_source=orders,
        fields=(
            FieldIr(field_id="order_id", name="订单ID", source=orders),
            FieldIr(field_id="amount", name="金额", source=orders),
            DerivedFieldIr(
                field_id="amount_x2",
                name="金额*2",
                dependencies=("amount",),
                call_by=CallBySpecIr(
                    reference=RuntimeHandleIdIr(handle_id="amount_x2.calculator"),
                    kwargs=(("amount", CallByValueIr(kind="field", value="amount")),),
                    field_names=("amount",),
                ),
            ),
        ),
        name="orders_report",
    )


def run_min_python() -> Dict[str, Any]:
    demand = build_min_demand()
    plan = PlanBuilder(demand).build()
    runtime_bindings = RuntimeBindings(
        main_source_loaders={"orders": load_orders},
        derived_calculators={"amount_x2": calc_amount_x2},
    )
    engine = ScalimEngine(
        demand=demand,
        plan=plan,
        runtime_bindings=runtime_bindings,
        batch_size=1000,
        parallel_mode="seq",
    )
    sink = InMemoryRowDataSink()
    engine.run(sink=sink)
    rows = list(sink.get_data())
    assert len(rows) == 3
    assert rows[0]["amount_x2"] == 20.0
    return {"rows": len(rows), "sample": rows[0]}
