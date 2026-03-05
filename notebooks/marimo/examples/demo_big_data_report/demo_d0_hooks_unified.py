import marimo

__generated_with = "0.19.4"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # 统一 Hook 与性能监控演示

    本演示整合了 Hook 系统的各种功能:

    ## 功能概览
    | 功能 | 说明 |
    |------|------|
    | 自定义 Hook | 继承 BaseHook 实现自定义监控 |
    | 性能分析 | 收集执行指标 (耗时、调用次数) |
    | 内存监控 | 内存采样、峰值检测 |
    | 进度追踪 | 批次完成进度 |
    | PerformanceObserver | 统一的性能监控 |

    **特点**: 一次执行展示所有 Hook 功能
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
    from typing import Any, Dict, List

    from typing_extensions import override

    _this_dir = _Path(__file__).parent
    if str(_this_dir) not in _sys.path:
        _sys.path.insert(0, str(_this_dir))

    from _loaders import ECommerceConfig, load_orders, set_config
    from _shared import TARGET_FIELDS_FULL, build_ecommerce_model
    from _verification import verify_scalim_output

    from scalim.execution import ScalimEngine
    from scalim.events.events import BatchEndEvent, BatchStartEvent, FieldSlimEvent, LoaderCallEvent, PipelineEndEvent, PipelineStartEvent
    from scalim.hooks.base import BaseHook, HookManager
    from scalim.ob.manager import ObserverManager
    from scalim.ob.presets.performance import PerformanceConfig, PerformanceObserver
    from scalim.planning import PlanBuilder
    from scalim.sinks.sink_memory import InMemoryColumnSink

    return (
        Any,
        BaseHook,
        BatchEndEvent,
        BatchStartEvent,
        Dict,
        ECommerceConfig,
        FieldSlimEvent,
        HookManager,
        InMemoryColumnSink,
        List,
        LoaderCallEvent,
        PerformanceConfig,
        PerformanceObserver,
        PipelineEndEvent,
        PipelineStartEvent,
        PlanBuilder,
        ObserverManager,
        ScalimEngine,
        TARGET_FIELDS_FULL,
        build_ecommerce_model,
        load_orders,
        override,
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
    ## Part 1: 自定义 Hook

    继承 `BaseHook` 实现自定义监控:
    """)
    return


@app.cell
def _(Any, BaseHook, BatchEndEvent, BatchStartEvent, Dict, List, LoaderCallEvent, PipelineEndEvent, PipelineStartEvent, override):
    class PerformanceProfilerHook(BaseHook):
        def __init__(self) -> None:
            self.pipeline_start_time: float = 0
            self.pipeline_end_time: float = 0
            self.batch_durations: List[float] = []
            self.loader_stats: Dict[str, Dict[str, Any]] = {}
            self.field_slim_count: int = 0

        @override
        def on_pipeline_start(self, event: PipelineStartEvent) -> None:
            import time

            self.pipeline_start_time = time.time()

        @override
        def on_pipeline_end(self, event: PipelineEndEvent) -> None:
            import time

            self.pipeline_end_time = time.time()

        @override
        def on_batch_end(self, event: BatchEndEvent) -> None:
            self.batch_durations.append(event.duration)

        @override
        def on_loader_call(self, event: LoaderCallEvent) -> None:
            if event.loader_name not in self.loader_stats:
                self.loader_stats[event.loader_name] = {"call_count": 0, "total_duration": 0.0, "total_records": 0}
            stats = self.loader_stats[event.loader_name]
            stats["call_count"] += 1
            stats["total_duration"] += event.duration
            stats["total_records"] += len(event.result)

        def get_report(self) -> dict:
            total_duration = self.pipeline_end_time - self.pipeline_start_time
            avg_batch = sum(self.batch_durations) / len(self.batch_durations) if self.batch_durations else 0
            return {
                "total_duration": total_duration,
                "batch_count": len(self.batch_durations),
                "avg_batch_duration": avg_batch,
                "loader_stats": self.loader_stats,
            }

    class ProgressBarHook(BaseHook):
        def __init__(self, total_records: int) -> None:
            self.total_records = total_records
            self.processed_records = 0
            self.progress_log: list = []

        @override
        def on_batch_start(self, event: BatchStartEvent) -> None:
            batch_size = len(event.row_ids)
            self.processed_records += batch_size
            progress = (self.processed_records / self.total_records) * 100 if self.total_records > 0 else 0
            self.progress_log.append({"batch": event.batch_num, "processed": self.processed_records, "progress": progress})

    print("自定义钩子类定义完成: `PerformanceProfilerHook`, `ProgressBarHook`")
    return PerformanceProfilerHook, ProgressBarHook


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""---
    ## Part 2: 执行并收集所有指标
    """)
    return


