import marimo

__generated_with = "0.20.2"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # `seq` vs `adaptive` 并行模式对比 + 三方对拍验证

    本示例回答两件事:

    1. `parallel_mode="adaptive"` 相比 `seq` 是否有提升? **取决于负载类型**.
    2. 结果是否一致? **必须一致**:`seq` / `adaptive` / `纯 Python 基准` 三方对拍通过才算 OK.

    ---
    ## 背景要点(结论先行)

    - `adaptive` 只会对 **批次内的 `LoadRef(keys)`** 做 fan-out/fan-in 并行.
    - 若耗时主要在 **I/O 型 ref loader**(网络/磁盘/远程服务),通常能提速.
    - 若 ref loader 主要是 **CPU/GIL** 计算或任务很小,并行开销可能抵消收益.
    - 若使用 **rows-binding**(loader 依赖 `batch_rows`),会触发 **屏障**,该层强制串行(可从调度原因看到).
    """)
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 1: 选择场景与参数
    """)
    return


@app.cell
def _(mo):
    case = mo.ui.dropdown(
        options={
            "io_latency_ref_loaders": "I/O 型 ref loader(注入 sleep) → 预期 adaptive 提升明显",
            "cpu_bound_ref_loaders": "CPU/GIL 型 ref loader(注入 CPU burn) → 预期 adaptive 无提升或更慢",
            "fast_loaders_smallish": "快 loader / CPU 为主 → 预期 adaptive 无提升或略慢",
            "below_min_parallel_tasks": "任务太少 → 预期串行(reason=below_min_parallel_tasks)",
            "rows_binding_barrier": "rows-binding 屏障 → 预期强制串行(看 reason=rows_binding_barrier)",
        },
        value="io_latency_ref_loaders",
        label="案例",
    )
    order_count = mo.ui.slider(start=100, stop=5000, value=500, step=100, label="订单/行数")
    batch_size = mo.ui.slider(start=50, stop=500, value=100, step=50, label="批次大小")

    delay_ms = mo.ui.slider(start=0, stop=30, value=5, step=1, label="ref loader 延迟(ms,仅 I/O 案例有效)")
    cpu_burn_per_id = mo.ui.slider(start=0, stop=2000, value=300, step=100, label="CPU burn/ID(iters,仅 CPU 案例有效)")
    max_workers = mo.ui.slider(start=0, stop=32, value=0, step=1, label="adaptive max_workers(0=自动)")
    min_parallel_tasks = mo.ui.slider(start=2, stop=12, value=2, step=1, label="每层最小并行任务数(min_parallel_tasks)")
    min_total_lookup_keys = mo.ui.slider(start=0, stop=2000, value=0, step=50, label="每层最小查找键总数(min_total_lookup_keys)")
    min_lookup_keys_per_task = mo.ui.slider(start=0, stop=2000, value=0, step=50, label="每任务最小查找键数(min_lookup_keys_per_task)")

    adaptive_backend = mo.ui.dropdown(
        options={
            "auto": "auto(默认策略)",
            "thread": "thread",
            "process": "process(本 demo 启用 hooks/observers 时会自动退化串行)",
        },
        value="auto",
        label="adaptive backend(可选)",
    )
    process_failure_mode = mo.ui.dropdown(
        options={
            "fallback_to_serial": "fallback_to_serial(推荐)",
            "fail_fast": "fail_fast(可能中断执行)",
        },
        value="fallback_to_serial",
        label="process failure mode(可选)",
    )

    float_tol = mo.ui.dropdown(
        options=["1e-9", "1e-6", "1e-3", "1e-2"],
        value="1e-9",
        label="float 绝对容差(对拍用)",
    )

    show_details = mo.ui.checkbox(value=False, label="显示更多细节(调度/耗时/差异样本)")

    mo.vstack(
        [
            case,
            mo.hstack([order_count, batch_size], justify="start", gap=2),
            mo.hstack([delay_ms, cpu_burn_per_id, max_workers], justify="start", gap=2),
            mo.hstack([min_parallel_tasks, min_total_lookup_keys, min_lookup_keys_per_task], justify="start", gap=2),
            mo.hstack([adaptive_backend, process_failure_mode], justify="start", gap=2),
            mo.hstack([float_tol, show_details], justify="start", gap=2),
        ]
    )
    return (
        adaptive_backend,
        batch_size,
        case,
        cpu_burn_per_id,
        delay_ms,
        float_tol,
        max_workers,
        min_lookup_keys_per_task,
        min_parallel_tasks,
        min_total_lookup_keys,
        order_count,
        process_failure_mode,
        show_details,
    )


@app.cell
def _(float_tol):
    abs_tol = float(float_tol.value)
    return (abs_tol,)


@app.cell
def _():
    import sys as _sys
    from pathlib import Path as _Path

    _this_dir = _Path(__file__).parent
    if str(_this_dir) not in _sys.path:
        _sys.path.insert(0, str(_this_dir))

    from _loaders import ECommerceConfig, load_orders, set_config
    from _shared import build_ecommerce_model, build_target_sets
    from _verification import python_build_order_report, verify_scalim_output

    from scalim.execution.adaptive.tuning import AdaptiveTuning
    from scalim.execution import ScalimEngine
    from scalim.execution.pipeline.overrides import PipelineOverrides
    from scalim.hooks.base import HookManager
    from scalim.ob.manager import ObserverManager
    from scalim.ob.presets.performance import PerformanceConfig, PerformanceObserver
    from scalim.planning import PlanBuilder
    from scalim.sinks.sink_memory import InMemoryColumnSink
    from scalim.spec.ir import BindingIr, DemandIr, FieldIr, KeyIr, LoaderIr, MainSourceIr, SourceIr

    return (
        AdaptiveTuning,
        BindingIr,
        DemandIr,
        ECommerceConfig,
        FieldIr,
        HookManager,
        InMemoryColumnSink,
        KeyIr,
        LoaderIr,
        MainSourceIr,
        ObserverManager,
        PerformanceConfig,
        PerformanceObserver,
        PipelineOverrides,
        PlanBuilder,
        ScalimEngine,
        SourceIr,
        build_ecommerce_model,
        build_target_sets,
        load_orders,
        python_build_order_report,
        set_config,
        verify_scalim_output,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 2: 选择目标字段集(仅电商案例)
    """)
    return


@app.cell
def _(build_target_sets, mo):
    target_sets = build_target_sets()
    target_profile = mo.ui.dropdown(
        options=list(target_sets.keys()),
        value="relations_only",
        label="目标字段集",
    )
    return target_profile, target_sets


@app.cell
def _(case, mo, target_profile, target_sets):
    mo.stop(case.value in ("rows_binding_barrier", "below_min_parallel_tasks"))
    mo.hstack([target_profile, mo.stat(value=str(len(target_sets[target_profile.value])), label="字段数", bordered=True)])
    return


@app.cell
def _(case, mo):
    mo.stop(case.value != "rows_binding_barrier")
    mo.callout(
        mo.md("rows-binding 案例使用最小模型: fields=`id`/`fk`/`fk_batch_count`,用于稳定触发 `rows_binding_barrier`."),
        kind="info",
    )
    return


@app.cell
def _(case, mo):
    mo.stop(case.value != "below_min_parallel_tasks")
    mo.callout(
        mo.md(
            "`below_min_parallel_tasks` 案例使用最小模型: 仅 1 个 ref loader,确保 `adaptive` 走串行并输出 reason=below_min_parallel_tasks."
        ),
        kind="info",
    )
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## Step 3: 执行 `seq` / `adaptive` / `纯 Python` 并对拍
    """)
    return


