import marimo

__generated_with = "0.19.4"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # 执行计划可视化演示

    本演示通过**对比不同场景**展示执行计划的特性:

    | 场景 | 特点 | 演示内容 |
    |------|------|----------|
    | 场景1 | 简单目标 | 仅主数据源字段 |
    | 场景2 | 派生字段 | 包含计算字段 (order_amount) |
    | 场景3 | 关联字段 | 跨数据源关联 |
    | 场景4 | 完整目标 | 所有功能组合 |

    **关键概念**: 字段剪枝、依赖分析、Loader 序列

    **注意**: 本演示仅分析执行计划,不执行实际数据处理
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
    """)
    return


@app.cell
def _():
    import sys as _sys
    from pathlib import Path as _Path

    _this_dir = _Path(__file__).parent
    if str(_this_dir) not in _sys.path:
        _sys.path.insert(0, str(_this_dir))

    from _loaders import ECommerceConfig, set_config
    from _shared import build_ecommerce_model

    return ECommerceConfig, build_ecommerce_model, set_config


@app.cell
def _():
    from scalim.planning import PlanBuilder

    return (PlanBuilder,)


@app.cell
def _(ECommerceConfig, build_ecommerce_model, set_config):
    cfg = ECommerceConfig(order_count=100)
    set_config(cfg)

    model = build_ecommerce_model()
    print(f"✓ 模型加载完成: {len(model.sources)} 个数据源, {len(model.fields)} 个字段")
    return cfg, model


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---
    ## 场景1: 简单目标 - 仅主数据源字段

    只请求主数据源 `orders` 中的字段,**无需加载关联表**.
    """)
    return


@app.cell
def _(PlanBuilder, mo, model):
    simple_targets = ["order_id", "quantity", "unit_price"]
    plan1 = PlanBuilder(model).build(targets=simple_targets)
    meta1 = plan1.metadata

    mo.md(f"""
    **目标字段**: `{", ".join(simple_targets)}`

    | 指标 | 值 |
    |------|-----|
    | 字段数 | {meta1.total_fields} |
    | 数据源 | {meta1.total_sources} |
    | 剪枝 | {meta1.pruned_fields} |
    | 派生字段 | {"是" if meta1.has_derived_fields else "否"} |
    | 关联字段 | {"是" if meta1.has_ref_fields else "否"} |
    """)
    return meta1, plan1, simple_targets


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---
    ## 场景2: 派生字段 - 包含计算字段

    `order_amount` 是派生字段,依赖 `quantity, unit_price, discount_rate`,框架会**自动添加依赖字段**.
    """)
    return


@app.cell
def _(PlanBuilder, mo, model):
    derived_targets = ["order_id", "quantity", "unit_price", "order_amount"]
    plan2 = PlanBuilder(model).build(targets=derived_targets)
    meta2 = plan2.metadata

    mo.md(f"""
    **目标字段**: `{", ".join(derived_targets)}`

    | 指标 | 值 |
    |------|-----|
    | 字段数 | {meta2.total_fields} |
    | 数据源 | {meta2.total_sources} |
    | 剪枝 | {meta2.pruned_fields} |
    | 派生字段 | {"是" if meta2.has_derived_fields else "否"} |

    说明: `order_amount = quantity * unit_price * discount_rate`
    """)
    return derived_targets, meta2, plan2


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---
    ## 场景3: 关联字段 - 跨数据源关联

    请求来自不同数据源的字段,展示**多种关联方式**:
    """)
    return


@app.cell
def _(PlanBuilder, mo, model):
    ref_targets = ["order_id", "customer_name", "product_name", "category_name"]
    plan3 = PlanBuilder(model).build(targets=ref_targets)
    meta3 = plan3.metadata

    mo.md(f"""
    **目标字段**: `{", ".join(ref_targets)}`

    | 指标 | 值 |
    |------|-----|
    | 字段数 | {meta3.total_fields} |
    | 数据源 | {meta3.total_sources} |
    | 剪枝 | {meta3.pruned_fields} |
    | 关联字段 | {"是" if meta3.has_ref_fields else "否"} |

    **关联类型说明**:
    - `customer_name`: 单级关联 (`orders.customer_id` → `customers`)
    - `product_name`: 单级关联 (`orders.product_id` → `products`)
    - `category_name`: 多级关联 (`orders` → `products` → `categories`)
    """)
    return meta3, plan3, ref_targets


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---
    ## 场景4: 完整目标 - 所有功能组合

    综合使用所有特性:派生字段 + 关联字段 + 多级关联 + 复合键关联
    """)
    return


@app.cell
def _(PlanBuilder, model):
    full_targets = [
        "order_id",
        "quantity",
        "unit_price",
        "customer_name",
        "product_name",
        "category_name",
        "region_name",
        "price_adjustment",  # 复合键关联
        "order_amount",
        "profit",
    ]
    plan4 = PlanBuilder(model).build(targets=full_targets)
    meta4 = plan4.metadata
    return full_targets, meta4, plan4


@app.cell
def _(full_targets, meta4, mo):
    mo.md(f"""
    **目标字段**: `{", ".join(full_targets)}`

    | 指标 | 值 |
    |------|-----|
    | 字段数 | {meta4.total_fields} |
    | 数据源 | {meta4.total_sources} |
    | Loader | {meta4.total_loaders} |
    | 剪枝 | {meta4.pruned_fields} |
    | 最大深度 | {meta4.max_depth} |
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---
    ## 字段执行顺序

    字段按依赖关系排序,确保依赖字段先计算:
    """)
    return


@app.cell
def _(mo, plan4):
    order_display = " → ".join(plan4.field_order[:15])
    if len(plan4.field_order) > 15:
        order_display += " ..."
    mo.md(f"**执行顺序**: {order_display}")
    return (order_display,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---
    ## Loader 加载序列

    展示数据源的加载顺序和加载的字段:
    """)
    return


@app.cell
def _(mo, plan4):
    loader_info = []
    for source, fields in plan4.loader_sequence:
        field_names = [f if isinstance(f, str) else f[0] for f in fields]
        loader_info.append(
            {
                "数据源": source.source_id,
                "加载字段": ", ".join(field_names[:5]) + ("..." if len(field_names) > 5 else ""),
            }
        )

    if plan4.ref_loader_sequence:
        for source, fields in plan4.ref_loader_sequence:
            field_names = [f if isinstance(f, str) else f[0] for f in fields]
            loader_info.append(
                {
                    "数据源": f"{source.source_id} (关联)",
                    "加载字段": ", ".join(field_names[:5]) + ("..." if len(field_names) > 5 else ""),
                }
            )

    mo.ui.table(loader_info)
    return (loader_info,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---
    ## 场景对比总结
    """)
    return


@app.cell
def _(meta1, meta2, meta3, meta4, mo):
    comparison = [
        {"场景": "场景1: 简单目标", "字段数": meta1.total_fields, "数据源": meta1.total_sources, "剪枝": meta1.pruned_fields},
        {"场景": "场景2: 派生字段", "字段数": meta2.total_fields, "数据源": meta2.total_sources, "剪枝": meta2.pruned_fields},
        {"场景": "场景3: 关联字段", "字段数": meta3.total_fields, "数据源": meta3.total_sources, "剪枝": meta3.pruned_fields},
        {"场景": "场景4: 完整目标", "字段数": meta4.total_fields, "数据源": meta4.total_sources, "剪枝": meta4.pruned_fields},
    ]
    mo.ui.table(comparison)
    return (comparison,)


if __name__ == "__main__":
    app.run()
