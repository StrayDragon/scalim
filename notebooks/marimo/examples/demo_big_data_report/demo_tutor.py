import marimo

__generated_with = "0.20.1"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # demo_tutor

    一个单文件的 **marimo 笔记本**,用来快速理解 Scalim 的核心能力(无需 YAML DSL):

    - IR(Demand/Source/Field/Relation)
    - Planning(PlanBuilder → ExecutionPlan)
    - Execution(ScalimEngine:seq / adaptive)
    - 编排(`run_ir`:与 DSL 无关的执行编排)
    - Sinks(memory / csv / excel / pandas)
    - Observability(Performance/Memory/Trace/Relation + 可选 Viz)
    - Runtime Guardrails(quiet / fast_fail)
    - Resilience:Loader Retry(可重试恢复)
    - **对拍验证**:
      - scalim vs python(逐行逐字段)
      - seq vs adaptive(同输入输出一致)
      - run_ir vs direct engine(同输出一致)
      - loader_retry(故障注入:启用 retry 后输出应与基线一致)

    说明:本 notebook 以默认配置会自动跑一遍(用于 `marimo export`),也可通过 UI 交互调整参数.
    """)
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    import json
    import sys
    import tempfile
    import time
    from dataclasses import dataclass
    from pathlib import Path
    from typing import Any, Dict, List, Optional, Sequence, Tuple

    _this_dir = Path(__file__).parent
    if str(_this_dir) not in sys.path:
        sys.path.insert(0, str(_this_dir))

    from _guardrails_demo_loaders import (  # noqa: PLC0415
        load_guardrails_demo_main_rows,
        load_guardrails_demo_ref_table,
    )
    from _loaders import ECommerceConfig, load_orders, set_config  # noqa: PLC0415
    from _shared import (  # noqa: PLC0415
        TARGET_FIELDS_BASIC,
        TARGET_FIELDS_FULL,
        build_ecommerce_model,
        build_target_sets,
    )
    from _verification import (  # noqa: PLC0415
        PythonOracle,
        compare_csv_files,
        compare_rows_by_pk,
        export_to_csv,
        python_build_order_report,
        verify_order_by,
        verify_scalim_output,
    )

    from scalim.events.catalog import EVENT_ERROR, EVENT_LOADER_RETRY  # noqa: PLC0415
    from scalim.events.events import BatchEndEvent, LoaderCallEvent, LoaderRetryEvent  # noqa: PLC0415
    from scalim.execution.engine import ScalimEngine  # noqa: PLC0415
    from scalim.execution.guardrails import (  # noqa: PLC0415
        GuardrailViolation,
        GuardrailsLoaderPolicy,
        GuardrailsPolicy,
    )
    from scalim.execution.loader_retry import LoaderRetryPolicies, LoaderRetryPolicy  # noqa: PLC0415
    from scalim.execution.run_ir import (  # noqa: PLC0415
        ExecutionRequest,
        ExportLayout,
        ObservabilitySpec,
        OutputSpec,
        run_ir,
    )
    from scalim.hooks.base import BaseHook, HookManager  # noqa: PLC0415
    from scalim.ob.manager import ObserverManager  # noqa: PLC0415
    from scalim.ob.observer import EventDispatchObserver  # noqa: PLC0415
    from scalim.ob.presets.execution_trace import ExecutionTraceObserver  # noqa: PLC0415
    from scalim.ob.presets.memory import MemoryOptimizationObserver  # noqa: PLC0415
    from scalim.ob.presets.performance import (  # noqa: PLC0415
        PerformanceConfig,
        PerformanceObserver,
    )
    from scalim.ob.presets.relations import RelationConfig, RelationObserver  # noqa: PLC0415
    from scalim.ob.presets.viz import VizObserver, VizObserverConfig  # noqa: PLC0415
    from scalim.planning.builder import PlanBuilder  # noqa: PLC0415
    from scalim.sinks.sink_csv import ColumnCSVSink  # noqa: PLC0415
    from scalim.sinks.sink_pandas import PandasColumnSink, PandasRowSink  # noqa: PLC0415
    from scalim.sinks.sink_memory import InMemoryColumnSink, InMemoryRowSink  # noqa: PLC0415
    from scalim.spec.ir.binding import BindingIr, LoaderIr  # noqa: PLC0415
    from scalim.spec.ir.demand import DemandIr  # noqa: PLC0415
    from scalim.spec.ir.fields import DerivedFieldIr, FieldIr  # noqa: PLC0415
    from scalim.spec.ir.sources import KeyIr, MainSourceIr, SourceIr  # noqa: PLC0415
    from scalim.typedefs import SourceSpecIrCacheMode  # noqa: PLC0415

    return (
        BaseHook,
        BatchEndEvent,
        ColumnCSVSink,
        DemandIr,
        DerivedFieldIr,
        ECommerceConfig,
        EVENT_ERROR,
        EVENT_LOADER_RETRY,
        EventDispatchObserver,
        ExecutionRequest,
        ExecutionTraceObserver,
        ExportLayout,
        FieldIr,
        GuardrailViolation,
        GuardrailsLoaderPolicy,
        GuardrailsPolicy,
        HookManager,
        InMemoryColumnSink,
        InMemoryRowSink,
        KeyIr,
        List,
        LoaderCallEvent,
        LoaderRetryEvent,
        LoaderRetryPolicies,
        LoaderRetryPolicy,
        BindingIr,
        LoaderIr,
        MainSourceIr,
        MemoryOptimizationObserver,
        ObservabilitySpec,
        ObserverManager,
        OutputSpec,
        PandasColumnSink,
        PandasRowSink,
        Path,
        PerformanceConfig,
        PerformanceObserver,
        PlanBuilder,
        PythonOracle,
        RelationConfig,
        RelationObserver,
        ScalimEngine,
        SourceIr,
        TARGET_FIELDS_BASIC,
        Tuple,
        VizObserver,
        VizObserverConfig,
        SourceSpecIrCacheMode,
        build_ecommerce_model,
        build_target_sets,
        compare_csv_files,
        compare_rows_by_pk,
        dataclass,
        export_to_csv,
        load_guardrails_demo_main_rows,
        load_guardrails_demo_ref_table,
        load_orders,
        python_build_order_report,
        run_ir,
        set_config,
        tempfile,
        time,
        verify_order_by,
        verify_scalim_output,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---
    ## 1) 配置(可交互)
    """)
    return


@app.cell
def _(build_target_sets, mo):
    _target_sets = build_target_sets()

    order_count = mo.ui.slider(start=100, stop=10000, value=200, step=100, label="订单数量")
    batch_size = mo.ui.slider(start=10, stop=500, value=100, step=10, label="批次大小")
    scenario = mo.ui.dropdown(options=list(_target_sets.keys()), value="full", label="目标字段集")

    compare_pipelines = mo.ui.checkbox(label="对拍:seq vs adaptive(同输入输出一致)", value=True)
    write_csv = mo.ui.checkbox(label="写出 CSV 并与 Python 对照组对拍", value=True)
    adaptive_max_workers = mo.ui.slider(start=0, stop=32, value=0, step=1, label="adaptive max_workers(0=auto)")
    run_ir_demo = mo.ui.checkbox(label="对拍:run_ir(csv/excel 的 row/column + pandas sinks)", value=True)
    write_viz = mo.ui.checkbox(label="写出 Viz 可视化产物(jsonl/snapshot)", value=False)
    output_dir = mo.ui.text(label="产物目录(可选,留空写到 /tmp/scalim-demo-tutor)", value="")

    loader_retry_demo = mo.ui.checkbox(label="演示:Loader Retry(可重试恢复)", value=True)
    loader_retry_case = mo.ui.dropdown(
        options=[
            "load_ref",
            "main_source",
            "preload_forever",
            "load",
            "all",
        ],
        value="load_ref",
        label="故障注入场景(哪个 callsite 先失败)",
    )
    loader_retry_fail_times = mo.ui.slider(start=0, stop=3, value=1, step=1, label="每个 flaky loader 的失败次数")
    loader_retry_max_attempts = mo.ui.slider(start=1, stop=5, value=3, step=1, label="retry max_attempts")
    loader_retry_demo_run_ir = mo.ui.checkbox(label="对拍:retry demo 也跑一遍 run_ir", value=False)
    loader_retry_demo_give_up = mo.ui.checkbox(label="也演示 give-up(超过 max_attempts)", value=False)

    mo.vstack(
        [
            mo.hstack([order_count, batch_size], gap=2),
            scenario,
            mo.hstack([compare_pipelines, write_csv], gap=2),
            mo.hstack([adaptive_max_workers, run_ir_demo], gap=2),
            mo.hstack([write_viz], gap=2),
            output_dir,
            mo.hstack([loader_retry_demo, loader_retry_demo_give_up], gap=2),
            loader_retry_case,
            mo.hstack([loader_retry_fail_times, loader_retry_max_attempts], gap=2),
            loader_retry_demo_run_ir,
        ],
        gap=1,
    )
    return (
        adaptive_max_workers,
        batch_size,
        compare_pipelines,
        loader_retry_case,
        loader_retry_demo,
        loader_retry_demo_give_up,
        loader_retry_demo_run_ir,
        loader_retry_fail_times,
        loader_retry_max_attempts,
        order_count,
        output_dir,
        run_ir_demo,
        scenario,
        write_csv,
        write_viz,
    )