@app.cell
def _(
    HookManager,
    InMemoryColumnSink,
    ObserverManager,
    PerformanceConfig,
    PerformanceObserver,
    PerformanceProfilerHook,
    PlanBuilder,
    ProgressBarHook,
    ScalimEngine,
    TARGET_FIELDS_FULL,
    cfg,
    load_orders,
    model,
    verify_scalim_output,
):
    import time

    targets = TARGET_FIELDS_FULL[:15]
    plan = PlanBuilder(model).build(targets=targets)

    # 注册多个 `Hook`
    hook_manager = HookManager()

    # 自定义性能分析 `Hook`
    custom_profiler = PerformanceProfilerHook()
    hook_manager.register(custom_profiler)

    # 进度 `Hook`
    progress_hook = ProgressBarHook(total_records=cfg.order_count)
    hook_manager.register(progress_hook)

    # 官方性能监控 `Observer`
    perf_config = PerformanceConfig(metrics={"duration", "memory"}, sampling_interval=1, report_format="none")
    observer = PerformanceObserver(config=perf_config)
    observer_manager = ObserverManager()
    observer_manager.register(observer)

    engine = ScalimEngine(
        demand=model,
        plan=plan,
        hook_manager=hook_manager,
        observer_manager=observer_manager,
        batch_size=100,
    )

    print("执行中...")
    start_time = time.time()
    with InMemoryColumnSink(field_names=targets) as sink:
        engine.run(main_rows=load_orders(), sink=sink)
        results = sink.get_rows()
    total_time = time.time() - start_time

    print(f"完成! 总耗时 {total_time:.3f}s, {len(results)} 行")

    # 验证
    vr = verify_scalim_output(results, targets)
    print(f"验证: {'✅ PASS' if vr.passed else '❌ FAIL'}")
    return (
        custom_profiler,
        engine,
        observer,
        perf_config,
        plan,
        progress_hook,
        results,
        sink,
        start_time,
        targets,
        time,
        total_time,
        vr,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""---
    ## Part 3: 性能分析报告
    """)
    return


@app.cell
def _(custom_profiler, mo):
    report = custom_profiler.get_report()
    mo.md(f"""
    ### 自定义 Hook 报告

    | 指标 | 值 |
    |------|-----|
    | 总耗时 | **{report["total_duration"]:.3f}s** |
    | 批次数 | {report["batch_count"]} |
    | 平均批次耗时 | {report["avg_batch_duration"]:.4f}s |
    """)
    return (report,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Loader 调用统计
    """)
    return


@app.cell
def _(mo, report):
    loader_data = []
    for name, stats in report["loader_stats"].items():
        avg_dur = stats["total_duration"] / stats["call_count"] if stats["call_count"] else 0
        loader_data.append(
            {
                "Loader": name.split(".")[-1],
                "调用次数": stats["call_count"],
                "总记录数": stats["total_records"],
                "平均耗时": f"{avg_dur:.4f}s",
            }
        )
    mo.ui.table(loader_data)
    return (loader_data,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""---
    ## Part 4: PerformanceObserver 指标
    """)
    return


@app.cell
def _(mo, observer):
    metrics = observer.get_metrics()
    mo.md(f"""
    ### 性能监控指标

    | 指标 | 值 |
    |------|-----|
    | 总耗时 | **{metrics.total_duration:.3f}s** |
    | 吞吐量 | **{metrics.throughput:.1f} rows/s** |
    | 批次数 | {metrics.batch_count} |
    | 平均批次耗时 | {metrics.avg_batch_duration:.4f}s |
    | 起始内存 | {metrics.start_memory_mb:.1f} MB |
    | 峰值内存 | **{metrics.peak_memory_mb:.1f} MB** |
    | 内存增长 | {metrics.memory_increase_mb:.1f} MB |
    """)
    return (metrics,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""---
    ## Part 5: 内存采样
    """)
    return


@app.cell
def _(metrics, mo):
    samples = metrics.memory_samples or []
    if samples:
        start_mem = samples[0].rss_mb
        end_mem = samples[-1].rss_mb
        peak_mem = max(s.rss_mb for s in samples)

        mo.md(f"""
        ### 内存采样统计

        | 指标 | 值 |
        |------|-----|
        | 起始内存 | {start_mem:.1f} MB |
        | 结束内存 | {end_mem:.1f} MB |
        | 峰值内存 | **{peak_mem:.1f} MB** |
        | 采样点数 | {len(samples)} |
        """)
    return end_mem, peak_mem, samples, start_mem