@app.cell
def _():
    def _values_equal(a, b, float_abs_tol):
        if a is None and b is None:
            return True
        if a is None or b is None:
            return False
        if isinstance(a, bool) or isinstance(b, bool):
            return a == b
        if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool):
            try:
                return abs(float(a) - float(b)) <= float_abs_tol
            except (TypeError, ValueError):
                return False
        if isinstance(a, float) or isinstance(b, float):
            try:
                return abs(float(a) - float(b)) <= float_abs_tol
            except (TypeError, ValueError):
                return False
        return a == b

    def compare_rows(rows_a, rows_b, *, key_field, fields, float_abs_tol, max_mismatches=10):
        def _index(rows):
            by_key = {}
            missing_key = 0
            dup_keys = set()
            for row in rows:
                if key_field not in row:
                    missing_key += 1
                    continue
                k = row.get(key_field)
                if k in by_key:
                    dup_keys.add(k)
                by_key[k] = row
            return by_key, missing_key, dup_keys

        a_by_key, a_missing_key, a_dups = _index(rows_a)
        b_by_key, b_missing_key, b_dups = _index(rows_b)

        a_keys = set(a_by_key.keys())
        b_keys = set(b_by_key.keys())

        missing_in_a = sorted(b_keys - a_keys)
        missing_in_b = sorted(a_keys - b_keys)

        mismatch_count = 0
        mismatches = []

        for k in sorted(a_keys & b_keys):
            ra = a_by_key[k]
            rb = b_by_key[k]
            for f in fields:
                va = ra.get(f)
                vb = rb.get(f)
                if _values_equal(va, vb, float_abs_tol=float_abs_tol):
                    continue
                mismatch_count += 1
                if len(mismatches) < max_mismatches:
                    diff = None
                    if (
                        isinstance(va, (int, float))
                        and isinstance(vb, (int, float))
                        and not isinstance(va, bool)
                        and not isinstance(vb, bool)
                    ):
                        diff = float(va) - float(vb)
                    mismatches.append({"key": k, "field": f, "a": va, "b": vb, "diff": diff})

        passed = (
            not mismatch_count
            and not missing_in_a
            and not missing_in_b
            and not a_dups
            and not b_dups
            and not a_missing_key
            and not b_missing_key
        )
        summary = {
            "passed": passed,
            "row_count_a": len(rows_a),
            "row_count_b": len(rows_b),
            "mismatch_count": mismatch_count,
            "missing_keys_in_a": len(missing_in_a),
            "missing_keys_in_b": len(missing_in_b),
            "dup_keys_a": len(a_dups),
            "dup_keys_b": len(b_dups),
            "rows_missing_key_a": a_missing_key,
            "rows_missing_key_b": b_missing_key,
            "first_mismatch": mismatches[0] if mismatches else None,
            "sample_mismatches": mismatches,
        }
        return summary

    return (compare_rows,)