@app.cell
def _(
    ECommerceConfig,
    Path,
    adaptive_max_workers,
    batch_size,
    compare_pipelines,
    loader_retry_case,
    loader_retry_demo,
    loader_retry_demo_give_up,
    loader_retry_demo_run_ir,
    loader_retry_fail_times,
    loader_retry_max_attempts,
    order_count,
    output_dir,
    run_ir_demo,
    scenario,
    set_config,
    tempfile,
    write_csv,
    write_viz,
):
    ORDER_COUNT = int(order_count.value)
    BATCH_SIZE = int(batch_size.value)
    TARGET_SET_ID = str(scenario.value)
    ADAPTIVE_MAX_WORKERS = int(adaptive_max_workers.value)
    DO_CSV_COMPARE = bool(write_csv.value)
    DO_PIPELINE_COMPARE = bool(compare_pipelines.value)
    DO_RUN_IR_DEMO = bool(run_ir_demo.value)
    DO_VIZ_ARTIFACTS = bool(write_viz.value)

    DO_LOADER_RETRY_DEMO = bool(loader_retry_demo.value)
    LOADER_RETRY_CASE = str(loader_retry_case.value)
    LOADER_RETRY_FAIL_TIMES = int(loader_retry_fail_times.value)
    LOADER_RETRY_MAX_ATTEMPTS = int(loader_retry_max_attempts.value)
    DO_LOADER_RETRY_DEMO_RUN_IR = bool(loader_retry_demo_run_ir.value)
    DO_LOADER_RETRY_DEMO_GIVE_UP = bool(loader_retry_demo_give_up.value)

    out_dir = str(output_dir.value).strip()
    if out_dir:
        artifacts_dir = Path(out_dir).expanduser().resolve()
    else:
        artifacts_dir = Path(tempfile.gettempdir()) / "scalim-demo-tutor"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    cfg = ECommerceConfig(order_count=ORDER_COUNT)
    set_config(cfg)
    return (
        ADAPTIVE_MAX_WORKERS,
        BATCH_SIZE,
        DO_CSV_COMPARE,
        DO_LOADER_RETRY_DEMO,
        DO_LOADER_RETRY_DEMO_GIVE_UP,
        DO_LOADER_RETRY_DEMO_RUN_IR,
        DO_PIPELINE_COMPARE,
        DO_RUN_IR_DEMO,
        DO_VIZ_ARTIFACTS,
        LOADER_RETRY_CASE,
        LOADER_RETRY_FAIL_TIMES,
        LOADER_RETRY_MAX_ATTEMPTS,
        ORDER_COUNT,
        TARGET_SET_ID,
        artifacts_dir,
        cfg,
    )


@app.cell
def _(PythonOracle, cfg):
    _ = cfg
    oracle = PythonOracle()
    return (oracle,)


@app.cell
def _(cfg, load_orders):
    _ = cfg
    main_rows = list(load_orders())
    return (main_rows,)


@app.cell
def _(TARGET_SET_ID, build_target_sets):
    target_sets = build_target_sets()
    selected_targets = list(target_sets[TARGET_SET_ID])
    return (selected_targets,)


@app.cell(hide_code=True)
def _(
    ADAPTIVE_MAX_WORKERS,
    DO_CSV_COMPARE,
    DO_LOADER_RETRY_DEMO,
    DO_LOADER_RETRY_DEMO_GIVE_UP,
    DO_LOADER_RETRY_DEMO_RUN_IR,
    DO_PIPELINE_COMPARE,
    DO_RUN_IR_DEMO,
    DO_VIZ_ARTIFACTS,
    LOADER_RETRY_CASE,
    LOADER_RETRY_FAIL_TIMES,
    LOADER_RETRY_MAX_ATTEMPTS,
    ORDER_COUNT,
    TARGET_SET_ID,
    artifacts_dir,
    mo,
    selected_targets,
):
    mo.md(f"""
    **当前配置**

    - orders: `{ORDER_COUNT}`
    - target_set: `{TARGET_SET_ID}`(字段数 `{len(selected_targets)}`)
    - 对拍:
      - oracle(csv): `{"ON" if DO_CSV_COMPARE else "OFF"}`
      - pipeline(seq vs adaptive): `{"ON" if DO_PIPELINE_COMPARE else "OFF"}` (max_workers=`{ADAPTIVE_MAX_WORKERS}`)
      - run_ir(csv/excel row/column): `{"ON" if DO_RUN_IR_DEMO else "OFF"}`
      - loader_retry: `{"ON" if DO_LOADER_RETRY_DEMO else "OFF"}` (case=`{LOADER_RETRY_CASE}`, fail_times=`{LOADER_RETRY_FAIL_TIMES}`, max_attempts=`{LOADER_RETRY_MAX_ATTEMPTS}`, run_ir=`{DO_LOADER_RETRY_DEMO_RUN_IR}`, give_up=`{DO_LOADER_RETRY_DEMO_GIVE_UP}`)
    - viz artifacts: `{"ON" if DO_VIZ_ARTIFACTS else "OFF"}`
    - artifacts_dir: `{artifacts_dir}`
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---
    ## 2) Build: Demand → Plan
    """)
    return


@app.cell
def _(PlanBuilder, build_ecommerce_model, selected_targets):
    demand = build_ecommerce_model()
    plan = PlanBuilder(demand).build(targets=selected_targets)
    meta = plan.metadata
    return demand, meta, plan


@app.cell(hide_code=True)
def _(meta, mo):
    mo.md(f"""
    **Plan metadata**

    - total_fields: `{meta.total_fields}`
    - total_sources: `{meta.total_sources}`
    - total_loaders: `{meta.total_loaders}`
    - pruned_fields: `{meta.pruned_fields}`
    - max_depth: `{meta.max_depth}`
    """)
    return


@app.cell
def _(plan):
    plan_snapshot = plan.to_viz_graph_snapshot()
    return (plan_snapshot,)


@app.cell
def _(plan_snapshot):
    edges = plan_snapshot.get("edges", [])
    nodes = plan_snapshot.get("nodes", [])
    return edges, nodes


@app.cell(hide_code=True)
def _(edges, mo, nodes):
    mo.md(f"""
    Plan snapshot: nodes=`{len(nodes)}` edges=`{len(edges)}`(用于可视化/诊断)
    """)
    return


@app.cell
def _(mo, nodes):
    mo.ui.table(nodes[:10])
    return


