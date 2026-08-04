"""等价 Scalim 路径：按批生成宽源行，但 Demand 只声明窄字段 + 计数 sink。"""

from __future__ import annotations

from typing import Any, Dict, Iterator, List

from scalim.execution.engine import ScalimEngine
from scalim.execution.runtime_bindings import RuntimeBindings
from scalim.planning import PlanBuilder
from scalim.spec.ir import CallBySpecIr, CallByValueIr, DemandIr, DerivedFieldIr, FieldIr, MainSourceIr, RuntimeHandleIdIr

from notebooks.marimo.example_readme_suite.support import knobs
from notebooks.marimo.example_readme_suite.support.counting_sink import CountingRowSink
from notebooks.marimo.example_readme_suite.support.measure import measure_rss_delta_kb
from notebooks.marimo.example_readme_suite.support.naive_baseline import build_wide_rows


def build_demand() -> DemandIr:
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
        name="readme_memory_compare",
    )


def calc_amount_x2(amount: Any) -> Any:
    return float(amount or 0) * 2


def _iter_generated_batches(
    *,
    n_rows: int,
    n_fields: int,
    payload_chars: int,
    batch_size: int,
) -> Iterator[List[Dict[str, Any]]]:
    size = max(1, int(batch_size))
    start = 0
    while start < int(n_rows):
        end = min(int(n_rows), start + size)
        yield build_wide_rows(end - start, n_fields, payload_chars)
        start = end


def run_scalim(
    *,
    n_rows: int = knobs.N_ROWS,
    n_fields: int = knobs.N_FIELDS,
    payload_chars: int = knobs.PAYLOAD_CHARS,
    batch_size: int = knobs.BATCH_SIZE,
) -> Dict[str, Any]:
    def _body() -> Dict[str, Any]:
        demand = build_demand()
        plan = PlanBuilder(demand).build()
        engine = ScalimEngine(
            demand=demand,
            plan=plan,
            runtime_bindings=RuntimeBindings(
                main_source_loaders={},
                derived_calculators={"amount_x2": calc_amount_x2},
            ),
            batch_size=int(batch_size),
            parallel_mode="seq",
        )
        sink = CountingRowSink()
        for batch in _iter_generated_batches(
            n_rows=n_rows,
            n_fields=n_fields,
            payload_chars=payload_chars,
            batch_size=batch_size,
        ):
            for offset, row in enumerate(batch):
                row["order_id"] = sink.rows_written + offset
                row["amount"] = float((sink.rows_written + offset) % 100)
            engine.run(main_rows=batch, sink=sink)
        return {"rows": sink.rows_written, "keep_fields": list(knobs.SCALIM_KEEP_FIELDS)}

    measured = measure_rss_delta_kb(_body)
    result = measured.pop("result")
    assert isinstance(result, dict)
    out = dict(result)
    out.update(measured)
    out["label"] = "scalim"
    return out
