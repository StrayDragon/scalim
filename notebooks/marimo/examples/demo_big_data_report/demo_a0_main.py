import marimo

__generated_with = "0.19.9"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # 电商订单报表示例

    这个示例展示 Scalim 框架的核心能力:

    | 功能 | 说明 |
    |------|------|
    | 单级关联 | orders → customers/products/promotions/payment/logistics |
    | 多级关联 | orders → products → categories (2级) |
    | 多级关联 | orders → warehouses → regions (2级) |
    | 复合键关联 | orders → region_pricing (region_id, product_category_id) |
    | 派生字段 | order_amount, profit, final_price |
    | 空值处理 | 部分订单无促销活动 |

    **特点**: 自动对拍验证,确保输出正确性
    """)
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---
    ## Step 1: 配置
    """)
    return


@app.cell
def _(mo):
    order_count = mo.ui.slider(start=100, stop=5000, value=1000, step=100, label="订单数量")
    batch_size = mo.ui.slider(start=50, stop=500, value=100, step=50, label="批次大小")
    mo.hstack([order_count, batch_size], justify="start", gap=2)
    return batch_size, order_count


@app.cell
def _(batch_size, order_count):
    import sys as _sys
    from pathlib import Path as _Path

    _this_dir = _Path(__file__).parent
    if str(_this_dir) not in _sys.path:
        _sys.path.insert(0, str(_this_dir))

    from _loaders import ECommerceConfig, load_orders, set_config, SCALE_MEDIUM, SCALE_LARGE
    from _shared import TARGET_FIELDS_FULL, build_ecommerce_model, build_target_sets

    ORDER_COUNT = order_count.value
    BATCH_SIZE = batch_size.value

    cfg = ECommerceConfig(order_count=ORDER_COUNT)
    set_config(cfg)
    print(f"📊 配置: {ORDER_COUNT} 订单, 批次大小 {BATCH_SIZE}")
    return BATCH_SIZE, build_ecommerce_model, build_target_sets, load_orders


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---
    ## Step 2: 选择目标字段集
    """)
    return


@app.cell
def _(build_target_sets, mo):
    target_sets = build_target_sets()
    scenario = mo.ui.dropdown(options=list(target_sets.keys()), value="full", label="目标字段集")
    scenario
    return scenario, target_sets


@app.cell
def _(scenario, target_sets):
    selected_targets = target_sets[scenario.value]
    print(f"📋 {scenario.value}: {len(selected_targets)} 字段")
    return (selected_targets,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---
    ## Step 3: 构建模型和执行
    """)
    return


@app.cell
def _(build_ecommerce_model, mo, selected_targets):
    import time

    from scalim.execution import ScalimEngine
    from scalim.hooks.base import HookManager
    from scalim.planning import PlanBuilder
    from scalim.sinks.sink_memory import InMemoryColumnSink

    # 构建模型
    demand = build_ecommerce_model()
    plan = PlanBuilder(demand).build(targets=selected_targets)
    meta = plan.metadata

    mo.md(f"""
    ### 执行计划
    | 指标 | 值 |
    |------|-----|
    | 目标字段 | {len(selected_targets)} |
    | 实际字段 | {meta.total_fields} |
    | 数据源 | {meta.total_sources} |
    | 缓存源 | {len(meta.cached_sources)} |
    """)
    return HookManager, InMemoryColumnSink, ScalimEngine, demand, plan, time