@app.cell
def _(BaseHook, BatchEndEvent, List, LoaderCallEvent, Tuple, dataclass):
    @dataclass(frozen=True)
    class TutorStats:
        batch_durations: List[float]
        loader_calls: List[Tuple[str, float]]

    class TutorHook(BaseHook):
        def __init__(self) -> None:
            self._batch_durations: List[float] = []
            self._loader_calls: List[Tuple[str, float]] = []

        def on_batch_end(self, event: BatchEndEvent) -> None:
            self._batch_durations.append(float(event.duration))

        def on_loader_call(self, event: LoaderCallEvent) -> None:
            self._loader_calls.append((event.loader_name, float(event.duration)))

        def snapshot(self) -> TutorStats:
            return TutorStats(batch_durations=list(self._batch_durations), loader_calls=list(self._loader_calls))

    return (TutorHook,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---
    ## 3) Run: Engine + Sink + Observability + 对拍
    """)
    return


@app.cell
def _(
    BATCH_SIZE,
    DO_VIZ_ARTIFACTS,
    ExecutionTraceObserver,
    HookManager,
    InMemoryColumnSink,
    MemoryOptimizationObserver,
    ObserverManager,
    PerformanceConfig,
    PerformanceObserver,
    RelationConfig,
    RelationObserver,
    ScalimEngine,
    TutorHook,
    VizObserver,
    VizObserverConfig,
    artifacts_dir,
    demand,
    main_rows,
    plan,
    selected_targets,
    time,
):
    hook_manager = HookManager()
    tutor_hook = TutorHook()
    hook_manager.register(tutor_hook)

    perf_observer = PerformanceObserver(PerformanceConfig(metrics={"duration"}, report_format="none"))
    mem_observer = MemoryOptimizationObserver(auto_report=False)
    trace_observer = ExecutionTraceObserver()
    rel_observer = RelationObserver(RelationConfig(report_format="none"))

    observers = [perf_observer, mem_observer, trace_observer, rel_observer]
    viz_observer = None
    if DO_VIZ_ARTIFACTS:
        viz_config = VizObserverConfig(
            output_dir=str(artifacts_dir),
            run_name="demo_tutor",
            env="local",
            event_mode="lite",
            payload_policy="summary",
            sample_size=5,
        )
        viz_observer = VizObserver.from_plan(plan, config=viz_config)
        observers.append(viz_observer)

    observer_manager = ObserverManager(observers=observers)

    engine = ScalimEngine(
        demand=demand,
        plan=plan,
        hook_manager=hook_manager,
        observer_manager=observer_manager,
        batch_size=BATCH_SIZE,
    )

    start = time.time()
    with InMemoryColumnSink(field_names=selected_targets) as sink:
        engine.run(main_rows=main_rows, sink=sink)
        results_col = sink.get_rows()
    elapsed = time.time() - start

    tutor_stats = tutor_hook.snapshot()
    perf_metrics = perf_observer.get_metrics()
    rel_metrics = rel_observer.get_metrics()
    return elapsed, perf_metrics, results_col, tutor_stats


@app.cell
def _(oracle, results_col, selected_targets, verify_scalim_output):
    verification = verify_scalim_output(results_col, fields_to_check=list(selected_targets), max_mismatches=20, oracle=oracle)
    if not verification.passed:
        raise AssertionError(
            "Oracle verification failed:\n{}\n\n{}".format(
                verification.summary,
                verification.get_mismatch_summary(),
            )
        )
    return (verification,)


@app.cell
def _(results_col, verify_order_by):
    order_check = verify_order_by(results_col, ["order_id"])
    if not order_check.passed:
        raise AssertionError(order_check.message)
    return (order_check,)


@app.cell(hide_code=True)
def _(
    elapsed,
    mo,
    order_check,
    perf_metrics,
    results_col,
    tutor_stats,
    verification,
):
    throughput = (len(results_col) / elapsed) if elapsed else 0.0
    mo.md(
        f"""
        **运行结果**

        - rows: `{len(results_col)}`
        - elapsed: `{elapsed:.4f}s`
        - throughput: `{throughput:.0f} rows/s`
        - order_by(order_id): `{"PASSED" if order_check.passed else "FAILED"}`
        - oracle verification: `{"PASSED" if verification.passed else "FAILED"}`(checked_rows=`{verification.checked_rows}`)
        - hook: batches=`{len(tutor_stats.batch_durations)}` loader_calls=`{len(tutor_stats.loader_calls)}`
        - perf: total_duration=`{perf_metrics.total_duration:.4f}s` avg_batch_duration=`{perf_metrics.avg_batch_duration:.4f}s`
        """
    )
    return


@app.cell
def _(mo, results_col, selected_targets):
    preview_fields = list(selected_targets)[:12]
    mo.ui.table([{k: row.get(k) for k in preview_fields} for row in results_col[:10]])
    return


@app.cell
def _(results_col):
    total = len(results_col)
    promotion_hits = sum(1 for row in results_col if row.get("promotion_name") is not None)
    promotion_hit_rate = (promotion_hits / total) if total else 0.0
    return promotion_hit_rate, promotion_hits, total


@app.cell(hide_code=True)
def _(mo, promotion_hit_rate, promotion_hits, total):
    mo.md(f"""
    **数据质量(示例)** promotion_name hit-rate: `{promotion_hits}/{total}` = `{100 * promotion_hit_rate:.1f}%`
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---
    ## 4) 执行策略对比:seq vs adaptive(对拍 + 性能)
    """)
    return


@app.cell
def _(
    ADAPTIVE_MAX_WORKERS,
    BATCH_SIZE,
    DO_PIPELINE_COMPARE,
    InMemoryColumnSink,
    ScalimEngine,
    compare_rows_by_pk,
    demand,
    main_rows,
    oracle,
    plan,
    selected_targets,
    time,
    verify_scalim_output,
):
    pipeline_seq_rows: list[dict] = []
    pipeline_adaptive_rows: list[dict] = []
    pipeline_compare = {"status": "disabled", "seq_s": 0.0, "adaptive_s": 0.0, "speedup": 0.0, "matched": True}

    if DO_PIPELINE_COMPARE:

        def _run(parallel_mode: str) -> tuple[list[dict], float]:
            engine = ScalimEngine(
                demand=demand,
                plan=plan,
                batch_size=BATCH_SIZE,
                parallel_mode=parallel_mode,
                max_workers=ADAPTIVE_MAX_WORKERS,
            )
            start = time.perf_counter()
            with InMemoryColumnSink(field_names=list(selected_targets)) as sink:
                engine.run(main_rows=main_rows, sink=sink)
                rows = sink.get_rows()
            return rows, time.perf_counter() - start

        pipeline_seq_rows, seq_s = _run("seq")
        pipeline_adaptive_rows, adaptive_s = _run("adaptive")

        seq_ver = verify_scalim_output(pipeline_seq_rows, fields_to_check=list(selected_targets), max_mismatches=20, oracle=oracle)
        if not seq_ver.passed:
            raise AssertionError("seq 执行策略对拍失败(oracle):\n{}\n\n{}".format(seq_ver.summary, seq_ver.get_mismatch_summary()))

        adaptive_ver = verify_scalim_output(
            pipeline_adaptive_rows,
            fields_to_check=list(selected_targets),
            max_mismatches=20,
            oracle=oracle,
        )
        if not adaptive_ver.passed:
            raise AssertionError(
                "adaptive 执行策略对拍失败(oracle):\n{}\n\n{}".format(adaptive_ver.summary, adaptive_ver.get_mismatch_summary())
            )

        pipeline_matched, pipeline_diff = compare_rows_by_pk(
            pipeline_seq_rows,
            pipeline_adaptive_rows,
            fields=list(selected_targets),
        )
        if not pipeline_matched:
            raise AssertionError("执行策略对比失败(seq vs adaptive):\n{}".format(pipeline_diff))

        speedup = (seq_s / adaptive_s) if adaptive_s else 0.0
        pipeline_compare = {
            "status": "matched",
            "seq_s": float(seq_s),
            "adaptive_s": float(adaptive_s),
            "speedup": float(speedup),
            "matched": True,
        }
    return (pipeline_compare,)


@app.cell(hide_code=True)
def _(ADAPTIVE_MAX_WORKERS, DO_PIPELINE_COMPARE, mo, pipeline_compare):
    if not DO_PIPELINE_COMPARE:
        pipeline_md_text = "执行策略对拍已关闭(可在配置中启用)."
    else:
        pipeline_md_text = "\n".join(
            [
                "- seq: `{:.4f}s`".format(pipeline_compare["seq_s"]),
                "- adaptive(max_workers={}): `{:.4f}s`".format(ADAPTIVE_MAX_WORKERS, pipeline_compare["adaptive_s"]),
                "- 加速比: `{:.2f}x`".format(pipeline_compare["speedup"]),
                "- 输出一致: `{}`".format(pipeline_compare["matched"]),
            ]
        )
    mo.md(pipeline_md_text)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---
    ## 5) Sink 对比:Row sink(基础字段集)
    """)
    return