@app.cell
def _(mo, samples):
    if samples:
        sample_data = []
        for sample in samples[:10]:
            sample_data.append({"标签": sample.label, "RSS (MB)": f"{sample.rss_mb:.1f}"})
        mo.ui.table(sample_data)
    return (sample_data,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""---
    ## Part 6: 进度追踪
    """)
    return


@app.cell
def _(mo, progress_hook):
    progress_data = []
    for p in progress_hook.progress_log[:10]:
        bar_length = 20
        filled = int(bar_length * p["progress"] / 100)
        bar = "█" * filled + "░" * (bar_length - filled)
        progress_data.append({"批次": p["batch"], "已处理": p["processed"], "进度条": f"[{bar}]", "百分比": f"{p['progress']:.1f}%"})
    mo.ui.table(progress_data)
    return (progress_data,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""---
    ## Part 7: 执行模式说明

    Scalim 支持三种执行模式:

    | 模式 | 说明 | 适用场景 | Sink 限制 |
    |------|------|----------|-----------|
    | `seq` | 顺序执行 | 默认,适合小数据量 | 支持所有 Sink |
    | `thread` | 线程并行 | I/O 密集型任务 | 仅支持非流式 Sink |
    | `process` | 进程并行 | CPU 密集型任务 | 仅支持非流式 Sink |

    **注意**: 并行模式 (`thread`/`process`) 不支持流式 Sink (`IRowSink`/`IColumnSink`),
    需要使用 `run()` 等高级 API 或自定义非流式 Sink.
    """)
    return


@app.cell
def _(HookManager, InMemoryColumnSink, PlanBuilder, ScalimEngine, cfg, load_orders, model, time):
    parallel_targets = ["order_id", "customer_name", "product_name", "order_amount"]
    parallel_plan = PlanBuilder(model).build(targets=parallel_targets)

    # 不同批次大小的顺序执行对比
    batch_sizes = [50, 100, 200]
    batch_results = {}

    for _bs in batch_sizes:
        _engine = ScalimEngine(demand=model, plan=parallel_plan, hook_manager=HookManager(), batch_size=_bs, parallel_mode="seq")
        _start = time.time()
        with InMemoryColumnSink(field_names=parallel_targets) as _sink:
            _engine.run(main_rows=load_orders(), sink=_sink)
            batch_results[_bs] = {"rows": len(_sink.get_rows()), "time": time.time() - _start}

    print(f"批次大小对比 ({cfg.order_count} 行):")
    for _bs, _stats in batch_results.items():
        print(f"  batch_size={_bs}: {_stats['time']:.3f}s")
    return batch_results, batch_sizes, parallel_plan, parallel_targets


@app.cell
def _(batch_results, mo):
    batch_table = []
    for _bs, _stats in batch_results.items():
        batch_table.append({"批次大小": _bs, "行数": _stats["rows"], "耗时": f"{_stats['time']:.3f}s"})
    mo.ui.table(batch_table)
    return (batch_table,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""---
    ## Part 8: RelationObserver

    `RelationObserver` 用于监控关联命中情况:
    """)
    return


@app.cell
def _(InMemoryColumnSink, ObserverManager, PlanBuilder, ScalimEngine, load_orders, model, time):
    from scalim.ob.presets.relations import RelationConfig, RelationObserver

    rel_targets = ["order_id", "customer_name", "promotion_name", "category_name", "price_adjustment"]
    rel_plan = PlanBuilder(model).build(targets=rel_targets)

    rel_config = RelationConfig(enabled=True, sampling_rate=1.0, log_type_mismatch=True, report_format="none")
    rel_observer = RelationObserver(config=rel_config)
    rel_observer_manager = ObserverManager()
    rel_observer_manager.register(rel_observer)

    rel_engine = ScalimEngine(demand=model, plan=rel_plan, observer_manager=rel_observer_manager, batch_size=100)

    start_rel = time.time()
    with InMemoryColumnSink(field_names=rel_targets) as sink_rel:
        rel_engine.run(main_rows=load_orders(), sink=sink_rel)
        rel_results = sink_rel.get_rows()
    rel_time = time.time() - start_rel

    print(f"RelationObserver 执行完成: {len(rel_results)} 行, {rel_time:.3f}s")
    return (
        RelationConfig,
        RelationObserver,
        rel_config,
        rel_engine,
        rel_observer_manager,
        rel_observer,
        rel_plan,
        rel_results,
        rel_targets,
        rel_time,
        sink_rel,
        start_rel,
    )


@app.cell
def _(mo, rel_observer):
    rel_metrics = rel_observer.get_metrics()
    rel_stats_table = []

    # 汇总统计
    rel_stats_table.append(
        {
            "关联": "(汇总)",
            "查询次数": rel_metrics.total_lookups,
            "命中次数": rel_metrics.hit_count,
            "命中率": f"{rel_metrics.hit_rate * 100:.1f}%",
        }
    )

    # 按数据源统计
    for _source_id, _stats in rel_metrics.per_source_stats.items():
        rel_stats_table.append(
            {
                "关联": _source_id,
                "查询次数": _stats.total_lookups,
                "命中次数": _stats.hit_count,
                "命中率": f"{_stats.hit_rate * 100:.1f}%",
            }
        )

    if rel_stats_table:
        mo.ui.table(rel_stats_table)
    else:
        print("无关联统计数据")
    return rel_metrics, rel_stats_table


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""---
    ## Part 9: LoggingObserver - 日志记录

    `LoggingObserver` 提供标准日志输出:
    """)
    return


