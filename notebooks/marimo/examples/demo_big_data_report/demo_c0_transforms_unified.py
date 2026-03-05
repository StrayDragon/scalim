import marimo

__generated_with = "0.19.4"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # 统一转换演示 - 关联与派生字段

    本演示整合了关联转换和派生字段计算的功能:

    ## 关联类型
    | 类型 | 说明 | 示例 |
    |------|------|------|
    | 单级关联 | FK → Key | orders.customer_id → customers |
    | 多级关联 | FK → Key → FK → Key | orders → products → categories |
    | 复合键关联 | (FK1, FK2) → (Key1, Key2) | orders → region_pricing |

    ## 派生字段
    | 字段 | 公式 |
    |------|------|
    | order_amount | quantity × unit_price × discount_rate |
    | profit | order_amount - product_cost × quantity |
    | final_price | order_amount × price_adjustment + shipping_fee |

    **特点**: 一次执行验证所有转换逻辑
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
    from _shared import TARGET_FIELDS_DERIVED, TARGET_FIELDS_FULL, build_ecommerce_model
    from _verification import python_build_order_report, verify_scalim_output

    from scalim.execution import ScalimEngine
    from scalim.planning import PlanBuilder
    from scalim.sinks.sink_memory import InMemoryColumnSink

    return (
        ECommerceConfig,
        InMemoryColumnSink,
        PlanBuilder,
        ScalimEngine,
        TARGET_FIELDS_DERIVED,
        TARGET_FIELDS_FULL,
        build_ecommerce_model,
        load_orders,
        python_build_order_report,
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
    ## Part 1: 关联转换

    电商模型中的关联类型演示:
    - **单级关联**: orders.customer_id → customers.customer_id
    - **多级关联**: orders → products → categories
    - **复合键关联**: orders → region_pricing (region_id, product_category_id)
    """)
    return


@app.cell
def _(InMemoryColumnSink, PlanBuilder, ScalimEngine, load_orders, model, verify_scalim_output):
    # 关联字段
    relation_targets = [
        "order_id",
        "quantity",
        "unit_price",
        # 单级关联
        "customer_name",
        "customer_level",
        "product_name",
        "product_brand",
        "promotion_name",  # 可能为空
        "payment_method_name",
        "logistics_name",
        # 多级关联
        "category_name",
        "region_name",
        "region_manager",
        # 复合键关联
        "price_adjustment",
        "shipping_fee",
        "tax_rate",
    ]

    plan_rel = PlanBuilder(model).build(targets=relation_targets)
    engine_rel = ScalimEngine(demand=model, plan=plan_rel, batch_size=100)

    with InMemoryColumnSink(field_names=relation_targets) as sink_rel:
        engine_rel.run(main_rows=load_orders(), sink=sink_rel)
        relation_results = sink_rel.get_rows()

    print(f"关联执行完成: {len(relation_results)} 行")

    vr_rel = verify_scalim_output(relation_results, relation_targets)
    print(f"验证: {'✅ PASS' if vr_rel.passed else '❌ FAIL'}")
    return engine_rel, plan_rel, relation_results, relation_targets, sink_rel, vr_rel


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### 关联结果预览
    """)
    return


@app.cell
def _(mo, relation_results):
    rel_preview = []
    for _r in relation_results[:10]:
        _row = {}
        for _k in ["order_id", "customer_name", "product_name", "category_name", "promotion_name", "region_name"]:
            _v = _r.get(_k)
            _row[_k] = str(_v) if _v is not None else "-"
        rel_preview.append(_row)
    mo.ui.table(rel_preview)
    return (rel_preview,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### 空值处理验证

    验证 promotion_name 字段的空值处理(部分订单无促销):
    """)
    return


@app.cell
def _(mo, relation_results):
    promo_stats = {"有促销": 0, "无促销": 0}
    for _rec in relation_results:
        if _rec.get("promotion_name"):
            promo_stats["有促销"] += 1
        else:
            promo_stats["无促销"] += 1

    total = len(relation_results)
    has_promo = promo_stats["有促销"]
    no_promo = promo_stats["无促销"]

    mo.hstack(
        [
            mo.stat(value=f"{has_promo}", label=f"有促销 ({100 * has_promo / total:.1f}%)", bordered=True),
            mo.stat(value=f"{no_promo}", label=f"无促销 ({100 * no_promo / total:.1f}%)", bordered=True),
        ],
        justify="start",
        gap=1,
    )
    return has_promo, no_promo, promo_stats, total


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""---
    ## Part 2: 派生字段计算

    派生字段计算逻辑:
    - `order_amount = quantity * unit_price * discount_rate`
    - `profit = order_amount - product_cost * quantity`
    - `final_price = order_amount * price_adjustment + shipping_fee`
    """)
    return