@app.cell
def _(
    BATCH_SIZE,
    InMemoryRowSink,
    PlanBuilder,
    ScalimEngine,
    TARGET_FIELDS_BASIC,
    demand,
    main_rows,
    oracle,
    verify_scalim_output,
):
    basic_targets = list(TARGET_FIELDS_BASIC)
    basic_plan = PlanBuilder(demand).build(targets=basic_targets)
    engine_basic = ScalimEngine(demand=demand, plan=basic_plan, batch_size=BATCH_SIZE)

    with InMemoryRowSink() as sink_row:
        engine_basic.run(main_rows=main_rows, sink=sink_row)
        results_row = sink_row.get_data()

    basic_verification = verify_scalim_output(results_row, fields_to_check=basic_targets, max_mismatches=20, oracle=oracle)
    if not basic_verification.passed:
        raise AssertionError(
            "Row-sink oracle verification failed:\n{}\n\n{}".format(
                basic_verification.summary,
                basic_verification.get_mismatch_summary(),
            )
        )
    return basic_targets, basic_verification


@app.cell(hide_code=True)
def _(basic_targets, basic_verification, mo):
    mo.md(f"""
    - targets: `{len(basic_targets)}`
    - verification: `{"PASSED" if basic_verification.passed else "FAILED"}`(checked_rows=`{basic_verification.checked_rows}`)
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---
    ## 6) CSV 文件对拍(scalim vs python)
    """)
    return


@app.cell
def _(
    BATCH_SIZE,
    ColumnCSVSink,
    DO_CSV_COMPARE,
    ScalimEngine,
    artifacts_dir,
    compare_csv_files,
    demand,
    export_to_csv,
    main_rows,
    oracle,
    plan,
    python_build_order_report,
    selected_targets,
):
    scalim_csv = None
    python_csv = None
    csv_compare = {"status": "disabled", "details": ""}

    if DO_CSV_COMPARE:
        scalim_csv = artifacts_dir / "demo_tutor_scalim.csv"
        python_csv = artifacts_dir / "demo_tutor_python.csv"

        engine_csv = ScalimEngine(demand=demand, plan=plan, batch_size=BATCH_SIZE)
        with ColumnCSVSink(str(scalim_csv), list(selected_targets)) as sink_csv:
            engine_csv.run(main_rows=main_rows, sink=sink_csv)

        expected = python_build_order_report(list(selected_targets), oracle=oracle)
        export_to_csv(expected, str(python_csv), list(selected_targets))

        csv_matched, csv_diff = compare_csv_files(str(scalim_csv), str(python_csv))
        if not csv_matched:
            raise AssertionError("CSV oracle comparison failed:\n{}".format(csv_diff))
        csv_compare = {"status": "matched", "details": ""}
    return python_csv, scalim_csv


@app.cell(hide_code=True)
def _(DO_CSV_COMPARE, mo):
    csv_note_text = "CSV 对拍已启用:将写出两份 CSV 并进行逐行比对." if DO_CSV_COMPARE else "CSV 对拍已关闭(避免写文件).如需启用请勾选."
    csv_note = mo.md(csv_note_text)
    csv_note
    return


