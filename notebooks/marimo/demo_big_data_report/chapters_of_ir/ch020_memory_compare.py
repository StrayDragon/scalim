"""Cells-native marimo notebook: ch020_memory_compare.

角色: README「为什么用 Scalim」的对比证据(同一假数据, 两条管线), 也是主线内存面第一站.

链路: 宽表行生成器 → naive 全量物化 → scalim 窄字段 Demand + 计数 sink → RSS 相对比.
零件: `scalim_misc.notebook_support.rss_proxy`(RSS 代理) / `counting_sink`(只计数不落行).
"""

import marimo

__generated_with = "0.23.14"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / ch020_memory_compare

        用同一份假宽表数据, 比较 **naive 全量物化** 与 **Scalim 窄字段流式** 两条管线的本地内存变化.

        口径说明(务必同读):

        - 这里的数字是**每次运行前后进程 RSS 的变化**(相对增量代理), 不是运行中的最高内存;
        - 不能跨机器比较绝对值, 也不构成 SLA 承诺; `just examples` 只断言"两条管线都跑通且行数一致".

        主线装配过程(每个步骤一个 cell, 可就地修改重跑):

        1. 旋钮表(本地可放大 scale 后重跑)
        2. 共享宽表行生成器 `build_wide_rows`
        3. naive 管线: 全量物化 + 全列 enrich 拷贝
        4. scalim 管线: 窄字段 `DemandIr` + 计数 sink + 按批喂行
        5. 对比与期望对拍(行数一致; 相对内存比)

        > 与 `ch050_memory_opt` 的分工: 本章量的是**两条管线的相对内存增量**,
        > `ch050` 看的是 scalim 侧的内存优化事件与列式写出.

        对拍入口: `run_chapter()` → `app.run()` → `chapter_result`
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
def _():
    from scalim_misc.notebook_support.chapter_result import make_chapter_result, render_checks

    return make_chapter_result, render_checks


@app.cell
def _(mo):
    # ① 旋钮: 直接改这里的常量即可本地放大 scale(门禁用默认小 scale 保证秒级)
    N_ROWS = 1500
    N_FIELDS = 48
    BATCH_SIZE = 150
    # 每个宽表字段的填充字节数: 放大 naive 全量物化与 scalim 窄字段路径的对比
    PAYLOAD_CHARS = 64
    # scalim 路径只保留这几个输出字段
    scalim_keep_fields = ("order_id", "amount", "amount_x2")

    knobs = {
        "N_ROWS": N_ROWS,
        "N_FIELDS": N_FIELDS,
        "BATCH_SIZE": BATCH_SIZE,
        "PAYLOAD_CHARS": PAYLOAD_CHARS,
        "SCALIM_KEEP_FIELDS": list(scalim_keep_fields),
    }
    mo.md("**旋钮(可改后重跑)**:")
    mo.ui.table([{"knob": k, "value": v} for k, v in knobs.items()], selection=None)
    return (
        BATCH_SIZE,
        N_FIELDS,
        N_ROWS,
        PAYLOAD_CHARS,
        knobs,
        scalim_keep_fields,
    )


@app.cell
def _():
    # ② 共享宽表行生成器(naive/scalim 两条管线喂同一形状的假数据)
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
def _(BATCH_SIZE, N_FIELDS, N_ROWS, PAYLOAD_CHARS, build_wide_rows, knobs):
    # ③ naive 基线: 一次性物化宽表全部字段, 再做一次「全列 enrich 拷贝」(模拟急切物化)
    from scalim_misc.notebook_support.rss_proxy import measure_rss_delta_kb

    def _naive_body():
        rows = build_wide_rows(N_ROWS, N_FIELDS, PAYLOAD_CHARS)
        enriched = [dict(r) for r in rows]
        total_amount = sum(float(r["amount"]) for r in enriched)
        return {"rows": len(enriched), "fields": N_FIELDS, "total_amount": total_amount}

    measured = measure_rss_delta_kb(_naive_body)
    naive_result = measured.pop("result")
    naive_result.update(measured)
    naive_result["label"] = "naive"
    print("naive  :", naive_result)
    _ = knobs
    return (naive_result,)


