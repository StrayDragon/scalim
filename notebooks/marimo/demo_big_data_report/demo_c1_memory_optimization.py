import marimo

__generated_with = "0.19.4"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # 内存优化演示

    本演示展示 Scalim 框架的**内存优化策略**:

    | 功能 | 说明 | 适用场景 |
    |------|------|----------|
    | **字段瘦身** | 中间字段用完即删 | 派生字段计算后释放依赖 |
    | **行级写入** | 每行完成后写入 | 窄表、实时输出 |
    | **列级写入** | 每列完成后写入 | 宽表、更早释放内存 |

    **特点**: 自动对拍验证,确保输出正确性
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
    from scalim.ob.manager import ObserverManager
    from scalim.ob.presets.memory import MemoryOptimizationObserver
    from scalim.sinks.sink_csv import CSVSink, ColumnCSVSink
    from scalim.sinks.sink_memory import InMemoryColumnSink
    from scalim.planning import PlanBuilder

    return (
        CSVSink,
        ColumnCSVSink,
        ECommerceConfig,
        ObserverManager,
        InMemoryColumnSink,
        MemoryOptimizationObserver,
        PlanBuilder,
        ScalimEngine,
        TARGET_FIELDS_FULL,
        build_ecommerce_model,
        load_orders,
        set_config,
        verify_scalim_output,
    )


@app.cell
def _(ECommerceConfig, build_ecommerce_model, mo, set_config):
    cfg = ECommerceConfig(order_count=1000)
    set_config(cfg)
    model = build_ecommerce_model()

    mo.hstack(
        [
            mo.stat(value=f"{len(model.sources)}", label="数据源数", bordered=True),
            mo.stat(value=f"{len(model.fields)}", label="字段数", bordered=True),
            mo.stat(value=f"{cfg.order_count}", label="订单数", bordered=True),
        ],
        justify="start",
        gap=1,
    )
    return cfg, model


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---
    ## Part 1: 行级流式写入 (CSVSink)

    **工作原理**:
    1. 每处理完一条记录,立即写入文件
    2. 写入后释放该行数据的内存
    3. 适合字段较少的窄表场景
    """)
    return


@app.cell
def _(
    CSVSink,
    InMemoryColumnSink,
    MemoryOptimizationObserver,
    ObserverManager,
    PlanBuilder,
    ScalimEngine,
    TARGET_FIELDS_FULL,
    load_orders,
    model,
    verify_scalim_output,
):
    targets_row = TARGET_FIELDS_FULL[:8]

    plan_row = PlanBuilder(model).build(targets=targets_row)

    observer_manager_row = ObserverManager()
    memory_observer_row = MemoryOptimizationObserver()
    observer_manager_row.register(memory_observer_row)

    engine_row = ScalimEngine(demand=model, plan=plan_row, observer_manager=observer_manager_row, batch_size=20)

    output_path_row = "/tmp/orders_streaming.csv"

    with CSVSink(output_path_row, field_names=targets_row) as sink_row:
        engine_row.run(main_rows=load_orders(), sink=sink_row)

    print(f"行级写入完成: {output_path_row}")
    print(f"字段瘦身次数: {len(memory_observer_row.field_slim_events)}")

    # 获取结果验证
    engine_row2 = ScalimEngine(demand=model, plan=plan_row, batch_size=20)
    with InMemoryColumnSink(field_names=targets_row) as mem_sink:
        engine_row2.run(main_rows=load_orders(), sink=mem_sink)
        results_row = mem_sink.get_rows()

    vr_row = verify_scalim_output(results_row, targets_row)
    print(f"验证: {vr_row}")
    assert vr_row.passed, vr_row.summary
    return memory_observer_row, output_path_row, results_row, targets_row, vr_row


@app.cell
def _(output_path_row):
    with open(output_path_row) as f:
        lines = f.readlines()
    print("文件预览 (前5行):")
    for line in lines[:5]:
        print(f"  {line.rstrip()}")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---
    ## Part 2: 列级流式写入 (ColumnCSVSink)

    **工作原理**:
    1. 按列组织数据,每列计算完成后立即写入
    2. 写入后释放该列数据的内存
    3. **更早释放内存** - 适合宽表场景
    """)
    return