@app.cell(hide_code=True)
def _(DO_CSV_COMPARE, mo, python_csv, scalim_csv):
    csv_paths = mo.md(f"CSV 输出路径:`{scalim_csv}` / `{python_csv}`") if DO_CSV_COMPARE else None
    csv_paths
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---
    ## 7) 编排:run_ir(csv/excel 的 row/column + pandas sinks)
    """)
    return


@app.cell
def _(
    ADAPTIVE_MAX_WORKERS,
    BATCH_SIZE,
    DO_RUN_IR_DEMO,
    DO_VIZ_ARTIFACTS,
    ExecutionRequest,
    ExportLayout,
    ObservabilitySpec,
    OutputSpec,
    PandasColumnSink,
    PandasRowSink,
    VizObserverConfig,
    artifacts_dir,
    compare_rows_by_pk,
    demand,
    oracle,
    results_col,
    run_ir,
    selected_targets,
    verify_scalim_output,
):
    run_ir_excel_row = None
    run_ir_excel_row_rows: list[dict] = []
    run_ir_excel_row_result = {"status": "disabled", "path": None, "rows": 0, "duration_s": 0.0, "output_path": None}

    run_ir_csv_row = None
    run_ir_csv_row_rows: list[dict] = []
    run_ir_csv_row_result = {"status": "disabled", "path": None, "rows": 0, "duration_s": 0.0, "output_path": None}

    run_ir_excel_col = None
    run_ir_excel_col_rows: list[dict] = []
    run_ir_excel_col_result = {"status": "disabled", "path": None, "rows": 0, "duration_s": 0.0, "output_path": None}

    if DO_RUN_IR_DEMO:

        def _maybe_viz(run_name: str) -> ObservabilitySpec | None:
            if not DO_VIZ_ARTIFACTS:
                return None
            return ObservabilitySpec(
                viz_config=VizObserverConfig(
                    output_dir=str(artifacts_dir),
                    run_name=run_name,
                    env="local",
                    event_mode="lite",
                    payload_policy="summary",
                    sample_size=5,
                )
            )

        # 1) `Excel`(行式 `sink`) + `PandasRowSink`
        run_ir_excel_row = artifacts_dir / "demo_tutor_run_ir.xlsx"
        excel_row_sink = PandasRowSink(field_names=list(selected_targets))
        excel_row_request = ExecutionRequest(
            export_layout=ExportLayout(field_ids=tuple(selected_targets), header_names=None),
            output=OutputSpec(format="excel", path=str(run_ir_excel_row), streaming=True),
            sink=excel_row_sink,
            observability=_maybe_viz("demo_tutor_run_ir_excel_row"),
            batch_size=BATCH_SIZE,
            parallel_mode="adaptive",
            max_workers=ADAPTIVE_MAX_WORKERS,
        )
        excel_row_exec = run_ir(demand, excel_row_request)

        run_ir_excel_row_rows = excel_row_sink.get_rows()
        excel_row_ver = verify_scalim_output(
            run_ir_excel_row_rows, fields_to_check=list(selected_targets), max_mismatches=20, oracle=oracle
        )
        if not excel_row_ver.passed:
            raise AssertionError(
                "run_ir(excel row) 对拍失败(oracle):\n{}\n\n{}".format(excel_row_ver.summary, excel_row_ver.get_mismatch_summary())
            )

        excel_row_matched, excel_row_diff = compare_rows_by_pk(results_col, run_ir_excel_row_rows, fields=list(selected_targets))
        if not excel_row_matched:
            raise AssertionError("run_ir(excel row) vs direct engine 不一致:\n{}".format(excel_row_diff))

        if not run_ir_excel_row.exists():
            raise AssertionError("run_ir 未写出 excel(row) 产物:{}".format(run_ir_excel_row))

        run_ir_excel_row_result = {
            "status": "matched",
            "path": str(run_ir_excel_row),
            "rows": len(run_ir_excel_row_rows),
            "duration_s": float(excel_row_exec.duration),
            "output_path": excel_row_exec.output_path,
        }

        # 2) `CSV`(行式 `sink`) + `PandasRowSink`
        run_ir_csv_row = artifacts_dir / "demo_tutor_run_ir.csv"
        csv_row_sink = PandasRowSink(field_names=list(selected_targets))
        csv_row_request = ExecutionRequest(
            export_layout=ExportLayout(field_ids=tuple(selected_targets), header_names=None),
            output=OutputSpec(format="csv", path=str(run_ir_csv_row), streaming=True),
            sink=csv_row_sink,
            observability=_maybe_viz("demo_tutor_run_ir_csv_row"),
            batch_size=BATCH_SIZE,
            parallel_mode="adaptive",
            max_workers=ADAPTIVE_MAX_WORKERS,
        )
        csv_row_exec = run_ir(demand, csv_row_request)

        run_ir_csv_row_rows = csv_row_sink.get_rows()
        csv_row_ver = verify_scalim_output(run_ir_csv_row_rows, fields_to_check=list(selected_targets), max_mismatches=20, oracle=oracle)
        if not csv_row_ver.passed:
            raise AssertionError(
                "run_ir(csv row) 对拍失败(oracle):\n{}\n\n{}".format(csv_row_ver.summary, csv_row_ver.get_mismatch_summary())
            )

        csv_row_matched, csv_row_diff = compare_rows_by_pk(results_col, run_ir_csv_row_rows, fields=list(selected_targets))
        if not csv_row_matched:
            raise AssertionError("run_ir(csv row) vs direct engine 不一致:\n{}".format(csv_row_diff))

        if not run_ir_csv_row.exists():
            raise AssertionError("run_ir 未写出 csv(row) 产物:{}".format(run_ir_csv_row))

        run_ir_csv_row_result = {
            "status": "matched",
            "path": str(run_ir_csv_row),
            "rows": len(run_ir_csv_row_rows),
            "duration_s": float(csv_row_exec.duration),
            "output_path": csv_row_exec.output_path,
        }

        # 3) `Excel`(列式 `sink`) + `PandasColumnSink`
        run_ir_excel_col = artifacts_dir / "demo_tutor_run_ir_column.xlsx"
        excel_col_sink = PandasColumnSink(field_names=list(selected_targets))
        excel_col_request = ExecutionRequest(
            export_layout=ExportLayout(field_ids=tuple(selected_targets), header_names=None),
            output=OutputSpec(format="excel", path=str(run_ir_excel_col), streaming=False),
            sink=excel_col_sink,
            observability=_maybe_viz("demo_tutor_run_ir_excel_col"),
            batch_size=BATCH_SIZE,
            parallel_mode="adaptive",
            max_workers=ADAPTIVE_MAX_WORKERS,
        )
        excel_col_exec = run_ir(demand, excel_col_request)

        excel_col_columns = excel_col_sink.get_columns()
        excel_col_row_ids = excel_col_sink.get_row_ids()
        run_ir_excel_col_rows = []
        for pk in excel_col_row_ids:
            row: dict = {}
            for field_key, values in excel_col_columns.items():
                if pk in values:
                    row[field_key] = values[pk]
            run_ir_excel_col_rows.append(row)

        excel_col_ver = verify_scalim_output(
            run_ir_excel_col_rows, fields_to_check=list(selected_targets), max_mismatches=20, oracle=oracle
        )
        if not excel_col_ver.passed:
            raise AssertionError(
                "run_ir(excel column) 对拍失败(oracle):\n{}\n\n{}".format(excel_col_ver.summary, excel_col_ver.get_mismatch_summary())
            )

        excel_col_matched, excel_col_diff = compare_rows_by_pk(results_col, run_ir_excel_col_rows, fields=list(selected_targets))
        if not excel_col_matched:
            raise AssertionError("run_ir(excel column) vs direct engine 不一致:\n{}".format(excel_col_diff))

        if not run_ir_excel_col.exists():
            raise AssertionError("run_ir 未写出 excel(column) 产物:{}".format(run_ir_excel_col))

        run_ir_excel_col_result = {
            "status": "matched",
            "path": str(run_ir_excel_col),
            "rows": len(run_ir_excel_col_rows),
            "duration_s": float(excel_col_exec.duration),
            "output_path": excel_col_exec.output_path,
        }
    return (
        run_ir_csv_row_result,
        run_ir_csv_row_rows,
        run_ir_excel_col_result,
        run_ir_excel_col_rows,
        run_ir_excel_row_result,
        run_ir_excel_row_rows,
    )


@app.cell(hide_code=True)
def _(
    DO_RUN_IR_DEMO,
    mo,
    run_ir_csv_row_result,
    run_ir_excel_col_result,
    run_ir_excel_row_result,
):
    if not DO_RUN_IR_DEMO:
        run_ir_md_text = "run_ir 对拍已关闭(可在配置中启用)."
    else:
        run_ir_md_text = "\n".join(
            [
                "**run_ir 产物(均已对拍:oracle + vs direct engine)**",
                "",
                "- CSV(row, streaming=True): `{}` rows=`{}` elapsed=`{:.4f}s` status=`{}`".format(
                    run_ir_csv_row_result["path"],
                    run_ir_csv_row_result["rows"],
                    run_ir_csv_row_result["duration_s"],
                    run_ir_csv_row_result["status"],
                ),
                "- Excel(row, streaming=True): `{}` rows=`{}` elapsed=`{:.4f}s` status=`{}`".format(
                    run_ir_excel_row_result["path"],
                    run_ir_excel_row_result["rows"],
                    run_ir_excel_row_result["duration_s"],
                    run_ir_excel_row_result["status"],
                ),
                "- Excel(column, streaming=False): `{}` rows=`{}` elapsed=`{:.4f}s` status=`{}`".format(
                    run_ir_excel_col_result["path"],
                    run_ir_excel_col_result["rows"],
                    run_ir_excel_col_result["duration_s"],
                    run_ir_excel_col_result["status"],
                ),
            ]
        )
    mo.md(run_ir_md_text)
    return


@app.cell
def _(
    DO_RUN_IR_DEMO,
    mo,
    run_ir_csv_row_rows: list[dict],
    run_ir_excel_col_rows: list[dict],
    run_ir_excel_row_rows: list[dict],
    selected_targets,
):
    run_ir_tables = None
    if DO_RUN_IR_DEMO:
        run_ir_preview_fields = list(selected_targets)[:10]
        run_ir_tables = mo.ui.tabs(
            {
                "CSV(row)": mo.ui.table([{k: row.get(k) for k in run_ir_preview_fields} for row in run_ir_csv_row_rows[:10]]),
                "Excel(row)": mo.ui.table([{k: row.get(k) for k in run_ir_preview_fields} for row in run_ir_excel_row_rows[:10]]),
                "Excel(column)": mo.ui.table([{k: row.get(k) for k in run_ir_preview_fields} for row in run_ir_excel_col_rows[:10]]),
            }
        )
    run_ir_tables
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---
    ## 8) Runtime Guardrails(quiet / fast_fail)
    """)
    return