@app.cell
def _(
    AdaptiveTuning,
    BindingIr,
    DemandIr,
    ECommerceConfig,
    FieldIr,
    HookManager,
    InMemoryColumnSink,
    KeyIr,
    LoaderIr,
    MainSourceIr,
    ObserverManager,
    PerformanceConfig,
    PerformanceObserver,
    PipelineOverrides,
    PlanBuilder,
    ScalimEngine,
    SourceIr,
    abs_tol,
    adaptive_backend,
    batch_size,
    build_ecommerce_model,
    case,
    compare_rows,
    cpu_burn_per_id,
    delay_ms,
    load_orders,
    max_workers,
    min_lookup_keys_per_task,
    min_parallel_tasks,
    min_total_lookup_keys,
    mo,
    order_count,
    process_failure_mode,
    python_build_order_report,
    set_config,
    show_details,
    target_profile,
    target_sets,
    verify_scalim_output,
):
    import time

    def run_scalim(*, demand, targets, main_rows, parallel_mode, max_workers_value, tuning):
        from scalim.events.catalog import EVENT_ADAPTIVE_SCHEDULER_DECISION, EVENT_STAGE_SPAN  # noqa: PLC0415
        from scalim.events.event import Event  # noqa: PLC0415
        from scalim.hooks.base import BaseHook  # noqa: PLC0415

        class _CollectorHook(BaseHook):
            event_types = {EVENT_STAGE_SPAN, EVENT_ADAPTIVE_SCHEDULER_DECISION}

            def __init__(self) -> None:
                self.stage_spans = []
                self.scheduler_decisions = []

            def on_event(self, event: Event) -> None:
                if event.event_type == EVENT_STAGE_SPAN:
                    self.stage_spans.append(event.payload)
                    return
                if event.event_type == EVENT_ADAPTIVE_SCHEDULER_DECISION:
                    self.scheduler_decisions.append(event.payload)

        perf_config = PerformanceConfig(
            metrics={"duration"},
            sampling_interval=1,
            report_format="none",
            include_scheduler_decisions=True,
        )
        observer = PerformanceObserver(config=perf_config)
        observer_manager = ObserverManager()
        observer_manager.register(observer)

        hook_manager = HookManager()
        collector = _CollectorHook()
        hook_manager.register(collector)

        from scalim.execution.adaptive.policy import (  # noqa: PLC0415
            AdaptivePolicy,
            PROCESS_FAILURE_FAIL_FAST,
            PROCESS_FAILURE_FALLBACK_SERIAL,
        )

        backend_choice = str(getattr(adaptive_backend, "value", None) or "auto")
        process_failure_mode_choice = str(getattr(process_failure_mode, "value", None) or PROCESS_FAILURE_FALLBACK_SERIAL)
        if backend_choice == "process" and process_failure_mode_choice == PROCESS_FAILURE_FAIL_FAST:
            process_failure_mode_choice = PROCESS_FAILURE_FALLBACK_SERIAL

        class _UiPolicy(AdaptivePolicy):
            def __init__(self, *, backend: str, process_failure_mode: str) -> None:
                self._backend = backend
                self._process_failure_mode = process_failure_mode

            def choose_backend(self, *, plan, runtime, tuning):  # type: ignore[override]
                if self._backend in ("thread", "process", "async"):
                    return self._backend
                return super().choose_backend(plan=plan, runtime=runtime, tuning=tuning)

            def choose_process_failure_mode(self, *, plan, runtime, tuning):  # type: ignore[override]
                if self._process_failure_mode in (PROCESS_FAILURE_FAIL_FAST, PROCESS_FAILURE_FALLBACK_SERIAL):
                    return self._process_failure_mode
                return super().choose_process_failure_mode(plan=plan, runtime=runtime, tuning=tuning)

        overrides = PipelineOverrides(
            adaptive_tuning=tuning,
            adaptive_policy=_UiPolicy(backend=backend_choice, process_failure_mode=process_failure_mode_choice),
        )

        engine = ScalimEngine(
            demand=demand,
            plan=PlanBuilder(demand).build(targets=targets),
            hook_manager=hook_manager,
            observer_manager=observer_manager,
            batch_size=int(batch_size.value),
            parallel_mode=parallel_mode,
            max_workers=int(max_workers_value),
            pipeline_overrides=overrides,
        )

        start = time.perf_counter()
        with InMemoryColumnSink(field_names=targets) as sink:
            engine.run(main_rows=main_rows, sink=sink)
            rows = sink.get_rows()
        wall = time.perf_counter() - start
        metrics = observer.get_metrics()
        return rows, wall, metrics, collector

    tuning = AdaptiveTuning(
        min_parallel_tasks_per_layer=int(min_parallel_tasks.value),
        min_total_lookup_keys_per_layer=int(min_total_lookup_keys.value),
        min_lookup_keys_per_task=int(min_lookup_keys_per_task.value),
    )

    # ------------------------------------------------------------------
    # 场景 A/B: 电商模型(快 `loader` / `I/O` 延迟的引用表 `loader`)
    # ------------------------------------------------------------------
    if case.value in ("fast_loaders_smallish", "io_latency_ref_loaders", "cpu_bound_ref_loaders"):
        cfg = ECommerceConfig(order_count=int(order_count.value))
        set_config(cfg)
        targets = list(target_sets[target_profile.value])

        patch_kind = None
        if case.value == "io_latency_ref_loaders" and int(delay_ms.value) > 0:
            patch_kind = "sleep"
        if case.value == "cpu_bound_ref_loaders" and int(cpu_burn_per_id.value) > 0:
            patch_kind = "cpu"

        # 注意:`patch` 只影响 Scalim `demand` 内部引用的 `loader callable`; 纯 Python 基准保持原始实现.
        if patch_kind is not None:
            import _loaders as _loaders_mod  # noqa: PLC0415
            import _shared as _shared_mod  # noqa: PLC0415

            def _wrap_sleep(fn, ms):
                def _inner(*args, **kwargs):
                    time.sleep(float(ms) / 1000.0)
                    return fn(*args, **kwargs)

                _inner.__name__ = getattr(fn, "__name__", "wrapped_loader")
                return _inner

            def _wrap_cpu(fn, iters_per_id):
                def _inner(*args, **kwargs):
                    ids = kwargs.get("ids")
                    if ids is None and args:
                        ids = args[0]
                    try:
                        n = len(ids) if ids is not None else 1
                    except TypeError:
                        n = 1

                    burn = int(iters_per_id) * max(1, int(n))
                    burn = min(burn, 200000)

                    x = 0
                    for i in range(int(burn)):
                        x = (x * 1664525 + 1013904223 + i) & 0xFFFFFFFF
                    if x == 0xDEADBEEF:  # pragma: no cover
                        time.sleep(0)

                    return fn(*args, **kwargs)

                _inner.__name__ = getattr(fn, "__name__", "wrapped_loader")
                return _inner

            def _wrap(fn):
                if patch_kind == "sleep":
                    return _wrap_sleep(fn, int(delay_ms.value))
                return _wrap_cpu(fn, int(cpu_burn_per_id.value))

            patch_names = [
                "load_customers",
                "load_products",
                "load_categories",
                "load_warehouses",
                "load_regions",
                "load_region_pricing",
                "load_promotions",
                "load_payment_methods",
                "load_logistics",
            ]

            backups = {}
            for name in patch_names:
                if hasattr(_shared_mod, name) and hasattr(_loaders_mod, name):
                    backups[name] = getattr(_shared_mod, name)
                    setattr(_shared_mod, name, _wrap(getattr(_loaders_mod, name)))
            try:
                demand = build_ecommerce_model()
            finally:
                for name, original in backups.items():
                    setattr(_shared_mod, name, original)
        else:
            demand = build_ecommerce_model()

        main_rows = list(load_orders())

        rows_seq, wall_seq, metrics_seq, collector_seq = run_scalim(
            demand=demand,
            targets=targets,
            main_rows=main_rows,
            parallel_mode="seq",
            max_workers_value=0,
            tuning=tuning,
        )
        rows_adp, wall_adp, metrics_adp, collector_adp = run_scalim(
            demand=demand,
            targets=targets,
            main_rows=main_rows,
            parallel_mode="adaptive",
            max_workers_value=int(max_workers.value),
            tuning=tuning,
        )

        baseline = python_build_order_report(targets)

        # 三方对拍
        cmp_seq_adp = compare_rows(rows_seq, rows_adp, key_field="order_id", fields=targets, float_abs_tol=abs_tol)
        cmp_seq_py = compare_rows(rows_seq, baseline, key_field="order_id", fields=targets, float_abs_tol=abs_tol)
        cmp_adp_py = compare_rows(rows_adp, baseline, key_field="order_id", fields=targets, float_abs_tol=abs_tol)

        # 纯 Py 基准验证(最终正确性)
        vr_seq = verify_scalim_output(rows_seq, fields_to_check=targets, tolerance=abs_tol, max_mismatches=20)
        vr_adp = verify_scalim_output(rows_adp, fields_to_check=targets, tolerance=abs_tol, max_mismatches=20)

        speedup = (wall_seq / wall_adp) if wall_adp > 0 else 0.0

        backends = {}
        if metrics_adp.adaptive_scheduler is not None:
            backends = dict(metrics_adp.adaptive_scheduler.backend_counts)
        backend_text = ", ".join(["{}={}".format(k, v) for k, v in sorted(backends.items())]) if backends else "unknown"

        mo.hstack(
            [
                mo.stat(value="{:.4f}s".format(wall_seq), label="seq wall", bordered=True),
                mo.stat(value="{:.4f}s".format(wall_adp), label="adaptive wall", bordered=True),
                mo.stat(value="{:.2f}x".format(speedup), label="speedup(seq/adp)", bordered=True),
                mo.stat(value="{:.0f}".format(metrics_seq.throughput), label="seq rows/s", bordered=True),
                mo.stat(value="{:.0f}".format(metrics_adp.throughput), label="adp rows/s", bordered=True),
                mo.stat(value=backend_text, label="adp backend", bordered=True),
            ],
            justify="start",
            gap=1,
        )

        def _status(x):
            return "✅ PASS" if x else "❌ FAIL"

        mo.md(
            """
            ### 三方对拍(同字段/同主键)

            - seq vs adaptive: **{}**
            - seq vs 纯Py基准: **{}**
            - adaptive vs 纯Py基准: **{}**

            ### 纯Py基准验证(对照 Join+派生逻辑)

            - seq: **{}**
            - adaptive: **{}**
            """.format(
                _status(cmp_seq_adp["passed"]),
                _status(cmp_seq_py["passed"]),
                _status(cmp_adp_py["passed"]),
                _status(vr_seq.passed),
                _status(vr_adp.passed),
            )
        )

        import altair as alt  # noqa: PLC0415
        import pandas as pd  # noqa: PLC0415

        seq_stage = metrics_seq.stage_metrics.to_dict()
        adp_stage = metrics_adp.stage_metrics.to_dict()
        stage_rows = []
        for stage in ("loader", "compute", "write"):
            seq_s = float(seq_stage.get(stage) or 0.0)
            adp_s = float(adp_stage.get(stage) or 0.0)
            stage_rows.append(
                {
                    "stage": stage,
                    "seq_s": round(seq_s, 4),
                    "adaptive_s": round(adp_s, 4),
                    "delta_s(seq-adp)": round(seq_s - adp_s, 4),
                    "ratio(seq/adp)": round((seq_s / adp_s), 3) if adp_s > 0 else None,
                }
            )

        def _summarize_stage_spans(spans):
            by_batch = {}
            for e in spans:
                b = int(getattr(e, "batch_num", 0) or 0)
                stage = str(getattr(e, "stage", "") or "")
                dur = float(getattr(e, "duration", 0.0) or 0.0)
                row = by_batch.get(b)
                if row is None:
                    row = {"batch_num": b, "loader": 0.0, "compute": 0.0, "write": 0.0}
                    by_batch[b] = row
                if stage in row:
                    row[stage] += max(0.0, dur)
            rows = [by_batch[b] for b in sorted(by_batch.keys())]
            for r in rows:
                r["loader"] = round(float(r["loader"]), 4)
                r["compute"] = round(float(r["compute"]), 4)
                r["write"] = round(float(r["write"]), 4)
            return rows

        perf_df = pd.DataFrame(
            [
                {"mode": "seq", "wall_s": float(wall_seq), "throughput_rows_s": float(metrics_seq.throughput)},
                {"mode": "adaptive", "wall_s": float(wall_adp), "throughput_rows_s": float(metrics_adp.throughput)},
            ]
        )

        perf_wall_chart = (
            alt.Chart(perf_df)
            .mark_bar()
            .encode(
                x=alt.X("mode:N", title="mode", sort=None),
                y=alt.Y("wall_s:Q", title="wall (s)"),
                color=alt.Color("mode:N", legend=None),
                tooltip=[alt.Tooltip("mode:N"), alt.Tooltip("wall_s:Q", format=".4f")],
            )
            .properties(width=230, height=180, title="Wall Time")
        )
        perf_tp_chart = (
            alt.Chart(perf_df)
            .mark_bar()
            .encode(
                x=alt.X("mode:N", title="mode", sort=None),
                y=alt.Y("throughput_rows_s:Q", title="rows/s"),
                color=alt.Color("mode:N", legend=None),
                tooltip=[alt.Tooltip("mode:N"), alt.Tooltip("throughput_rows_s:Q", format=".0f")],
            )
            .properties(width=230, height=180, title="Throughput")
        )
        perf_chart = alt.hconcat(perf_wall_chart, perf_tp_chart).resolve_scale(y="independent")

        stage_df = pd.DataFrame(stage_rows)
        stage_long_df = stage_df.melt(
            id_vars=["stage"],
            value_vars=["seq_s", "adaptive_s"],
            var_name="mode",
            value_name="seconds",
        )
        stage_long_df["mode"] = stage_long_df["mode"].map({"seq_s": "seq", "adaptive_s": "adaptive"})
        stage_chart = (
            alt.Chart(stage_long_df)
            .mark_bar()
            .encode(
                x=alt.X("mode:N", title="mode", sort=None),
                y=alt.Y("seconds:Q", title="stage seconds"),
                color=alt.Color("stage:N", title="stage", sort=["loader", "compute", "write"]),
                tooltip=[alt.Tooltip("mode:N"), alt.Tooltip("stage:N"), alt.Tooltip("seconds:Q", format=".4f")],
            )
            .properties(width=520, height=220, title="Stage Breakdown (stacked)")
        )

        spans_seq_all = _summarize_stage_spans(getattr(collector_seq, "stage_spans", []))
        spans_adp_all = _summarize_stage_spans(getattr(collector_adp, "stage_spans", []))
        spans_df = pd.concat(
            [
                pd.DataFrame(spans_seq_all, columns=["batch_num", "loader", "compute", "write"]).assign(mode="seq"),
                pd.DataFrame(spans_adp_all, columns=["batch_num", "loader", "compute", "write"]).assign(mode="adaptive"),
            ],
            ignore_index=True,
        )
        spans_long_df = spans_df.melt(
            id_vars=["mode", "batch_num"],
            value_vars=["loader", "compute", "write"],
            var_name="stage",
            value_name="seconds",
        )
        spans_chart = (
            alt.Chart(spans_long_df)
            .mark_line(point=True)
            .encode(
                x=alt.X("batch_num:Q", title="batch"),
                y=alt.Y("seconds:Q", title="seconds"),
                color=alt.Color("stage:N", title="stage", sort=["loader", "compute", "write"]),
                column=alt.Column("mode:N", title="mode", sort=None),
                tooltip=[
                    alt.Tooltip("mode:N"),
                    alt.Tooltip("batch_num:Q"),
                    alt.Tooltip("stage:N"),
                    alt.Tooltip("seconds:Q", format=".4f"),
                ],
            )
            .properties(width=250, height=220, title="Stage Span Timeline (per batch)")
            .interactive()
        )

        sched = metrics_adp.adaptive_scheduler
        sched_summary_rows = []
        serial_reasons_view = mo.callout(mo.md("未收集到 adaptive_scheduler 指标(请确认 `include_scheduler_decisions=True`)"), kind="warn")
        backend_view = mo.callout(mo.md("未收集到 adaptive_scheduler 指标(请确认 `include_scheduler_decisions=True`)"), kind="warn")
        pool_wait_view = mo.callout(mo.md("未收集到 adaptive_scheduler 指标(请确认 `include_scheduler_decisions=True`)"), kind="warn")

        if sched is not None:
            sched_summary_rows = [
                {"k": "parallel_layers", "v": int(sched.parallel_layers)},
                {"k": "serial_layers", "v": int(sched.serial_layers)},
            ]

            reasons_df = pd.DataFrame(
                [{"reason": k, "count": int(v)} for k, v in sorted(sched.serial_reasons.items(), key=lambda kv: (-int(kv[1]), str(kv[0])))]
            )
            if len(reasons_df):
                reasons_chart = (
                    alt.Chart(reasons_df)
                    .mark_bar()
                    .encode(
                        y=alt.Y("reason:N", title="reason", sort="-x"),
                        x=alt.X("count:Q", title="count"),
                        tooltip=[alt.Tooltip("reason:N"), alt.Tooltip("count:Q")],
                    )
                    .properties(width=520, height=220, title="Serial Reasons")
                )
                serial_reasons_view = mo.ui.altair_chart(reasons_chart)
            else:
                serial_reasons_view = mo.callout(mo.md("本次 adaptive 没有串行层(全部为 parallel)"), kind="info")

            backend_df = pd.DataFrame(
                [{"backend": k, "count": int(v)} for k, v in sorted(sched.backend_counts.items(), key=lambda kv: (-int(kv[1]), str(kv[0])))]
            )
            if len(backend_df):
                backend_chart = (
                    alt.Chart(backend_df)
                    .mark_bar()
                    .encode(
                        y=alt.Y("backend:N", title="backend", sort="-x"),
                        x=alt.X("count:Q", title="count"),
                        tooltip=[alt.Tooltip("backend:N"), alt.Tooltip("count:Q")],
                    )
                    .properties(width=520, height=200, title="Backend Counts")
                )
                backend_view = mo.ui.altair_chart(backend_chart)
            else:
                backend_view = mo.callout(mo.md("未记录到 backend_counts(可能未触发调度事件)"), kind="info")

            pool_wait_df = pd.DataFrame(
                [
                    {
                        "pool": k,
                        "wait_ms_total": float(sched.pool_wait_ms_total.get(k, 0.0)),
                        "wait_ms_max": float(sched.pool_wait_ms_max.get(k, 0.0)),
                        "wait_count": int(sched.pool_wait_count.get(k, 0)),
                    }
                    for k in sorted(
                        set(
                            list(sched.pool_wait_ms_total.keys()) + list(sched.pool_wait_ms_max.keys()) + list(sched.pool_wait_count.keys())
                        )
                    )
                ]
            )
            if len(pool_wait_df):
                pool_wait_chart = (
                    alt.Chart(pool_wait_df)
                    .mark_bar()
                    .encode(
                        y=alt.Y("pool:N", title="pool", sort="-x"),
                        x=alt.X("wait_ms_total:Q", title="wait ms total"),
                        tooltip=[
                            alt.Tooltip("pool:N"),
                            alt.Tooltip("wait_ms_total:Q", format=".3f"),
                            alt.Tooltip("wait_ms_max:Q", format=".3f"),
                            alt.Tooltip("wait_count:Q"),
                        ],
                    )
                    .properties(width=520, height=200, title="Pool Wait (total)")
                )
                pool_wait_view = mo.ui.altair_chart(pool_wait_chart)
            else:
                pool_wait_view = mo.callout(mo.md("本次没有 pool wait(没有发生排队等待)"), kind="info")

        mo.md("### 可视化面板(交互式)")
        mo.tabs(
            {
                "性能": mo.vstack(
                    [
                        mo.ui.altair_chart(perf_chart, chart_selection="interval", legend_selection=False),
                        mo.ui.table(perf_df.to_dict(orient="records"), selection=None),
                    ]
                ),
                "阶段": mo.vstack(
                    [
                        mo.ui.altair_chart(stage_chart, chart_selection="interval"),
                        mo.ui.table(stage_rows, selection=None),
                    ]
                ),
                "按批次": mo.vstack([mo.ui.altair_chart(spans_chart, chart_selection="interval")]),
                "调度": mo.vstack(
                    [
                        mo.ui.table(sched_summary_rows, selection=None),
                        serial_reasons_view,
                        backend_view,
                        pool_wait_view,
                    ]
                ),
            }
        )

        if show_details.value:
            mismatch_rows = [
                {"pair": "seq_vs_adaptive", "first_mismatch": cmp_seq_adp.get("first_mismatch")},
                {"pair": "seq_vs_pure_py", "first_mismatch": cmp_seq_py.get("first_mismatch")},
                {"pair": "adaptive_vs_pure_py", "first_mismatch": cmp_adp_py.get("first_mismatch")},
            ]

            spans_seq_sample = spans_seq_all[:10]
            spans_adp_sample = spans_adp_all[:10]

            decisions = []
            for ev in getattr(collector_adp, "scheduler_decisions", [])[:30]:
                decisions.append(
                    {
                        "batch": getattr(ev, "batch_num", None),
                        "layer": getattr(ev, "layer_index", None),
                        "decision": getattr(ev, "decision", None),
                        "backend": getattr(ev, "backend", None),
                        "reason": getattr(ev, "reason", None),
                        "tasks": getattr(ev, "layer_task_count", None),
                    }
                )

            adp_sched = metrics_adp.adaptive_scheduler.to_dict() if metrics_adp.adaptive_scheduler is not None else {}
            mo.accordion(
                {
                    "对拍差异样本": mo.ui.table(mismatch_rows, selection=None),
                    "调度摘要(raw)": mo.ui.table([{"k": k, "v": v} for k, v in adp_sched.items()], selection=None),
                    "按批次 stage span(表格采样)": mo.vstack(
                        [
                            mo.md("seq: 前 10 个批次"),
                            mo.ui.table(spans_seq_sample, selection=None),
                            mo.md("adaptive: 前 10 个批次"),
                            mo.ui.table(spans_adp_sample, selection=None),
                        ]
                    ),
                    "每层决策日志(前 30 条)": mo.ui.table(decisions, selection=None),
                },
                multiple=True,
                lazy=True,
            )

    # ------------------------------------------------------------------
    # 场景 C: 任务太少(触发 `below_min_parallel_tasks`) 最小模型
    # ------------------------------------------------------------------
    if case.value == "below_min_parallel_tasks":
        n = int(order_count.value)
        main_rows = [{"id": i} for i in range(n)]

        def load_main():
            return list(main_rows)

        def load_ref(ids=None, field_keys=None, is_ref_loader=False):
            _ = field_keys
            _ = is_ref_loader
            if not ids:
                return {}
            result = {}
            for raw in ids:
                try:
                    rid = int(raw)
                except (TypeError, ValueError):
                    continue
                result[rid] = {"id": rid, "val": rid * 2}
            return result

        def keys_params(ctx):
            return (), {"ids": list(ctx.lookup_keys_list or [])}

        main = MainSourceIr(source_id="main", loader=load_main)
        ref = SourceIr(
            source_id="ref",
            key=KeyIr(key="id"),
            loader_spec=LoaderIr(
                callable=load_ref,
                bindings={
                    "id": BindingIr(
                        key_field="id",
                        params_builder=keys_params,
                        mode="keys",
                        cache_mode="none",
                    )
                },
            ),
        )

        fields = [
            FieldIr(field_id="id", name="id", source=main, is_primary=True),
            FieldIr(
                field_id="val",
                name="val",
                source=ref,
                relation=main["id"].join(ref["id"]),
            ),
        ]

        demand = DemandIr.from_irs(sources=[ref], fields=fields, main_source=main, batch_size_hint=int(batch_size.value))
        targets = ["id", "val"]

        rows_seq, wall_seq, metrics_seq, collector_seq = run_scalim(
            demand=demand,
            targets=targets,
            main_rows=list(main_rows),
            parallel_mode="seq",
            max_workers_value=0,
            tuning=tuning,
        )
        rows_adp, wall_adp, metrics_adp, collector_adp = run_scalim(
            demand=demand,
            targets=targets,
            main_rows=list(main_rows),
            parallel_mode="adaptive",
            max_workers_value=int(max_workers.value),
            tuning=tuning,
        )

        baseline = [{"id": int(r.get("id")), "val": int(r.get("id")) * 2} for r in main_rows]

        cmp_seq_adp = compare_rows(rows_seq, rows_adp, key_field="id", fields=targets, float_abs_tol=abs_tol)
        cmp_seq_py = compare_rows(rows_seq, baseline, key_field="id", fields=targets, float_abs_tol=abs_tol)
        cmp_adp_py = compare_rows(rows_adp, baseline, key_field="id", fields=targets, float_abs_tol=abs_tol)

        speedup = (wall_seq / wall_adp) if wall_adp > 0 else 0.0

        backends = {}
        if metrics_adp.adaptive_scheduler is not None:
            backends = dict(metrics_adp.adaptive_scheduler.backend_counts)
        backend_text = ", ".join(["{}={}".format(k, v) for k, v in sorted(backends.items())]) if backends else "unknown"

        mo.hstack(
            [
                mo.stat(value="{:.4f}s".format(wall_seq), label="seq wall", bordered=True),
                mo.stat(value="{:.4f}s".format(wall_adp), label="adaptive wall", bordered=True),
                mo.stat(value="{:.2f}x".format(speedup), label="speedup(seq/adp)", bordered=True),
                mo.stat(value="{:.0f}".format(metrics_seq.throughput), label="seq rows/s", bordered=True),
                mo.stat(value="{:.0f}".format(metrics_adp.throughput), label="adp rows/s", bordered=True),
                mo.stat(value=backend_text, label="adp backend", bordered=True),
            ],
            justify="start",
            gap=1,
        )

        mo.md(
            """
            ### 三方对拍(任务太少案例)

            - seq vs adaptive: **{}**
            - seq vs 纯Py基准: **{}**
            - adaptive vs 纯Py基准: **{}**
            """.format(
                "✅ PASS" if cmp_seq_adp["passed"] else "❌ FAIL",
                "✅ PASS" if cmp_seq_py["passed"] else "❌ FAIL",
                "✅ PASS" if cmp_adp_py["passed"] else "❌ FAIL",
            )
        )

        import altair as alt  # noqa: PLC0415
        import pandas as pd  # noqa: PLC0415

        seq_stage = metrics_seq.stage_metrics.to_dict()
        adp_stage = metrics_adp.stage_metrics.to_dict()
        stage_rows = []
        for stage in ("loader", "compute", "write"):
            seq_s = float(seq_stage.get(stage) or 0.0)
            adp_s = float(adp_stage.get(stage) or 0.0)
            stage_rows.append(
                {
                    "stage": stage,
                    "seq_s": round(seq_s, 4),
                    "adaptive_s": round(adp_s, 4),
                    "delta_s(seq-adp)": round(seq_s - adp_s, 4),
                    "ratio(seq/adp)": round((seq_s / adp_s), 3) if adp_s > 0 else None,
                }
            )

        def _summarize_stage_spans(spans):
            by_batch = {}
            for e in spans:
                b = int(getattr(e, "batch_num", 0) or 0)
                stage = str(getattr(e, "stage", "") or "")
                dur = float(getattr(e, "duration", 0.0) or 0.0)
                row = by_batch.get(b)
                if row is None:
                    row = {"batch_num": b, "loader": 0.0, "compute": 0.0, "write": 0.0}
                    by_batch[b] = row
                if stage in row:
                    row[stage] += max(0.0, dur)
            rows = [by_batch[b] for b in sorted(by_batch.keys())]
            for r in rows:
                r["loader"] = round(float(r["loader"]), 4)
                r["compute"] = round(float(r["compute"]), 4)
                r["write"] = round(float(r["write"]), 4)
            return rows

        perf_df = pd.DataFrame(
            [
                {"mode": "seq", "wall_s": float(wall_seq), "throughput_rows_s": float(metrics_seq.throughput)},
                {"mode": "adaptive", "wall_s": float(wall_adp), "throughput_rows_s": float(metrics_adp.throughput)},
            ]
        )
        perf_wall_chart = (
            alt.Chart(perf_df)
            .mark_bar()
            .encode(
                x=alt.X("mode:N", title="mode", sort=None),
                y=alt.Y("wall_s:Q", title="wall (s)"),
                color=alt.Color("mode:N", legend=None),
                tooltip=[alt.Tooltip("mode:N"), alt.Tooltip("wall_s:Q", format=".4f")],
            )
            .properties(width=230, height=180, title="Wall Time")
        )
        perf_tp_chart = (
            alt.Chart(perf_df)
            .mark_bar()
            .encode(
                x=alt.X("mode:N", title="mode", sort=None),
                y=alt.Y("throughput_rows_s:Q", title="rows/s"),
                color=alt.Color("mode:N", legend=None),
                tooltip=[alt.Tooltip("mode:N"), alt.Tooltip("throughput_rows_s:Q", format=".0f")],
            )
            .properties(width=230, height=180, title="Throughput")
        )
        perf_chart = alt.hconcat(perf_wall_chart, perf_tp_chart).resolve_scale(y="independent")

        stage_df = pd.DataFrame(stage_rows)
        stage_long_df = stage_df.melt(
            id_vars=["stage"],
            value_vars=["seq_s", "adaptive_s"],
            var_name="mode",
            value_name="seconds",
        )
        stage_long_df["mode"] = stage_long_df["mode"].map({"seq_s": "seq", "adaptive_s": "adaptive"})
        stage_chart = (
            alt.Chart(stage_long_df)
            .mark_bar()
            .encode(
                x=alt.X("mode:N", title="mode", sort=None),
                y=alt.Y("seconds:Q", title="stage seconds"),
                color=alt.Color("stage:N", title="stage", sort=["loader", "compute", "write"]),
                tooltip=[alt.Tooltip("mode:N"), alt.Tooltip("stage:N"), alt.Tooltip("seconds:Q", format=".4f")],
            )
            .properties(width=520, height=220, title="Stage Breakdown (stacked)")
        )

        spans_seq_all = _summarize_stage_spans(getattr(collector_seq, "stage_spans", []))
        spans_adp_all = _summarize_stage_spans(getattr(collector_adp, "stage_spans", []))
        spans_df = pd.concat(
            [
                pd.DataFrame(spans_seq_all, columns=["batch_num", "loader", "compute", "write"]).assign(mode="seq"),
                pd.DataFrame(spans_adp_all, columns=["batch_num", "loader", "compute", "write"]).assign(mode="adaptive"),
            ],
            ignore_index=True,
        )
        spans_long_df = spans_df.melt(
            id_vars=["mode", "batch_num"],
            value_vars=["loader", "compute", "write"],
            var_name="stage",
            value_name="seconds",
        )
        spans_chart = (
            alt.Chart(spans_long_df)
            .mark_line(point=True)
            .encode(
                x=alt.X("batch_num:Q", title="batch"),
                y=alt.Y("seconds:Q", title="seconds"),
                color=alt.Color("stage:N", title="stage", sort=["loader", "compute", "write"]),
                column=alt.Column("mode:N", title="mode", sort=None),
                tooltip=[
                    alt.Tooltip("mode:N"),
                    alt.Tooltip("batch_num:Q"),
                    alt.Tooltip("stage:N"),
                    alt.Tooltip("seconds:Q", format=".4f"),
                ],
            )
            .properties(width=250, height=220, title="Stage Span Timeline (per batch)")
            .interactive()
        )

        sched = metrics_adp.adaptive_scheduler
        sched_summary_rows = []
        serial_reasons_view = mo.callout(mo.md("未收集到 adaptive_scheduler 指标(请确认 `include_scheduler_decisions=True`)"), kind="warn")
        backend_view = mo.callout(mo.md("未收集到 adaptive_scheduler 指标(请确认 `include_scheduler_decisions=True`)"), kind="warn")

        if sched is not None:
            sched_summary_rows = [
                {"k": "parallel_layers", "v": int(sched.parallel_layers)},
                {"k": "serial_layers", "v": int(sched.serial_layers)},
            ]

            reasons_df = pd.DataFrame(
                [{"reason": k, "count": int(v)} for k, v in sorted(sched.serial_reasons.items(), key=lambda kv: (-int(kv[1]), str(kv[0])))]
            )
            if len(reasons_df):
                reasons_chart = (
                    alt.Chart(reasons_df)
                    .mark_bar()
                    .encode(
                        y=alt.Y("reason:N", title="reason", sort="-x"),
                        x=alt.X("count:Q", title="count"),
                        tooltip=[alt.Tooltip("reason:N"), alt.Tooltip("count:Q")],
                    )
                    .properties(width=520, height=220, title="Serial Reasons")
                )
                serial_reasons_view = mo.ui.altair_chart(reasons_chart)
            else:
                serial_reasons_view = mo.callout(mo.md("本次 adaptive 没有串行层(全部为 parallel)"), kind="info")

            backend_df = pd.DataFrame(
                [{"backend": k, "count": int(v)} for k, v in sorted(sched.backend_counts.items(), key=lambda kv: (-int(kv[1]), str(kv[0])))]
            )
            if len(backend_df):
                backend_chart = (
                    alt.Chart(backend_df)
                    .mark_bar()
                    .encode(
                        y=alt.Y("backend:N", title="backend", sort="-x"),
                        x=alt.X("count:Q", title="count"),
                        tooltip=[alt.Tooltip("backend:N"), alt.Tooltip("count:Q")],
                    )
                    .properties(width=520, height=200, title="Backend Counts")
                )
                backend_view = mo.ui.altair_chart(backend_chart)
            else:
                backend_view = mo.callout(mo.md("未记录到 backend_counts(可能未触发调度事件)"), kind="info")

        mo.md("### 可视化面板(交互式)")
        mo.tabs(
            {
                "性能": mo.vstack(
                    [
                        mo.ui.altair_chart(perf_chart, chart_selection="interval", legend_selection=False),
                        mo.ui.table(perf_df.to_dict(orient="records"), selection=None),
                    ]
                ),
                "阶段": mo.vstack(
                    [
                        mo.ui.altair_chart(stage_chart, chart_selection="interval"),
                        mo.ui.table(stage_rows, selection=None),
                    ]
                ),
                "按批次": mo.vstack([mo.ui.altair_chart(spans_chart, chart_selection="interval")]),
                "调度": mo.vstack([mo.ui.table(sched_summary_rows, selection=None), serial_reasons_view, backend_view]),
            }
        )

        if show_details.value:
            decisions = []
            for ev in getattr(collector_adp, "scheduler_decisions", [])[:30]:
                decisions.append(
                    {
                        "batch": getattr(ev, "batch_num", None),
                        "layer": getattr(ev, "layer_index", None),
                        "decision": getattr(ev, "decision", None),
                        "backend": getattr(ev, "backend", None),
                        "reason": getattr(ev, "reason", None),
                        "tasks": getattr(ev, "layer_task_count", None),
                    }
                )

            adp_sched = metrics_adp.adaptive_scheduler.to_dict() if metrics_adp.adaptive_scheduler is not None else {}
            mo.accordion(
                {
                    "调度摘要(raw)": mo.ui.table([{"k": k, "v": v} for k, v in adp_sched.items()], selection=None),
                    "每层决策日志(前 30 条)": mo.ui.table(decisions, selection=None),
                },
                multiple=True,
                lazy=True,
            )

    # ------------------------------------------------------------------
    # 场景 D: `rows-binding` 屏障最小模型
    # ------------------------------------------------------------------
    if case.value == "rows_binding_barrier":
        n = int(order_count.value)
        k = 10
        main_rows = [{"id": i, "fk": i % k} for i in range(n)]

        def load_main():
            return list(main_rows)

        def load_fk_batch_count(*, batch_rows):
            counts = {}
            for row in batch_rows or []:
                fk = row.get("fk")
                if fk is None:
                    continue
                counts[fk] = counts.get(fk, 0) + 1
            return {fk: {"fk": fk, "fk_batch_count": c} for fk, c in counts.items()}

        def rows_params(ctx):
            return (), {"batch_rows": list(ctx.batch_rows or [])}

        main = MainSourceIr(source_id="main", loader=load_main)
        ref = SourceIr(
            source_id="fk_batch",
            key=KeyIr(key="fk"),
            loader_spec=LoaderIr(
                callable=load_fk_batch_count,
                bindings={
                    "fk": BindingIr(
                        key_field="fk",
                        params_builder=rows_params,
                        mode="rows",
                        cache_mode="none",
                    )
                },
            ),
        )

        fields = [
            FieldIr(field_id="id", name="id", source=main, is_primary=True),
            FieldIr(field_id="fk", name="fk", source=main),
            FieldIr(
                field_id="fk_batch_count",
                name="fk_batch_count",
                source=ref,
                relation=main["fk"].join(ref["fk"]),
            ),
        ]

        demand = DemandIr.from_irs(sources=[ref], fields=fields, main_source=main, batch_size_hint=int(batch_size.value))
        targets = ["id", "fk", "fk_batch_count"]

        rows_seq, wall_seq, metrics_seq, collector_seq = run_scalim(
            demand=demand,
            targets=targets,
            main_rows=list(main_rows),
            parallel_mode="seq",
            max_workers_value=0,
            tuning=tuning,
        )
        rows_adp, wall_adp, metrics_adp, collector_adp = run_scalim(
            demand=demand,
            targets=targets,
            main_rows=list(main_rows),
            parallel_mode="adaptive",
            max_workers_value=int(max_workers.value),
            tuning=tuning,
        )

        def build_baseline(rows, bs):
            out = []
            for offset in range(0, len(rows), bs):
                batch = rows[offset : offset + bs]
                counts = {}
                for r in batch:
                    fk = r.get("fk")
                    if fk is None:
                        continue
                    counts[fk] = counts.get(fk, 0) + 1
                for r in batch:
                    fk = r.get("fk")
                    out.append({"id": r.get("id"), "fk": fk, "fk_batch_count": counts.get(fk)})
            return out

        baseline = build_baseline(list(main_rows), int(batch_size.value))

        cmp_seq_adp = compare_rows(rows_seq, rows_adp, key_field="id", fields=targets, float_abs_tol=abs_tol)
        cmp_seq_py = compare_rows(rows_seq, baseline, key_field="id", fields=targets, float_abs_tol=abs_tol)
        cmp_adp_py = compare_rows(rows_adp, baseline, key_field="id", fields=targets, float_abs_tol=abs_tol)

        speedup = (wall_seq / wall_adp) if wall_adp > 0 else 0.0

        mo.hstack(
            [
                mo.stat(value="{:.4f}s".format(wall_seq), label="seq wall", bordered=True),
                mo.stat(value="{:.4f}s".format(wall_adp), label="adaptive wall", bordered=True),
                mo.stat(value="{:.2f}x".format(speedup), label="speedup(seq/adp)", bordered=True),
            ],
            justify="start",
            gap=1,
        )

        mo.md(
            """
            ### 三方对拍(屏障案例)

            - seq vs adaptive: **{}**
            - seq vs 纯Py基准: **{}**
            - adaptive vs 纯Py基准: **{}**
            """.format(
                "✅ PASS" if cmp_seq_adp["passed"] else "❌ FAIL",
                "✅ PASS" if cmp_seq_py["passed"] else "❌ FAIL",
                "✅ PASS" if cmp_adp_py["passed"] else "❌ FAIL",
            )
        )

        import altair as alt  # noqa: PLC0415
        import pandas as pd  # noqa: PLC0415

        seq_stage = metrics_seq.stage_metrics.to_dict()
        adp_stage = metrics_adp.stage_metrics.to_dict()
        stage_rows = []
        for stage in ("loader", "compute", "write"):
            seq_s = float(seq_stage.get(stage) or 0.0)
            adp_s = float(adp_stage.get(stage) or 0.0)
            stage_rows.append(
                {
                    "stage": stage,
                    "seq_s": round(seq_s, 4),
                    "adaptive_s": round(adp_s, 4),
                    "delta_s(seq-adp)": round(seq_s - adp_s, 4),
                    "ratio(seq/adp)": round((seq_s / adp_s), 3) if adp_s > 0 else None,
                }
            )

        def _summarize_stage_spans(spans):
            by_batch = {}
            for e in spans:
                b = int(getattr(e, "batch_num", 0) or 0)
                stage = str(getattr(e, "stage", "") or "")
                dur = float(getattr(e, "duration", 0.0) or 0.0)
                row = by_batch.get(b)
                if row is None:
                    row = {"batch_num": b, "loader": 0.0, "compute": 0.0, "write": 0.0}
                    by_batch[b] = row
                if stage in row:
                    row[stage] += max(0.0, dur)
            rows = [by_batch[b] for b in sorted(by_batch.keys())]
            for r in rows:
                r["loader"] = round(float(r["loader"]), 4)
                r["compute"] = round(float(r["compute"]), 4)
                r["write"] = round(float(r["write"]), 4)
            return rows

        perf_df = pd.DataFrame(
            [
                {"mode": "seq", "wall_s": float(wall_seq)},
                {"mode": "adaptive", "wall_s": float(wall_adp)},
            ]
        )
        perf_chart = (
            alt.Chart(perf_df)
            .mark_bar()
            .encode(
                x=alt.X("mode:N", title="mode", sort=None),
                y=alt.Y("wall_s:Q", title="wall (s)"),
                color=alt.Color("mode:N", legend=None),
                tooltip=[alt.Tooltip("mode:N"), alt.Tooltip("wall_s:Q", format=".4f")],
            )
            .properties(width=520, height=180, title="Wall Time")
        )

        stage_df = pd.DataFrame(stage_rows)
        stage_long_df = stage_df.melt(
            id_vars=["stage"],
            value_vars=["seq_s", "adaptive_s"],
            var_name="mode",
            value_name="seconds",
        )
        stage_long_df["mode"] = stage_long_df["mode"].map({"seq_s": "seq", "adaptive_s": "adaptive"})
        stage_chart = (
            alt.Chart(stage_long_df)
            .mark_bar()
            .encode(
                x=alt.X("mode:N", title="mode", sort=None),
                y=alt.Y("seconds:Q", title="stage seconds"),
                color=alt.Color("stage:N", title="stage", sort=["loader", "compute", "write"]),
                tooltip=[alt.Tooltip("mode:N"), alt.Tooltip("stage:N"), alt.Tooltip("seconds:Q", format=".4f")],
            )
            .properties(width=520, height=220, title="Stage Breakdown (stacked)")
        )

        spans_seq_all = _summarize_stage_spans(getattr(collector_seq, "stage_spans", []))
        spans_adp_all = _summarize_stage_spans(getattr(collector_adp, "stage_spans", []))
        spans_df = pd.concat(
            [
                pd.DataFrame(spans_seq_all, columns=["batch_num", "loader", "compute", "write"]).assign(mode="seq"),
                pd.DataFrame(spans_adp_all, columns=["batch_num", "loader", "compute", "write"]).assign(mode="adaptive"),
            ],
            ignore_index=True,
        )
        spans_long_df = spans_df.melt(
            id_vars=["mode", "batch_num"],
            value_vars=["loader", "compute", "write"],
            var_name="stage",
            value_name="seconds",
        )
        spans_chart = (
            alt.Chart(spans_long_df)
            .mark_line(point=True)
            .encode(
                x=alt.X("batch_num:Q", title="batch"),
                y=alt.Y("seconds:Q", title="seconds"),
                color=alt.Color("stage:N", title="stage", sort=["loader", "compute", "write"]),
                column=alt.Column("mode:N", title="mode", sort=None),
                tooltip=[
                    alt.Tooltip("mode:N"),
                    alt.Tooltip("batch_num:Q"),
                    alt.Tooltip("stage:N"),
                    alt.Tooltip("seconds:Q", format=".4f"),
                ],
            )
            .properties(width=250, height=220, title="Stage Span Timeline (per batch)")
            .interactive()
        )

        sched = metrics_adp.adaptive_scheduler
        sched_summary_rows = []
        serial_reasons_view = mo.callout(mo.md("未收集到 adaptive_scheduler 指标(请确认 `include_scheduler_decisions=True`)"), kind="warn")
        backend_view = mo.callout(mo.md("未收集到 adaptive_scheduler 指标(请确认 `include_scheduler_decisions=True`)"), kind="warn")

        if sched is not None:
            sched_summary_rows = [
                {"k": "parallel_layers", "v": int(sched.parallel_layers)},
                {"k": "serial_layers", "v": int(sched.serial_layers)},
            ]

            reasons_df = pd.DataFrame(
                [{"reason": k, "count": int(v)} for k, v in sorted(sched.serial_reasons.items(), key=lambda kv: (-int(kv[1]), str(kv[0])))]
            )
            if len(reasons_df):
                reasons_chart = (
                    alt.Chart(reasons_df)
                    .mark_bar()
                    .encode(
                        y=alt.Y("reason:N", title="reason", sort="-x"),
                        x=alt.X("count:Q", title="count"),
                        tooltip=[alt.Tooltip("reason:N"), alt.Tooltip("count:Q")],
                    )
                    .properties(width=520, height=220, title="Serial Reasons")
                )
                serial_reasons_view = mo.ui.altair_chart(reasons_chart)
            else:
                serial_reasons_view = mo.callout(mo.md("本次 adaptive 没有串行层(全部为 parallel)"), kind="info")

            backend_df = pd.DataFrame(
                [{"backend": k, "count": int(v)} for k, v in sorted(sched.backend_counts.items(), key=lambda kv: (-int(kv[1]), str(kv[0])))]
            )
            if len(backend_df):
                backend_chart = (
                    alt.Chart(backend_df)
                    .mark_bar()
                    .encode(
                        y=alt.Y("backend:N", title="backend", sort="-x"),
                        x=alt.X("count:Q", title="count"),
                        tooltip=[alt.Tooltip("backend:N"), alt.Tooltip("count:Q")],
                    )
                    .properties(width=520, height=200, title="Backend Counts")
                )
                backend_view = mo.ui.altair_chart(backend_chart)
            else:
                backend_view = mo.callout(mo.md("未记录到 backend_counts(可能未触发调度事件)"), kind="info")

        mo.md("### 可视化面板(交互式)")
        mo.tabs(
            {
                "性能": mo.vstack(
                    [
                        mo.ui.altair_chart(perf_chart, chart_selection="interval", legend_selection=False),
                        mo.ui.table(perf_df.to_dict(orient="records"), selection=None),
                    ]
                ),
                "阶段": mo.vstack(
                    [
                        mo.ui.altair_chart(stage_chart, chart_selection="interval"),
                        mo.ui.table(stage_rows, selection=None),
                    ]
                ),
                "按批次": mo.vstack([mo.ui.altair_chart(spans_chart, chart_selection="interval")]),
                "调度": mo.vstack([mo.ui.table(sched_summary_rows, selection=None), serial_reasons_view, backend_view]),
            }
        )

        if show_details.value:
            decisions = []
            for ev in getattr(collector_adp, "scheduler_decisions", [])[:30]:
                decisions.append(
                    {
                        "batch": getattr(ev, "batch_num", None),
                        "layer": getattr(ev, "layer_index", None),
                        "decision": getattr(ev, "decision", None),
                        "backend": getattr(ev, "backend", None),
                        "reason": getattr(ev, "reason", None),
                        "tasks": getattr(ev, "layer_task_count", None),
                    }
                )

            adp_sched = metrics_adp.adaptive_scheduler.to_dict() if metrics_adp.adaptive_scheduler is not None else {}
            mo.accordion(
                {
                    "调度摘要(raw)": mo.ui.table([{"k": k, "v": v} for k, v in adp_sched.items()], selection=None),
                    "每层决策日志(前 30 条)": mo.ui.table(decisions, selection=None),
                },
                multiple=True,
                lazy=True,
            )
    return


