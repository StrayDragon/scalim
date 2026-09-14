"""Cells-native: ch040_sinks — multiple sink types and output shapes.

改造说明(对齐 repo cells-native A+C 模式,参考 `ch010_basics`):
- `build_ecommerce_model` / `build_ecommerce_runtime_bindings` 是**复杂复用零件**
  (多源/多级 Join/复合键/派生字段装配在库里),保留在 `scalim_misc` 库中不动;
  但新增**模型窥视 cell** 直接把装配产物(`demand.fields` / plan 元数据 /
  runtime_bindings 键 / targets)渲染出来,读者无需跳库即可看到 scalim 装配是怎样构成的。
- scalim 装配、运行、断言/对拍展开逐 cell 写在本 notebook 内。
- 通过 `chapter_result` 变量向 headless runner / pytest 暴露对拍结果。
- `run_chapter()` 薄兼容层: `app.run()` → `chapter_result`。
"""

import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # demo_big_data_report / ch040_sinks

    本章演示把**同一个 IR 模型**交给**多种 sink**(行式 / 列式 / CSV / 列式 CSV)
    会得到怎样的输出形态,并与纯 Python 对照组对拍。

    主线装配过程(每个步骤一个 cell,可就地修改重跑):
    1. 组装测试配置 `cfg`(30 单 / 10 客户 / ... 小型数据集)与目标字段集 `targets`
    2. `build_ecommerce_model(cfg)` 构建多源电商 IR 模型(主源 orders + 多级/复合键关联 + 派生字段)
    3. `build_ecommerce_runtime_bindings()` 注入 loader / 派生计算函数(运行时接线)
    4. `PlanBuilder(demand).build(targets=...)` 生成可执行计划;下方"模型窥视" cell 直接渲染装配产物
    5. `ScalimEngine` 分别接 `InMemoryRowDataSink` / `InMemoryColumnSink` 运行,输出各自形态
    6. `CSVSink` / `ColumnCSVSink` 落盘 + 纯 Python 对照组 `compare_csv_files` 对拍
    7. 可选 `pandas` 往返,最后汇总 `chapter_result`(含 `expected` 期望键)

    > 完整电商模型(多源/多级 Join/复合键/派生)的细节装配在 `scalim_misc.demo_big_data_report.shared`,
    > 作为**复杂复用零件**保留在库里;但"装配产物长什么样"由下方"模型窥视" cell 直接渲染,
    > 读者无需跳库即可看到 `demand.fields` / plan 元数据 / 运行时接线键。

    对拍入口: `run_chapter()` → `app.run()` → `chapter_result`
    Gate: `just examples`
    """)
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    from scalim_misc.notebook_support.pathing import ensure_repo_root_on_sys_path

    ensure_repo_root_on_sys_path(__file__)
    return


@app.cell
def _():
    import tempfile
    from pathlib import Path
    from typing import Dict, List, Tuple, cast

    from scalim.execution.engine import ScalimEngine
    from scalim.planning import PlanBuilder
    from scalim.sinks import ColumnCSVSink, CSVSink
    from scalim.sinks.memory import InMemoryColumnSink, InMemoryRowDataSink
    from scalim.typedefs import RowData
    from scalim_misc.demo_big_data_report.cases import build_test_config_small
    from scalim_misc.demo_big_data_report.shared import (
        TARGET_FIELDS_FULL,
        build_ecommerce_model,
        build_ecommerce_runtime_bindings,
    )
    from scalim_misc.demo_big_data_report.verification import (
        compare_csv_files,
        export_to_csv,
        python_build_order_report,
        verify_scalim_output,
    )
    from scalim_misc.notebook_support.chapter_result import make_chapter_result

    return (
        ColumnCSVSink,
        CSVSink,
        Dict,
        InMemoryColumnSink,
        InMemoryRowDataSink,
        Path,
        PlanBuilder,
        RowData,
        ScalimEngine,
        TARGET_FIELDS_FULL,
        build_ecommerce_model,
        build_ecommerce_runtime_bindings,
        build_test_config_small,
        cast,
        compare_csv_files,
        export_to_csv,
        make_chapter_result,
        python_build_order_report,
        tempfile,
        verify_scalim_output,
    )


@app.cell
def _(build_test_config_small, TARGET_FIELDS_FULL):
    # ① 组装测试配置与目标字段集(小型数据,保证 CI 稳定且足够快)
    cfg = build_test_config_small()
    targets = list(TARGET_FIELDS_FULL[:12])
    print("cfg built, {} targets".format(len(targets)))
    return cfg, targets


@app.cell
def _(PlanBuilder, build_ecommerce_model, build_ecommerce_runtime_bindings, cfg, targets):
    # ② 复用零件:构建多源电商 IR 模型(主源 orders + 多级/复合键关联 + 派生字段,细节在库中)
    demand = build_ecommerce_model(cfg)
    # ③ 复用零件:构建运行时接线(loader / 派生计算函数注入点,与 demand 配套)
    runtime_bindings = build_ecommerce_runtime_bindings()
    # ④ 计划构建:选定 targets 字段集,产出可执行的 `ExecutionPlan`(只规划目标字段)
    plan = PlanBuilder(demand).build(targets=targets)
    print("demand.fields={} plan.total_sources={}".format(len(demand.fields), plan.metadata.total_sources))
    return demand, plan, runtime_bindings


@app.cell(hide_code=True)
def _(demand, mo, plan, runtime_bindings, targets):
    # ⑤ 模型窥视:把库 builder 的装配产物直接渲染出来,读者无需跳库即能看到 scalim 装配长什么样
    fields_summary = [
        {"field_id": f.field_id, "name": f.name, "source_id": getattr(f, "source_id", "-"), "kind": type(f).__name__}
        for f in demand.fields.values()
    ]
    derived_keys = list(getattr(runtime_bindings, "derived_calculators", {}).keys())
    main_loader_keys = list(getattr(runtime_bindings, "main_source_loaders", {}).keys())
    source_loader_keys = list(getattr(runtime_bindings, "source_loaders", {}).keys())
    mo.vstack(
        [
            mo.md("**模型窥视（读者无需跳库）**: `build_ecommerce_model(cfg)` + `build_ecommerce_runtime_bindings()` 的装配产物"),
            mo.md(
                "`demand.fields` = **{}** 个字段; `plan.metadata.total_sources` = **{}**, `total_fields` = **{}**; "
                "`targets` = **{}** 个; `derived_calculators` = {}; "
                "`main_source_loaders` = {}; `source_loaders` = {}".format(
                    len(demand.fields),
                    plan.metadata.total_sources,
                    plan.metadata.total_fields,
                    len(targets),
                    derived_keys,
                    main_loader_keys,
                    source_loader_keys,
                )
            ),
            mo.ui.table(fields_summary, selection=None),
        ]
    )
    return fields_summary


@app.cell
def _(InMemoryColumnSink, InMemoryRowDataSink, ScalimEngine, demand, plan, runtime_bindings, targets, verify_scalim_output):
    # ⑥ 行式 vs 列式:两个引擎实例分别接 `InMemoryRowDataSink` / `InMemoryColumnSink`,产出各自形态
    #    再交给纯 Python 对照组 `verify_scalim_output` 做字段级对拍
    e1 = ScalimEngine(demand=demand, plan=plan, runtime_bindings=runtime_bindings, batch_size=10)
    with InMemoryRowDataSink() as row_sink:
        e1.run(main_rows=None, sink=row_sink)
        row_results = row_sink.get_data()

    e2 = ScalimEngine(demand=demand, plan=plan, runtime_bindings=runtime_bindings, batch_size=10)
    with InMemoryColumnSink(field_names=targets) as col_sink:
        e2.run(main_rows=None, sink=col_sink)
        col_results = col_sink.get_rows()

    vr_row = verify_scalim_output(row_results, fields_to_check=targets)
    vr_col = verify_scalim_output(col_results, fields_to_check=targets)
    print("row={} verify={}  col={} verify={}".format(len(row_results), vr_row.passed, len(col_results), vr_col.passed))
    return col_results, row_results, vr_col, vr_row


@app.cell
def _(
    ColumnCSVSink,
    CSVSink,
    ScalimEngine,
    Path,
    col_results,
    compare_csv_files,
    export_to_csv,
    python_build_order_report,
    demand,
    plan,
    runtime_bindings,
    targets,
    tempfile,
):
    # ⑦ CSV 落盘 + 对拍:先用纯 Python 对照组构建报表,再导出两边 CSV 做文件级对比;
    #    同时用真实 `CSVSink` / `ColumnCSVSink` 落盘并统计行数
    py_results = python_build_order_report(targets)
    with tempfile.TemporaryDirectory() as tmpdir:
        tp = Path(tmpdir)
        scalim_csv = tp / "scalim.csv"
        python_csv = tp / "python.csv"
        export_to_csv(col_results, str(scalim_csv), targets)
        export_to_csv(py_results, str(python_csv), targets)
        csv_matched, csv_diff = compare_csv_files(str(scalim_csv), str(python_csv))

        csv_row_path = tp / "row_sink.csv"
        er = ScalimEngine(demand=demand, plan=plan, runtime_bindings=runtime_bindings, batch_size=10)
        with CSVSink(str(csv_row_path), field_names=targets) as rs:
            er.run(main_rows=None, sink=rs)

        csv_col_path = tp / "col_sink.csv"
        ec = ScalimEngine(demand=demand, plan=plan, runtime_bindings=runtime_bindings, batch_size=10)
        with ColumnCSVSink(str(csv_col_path), field_names=targets) as cs:
            ec.run(main_rows=None, sink=cs)

        with csv_row_path.open(encoding="utf-8") as fr:
            row_lines = sum(1 for _ in fr) - 1
        with csv_col_path.open(encoding="utf-8") as fc:
            col_lines = sum(1 for _ in fc) - 1
        print("csv_match={}  row_lines={}  col_lines={}".format(csv_matched, row_lines, col_lines))
    return col_lines, csv_diff, csv_matched, row_lines


@app.cell
def _(col_results, targets, verify_scalim_output):
    # ⑧ 可选:如果环境装有 `pandas`,做一次 DataFrame 往返后再对拍(未安装则跳过)
    available = False
    vr_pd = None
    try:
        import pandas as pd

        df = pd.DataFrame(col_results)
        pd_rows = df[list(targets)].to_dict(orient="records")
        vr_pd = verify_scalim_output(pd_rows, fields_to_check=targets)
        available = True
        print("pandas: available, verify={}".format(vr_pd.passed))
    except ImportError:
        print("pandas: not available (skipped)")
    return available, vr_pd


@app.cell
def _(available, col_lines, col_results, csv_matched, make_chapter_result, row_lines, targets, vr_col, vr_pd, vr_row):
    # ⑨ 汇总对拍结果:所有断言必须全绿(行式/列式/pandas 对拍 + CSV 文件匹配 + 两种 CSV sink 行数一致)
    passed = bool(vr_row.passed and vr_col.passed and csv_matched and row_lines == len(col_results) and col_lines == len(col_results))
    if available and vr_pd:
        passed = passed and vr_pd.passed

    summary = "rows={} verify_row={} verify_col={} csv_match={} csv_sinks={}/{}".format(
        len(col_results), vr_row.passed, vr_col.passed, csv_matched, row_lines, col_lines
    )
    if not csv_matched:
        summary = summary + "\n" + (csv_diff or "(csv diff unavailable)")

    # 对拍期望(教学 payload;headless 可经 details["expected"] 定位)
    expected = {
        "targets": len(targets),
        "verify_row_passed": True,
        "verify_col_passed": True,
        "csv_matched": True,
    }
    print("expected:", expected)

    chapter_result = make_chapter_result(
        passed=passed,
        summary=summary,
        details={
            "expected": expected,
            "rows": len(col_results),
            "verify_row": vr_row,
            "verify_col": vr_col,
            "csv_matched": csv_matched,
            "pandas_available": available,
        },
    )
    return chapter_result, expected, passed, summary


@app.cell(hide_code=True)
def _(chapter_result, mo):
    ok = chapter_result["passed"]
    mo.callout(
        mo.md("## {}: {}".format("✅ PASS" if ok else "❌ FAIL", chapter_result["summary"])),
        kind="success" if ok else "danger",
    )
    return


@app.cell(hide_code=True)
def _(chapter_result, mo):
    from scalim_misc.notebook_support.results_view import details_to_rows

    detail_rows = details_to_rows(chapter_result["details"])
    if detail_rows:
        mo.ui.table(detail_rows, selection=None)
    return


def run_chapter():
    outputs, defs = app.run()
    return defs["chapter_result"]


if __name__ == "__main__":
    app.run()