@app.cell
def _(InMemoryColumnSink, PlanBuilder, ScalimEngine, TARGET_FIELDS_DERIVED, load_orders, model, verify_scalim_output):
    # 派生字段及其依赖
    derived_targets = [
        "order_id",
        "quantity",
        "unit_price",
        "discount_rate",
        "product_cost",
        "price_adjustment",
        "shipping_fee",
    ] + TARGET_FIELDS_DERIVED

    plan_der = PlanBuilder(model).build(targets=derived_targets)
    engine_der = ScalimEngine(demand=model, plan=plan_der, batch_size=100)

    with InMemoryColumnSink(field_names=derived_targets) as sink_der:
        engine_der.run(main_rows=load_orders(), sink=sink_der)
        derived_results = sink_der.get_rows()

    print(f"派生字段执行完成: {len(derived_results)} 行")

    vr_der = verify_scalim_output(derived_results, derived_targets)
    print(f"验证: {'✅ PASS' if vr_der.passed else '❌ FAIL'}")
    return derived_results, derived_targets, engine_der, plan_der, sink_der, vr_der


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### 派生字段计算验证

    手动验证派生字段计算逻辑:
    """)
    return


@app.cell
def _(derived_results, mo):
    verification_rows = []
    for _rec in derived_results[:5]:
        qty = _rec.get("quantity", 0)
        price = _rec.get("unit_price", 0)
        disc = _rec.get("discount_rate", 1)
        cost = _rec.get("product_cost", 0)
        adj = _rec.get("price_adjustment", 1)
        ship = _rec.get("shipping_fee", 0)

        expected_amount = qty * price * disc
        expected_profit = expected_amount - cost * qty if cost else None
        expected_final = expected_amount * adj + ship if adj else None

        actual_amount = _rec.get("order_amount", 0)
        actual_profit = _rec.get("profit")
        actual_final = _rec.get("final_price")

        amount_ok = abs(expected_amount - actual_amount) < 0.01
        profit_ok = actual_profit is None or expected_profit is None or abs(expected_profit - actual_profit) < 0.01
        final_ok = actual_final is None or expected_final is None or abs(expected_final - actual_final) < 0.01

        verification_rows.append(
            {
                "order_id": _rec.get("order_id"),
                "order_amount 公式": f"{qty}×{price}×{disc}",
                "order_amount 预期": f"{expected_amount:.2f}",
                "order_amount 实际": f"{actual_amount:.2f}",
                "order_amount 状态": "✅" if amount_ok else "❌",
                "profit 状态": "✅" if profit_ok else "❌",
                "final_price 状态": "✅" if final_ok else "❌",
            }
        )

    mo.md(r"""
    ### 派生字段计算验证 (前5行)
    """)
    return (
        actual_amount,
        actual_final,
        actual_profit,
        adj,
        amount_ok,
        cost,
        disc,
        expected_amount,
        expected_final,
        expected_profit,
        final_ok,
        price,
        profit_ok,
        qty,
        ship,
        verification_rows,
    )


@app.cell
def _(mo, verification_rows):
    mo.ui.table(verification_rows, selection=None)
    return


@app.cell
def _(derived_results, mo):
    der_preview = []
    for _r in derived_results[:10]:
        der_preview.append(
            {
                "order_id": _r.get("order_id"),
                "quantity": _r.get("quantity"),
                "unit_price": f"{_r.get('unit_price', 0):.2f}",
                "order_amount": f"{_r.get('order_amount', 0):.2f}",
                "profit": f"{_r.get('profit', 0):.2f}" if _r.get("profit") else "-",
                "final_price": f"{_r.get('final_price', 0):.2f}" if _r.get("final_price") else "-",
            }
        )
    mo.ui.table(der_preview)
    return (der_preview,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""---
    ## Part 3: 纯 Python 对照验证
    """)
    return


@app.cell
def _(TARGET_FIELDS_FULL, python_build_order_report, verify_scalim_output):
    import time

    # 纯 Python 实现
    start_py = time.time()
    python_results = python_build_order_report(TARGET_FIELDS_FULL)
    py_time = time.time() - start_py

    print(f"纯 `Python` 实现: {len(python_results)} 行, {py_time:.3f}s")

    # 对比验证
    vr_py = verify_scalim_output(python_results, TARGET_FIELDS_FULL)
    print(f"纯 `Python` 自验证: {'✅ 通过' if vr_py.passed else '❌ 失败'}")
    return py_time, python_results, start_py, time, vr_py


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""---
    ## 汇总结果
    """)
    return


@app.cell
def _(mo, vr_der, vr_py, vr_rel):
    results_data = [
        {"测试项": "关联转换 (单级/多级/复合键)", "状态": "✅ PASS" if vr_rel.passed else "❌ FAIL"},
        {"测试项": "派生字段计算", "状态": "✅ PASS" if vr_der.passed else "❌ FAIL"},
        {"测试项": "纯 Python 对照", "状态": "✅ PASS" if vr_py.passed else "❌ FAIL"},
    ]
    mo.ui.table(results_data, selection=None)
    return (results_data,)


@app.cell(hide_code=True)
def _(mo, vr_der, vr_py, vr_rel):
    all_passed = vr_rel.passed and vr_der.passed and vr_py.passed
    final_status = "🎉 所有转换验证通过!" if all_passed else "❌ 部分转换验证失败"
    mo.callout(mo.md(f"## {final_status}"), kind="success" if all_passed else "danger")
    return all_passed, final_status


if __name__ == "__main__":
    app.run()
