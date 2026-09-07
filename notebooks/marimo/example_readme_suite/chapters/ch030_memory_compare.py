"""Cells-native marimo notebook: ch030_memory_compare.

迁移对照:
  Before: cells 薄壳调用 support/compare.py::run_compare()（naive/scalim 两条管线在零件里）
  After:  naive 管线/scalim 管线/对比与期望全部在 cells 内（measure/counting_sink/knobs 零件照用）
"""

import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # example_readme_suite / ch030_memory_compare

        用假数据比较全量读取和 Scalim 的内存变化。

        这里的数字是每次运行前后进程 RSS 的变化，不是运行中的最高内存。

        教程核心全部在下方 cells 内逐步展开（无需跳转 support 实现）：

        1. knobs 旋钮表（本地可放大 scale）
        2. 共享宽表行生成器 `build_wide_rows`
        3. naive 管线：全量物化 + 全列 enrich 拷贝
        4. scalim 管线：窄字段 Demand + 计数 sink + 按批喂行
        5. 对比与期望对拍（行数一致；相对内存比）

        零件: `support/measure.py`（RSS 测量）/ `support/counting_sink.py` / `support/knobs.py`
        Gate: `just examples`
        """
    )
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    from scalim_misc.notebook_support.pathing import ensure_repo_root_on_sys_path

    repo_root = ensure_repo_root_on_sys_path(__file__)
    _ = repo_root
    return (repo_root,)


@app.cell
def _(mo):
    from notebooks.marimo.example_readme_suite.support import knobs
    from scalim_misc.notebook_support.chapter_result import make_chapter_result, render_checks

    mo.ui.table(
        [
            {"knob": "N_ROWS", "value": knobs.N_ROWS},
            {"knob": "N_FIELDS", "value": knobs.N_FIELDS},
            {"knob": "BATCH_SIZE", "value": knobs.BATCH_SIZE},
            {"knob": "PAYLOAD_CHARS", "value": knobs.PAYLOAD_CHARS},
        ]
    )
    return knobs, make_chapter_result, render_checks


@app.cell
def _():
    # ① 共享宽表行生成器（naive/scalim 两条管线喂同一形状的假数据）
    def build_wide_rows(n_rows, n_fields, payload_chars):
        pad = "x" * int(payload_chars)
        rows = []
        for i in range(int(n_rows)):
            row = {"order_id": i, "amount": float(i % 100)}
            for f in range(int(n_fields)):
                row["f{:03d}".format(f)] = "{}-{}-{}".format(i, f, pad)
            rows.append(row)
        return rows

    return (build_wide_rows,)


@app.cell
def _(build_wide_rows, knobs):
    # ② naive 基线：一次性物化宽表全部字段，再做一次「全列 enrich 拷贝」（模拟急切物化）
    from notebooks.marimo.example_readme_suite.support.measure import measure_rss_delta_kb

    def _naive_body():
        rows = build_wide_rows(knobs.N_ROWS, knobs.N_FIELDS, knobs.PAYLOAD_CHARS)
        enriched = [dict(r) for r in rows]
        total_amount = sum(float(r["amount"]) for r in enriched)
        return {"rows": len(enriched), "fields": knobs.N_FIELDS, "total_amount": total_amount}

    measured = measure_rss_delta_kb(_naive_body)
    naive_result = measured.pop("result")
    naive_result.update(measured)
    naive_result["label"] = "naive"
    print("naive  :", naive_result)
    return naive_result


@app.cell
def _(build_wide_rows, knobs, naive_result):
    # ③ scalim 路径：Demand 只声明窄字段 + 计数 sink，按批喂宽源行
    from scalim.execution.engine import ScalimEngine
    from scalim.execution.runtime_bindings import RuntimeBindings
    from scalim.planning import PlanBuilder
    from scalim.spec.ir import CallBySpecIr, CallByValueIr, DemandIr, DerivedFieldIr, FieldIr, MainSourceIr, RuntimeHandleIdIr

    from notebooks.marimo.example_readme_suite.support.counting_sink import CountingRowSink
    from notebooks.marimo.example_readme_suite.support.measure import measure_rss_delta_kb as _measure_rss_delta_kb

    _ = naive_result  # 仅固定执行顺序：先 naive 后 scalim，保持 RSS 口径稳定

    def build_demand():
        orders = MainSourceIr(source_id="orders", loader_ref=RuntimeHandleIdIr(handle_id="orders.loader"))
        return DemandIr.from_irs(
            sources=[],
            main_source=orders,
            fields=(
                FieldIr(field_id="order_id", name="订单ID", source_id=orders.source_id),
                FieldIr(field_id="amount", name="金额", source_id=orders.source_id),
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

    def calc_amount_x2(amount):
        return float(amount or 0) * 2

    def _iter_generated_batches(*, n_rows, n_fields, payload_chars, batch_size):
        size = max(1, int(batch_size))
        start = 0
        while start < int(n_rows):
            end = min(int(n_rows), start + size)
            yield build_wide_rows(end - start, n_fields, payload_chars)
            start = end

    def _scalim_body():
        demand = build_demand()
        plan = PlanBuilder(demand).build()
        engine = ScalimEngine(
            demand=demand,
            plan=plan,
            runtime_bindings=RuntimeBindings(
                main_source_loaders={},
                derived_calculators={"amount_x2": calc_amount_x2},
            ),
            batch_size=int(knobs.BATCH_SIZE),
            parallel_mode="seq",
        )
        sink = CountingRowSink()
        for batch in _iter_generated_batches(
            n_rows=knobs.N_ROWS,
            n_fields=knobs.N_FIELDS,
            payload_chars=knobs.PAYLOAD_CHARS,
            batch_size=knobs.BATCH_SIZE,
        ):
            for offset, row in enumerate(batch):
                row["order_id"] = sink.rows_written + offset
                row["amount"] = float((sink.rows_written + offset) % 100)
            engine.run(main_rows=batch, sink=sink)
        return {"rows": sink.rows_written, "keep_fields": list(knobs.SCALIM_KEEP_FIELDS)}

    _measured = _measure_rss_delta_kb(_scalim_body)
    scalim_result = _measured.pop("result")
    scalim_result.update(measured)
    scalim_result["label"] = "scalim"
    print("scalim :", scalim_result)
    return scalim_result


@app.cell
def _(knobs, mo, naive_result, scalim_result):
    # ④ 期望与对比（期望值直接写在 cells 里：两条路径行数一致 = N_ROWS）
    def _relative_ratio(naive_delta, scalim_delta):
        naive_v = float(max(1, int(naive_delta)))
        scalim_v = float(max(0, int(scalim_delta)))
        return {"naive_rel": 1.0, "scalim_rel": round(scalim_v / naive_v, 4)}

    expected_rows = int(knobs.N_ROWS)
    ratios = _relative_ratio(int(naive_result["rss_kb_delta"]), int(scalim_result["rss_kb_delta"]))
    mo.vstack(
        [
            mo.md("**期望 vs 实际**："),
            mo.ui.table(
                [
                    {"kind": "期望", "rows": expected_rows, "rss_kb_delta": "(不硬闸，仅展示)"},
                    {
                        "kind": "实际 naive",
                        "rows": naive_result.get("rows"),
                        "rss_kb_delta": naive_result.get("rss_kb_delta"),
                    },
                    {
                        "kind": "实际 scalim",
                        "rows": scalim_result.get("rows"),
                        "rss_kb_delta": scalim_result.get("rss_kb_delta"),
                    },
                ],
                selection=None,
            ),
            mo.md("**相对内存比**（naive=1.0 基线）：{}".format(ratios)),
        ]
    )
    return expected_rows, ratios


@app.cell
def _(expected_rows, knobs, make_chapter_result, naive_result, ratios, render_checks, scalim_result):
    # ⑤ 对拍断言 + 结构化 chapter_result
    checks = {
        "naive/scalim 行数一致且非空": bool(
            int(naive_result.get("rows") or 0) == int(scalim_result.get("rows") or -1) == expected_rows > 0
        ),
    }
    render_checks(checks)
    passed = bool(all(checks.values()))
    summary = str(
        {
            "knobs": knobs.effective_knobs(),
            "ratios": ratios,
            "naive_rss_kb_delta": naive_result.get("rss_kb_delta"),
            "scalim_rss_kb_delta": scalim_result.get("rss_kb_delta"),
        }
    )
    chapter_result = make_chapter_result(
        passed=passed,
        summary=summary,
        details={
            "expected_rows": expected_rows,
            "naive": {k: naive_result[k] for k in ("rows", "rss_kb_delta", "label") if k in naive_result},
            "scalim": {k: scalim_result[k] for k in ("rows", "rss_kb_delta", "label") if k in scalim_result},
            "ratios": ratios,
            "knobs": knobs.effective_knobs(),
            "checks": {k: bool(v) for k, v in checks.items()},
        },
    )
    return chapter_result, checks, passed, summary


@app.cell(hide_code=True)
def _(chapter_result, mo):
    mo.callout(
        mo.md("## {}: {}".format("✅ PASS" if chapter_result["passed"] else "❌ FAIL", chapter_result["summary"])),
        kind="success" if chapter_result["passed"] else "danger",
    )
    return


@app.cell(hide_code=True)
def _(chapter_result, mo):
    from scalim_misc.notebook_support.results_view import details_to_rows

    table_rows = details_to_rows(chapter_result["details"])
    mo.ui.table(table_rows, selection=None) if table_rows else mo.md("(无详情)")
    return


def run_chapter():
    """SSOT 入口：headless runner 与 pytest 通过此函数执行对拍。"""
    outputs, defs = app.run()
    return defs["chapter_result"]


if __name__ == "__main__":
    app.run()