@app.cell
def _(
    DemandIr,
    DerivedFieldIr,
    EVENT_ERROR,
    EventDispatchObserver,
    FieldIr,
    GuardrailViolation,
    GuardrailsLoaderPolicy,
    GuardrailsPolicy,
    KeyIr,
    List,
    LoaderIr,
    MainSourceIr,
    ObserverManager,
    PlanBuilder,
    ScalimEngine,
    SourceIr,
    load_guardrails_demo_main_rows,
    load_guardrails_demo_ref_table,
):
    class _ErrorCollector(EventDispatchObserver):
        event_types = {EVENT_ERROR}

        def __init__(self) -> None:
            self.errors: List[object] = []

        def on_error(self, payload: object) -> None:
            self.errors.append(payload)

    main_source = MainSourceIr(source_id="main", loader=load_guardrails_demo_main_rows)
    ref_source = SourceIr(source_id="ref", key=KeyIr("id"), loader_spec=LoaderIr(callable=load_guardrails_demo_ref_table))
    rel_to_ref = main_source["ref_id"].join(ref_source["id"])

    fields = [
        FieldIr(field_id="ref_id", name="ref_id", source=main_source),
        FieldIr(field_id="a", name="a", source=main_source, transform=int),
        FieldIr(field_id="b", name="b", source=main_source),
        DerivedFieldIr(field_id="ratio", name="ratio", dependencies=("a", "b"), calculator=lambda a, b: a / b),
        FieldIr(field_id="ref_value", name="ref_value", source=ref_source, data_key="value", relation=rel_to_ref),
    ]
    guardrails_demand = DemandIr.from_irs(
        sources=[ref_source],
        fields=fields,
        main_source=main_source,
        name="runtime_guardrails_demo",
        batch_size_hint=50,
    )

    targets = ["ref_id", "a", "b", "ratio", "ref_value"]
    guardrails_plan = PlanBuilder(guardrails_demand).build(targets=targets)

    errors = _ErrorCollector()
    guardrails_quiet = GuardrailsPolicy(
        enabled=True,
        mode="quiet",
        loader=GuardrailsLoaderPolicy(required_fields=("b",)),
    )
    engine_quiet = ScalimEngine(
        demand=guardrails_demand,
        plan=guardrails_plan,
        observer_manager=ObserverManager(observers=[errors]),
        batch_size=50,
        guardrails=guardrails_quiet,
    )
    quiet_rows = list(engine_quiet.run())

    expected_rows = [
        {"ref_id": 1, "a": 1, "b": 2, "ratio": 0.5, "ref_value": "U1"},
        {"ref_id": 2, "a": 2, "b": 4, "ratio": 0.5, "ref_value": "P2"},
        {"ref_id": 3, "a": 3, "b": 0, "ratio": None, "ref_value": "S3"},
        {"ref_id": 4, "a": 4, "b": 8, "ratio": 0.5, "ref_value": "D4"},
        {"ref_id": 5, "a": 5, "b": 10, "ratio": 0.5, "ref_value": "G5"},
        {"ref_id": 999, "a": 6, "b": 12, "ratio": 0.5, "ref_value": None},
        {"ref_id": 1, "a": None, "b": 14, "ratio": None, "ref_value": "U1"},
        {"ref_id": 2, "a": 7, "b": None, "ratio": None, "ref_value": "P2"},
    ]
    if quiet_rows != expected_rows:
        raise AssertionError("Guardrails quiet rows mismatch.\nactual={!r}\nexpected={!r}".format(quiet_rows, expected_rows))

    guardrail_errors = [e for e in errors.errors if getattr(e, "context", {}).get("guardrail")]
    codes = sorted({e.context.get("guardrail_code") for e in guardrail_errors})
    for expected_code in ("loader_transform_error", "compute_error", "loader_required_field_missing"):
        if expected_code not in codes:
            raise AssertionError("Expected guardrail code missing: {}. got={}".format(expected_code, codes))

    guardrails_fast_fail = GuardrailsPolicy(
        enabled=True,
        mode="fast_fail",
        loader=GuardrailsLoaderPolicy(required_fields=("b",)),
    )
    engine_fast = ScalimEngine(demand=guardrails_demand, plan=guardrails_plan, batch_size=50, guardrails=guardrails_fast_fail)
    try:
        _ = engine_fast.run()
        fast_fail_code = None
    except GuardrailViolation as exc:
        fast_fail_code = exc.code
    if fast_fail_code != "loader_transform_error":
        raise AssertionError("Expected fast_fail code loader_transform_error, got {!r}".format(fast_fail_code))
    return codes, fast_fail_code, quiet_rows


@app.cell(hide_code=True)
def _(codes, fast_fail_code, mo, quiet_rows):
    mo.md(f"""
    **quiet 模式**

    - 输出行数:`{len(quiet_rows)}`
    - 记录到的 guardrail codes:`{", ".join(codes) if codes else "(none)"}`

    **fast_fail 模式**

    - raise code:`{fast_fail_code}`
    """)
    return