@app.cell
def _(
    BATCH_SIZE,
    HookManager,
    InMemoryColumnSink,
    ScalimEngine,
    demand,
    load_orders,
    mo,
    plan,
    selected_targets,
    time,
):
    # 执行
    engine = ScalimEngine(demand=demand, plan=plan, hook_manager=HookManager(), batch_size=BATCH_SIZE)
    main_rows = load_orders()

    start_time = time.time()
    with InMemoryColumnSink(field_names=selected_targets) as sink:
        _ = engine.run(main_rows=main_rows, sink=sink)
        scalim_results = sink.get_rows()
    elapsed = time.time() - start_time

    throughput = len(scalim_results) / elapsed if elapsed > 0 else 0

    mo.hstack(
        [
            mo.stat(value=f"{elapsed:.3f}s", label="执行耗时", bordered=True),
            mo.stat(value=f"{len(scalim_results)}", label="输出行数", bordered=True),
            mo.stat(value=f"{throughput:.0f} rows/s", label="吞吐量", bordered=True),
        ],
        justify="start",
        gap=1,
    )
    return (scalim_results,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---
    ## Step 4: 对拍验证
    """)
    return


@app.cell
def _(mo, scalim_results, selected_targets, time):
    from _verification import get_relation_check_results, get_relation_type_summary, verify_scalim_output, DetailedVerification

    verify_start = time.time()
    verification = verify_scalim_output(scalim_results, fields_to_check=selected_targets)
    verify_elapsed = time.time() - verify_start

    status_icon = "✅" if verification.passed else "❌"
    status_text = "PASSED" if verification.passed else "FAILED"
    status_color = "success" if verification.passed else "danger"

    mo.hstack(
        [
            mo.stat(value=f"{status_icon} {status_text}", label="验证状态", bordered=True),
            mo.stat(value=f"{verification.checked_rows}/{verification.total_rows}", label="检查行数", bordered=True),
            mo.stat(value=f"{len(verification.mismatches)}", label="不匹配数", bordered=True),
            mo.stat(value=f"{verify_elapsed:.3f}s", label="验证耗时", bordered=True),
        ],
        justify="start",
        gap=1,
    )
    return get_relation_check_results, get_relation_type_summary, verification


@app.cell
def _(mo, scalim_results):
    from _verification import verify_order_by

    order_by = ["order_id"]
    order_check = verify_order_by(scalim_results, order_by)
    order_status_icon = "✅" if order_check.passed else "❌"
    order_status_text = "PASSED" if order_check.passed else "FAILED"

    mo.stat(value=f"{order_status_icon} {order_status_text}", label="order_by 校验", bordered=True)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### 关联类型验证汇总
    """)
    return


@app.cell
def _(get_relation_type_summary, mo, verification):
    type_summary = get_relation_type_summary(verification)
    mo.ui.table(type_summary, selection=None)
    return


@app.cell(hide_code=True)
def _(mo):
    show_details = mo.ui.checkbox(label="显示详细字段验证结果")
    show_details
    return (show_details,)


@app.cell
def _(get_relation_check_results, mo, show_details, verification):
    mo.stop(not show_details.value)
    checks = get_relation_check_results(verification)
    mo.ui.table(checks, selection=None)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---
    ## Step 5: 文件对照测试

    同时用纯 Python 实现相同逻辑,导出 CSV 进行对比:
    """)
    return


@app.cell
def _(selected_targets, time):
    from _verification import python_build_order_report, export_to_csv, compare_csv_files

    # 纯 Python 实现
    py_start = time.time()
    python_results = python_build_order_report(selected_targets)
    py_elapsed = time.time() - py_start

    print(f"纯 `Python` 实现: {py_elapsed:.3f}s, {len(python_results)} 行")
    return compare_csv_files, export_to_csv, python_results


@app.cell
def _(
    compare_csv_files,
    export_to_csv,
    python_results,
    scalim_results,
    selected_targets,
):
    import os
    import tempfile

    # 导出两边结果到 CSV
    with tempfile.TemporaryDirectory() as tmpdir:
        scalim_csv = os.path.join(tmpdir, "scalim_output.csv")
        python_csv = os.path.join(tmpdir, "python_output.csv")

        export_to_csv(scalim_results, scalim_csv, selected_targets)
        export_to_csv(python_results, python_csv, selected_targets)

        # 对比文件
        csv_matched, csv_diff = compare_csv_files(scalim_csv, python_csv)

    print(f"CSV 文件对比: {'✅ 完全匹配' if csv_matched else '❌ 存在差异'}")
    if not csv_matched:
        print(csv_diff)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---
    ## Step 6: 结果预览
    """)
    return


@app.cell
def _(mo):
    preview_rows = mo.ui.slider(start=5, stop=50, value=10, step=5, label="显示行数")
    preview_rows
    return (preview_rows,)


@app.cell
def _(mo, preview_rows, scalim_results, selected_targets):
    import pandas as pd

    preview_data = []
    for row in scalim_results[: preview_rows.value]:
        p = {}
        for f in selected_targets:
            v = row.get(f)
            p[f] = round(v, 2) if isinstance(v, float) else v
        preview_data.append(p)

    df_preview = pd.DataFrame(preview_data)
    mo.ui.dataframe(df_preview)
    return


@app.cell(hide_code=True)
def _(mo, verification):
    final_status = "🎉 验证通过!" if verification.passed else "❌ 验证失败"
    mo.callout(mo.md(f"## {final_status}"), kind="success" if verification.passed else "danger")
    return


if __name__ == "__main__":
    app.run()