@app.cell
def _(InMemoryColumnSink, ObserverManager, PlanBuilder, ScalimEngine, load_orders, model):
    from scalim.ob.presets.logs import LoggingObserver
    import logging

    # 配置日志级别
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    log_targets = ["order_id", "customer_name", "order_amount"]
    log_plan = PlanBuilder(model).build(targets=log_targets)

    log_observer_manager = ObserverManager()
    log_observer = LoggingObserver()
    log_observer_manager.register(log_observer)

    log_engine = ScalimEngine(demand=model, plan=log_plan, observer_manager=log_observer_manager, batch_size=200)

    with InMemoryColumnSink(field_names=log_targets) as sink_log:
        log_engine.run(main_rows=load_orders(), sink=sink_log)
        log_results = sink_log.get_rows()

    print(f"✅ LoggingObserver 执行完成: {len(log_results)} 行")
    return LoggingObserver, log_engine, log_observer, log_observer_manager, log_plan, log_results, log_targets, logging, sink_log


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""---
    ## Part 10: PerformanceObserver - 指标收集

    `PerformanceObserver` 收集详细的执行指标:
    """)
    return


@app.cell
def _(InMemoryColumnSink, ObserverManager, PerformanceConfig, PerformanceObserver, PlanBuilder, ScalimEngine, load_orders, model, time):
    metric_targets = ["order_id", "customer_name", "product_name", "order_amount"]
    metric_plan = PlanBuilder(model).build(targets=metric_targets)

    metric_observer_manager = ObserverManager()
    perf_config_metrics = PerformanceConfig(metrics={"duration"}, report_format="none", include_details=True)
    perf_observer = PerformanceObserver(config=perf_config_metrics)
    metric_observer_manager.register(perf_observer)

    metric_engine = ScalimEngine(demand=model, plan=metric_plan, observer_manager=metric_observer_manager, batch_size=100)

    start_metric = time.time()
    with InMemoryColumnSink(field_names=metric_targets) as sink_metric:
        metric_engine.run(main_rows=load_orders(), sink=sink_metric)
        metric_results = sink_metric.get_rows()
    metric_time = time.time() - start_metric

    print(f"✅ PerformanceObserver 执行完成: {len(metric_results)} 行, {metric_time:.3f}s")

    # 获取指标 (PerformanceObserver 使用 get_metrics)
    collected_metrics = perf_observer.get_metrics()
    print(f"   加载器指标数: {len(collected_metrics.loader_stats)}")
    return (
        collected_metrics,
        metric_engine,
        metric_observer_manager,
        metric_plan,
        metric_results,
        metric_targets,
        metric_time,
        perf_config_metrics,
        perf_observer,
        sink_metric,
        start_metric,
    )


@app.cell
def _(collected_metrics, mo):
    loader_metrics_table = []
    for _loader_name, _loader_metrics in collected_metrics.loader_stats.items():
        loader_metrics_table.append(
            {
                "Loader": _loader_name.split(".")[-1],
                "调用次数": _loader_metrics.call_count,
                "总记录数": _loader_metrics.total_records,
                "总耗时": f"{_loader_metrics.total_duration:.4f}s",
            }
        )
    if loader_metrics_table:
        mo.ui.table(loader_metrics_table)
    else:
        print("无加载器指标")
    return (loader_metrics_table,)


@app.cell(hide_code=True)
def _(mo, vr):
    _status = "🎉 所有 Hook 功能验证通过!" if vr.passed else "❌ 验证失败"
    mo.callout(mo.md(f"## {_status}"), kind="success" if vr.passed else "danger")
    return


if __name__ == "__main__":
    app.run()