@app.cell
def _(mo, quiet_rows):
    mo.ui.table(quiet_rows)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---
    ## 9) Resilience:Loader Retry(可重试恢复)

    目标:演示当 loader 出现**瞬时失败**(如网络抖动、临时超时)时:

    - 未启用 retry:执行会直接失败(可能在 preload / main_source / load / load_ref 的任意阶段)
    - 启用 retry:在策略允许的范围内自动重试并恢复,最终输出与无故障基线一致

    说明:
    - Loader Retry 默认关闭,需要显式传入 `LoaderRetryPolicies` 才会启用.
    - `loader_retry` 事件是 wants-gated:只有订阅了 `EVENT_LOADER_RETRY` 才会发出(避免热路径额外开销).
    """)
    return


@app.cell
def _(BindingIr, DemandIr, FieldIr, KeyIr, LoaderIr, MainSourceIr, SourceIr, SourceSpecIrCacheMode):
    class TransientLoaderError(RuntimeError):
        pass

    def make_flaky_loader(*, name: str, fn, fail_times: int):  # type: ignore[no-untyped-def]
        state = {"calls": 0}

        def _wrapped(*args, **kwargs):  # type: ignore[no-untyped-def]
            state["calls"] += 1
            if state["calls"] <= int(fail_times):
                raise TransientLoaderError("[{}] transient failure #{}".format(name, state["calls"]))
            return fn(*args, **kwargs)

        return _wrapped, state

    RETRY_DEMO_MAIN_ROWS = [
        {"order_id": 1, "customer_id": 101, "promotion_id": 201},
        {"order_id": 2, "customer_id": 102, "promotion_id": 202},
        {"order_id": 3, "customer_id": 101, "promotion_id": 201},
        {"order_id": 4, "customer_id": 103, "promotion_id": 201},
        {"order_id": 5, "customer_id": 102, "promotion_id": 202},
    ]
    RETRY_DEMO_CUSTOMERS = {
        101: {"customer_name": "Alice"},
        102: {"customer_name": "Bob"},
        103: {"customer_name": "Carol"},
    }
    RETRY_DEMO_PROMOTIONS = {
        201: {"promotion_name": "P1"},
        202: {"promotion_name": "P2"},
    }
    RETRY_DEMO_TARGETS = ["order_id", "customer_name", "promotion_name", "is_even_row"]

    def build_retry_demo_demand(*, main_loader, customers_loader, promotions_loader, flags_loader):  # type: ignore[no-untyped-def]
        main_source = MainSourceIr(source_id="orders", loader=main_loader)

        customers_source = SourceIr(
            source_id="customers",
            key=KeyIr("customer_id"),
            loader_spec=LoaderIr(
                callable=customers_loader,
                bindings={
                    "customer_id": BindingIr(
                        key_field="customer_id",
                        params_builder=lambda ctx: ((), {"customer_ids": ctx.lookup_keys_list}),
                        as_="list",
                        param_name="customer_ids",
                    ),
                },
            ),
        )

        promotions_source = SourceIr(
            source_id="promotions",
            key=KeyIr("promotion_id"),
            loader_spec=LoaderIr(callable=promotions_loader),
            cache_mode=SourceSpecIrCacheMode.PRELOAD_FOREVER,
        )

        flags_source = SourceIr(
            source_id="order_flags",
            key=KeyIr("row_nth"),
            loader_spec=LoaderIr(
                callable=flags_loader,
                bindings={
                    "row_nth": BindingIr(
                        key_field="row_nth",
                        params_builder=lambda ctx: ((), {"row_nth": list(ctx.batch_row_nth)}),
                        param_name="row_nth",
                    ),
                },
            ),
        )

        rel_customer = main_source["customer_id"].join(customers_source["customer_id"])
        rel_promo = main_source["promotion_id"].join(promotions_source["promotion_id"])

        fields = [
            FieldIr(field_id="order_id", name="order_id", source=main_source),
            FieldIr(field_id="customer_id", name="customer_id", source=main_source),
            FieldIr(field_id="promotion_id", name="promotion_id", source=main_source),
            FieldIr(
                field_id="customer_name",
                name="customer_name",
                source=customers_source,
                data_key="customer_name",
                relation=rel_customer,
            ),
            FieldIr(
                field_id="promotion_name",
                name="promotion_name",
                source=promotions_source,
                data_key="promotion_name",
                relation=rel_promo,
            ),
            FieldIr(field_id="is_even_row", name="is_even_row", source=flags_source, data_key="is_even_row"),
        ]

        demand = DemandIr.from_irs(
            sources=[customers_source, promotions_source, flags_source],
            fields=fields,
            main_source=main_source,
            name="loader_retry_demo",
            batch_size_hint=3,
        )
        return demand

    def build_retry_demo_expected_rows():  # type: ignore[no-untyped-def]
        rows = []
        for row_nth, row in enumerate(RETRY_DEMO_MAIN_ROWS):
            customer = RETRY_DEMO_CUSTOMERS.get(row["customer_id"])
            promo = RETRY_DEMO_PROMOTIONS.get(row["promotion_id"])
            rows.append(
                {
                    "order_id": row["order_id"],
                    "customer_name": None if customer is None else customer.get("customer_name"),
                    "promotion_name": None if promo is None else promo.get("promotion_name"),
                    "is_even_row": bool(row_nth % 2 == 0),
                }
            )
        return rows

    return (
        RETRY_DEMO_CUSTOMERS,
        RETRY_DEMO_MAIN_ROWS,
        RETRY_DEMO_PROMOTIONS,
        RETRY_DEMO_TARGETS,
        TransientLoaderError,
        build_retry_demo_demand,
        build_retry_demo_expected_rows,
        make_flaky_loader,
    )


@app.cell
def _(EVENT_ERROR, EVENT_LOADER_RETRY, EventDispatchObserver, LoaderRetryEvent, TransientLoaderError):
    class RetryDemoCollector(EventDispatchObserver):
        event_types = {EVENT_LOADER_RETRY, EVENT_ERROR}

        def __init__(self) -> None:
            self.retries: list[LoaderRetryEvent] = []
            self.errors: list[object] = []

        def on_loader_retry(self, payload: LoaderRetryEvent) -> None:
            self.retries.append(payload)

        def on_error(self, payload: object) -> None:
            self.errors.append(payload)

    def retry_demo_should_retry(exc: Exception, _ctx) -> bool:  # type: ignore[no-untyped-def]
        return isinstance(exc, TransientLoaderError)

    return RetryDemoCollector, retry_demo_should_retry


@app.cell
def _(
    DO_LOADER_RETRY_DEMO,
    DO_LOADER_RETRY_DEMO_GIVE_UP,
    DO_LOADER_RETRY_DEMO_RUN_IR,
    InMemoryRowSink,
    LOADER_RETRY_CASE,
    LOADER_RETRY_FAIL_TIMES,
    LOADER_RETRY_MAX_ATTEMPTS,
    LoaderRetryPolicies,
    LoaderRetryPolicy,
    ObserverManager,
    PlanBuilder,
    RETRY_DEMO_CUSTOMERS,
    RETRY_DEMO_MAIN_ROWS,
    RETRY_DEMO_PROMOTIONS,
    RETRY_DEMO_TARGETS,
    RetryDemoCollector,
    ScalimEngine,
    build_retry_demo_demand,
    build_retry_demo_expected_rows,
    compare_rows_by_pk,
    make_flaky_loader,
    retry_demo_should_retry,
    run_ir,
    ExecutionRequest,
    ExportLayout,
    OutputSpec,
):
    retry_demo = {
        "status": "disabled",
        "case": LOADER_RETRY_CASE,
        "fail_times": int(LOADER_RETRY_FAIL_TIMES),
        "max_attempts": int(LOADER_RETRY_MAX_ATTEMPTS),
        "baseline_rows": 0,
        "retry_rows": 0,
        "retry_error": None,
        "error_events": 0,
        "no_retry_failed": False,
        "no_retry_error": None,
        "retry_events": [],
        "give_up": {"enabled": False, "failed": False, "error": None, "error_events": 0, "retry_events": 0},
        "run_ir": {"enabled": False, "failed": False, "error": None, "rows": 0, "retry_events": 0, "error_events": 0},
    }

    if DO_LOADER_RETRY_DEMO:
        demo_targets = list(RETRY_DEMO_TARGETS)

        def _stable_main_loader():  # type: ignore[no-untyped-def]
            return list(RETRY_DEMO_MAIN_ROWS)

        def _stable_promotions_loader():  # type: ignore[no-untyped-def]
            return dict(RETRY_DEMO_PROMOTIONS)

        def _stable_customers_loader(*, customer_ids):  # type: ignore[no-untyped-def]
            if not customer_ids:
                return dict(RETRY_DEMO_CUSTOMERS)
            return {cid: RETRY_DEMO_CUSTOMERS[cid] for cid in customer_ids if cid in RETRY_DEMO_CUSTOMERS}

        def _stable_flags_loader(*, row_nth):  # type: ignore[no-untyped-def]
            return {int(n): {"is_even_row": bool(int(n) % 2 == 0)} for n in row_nth}

        baseline_demand = build_retry_demo_demand(
            main_loader=_stable_main_loader,
            customers_loader=_stable_customers_loader,
            promotions_loader=_stable_promotions_loader,
            flags_loader=_stable_flags_loader,
        )
        baseline_plan = PlanBuilder(baseline_demand).build(targets=demo_targets)
        baseline_engine = ScalimEngine(demand=baseline_demand, plan=baseline_plan, batch_size=3)
        baseline_rows = list(baseline_engine.run())
        retry_demo_expected_rows = build_retry_demo_expected_rows()

        matched, diff = compare_rows_by_pk(baseline_rows, retry_demo_expected_rows, pk_field="order_id", fields=demo_targets)
        if not matched:
            raise AssertionError("LoaderRetry demo baseline 对拍失败(scalim vs python-expected):\n{}".format(diff))

        retry_demo["baseline_rows"] = len(baseline_rows)

        def _build_flaky_demand_and_states(*, fail_times: int):  # type: ignore[no-untyped-def]
            case = str(LOADER_RETRY_CASE)
            main_fail = fail_times if case in {"main_source", "all"} else 0
            preload_fail = fail_times if case in {"preload_forever", "all"} else 0
            load_fail = fail_times if case in {"load", "all"} else 0
            loadref_fail = fail_times if case in {"load_ref", "all"} else 0

            main_loader, main_state = make_flaky_loader(name="main_source", fn=_stable_main_loader, fail_times=main_fail)
            promotions_loader, promotions_state = make_flaky_loader(
                name="preload_forever", fn=_stable_promotions_loader, fail_times=preload_fail
            )
            flags_loader, flags_state = make_flaky_loader(name="load", fn=_stable_flags_loader, fail_times=load_fail)
            customers_loader, customers_state = make_flaky_loader(name="load_ref", fn=_stable_customers_loader, fail_times=loadref_fail)

            demand = build_retry_demo_demand(
                main_loader=main_loader,
                customers_loader=customers_loader,
                promotions_loader=promotions_loader,
                flags_loader=flags_loader,
            )
            states = {
                "main_source": dict(main_state),
                "preload_forever": dict(promotions_state),
                "load": dict(flags_state),
                "load_ref": dict(customers_state),
            }
            return demand, states

        # 1) 不启用重试:注入 `fail_times > 0` 时应失败.
        flaky_demand_no_retry, _states_no_retry = _build_flaky_demand_and_states(fail_times=int(LOADER_RETRY_FAIL_TIMES))
        flaky_plan_no_retry = PlanBuilder(flaky_demand_no_retry).build(targets=demo_targets)
        flaky_engine_no_retry = ScalimEngine(demand=flaky_demand_no_retry, plan=flaky_plan_no_retry, batch_size=3)
        try:
            _ = list(flaky_engine_no_retry.run())
            retry_demo["no_retry_failed"] = False
            retry_demo["no_retry_error"] = None
        except Exception as exc:
            retry_demo["no_retry_failed"] = True
            retry_demo["no_retry_error"] = "{}: {}".format(type(exc).__name__, str(exc))

        # 2) 启用重试:应恢复并与基线输出一致.
        flaky_demand_retry, _states_retry = _build_flaky_demand_and_states(fail_times=int(LOADER_RETRY_FAIL_TIMES))
        flaky_plan_retry = PlanBuilder(flaky_demand_retry).build(targets=demo_targets)
        collector = RetryDemoCollector()
        retry_demo_observer_manager = ObserverManager(observers=[collector])
        policy = LoaderRetryPolicy(
            enabled=True,
            should_retry=retry_demo_should_retry,
            max_attempts=int(LOADER_RETRY_MAX_ATTEMPTS),
            max_elapsed_seconds=10.0,
            backoff="fixed",
            base_delay_seconds=0.0,
            max_delay_seconds=0.0,
            jitter=False,
        )
        engine_retry = ScalimEngine(
            demand=flaky_demand_retry,
            plan=flaky_plan_retry,
            observer_manager=retry_demo_observer_manager,
            loader_retry=LoaderRetryPolicies(default=policy),
            batch_size=3,
        )
        retry_rows = []
        try:
            retry_rows = list(engine_retry.run())
            retry_demo["retry_rows"] = len(retry_rows)

            matched, diff = compare_rows_by_pk(baseline_rows, retry_rows, pk_field="order_id", fields=demo_targets)
            if not matched:
                raise AssertionError("LoaderRetry demo 对拍失败(baseline vs retry-run):\n{}".format(diff))

            retry_demo["status"] = "matched"
            retry_demo["retry_error"] = None
        except Exception as exc:
            retry_demo["status"] = "failed"
            retry_demo["retry_error"] = "{}: {}".format(type(exc).__name__, str(exc))
            retry_demo["retry_rows"] = 0

        retry_demo["error_events"] = len(collector.errors)
        retry_demo["retry_events"] = [
            {
                "loader_name": e.loader_name,
                "callsite": e.callsite,
                "attempt_num": e.attempt_num,
                "max_attempts": e.max_attempts,
                "elapsed_seconds": e.elapsed_seconds,
                "sleep_seconds": e.sleep_seconds,
                "error_type": e.error_type,
                "error_message": e.error_message,
            }
            for e in collector.retries
        ]

        # 3) 可选:`run_ir` 路径(也会覆盖 `main_source` 加载器的调用点).
        if DO_LOADER_RETRY_DEMO_RUN_IR:
            retry_demo["run_ir"]["enabled"] = True
            flaky_demand_run_ir, _states_run_ir = _build_flaky_demand_and_states(fail_times=int(LOADER_RETRY_FAIL_TIMES))
            run_ir_collector = RetryDemoCollector()
            retry_demo_sink = InMemoryRowSink()
            request = ExecutionRequest(
                export_layout=ExportLayout(field_ids=tuple(demo_targets), header_names=None),
                output=OutputSpec(path=None),
                sink=retry_demo_sink,
                components=[run_ir_collector],
                loader_retry=LoaderRetryPolicies(default=policy),
                batch_size=3,
                parallel_mode="seq",
            )
            try:
                _ = run_ir(flaky_demand_run_ir, request)
                run_ir_rows = retry_demo_sink.get_data()
                retry_demo["run_ir"]["rows"] = len(run_ir_rows)
                retry_demo["run_ir"]["retry_events"] = len(run_ir_collector.retries)
                retry_demo["run_ir"]["error_events"] = len(run_ir_collector.errors)
                retry_demo["run_ir"]["failed"] = False
                retry_demo["run_ir"]["error"] = None

                matched, diff = compare_rows_by_pk(baseline_rows, run_ir_rows, pk_field="order_id", fields=demo_targets)
                if not matched:
                    raise AssertionError("LoaderRetry demo 对拍失败(baseline vs run_ir):\n{}".format(diff))
            except Exception as exc:
                retry_demo["run_ir"]["failed"] = True
                retry_demo["run_ir"]["error"] = "{}: {}".format(type(exc).__name__, str(exc))
                retry_demo["run_ir"]["rows"] = 0
                retry_demo["run_ir"]["retry_events"] = len(run_ir_collector.retries)
                retry_demo["run_ir"]["error_events"] = len(run_ir_collector.errors)

        # 4) 可选:放弃演示(超过 `max_attempts` -> 仅发出一次 `error` 事件).
        if DO_LOADER_RETRY_DEMO_GIVE_UP:
            retry_demo["give_up"]["enabled"] = True
            give_up_fail_times = max(int(LOADER_RETRY_MAX_ATTEMPTS), 1)
            give_up_demand, _states_give_up = _build_flaky_demand_and_states(fail_times=give_up_fail_times)
            give_up_plan = PlanBuilder(give_up_demand).build(targets=demo_targets)
            give_up_collector = _RetryDemoCollector()
            give_up_engine = ScalimEngine(
                demand=give_up_demand,
                plan=give_up_plan,
                observer_manager=ObserverManager(observers=[give_up_collector]),
                loader_retry=LoaderRetryPolicies(default=policy),
                batch_size=3,
            )
            try:
                _ = list(give_up_engine.run())
                retry_demo["give_up"]["failed"] = False
            except Exception as exc:
                retry_demo["give_up"]["failed"] = True
                retry_demo["give_up"]["error"] = "{}: {}".format(type(exc).__name__, str(exc))
            retry_demo["give_up"]["retry_events"] = len(give_up_collector.retries)
            retry_demo["give_up"]["error_events"] = len(give_up_collector.errors)

            if retry_demo["give_up"]["failed"] and retry_demo["give_up"]["error_events"] != 1:
                raise AssertionError(
                    "Expected give-up path to emit exactly one error event, got {}".format(retry_demo["give_up"]["error_events"])
                )

    return (retry_demo,)


@app.cell(hide_code=True)
def _(DO_LOADER_RETRY_DEMO, mo, retry_demo):
    if not DO_LOADER_RETRY_DEMO:
        mo.md("Loader Retry demo 已关闭(可在配置中启用).")
    else:
        no_retry_line = (
            "未启用 retry:`FAILED` ({})".format(retry_demo["no_retry_error"])
            if retry_demo["no_retry_failed"]
            else "未启用 retry:`OK`(本次未触发故障注入)"
        )

        run_ir_meta = retry_demo["run_ir"]
        run_ir_line = (
            "- run_ir: `ON` failed=`{}` rows=`{}` retry_events=`{}` error_events=`{}` error=`{}`".format(
                run_ir_meta.get("failed", False),
                run_ir_meta.get("rows", 0),
                run_ir_meta.get("retry_events", 0),
                run_ir_meta.get("error_events", 0),
                run_ir_meta.get("error"),
            )
            if run_ir_meta.get("enabled")
            else "- run_ir: `OFF`"
        )

        give_up_meta = retry_demo["give_up"]
        give_up_line = (
            "- give-up: `ON` failed=`{}` retry_events=`{}` error_events=`{}` error=`{}`".format(
                give_up_meta.get("failed"),
                give_up_meta.get("retry_events"),
                give_up_meta.get("error_events"),
                give_up_meta.get("error"),
            )
            if give_up_meta.get("enabled")
            else "- give-up: `OFF`"
        )

        lines = [
            "**Loader Retry demo**",
            "",
            "- case: `{}`".format(retry_demo["case"]),
            "- fail_times: `{}` max_attempts: `{}`".format(retry_demo["fail_times"], retry_demo["max_attempts"]),
            "- baseline_rows: `{}` retry_rows: `{}` status: `{}`".format(
                retry_demo["baseline_rows"], retry_demo["retry_rows"], retry_demo["status"]
            ),
            "- retry_events: `{}` error_events: `{}`".format(len(retry_demo.get("retry_events", [])), retry_demo.get("error_events", 0)),
        ]
        if retry_demo.get("retry_error") is not None:
            lines.append("- retry_error: `{}`".format(retry_demo["retry_error"]))
        lines.extend(["- " + no_retry_line, run_ir_line, give_up_line])
        mo.md("\n".join(lines))

    return


@app.cell
def _(DO_LOADER_RETRY_DEMO, mo, retry_demo):
    if DO_LOADER_RETRY_DEMO:
        events = retry_demo.get("retry_events", [])
        if events:
            mo.ui.table(events[:20])
    return


if __name__ == "__main__":
    app.run()
