import marimo

__generated_with = "0.19.4"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # 统一数据质量演示 - 关联与完整性

    本演示整合了数据质量相关的功能:

    ## 功能概览
    | 功能 | 说明 |
    |------|------|
    | 关联命中率 | 分析各类型关联的命中情况 |
    | 空值分析 | 统计各字段的空值比例 |
    | 数据完整性 | 检测主键连续性和间隙 |
    | 字段完整性 | 各字段的非空率统计 |

    **特点**: 一次执行验证所有数据质量指标
    """)
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    import sys as _sys
    from pathlib import Path as _Path

    _this_dir = _Path(__file__).parent
    if str(_this_dir) not in _sys.path:
        _sys.path.insert(0, str(_this_dir))

    from _loaders import ECommerceConfig, load_orders, set_config
    from _shared import TARGET_FIELDS_FULL, build_ecommerce_model
    from _verification import verify_scalim_output

    from scalim.execution import ScalimEngine
    from scalim.hooks.base import HookManager
    from scalim.planning import PlanBuilder
    from scalim.sinks.sink_memory import InMemoryColumnSink

    return (
        ECommerceConfig,
        HookManager,
        InMemoryColumnSink,
        PlanBuilder,
        ScalimEngine,
        TARGET_FIELDS_FULL,
        build_ecommerce_model,
        load_orders,
        set_config,
        verify_scalim_output,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""---
    ## 配置
    """)
    return


@app.cell
def _(ECommerceConfig, build_ecommerce_model, set_config):
    cfg = ECommerceConfig(order_count=1000)
    set_config(cfg)
    model = build_ecommerce_model()
    print(f"模型: {len(model.sources)} 个数据源, {len(model.fields)} 个字段, {cfg.order_count} 订单")
    return cfg, model


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""---
    ## 执行数据处理
    """)
    return


@app.cell
def _(HookManager, InMemoryColumnSink, PlanBuilder, ScalimEngine, TARGET_FIELDS_FULL, load_orders, mo, model, verify_scalim_output):
    import time

    targets = TARGET_FIELDS_FULL
    plan = PlanBuilder(model).build(targets=targets)
    engine = ScalimEngine(demand=model, plan=plan, hook_manager=HookManager(), batch_size=100)

    start = time.time()
    with InMemoryColumnSink(field_names=targets) as sink:
        engine.run(main_rows=load_orders(), sink=sink)
        results = sink.get_rows()
    elapsed = time.time() - start

    vr = verify_scalim_output(results, targets)

    mo.hstack(
        [
            mo.stat(value=f"{elapsed:.3f}s", label="执行耗时", bordered=True),
            mo.stat(value=f"{len(results)}", label="输出行数", bordered=True),
            mo.stat(value="✅ PASS" if vr.passed else "❌ FAIL", label="验证状态", bordered=True),
        ],
        justify="start",
        gap=1,
    )
    return elapsed, engine, plan, results, sink, start, targets, time, vr


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""---
    ## Part 1: 关联命中率分析

    分析各类型关联的命中情况:
    - **单级关联**: 100% 命中 (customer, product)
    - **单级关联**: 约80% 命中 (promotion - 部分订单无促销)
    - **多级关联**: orders → products → categories
    - **复合键关联**: orders → region_pricing
    """)
    return


@app.cell
def _(results):
    # 分析各字段的非空率(代表关联命中率)
    fields_to_check = [
        ("customer_name", "单级-客户"),
        ("customer_level", "单级-会员等级"),
        ("product_name", "单级-产品"),
        ("product_brand", "单级-品牌"),
        ("promotion_name", "单级-促销"),
        ("payment_method_name", "单级-支付"),
        ("logistics_name", "单级-物流"),
        ("category_name", "多级-分类"),
        ("region_name", "多级-区域"),
        ("region_manager", "多级-区域经理"),
        ("price_adjustment", "复合键-价格调整"),
        ("shipping_fee", "复合键-运费"),
        ("tax_rate", "复合键-税率"),
    ]

    total = len(results)

    print("关联命中率分析:")
    print()
    for _field, _desc in fields_to_check:
        _non_null = sum(1 for _r in results if _r.get(_field) is not None)
        _rate = 100 * _non_null / total if total > 0 else 0
        _status = "✅" if _rate == 100 else ("⚠️" if _rate >= 80 else "❌")
        print(f"  {_status} {_desc} ({_field}): {_non_null}/{total} = {_rate:.1f}%")
    return fields_to_check, total