@app.cell
def _(
    ColumnCSVSink,
    InMemoryColumnSink,
    MemoryOptimizationObserver,
    ObserverManager,
    PlanBuilder,
    ScalimEngine,
    TARGET_FIELDS_FULL,
    load_orders,
    model,
    verify_scalim_output,
):
    targets_col = TARGET_FIELDS_FULL

    plan_col = PlanBuilder(model).build(targets=targets_col)

    observer_manager_col = ObserverManager()
    memory_observer_col = MemoryOptimizationObserver()
    observer_manager_col.register(memory_observer_col)

    engine_col = ScalimEngine(demand=model, plan=plan_col, observer_manager=observer_manager_col, batch_size=20)

    output_path_col = "/tmp/orders_column_streaming.csv"

    with ColumnCSVSink(output_path_col, field_names=targets_col) as sink_col:
        engine_col.run(main_rows=load_orders(), sink=sink_col)

    print(f"列级写入完成: {output_path_col}")
    print(f"列写入次数: {len(memory_observer_col.column_write_events)}")

    # 获取结果验证
    engine_col2 = ScalimEngine(demand=model, plan=plan_col, batch_size=20)
    with InMemoryColumnSink(field_names=targets_col) as mem_sink2:
        engine_col2.run(main_rows=load_orders(), sink=mem_sink2)
        results_col = mem_sink2.get_rows()

    vr_col = verify_scalim_output(results_col, targets_col)
    print(f"验证: {vr_col}")
    assert vr_col.passed, vr_col.summary
    return memory_observer_col, output_path_col, results_col, targets_col, vr_col


@app.cell
def _(output_path_col):
    with open(output_path_col) as f2:
        lines2 = f2.readlines()
    print("文件预览:")
    for line2 in lines2[:4]:
        print(f"  {line2.rstrip()}")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""---
    ## Part 3: BlockColumnCSVSink - 实时可见列式写入

    `BlockColumnCSVSink` 是一种特殊的列式 Sink:
    - 每个批次完成后立即写入文件
    - 文件内容实时可见(适合监控进度)
    - 适合需要实时查看输出的场景
    """)
    return


@app.cell
def _(InMemoryColumnSink, PlanBuilder, ScalimEngine, TARGET_FIELDS_FULL, load_orders, model, verify_scalim_output):
    from scalim.sinks.sink_csv import BlockColumnCSVSink

    targets_block = TARGET_FIELDS_FULL[:10]
    plan_block = PlanBuilder(model).build(targets=targets_block)

    engine_block = ScalimEngine(demand=model, plan=plan_block, batch_size=50)

    output_path_block = "/tmp/orders_block_column.csv"

    with BlockColumnCSVSink(output_path_block, field_names=targets_block) as sink_block:
        engine_block.run(main_rows=load_orders(), sink=sink_block)

    print(f"BlockColumnCSVSink 写入完成: {output_path_block}")

    # 验证
    engine_block2 = ScalimEngine(demand=model, plan=plan_block, batch_size=50)
    with InMemoryColumnSink(field_names=targets_block) as mem_sink_block:
        engine_block2.run(main_rows=load_orders(), sink=mem_sink_block)
        results_block = mem_sink_block.get_rows()

    vr_block = verify_scalim_output(results_block, targets_block)
    print(f"验证: {'✅ PASS' if vr_block.passed else '❌ FAIL'}")
    return BlockColumnCSVSink, output_path_block, results_block, targets_block, vr_block


@app.cell
def _(output_path_block):
    with open(output_path_block) as f_block:
        block_lines = f_block.readlines()
    print(f"BlockColumnCSVSink 文件预览 ({len(block_lines)} 行):")
    for _line in block_lines[:4]:
        print(f"  {_line.rstrip()}")
    return (block_lines,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""---
    ## 汇总结果
    """)
    return


@app.cell
def _(mo, vr_block, vr_col, vr_row):
    results_data = [
        {"写入方式": "CSVSink (行级)", "行数": vr_row.checked_rows, "验证": "✅" if vr_row.passed else "❌", "特点": "逐行写入,内存最优"},
        {"写入方式": "ColumnCSVSink (列级)", "行数": vr_col.checked_rows, "验证": "✅" if vr_col.passed else "❌", "特点": "列完成后写入"},
        {
            "写入方式": "BlockColumnCSVSink",
            "行数": vr_block.checked_rows,
            "验证": "✅" if vr_block.passed else "❌",
            "特点": "批次完成后写入,实时可见",
        },
    ]
    mo.ui.table(results_data, selection=None)
    return (results_data,)


@app.cell(hide_code=True)
def _(mo, vr_block, vr_col, vr_row):
    _all_passed = vr_row.passed and vr_col.passed and vr_block.passed
    _status = "✅ 所有内存优化模式验证通过" if _all_passed else "❌ 验证失败"
    mo.callout(mo.md(f"## {_status}"), kind="success" if _all_passed else "danger")
    return


if __name__ == "__main__":
    app.run()
