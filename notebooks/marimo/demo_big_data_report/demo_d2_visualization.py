import marimo

__generated_with = "0.19.4"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # 执行过程可视化演示

    展示 Scalim 框架执行过程的可视化:

    | 可视化内容 | 说明 |
    |------------|------|
    | 执行计划 | 算子序列、执行阶段 |
    | 批次执行 | 批次耗时、进度 |
    | 数据流 | 字段依赖关系 |

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
    from scalim.sinks.sink_memory import InMemoryColumnSink
    from scalim.planning import PlanBuilder

    return (
        ECommerceConfig,
        InMemoryColumnSink,
        PlanBuilder,
        ScalimEngine,
        TARGET_FIELDS_FULL,
        build_ecommerce_model,
        load_orders,
        set_config,
        verify_scalim_output,
    )


@app.cell
def _(ECommerceConfig, build_ecommerce_model, set_config):
    cfg = ECommerceConfig(order_count=500)
    set_config(cfg)
    model = build_ecommerce_model()
    print(f"模型: {len(model.sources)} 个数据源, {len(model.fields)} 个字段, {cfg.order_count} 订单")
    return cfg, model


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---
    ## 执行计划可视化
    """)
    return


@app.cell
def _(PlanBuilder, TARGET_FIELDS_FULL, model, mo):
    targets = TARGET_FIELDS_FULL

    plan = PlanBuilder(model).build(targets=targets)
    meta = plan.metadata

    mo.md(f"""
    ### 计划元数据

    | 指标 | 值 |
    |------|-----|
    | 目标字段数 | {len(targets)} |
    | 总字段数 | {meta.total_fields} |
    | 数据源数 | {meta.total_sources} |
    | 缓存源 | {", ".join(meta.cached_sources) if meta.cached_sources else "None"} |
    | 最大依赖深度 | {meta.max_depth} |
    | 有派生字段 | {"是" if meta.has_derived_fields else "否"} |
    | 有关联字段 | {"是" if meta.has_ref_fields else "否"} |
    """)
    return meta, plan, targets


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### 执行阶段
    """)
    return


@app.cell
def _(mo, plan):
    stage_info = []
    for stage in plan.stages:
        fields_preview = ", ".join(stage.field_keys[:5])
        if len(stage.field_keys) > 5:
            fields_preview += f"... (+{len(stage.field_keys) - 5})"
        stage_info.append({"阶段": stage.stage_id, "层级": stage.level, "字段数": len(stage.field_keys), "字段预览": fields_preview})
    mo.ui.table(stage_info)
    return (stage_info,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### 算子序列 (前10个)
    """)
    return


@app.cell
def _(mo, plan):
    from scalim.planning import ComputeOperatorIr, LoadOperatorIr, LoadRefOperatorIr

    op_table = []
    for op in plan.operators[:10]:
        if isinstance(op, LoadOperatorIr):
            fields_str = ", ".join(op.field_keys[:3])
            if len(op.field_keys) > 3:
                fields_str += f"... (+{len(op.field_keys) - 3})"
            op_table.append({"算子ID": op.operator_id, "类型": "Load", "数据源": op.source.source_id, "详情": fields_str})
        elif isinstance(op, LoadRefOperatorIr):
            op_table.append({"算子ID": op.operator_id, "类型": "LoadRef", "数据源": op.source.source_id, "详情": op.field_key})
        elif isinstance(op, ComputeOperatorIr):
            deps = ", ".join(op.input_fields[:3])
            if len(op.input_fields) > 3:
                deps += "..."
            op_table.append({"算子ID": op.operator_id, "类型": "Compute", "数据源": "-", "详情": f"{op.field_spec.field_id} = f({deps})"})
    mo.ui.table(op_table)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---
    ## 执行并验证
    """)
    return


@app.cell
def _(
    InMemoryColumnSink,
    ScalimEngine,
    load_orders,
    mo,
    model,
    plan,
    targets,
    verify_scalim_output,
):
    engine = ScalimEngine(demand=model, plan=plan, batch_size=20)

    with InMemoryColumnSink(field_names=targets) as sink:
        engine.run(main_rows=load_orders(), sink=sink)
        results = sink.get_rows()

    vr = verify_scalim_output(results, targets)

    mo.hstack(
        [
            mo.stat(value=f"{len(results)}", label="输出行数", bordered=True),
            mo.stat(value="✅ PASS" if vr.passed else "❌ FAIL", label="验证状态", bordered=True),
        ],
        justify="start",
        gap=1,
    )
    return results, vr


@app.cell
def _(mo, results):
    preview = []
    for r in results[:5]:
        row = {}
        for k in ["order_id", "customer_name", "category_name", "order_amount", "profit"]:
            v = r.get(k)
            row[k] = f"{v:.2f}" if isinstance(v, float) else (str(v) if v is not None else "-")
        preview.append(row)
    mo.ui.table(preview)
    return k, preview, r, row, v


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""---
    ## ExecutionTraceObserver - 执行追踪

    `ExecutionTraceObserver` 记录详细的执行步骤:
    """)
    return


@app.cell
def _(InMemoryColumnSink, ScalimEngine, load_orders, model, plan, targets):
    from scalim.ob.manager import ObserverManager
    from scalim.ob.presets.execution_trace import ExecutionTraceObserver

    trace_observer_manager = ObserverManager()
    trace_observer = ExecutionTraceObserver()
    trace_observer_manager.register(trace_observer)

    trace_engine = ScalimEngine(demand=model, plan=plan, observer_manager=trace_observer_manager, batch_size=50)

    with InMemoryColumnSink(field_names=targets) as sink_trace:
        trace_engine.run(main_rows=load_orders(), sink=sink_trace)
        trace_results = sink_trace.get_rows()

    print(f"ExecutionTraceObserver 执行完成: {len(trace_results)} 行")

    # 获取追踪数据(使用 `batches` 属性)
    traces = trace_observer.batches
    print(f"追踪批次数: {len(traces)}")
    return ExecutionTraceObserver, ObserverManager, sink_trace, trace_engine, trace_observer, trace_observer_manager, trace_results, traces


@app.cell
def _(mo, traces):
    from scalim.ob.presets.execution_trace import FieldSlimStep, LoaderCallStep, RowWriteStep

    if traces:
        trace_summary = []
        for _batch_trace in traces[:5]:
            _loader_calls = sum(1 for s in _batch_trace.steps if isinstance(s, LoaderCallStep))
            _field_slims = sum(1 for s in _batch_trace.steps if isinstance(s, FieldSlimStep))
            _row_writes = sum(1 for s in _batch_trace.steps if isinstance(s, RowWriteStep))
            trace_summary.append(
                {
                    "批次": _batch_trace.batch_num,
                    "行数": len(_batch_trace.row_ids),
                    "Loader调用": _loader_calls,
                    "字段剪枝": _field_slims,
                    "行写入": _row_writes,
                    "耗时": f"{_batch_trace.duration:.4f}s" if _batch_trace.duration else "-",
                }
            )
        mo.ui.table(trace_summary)
    else:
        print("无追踪数据")
    return FieldSlimStep, LoaderCallStep, RowWriteStep, trace_summary


@app.cell(hide_code=True)
def _(mo, vr):
    _status = "✅ 验证通过" if vr.passed else "❌ 验证失败"
    mo.callout(mo.md(f"## {_status}"), kind="success" if vr.passed else "danger")
    return


if __name__ == "__main__":
    app.run()