@app.cell(hide_code=True)
def _(case, mo):
    mo.md(
        r"""
        ---
        ## Step 4: 使用建议与优劣权衡

        ### 何时更推荐 `adaptive`
        - ref loader 明显 **I/O 型**(网络/磁盘/远程服务),且同一批次内存在多个独立 LoadRef 任务.
        - 你愿意用可观测指标解释调度决策(建议同时启用 `PerformanceObserver` 观察 `adaptive_scheduler`).

        ### 何时更推荐 `seq`
        - ref loader 主要是 **CPU/GIL** 工作负载(纯 Python 算数/拼装大 dict),线程并行收益有限甚至更慢.
        - 工作负载很小(任务数少/查找键少),并行调度与 overlay 合并开销可能占主导.
        - 使用了 **rows-binding**(依赖 `batch_rows`)时,本层会触发屏障并串行;此时 adaptive 模式更多是“可解释的串行”.

        ### `adaptive` 是否“生产可用”?
        - **语义上**:`adaptive` 与 `seq` 应当产出一致结果(本示例用 `seq`/`adaptive`/`纯Py` 三方对拍作为底线).
        - **工程上**:是否可上线主要取决于你的 ref loader 是否满足并发前提:
          - loader **无副作用/线程安全**(避免共享可变全局状态),外部服务能承受并发与限流策略.
          - 通过 `adaptive_scheduler` 观察串行原因、pool wait、backend 选择,避免“看起来 adaptive 其实全串行”.
        - **后端差异**:
          - `thread`(默认):更适合 I/O 型 loader;CPU/GIL 型可能更慢.
          - `process`:更适合 CPU 型,但对 **pickle/上下文可序列化** 要求高,且当前与 hooks/observers 存在兼容约束(本 demo 会展示退化原因).

        ### 常见排查路径
        1. 先看 `adaptive_scheduler.serial_reasons`:为什么串行(no_pool/single_worker/below_min*/rows_binding_barrier).
        2. 再调 `max_workers` 与阈值(min_parallel_tasks / min_total_lookup_keys / min_lookup_keys_per_task).
        3. 若是 CPU/GIL 为主:考虑提升批次粒度/减少 Python 拼装开销,而非盲目加并发.
        """
    )
    if case.value == "io_latency_ref_loaders":
        _ = mo.callout(mo.md("当前选中 I/O 案例:如果你把 `delay_ms` 调到 0,通常 speedup 会快速收敛到 1x."), kind="info")
    if case.value == "cpu_bound_ref_loaders":
        _ = mo.callout(mo.md("当前选中 CPU/GIL 案例:把 `CPU burn/ID` 调大后,通常可看到 adaptive 线程并发收益有限甚至更慢."), kind="info")
    if case.value == "below_min_parallel_tasks":
        _ = mo.callout(mo.md("当前选中任务太少案例:如需更强对比,可把 `min_parallel_tasks` 调高以稳定触发串行."), kind="info")
    return


if __name__ == "__main__":
    app.run()