@app.cell
def _(BATCH_SIZE, N_FIELDS, N_ROWS, PAYLOAD_CHARS, build_wide_rows, knobs, naive_result, scalim_keep_fields):
    # ④ scalim 路径: Demand 只声明窄字段 + 计数 sink, 按批喂宽源行
    from scalim.execution.engine import ScalimEngine
    from scalim.execution.runtime_bindings import RuntimeBindings
    from scalim.planning import PlanBuilder
    from scalim.spec.ir import (
        CallBySpecIr,
        CallByValueIr,
        DemandIr,
        DerivedFieldIr,
        FieldIr,
        MainSourceIr,
        RuntimeHandleIdIr,
    )

    from scalim_misc.notebook_support.counting_sink import CountingRowSink
    from scalim_misc.notebook_support.rss_proxy import measure_rss_delta_kb as _measure_rss_delta_kb

    _ = naive_result  # 仅固定执行顺序: 先 naive 后 scalim, 保持 RSS 口径稳定

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
            name="demo_big_data_report_ch020_memory_compare",
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
            batch_size=int(BATCH_SIZE),
            parallel_mode="seq",
        )
        sink = CountingRowSink()
        for batch in _iter_generated_batches(
            n_rows=N_ROWS,
            n_fields=N_FIELDS,
            payload_chars=PAYLOAD_CHARS,
            batch_size=BATCH_SIZE,
        ):
            for offset, row in enumerate(batch):
                row["order_id"] = sink.rows_written + offset
                row["amount"] = float((sink.rows_written + offset) % 100)
            engine.run(main_rows=batch, sink=sink)
        return {"rows": sink.rows_written, "keep_fields": list(scalim_keep_fields)}

    _measured = _measure_rss_delta_kb(_scalim_body)
    scalim_result = _measured.pop("result")
    scalim_result.update(_measured)
    scalim_result["label"] = "scalim"
    print("scalim :", scalim_result)
    _ = knobs
    return (scalim_result,)


@app.cell
def _(knobs, mo, naive_result, scalim_result):
    # ⑤ 期望与对比(期望值直接写在 cells 里: 两条路径行数一致)
    def _relative_ratio(naive_delta, scalim_delta):
        naive_v = float(max(1, int(naive_delta)))
        scalim_v = float(max(0, int(scalim_delta)))
        return {"naive_rel": 1.0, "scalim_rel": round(scalim_v / naive_v, 4)}

    expected_rows = int(knobs["N_ROWS"])
    ratios = _relative_ratio(int(naive_result["rss_kb_delta"]), int(scalim_result["rss_kb_delta"]))
    mo.vstack(
        [
            mo.md("**期望 vs 实际**:"),
            mo.ui.table(
                [
                    {"kind": "期望", "rows": expected_rows, "rss_kb_delta": "(不硬闸, 仅展示)"},
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
            mo.md("**相对内存比**(naive=1.0 基线): {}".format(ratios)),
        ]
    )
    return expected_rows, ratios


@app.cell
def _(expected_rows, knobs, make_chapter_result, naive_result, ratios, render_checks, scalim_result):
    # ⑥ 对拍断言 + 结构化 chapter_result
    checks = {
        "naive/scalim 行数一致且非空": bool(
            int(naive_result.get("rows") or 0) == int(scalim_result.get("rows") or -1) == expected_rows > 0
        ),
    }
    render_checks(checks)
    passed = bool(all(checks.values()))
    summary = "rows={} scalim_rel={}".format(expected_rows, ratios.get("scalim_rel"))

    # 对拍期望(教学 payload; headless 可经 details["expected"] 键定位)
    expected = {"rows": expected_rows, "naive_rel": 1.0}
    print("expected:", expected)

    chapter_result = make_chapter_result(
        passed=passed,
        summary=summary,
        details={
            "expected": expected,
            "expected_rows": expected_rows,
            "naive": {k: naive_result[k] for k in ("rows", "rss_kb_delta", "label") if k in naive_result},
            "scalim": {k: scalim_result[k] for k in ("rows", "rss_kb_delta", "label") if k in scalim_result},
            "ratios": ratios,
            "knobs": knobs,
            "checks": {k: bool(v) for k, v in checks.items()},
        },
    )
    return (chapter_result,)


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

    detail_rows = details_to_rows(chapter_result["details"])
    mo.ui.table(detail_rows, selection=None) if detail_rows else mo.md("(无详情)")
    return


def run_chapter():
    """SSOT 入口：headless runner 与 pytest 通过此函数执行对拍。"""
    outputs, defs = app.run()
    return defs["chapter_result"]


if __name__ == "__main__":
    app.run()