@app.cell
def _(fields_to_check, mo, results, total):
    hit_data = []
    for _f, _d in fields_to_check:
        _cnt = sum(1 for _row in results if _row.get(_f) is not None)
        _pct = 100 * _cnt / total if total > 0 else 0
        _status = "✅" if _pct == 100 else ("⚠️" if _pct >= 80 else "❌")
        hit_data.append({"关联类型": _d, "字段": _f, "命中数": _cnt, "总数": total, "命中率": f"{_pct:.1f}%", "状态": _status})
    mo.ui.table(hit_data)
    return (hit_data,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""---
    ## Part 2: 数据完整性检查

    检查主键连续性和间隙:
    """)
    return


@app.cell
def _(results):
    # 检查主键连续性
    order_ids = sorted([r.get("order_id") for r in results if r.get("order_id") is not None])

    gaps = []
    for i in range(1, len(order_ids)):
        if order_ids[i] - order_ids[i - 1] > 1:
            gaps.append((order_ids[i - 1], order_ids[i]))

    print("数据完整性检查:")
    print(f"  总行数: {len(results)}")
    print(f"  主键范围: {min(order_ids)} - {max(order_ids)}")
    print(f"  间隙数量: {len(gaps)}")

    if gaps:
        print("  间隙列表:")
        for start_id, end_id in gaps[:5]:
            print(f"    {start_id} -> {end_id} (缺失 {end_id - start_id - 1} 行)")
    else:
        print("  ✅ 无间隙,数据连续")
    return gaps, order_ids


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""---
    ## Part 3: 字段完整性检查

    统计各字段的非空率:
    """)
    return


@app.cell
def _(mo, results):
    # 检查各字段的非空率
    all_fields = [
        "order_id",
        "quantity",
        "unit_price",
        "discount_rate",
        "order_date",
        "customer_name",
        "product_name",
        "promotion_name",
        "category_name",
        "region_name",
        "price_adjustment",
        "order_amount",
        "profit",
        "final_price",
    ]

    field_completeness = []
    total_rows = len(results)

    for field in all_fields:
        non_null = sum(1 for r in results if r.get(field) is not None)
        rate = 100 * non_null / total_rows if total_rows > 0 else 0
        _status = "✅ 完整" if rate == 100 else ("⚠️ 部分空" if rate >= 80 else "❌ 大量空")
        field_completeness.append({"字段": field, "非空数": non_null, "总数": total_rows, "完整率": f"{rate:.1f}%", "状态": _status})

    mo.ui.table(field_completeness)
    return all_fields, field_completeness, total_rows


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""---
    ## Part 4: 数据预览
    """)
    return


@app.cell
def _(mo, results):
    preview = []
    for _r in results[:10]:
        _row = {
            "order_id": _r.get("order_id"),
            "customer_name": _r.get("customer_name") or "-",
            "promotion_name": _r.get("promotion_name") or "(无)",
            "category_name": _r.get("category_name") or "-",
            "region_name": _r.get("region_name") or "-",
            "order_amount": f"{_r.get('order_amount', 0):.2f}",
        }
        preview.append(_row)
    mo.ui.table(preview)
    return (preview,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""---
    ## Part 5: RowGapObserver - Loader 行缺口检测

    `RowGapObserver` 监控 Loader 调用的行缺口:
    - 记录主数据源行数
    - 检测批次加载时的数据缺失
    """)
    return


@app.cell
def _(InMemoryColumnSink, PlanBuilder, ScalimEngine, TARGET_FIELDS_FULL, load_orders, model):
    from scalim.ob.manager import ObserverManager
    from scalim.ob.presets.row_gap import RowGapObserver
    import logging

    logging.basicConfig(level=logging.INFO)

    gap_targets = TARGET_FIELDS_FULL[:8]
    gap_plan = PlanBuilder(model).build(targets=gap_targets)

    gap_observer_manager = ObserverManager()
    # `RowGapObserver` 监控指定 `loader` 的行缺口
    row_gap_observer = RowGapObserver(
        primary_loader_name="primary_keys",  # 主数据源 `loader` 名称
        data_loader_names={"base_info"},  # 要监控的数据 `loader`
        sample_limit=5,  # 缺失样本数量限制
    )
    gap_observer_manager.register(row_gap_observer)

    gap_engine = ScalimEngine(demand=model, plan=gap_plan, observer_manager=gap_observer_manager, batch_size=100)

    with InMemoryColumnSink(field_names=gap_targets) as sink_gap:
        gap_engine.run(main_rows=load_orders(), sink=sink_gap)
        gap_results = sink_gap.get_rows()

    print(f"RowGapObserver 执行完成: {len(gap_results)} 行")
    print(f"总期望行数: {row_gap_observer._total_expected}")
    print(f"总实际行数: {row_gap_observer._total_actual}")
    print(f"总缺失行数: {row_gap_observer._total_missing}")
    return (
        RowGapObserver,
        gap_engine,
        gap_observer_manager,
        gap_plan,
        gap_results,
        gap_targets,
        logging,
        row_gap_observer,
        sink_gap,
    )


@app.cell(hide_code=True)
def _(gaps, mo, row_gap_observer, vr):
    _all_passed = vr.passed and len(gaps) == 0
    _status = "🎉 数据质量检查通过!" if _all_passed else "⚠️ 存在数据质量问题"
    _gap_info = f"(RowGapObserver: 缺失 {row_gap_observer._total_missing} 行)" if row_gap_observer._total_missing > 0 else "(无行缺口)"
    mo.callout(mo.md(f"## {_status} {_gap_info}"), kind="success" if _all_passed else "warn")
    return


if __name__ == "__main__":
    app.run()
