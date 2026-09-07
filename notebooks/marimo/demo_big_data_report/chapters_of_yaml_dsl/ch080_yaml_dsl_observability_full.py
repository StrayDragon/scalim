"""Cells-native marimo notebook: ch080_yaml_dsl_observability_full.

迁移对照:
  Before: 模块级 run_*() 持全部逻辑;cells 薄壳
  After:  三个 observer 零件、运行、五路校验全部在 cells 内
"""

import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / yaml_dsl_observability_full

        ## 回归点

        全量可观测性装配：logging / execution_trace / memory_optimization / viz 四类
        observer 同时生效，产物（detail CSV + scalim-viz 快照/事件/跟踪）可校验。

        ## 主线装配过程（每个步骤一个 cell，可就地修改重跑）

        1. 零件：LoggingObserver / ExecutionTraceObserver / MemoryOptimizationObserver + viz 配置
        2. `run`（batch_size=2 → 固定 5 条 tickets → 3 个 batch）
        3. 产物定位（detail CSV + `scalim-viz/run_*/` 三文件）
        4. 五路断言：rows / trace batch / memory / logging / viz
        5. 汇总 chapter_result

        Gate: `just examples`
        """
    )
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    from pathlib import Path

    from scalim_misc.notebook_support.pathing import ensure_repo_root_on_sys_path

    repo_root = ensure_repo_root_on_sys_path(__file__)
    demo_dir = Path(__file__).resolve().parents[1]
    yaml_path = demo_dir / "chapters_of_yaml_dsl" / "declared_yaml_dsl" / "support" / "support_observability_full.yaml"
    _ = repo_root
    return Path, demo_dir, yaml_path


@app.cell
def _(Path):
    import csv
    import tempfile
    from typing import Any, Dict, List, Optional, Sequence, Tuple

    from scalim.dsl.yaml_dsl import (
        DemandRunOptions,
        DemandRunOutputOptions,
        DemandRunRuntimeOptions,
        DemandRunSecurityOptions,
        DemandRunTemplateOptions,
        RunOverrides,
        run as run_yaml,
    )
    from scalim.ob.presets.execution_trace import ExecutionTraceObserver
    from scalim.ob.presets.logs import LoggingObserver
    from scalim.ob.presets.memory import MemoryOptimizationObserver
    from scalim.ob.presets.viz import VizObserverConfig
    from scalim_misc.notebook_support.chapter_result import make_chapter_result, render_checks

    return (
        Any,
        DemandRunOptions,
        DemandRunOutputOptions,
        DemandRunRuntimeOptions,
        DemandRunSecurityOptions,
        DemandRunTemplateOptions,
        Dict,
        ExecutionTraceObserver,
        List,
        LoggingObserver,
        MemoryOptimizationObserver,
        Optional,
        Path,
        RunOverrides,
        Sequence,
        Tuple,
        VizObserverConfig,
        csv,
        make_chapter_result,
        render_checks,
        run_yaml,
        tempfile,
    )


@app.cell
def _(Any, Dict, List, Optional, Path, Sequence, Tuple, csv):
    # 零件: CSV 读取 / observer 查找 / viz 产物定位
    def read_csv_rows(path: Path) -> List[Dict[str, str]]:
        rows: List[Dict[str, str]] = []
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                if not row:
                    continue
                rows.append({str(k): str(v) if v is not None else "" for k, v in row.items()})
        return rows

    def find_first_instance(components: Optional[Sequence[object]], cls: type) -> Optional[object]:
        for c in components or ():
            if isinstance(c, cls):
                return c
        return None

    def glob_viz_files(base_dir: Path) -> Dict[str, str]:
        scalim_viz_dir = base_dir / "scalim-viz"
        run_dirs = sorted([p for p in scalim_viz_dir.glob("run_*") if p.is_dir()]) if scalim_viz_dir.exists() else []
        if len(run_dirs) != 1:
            return {"runs": str(len(run_dirs)), "dir": str(scalim_viz_dir)}
        run_dir = run_dirs[0]
        return {
            "run_dir": str(run_dir),
            "snapshot": str(run_dir / "viz_snapshot.json"),
            "events": str(run_dir / "viz_events.jsonl"),
            "trace": str(run_dir / "viz_trace.jsonl"),
        }

    return find_first_instance, glob_viz_files, read_csv_rows


@app.cell
def _(Path, tempfile):
    import atexit
    import shutil

    tmp = Path(tempfile.mkdtemp(prefix="scalim-ob-full-"))
    atexit.register(lambda: shutil.rmtree(tmp, ignore_errors=True))
    out_root_detail = tmp / "out_detail"
    viz_base_dir = tmp / "viz_out"
    ALLOWED_MODULES = frozenset(["scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario"])
    print("tmp dir:", tmp)
    return ALLOWED_MODULES, out_root_detail, tmp, viz_base_dir


@app.cell
def _(
    Dict,
    ExecutionTraceObserver,
    LoggingObserver,
    MemoryOptimizationObserver,
    RunOverrides,
    VizObserverConfig,
    out_root_detail,
    viz_base_dir,
):
    # 装配: 四类可观测性 + viz 配置
    init_vars: Dict[str, object] = {"out_path_detail": str(out_root_detail)}
    overrides = RunOverrides(
        viz_config=VizObserverConfig(
            output_dir=str(viz_base_dir),
            trace_enabled=True,
            payload_policy="sample",
            sample_size=3,
            append=False,
            run_name="support-observability",
            env="ci",
        )
    )
    components = [
        LoggingObserver(),
        ExecutionTraceObserver(),
        MemoryOptimizationObserver(auto_report=False, max_fields=10),
    ]
    return components, init_vars, overrides


@app.cell
def _(
    ALLOWED_MODULES,
    DemandRunOptions,
    DemandRunOutputOptions,
    DemandRunRuntimeOptions,
    DemandRunSecurityOptions,
    DemandRunTemplateOptions,
    ExecutionTraceObserver,
    LoggingObserver,
    MemoryOptimizationObserver,
    Path,
    components,
    find_first_instance,
    init_vars,
    out_root_detail,
    overrides,
    run_yaml,
    yaml_path,
):
    result = run_yaml(
        str(yaml_path),
        options=DemandRunOptions(
            security=DemandRunSecurityOptions(allowed_modules=ALLOWED_MODULES),
            template=DemandRunTemplateOptions(init_vars=init_vars),
            runtime=DemandRunRuntimeOptions(components=components, batch_size=2),
            outputs=DemandRunOutputOptions(overrides=overrides),
        ),
    )
    trace_observer = find_first_instance(components, ExecutionTraceObserver)
    memory_opt_observer = find_first_instance(components, MemoryOptimizationObserver)
    logging_observer = find_first_instance(components, LoggingObserver)
    core = result.core

    detail_csv_path = Path(str((core.outputs or {}).get("detail") or ""))
    print("total_rows =", core.total_rows)
    print("outputs    =", sorted(core.outputs.keys()) if core.outputs else None)
    return core, detail_csv_path, logging_observer, memory_opt_observer, result, trace_observer


@app.cell
def _(
    ExecutionTraceObserver,
    LoggingObserver,
    MemoryOptimizationObserver,
    Path,
    core,
    detail_csv_path,
    find_first_instance,
    glob_viz_files,
    logging_observer,
    memory_opt_observer,
    read_csv_rows,
    trace_observer,
    viz_base_dir,
):
    # 产物 + 五路校验
    rows = read_csv_rows(detail_csv_path) if detail_csv_path.exists() else []
    trace = trace_observer if isinstance(trace_observer, ExecutionTraceObserver) else None
    mem = memory_opt_observer if isinstance(memory_opt_observer, MemoryOptimizationObserver) else None
    log = logging_observer if isinstance(logging_observer, LoggingObserver) else None

    viz_files = glob_viz_files(viz_base_dir)
    snapshot_ok = Path(viz_files.get("snapshot") or "").exists() if "snapshot" in viz_files else False
    events_ok = Path(viz_files.get("events") or "").exists() if "events" in viz_files else False
    trace_ok_file = Path(viz_files.get("trace") or "").exists() if "trace" in viz_files else False

    # 固定 5 条 tickets, batch_size=2 -> 3 个 batch(2,2,1)
    ok_trace = bool(trace and len(trace.batches) == 3 and trace.total_loader_calls >= 1)
    ok_memory = bool(mem and len(mem.row_write_events) >= 5)
    ok_logging = bool(log is not None)
    ok_viz = bool(snapshot_ok and events_ok and trace_ok_file)
    ok_rows = bool(len(rows) == 5 and core.total_rows == 5)

    print("rows=", ok_rows, "trace=", ok_trace, "memory=", ok_memory, "logging=", ok_logging, "viz=", ok_viz)
    return (
        log,
        mem,
        ok_logging,
        ok_memory,
        ok_rows,
        ok_trace,
        ok_viz,
        rows,
        trace,
        trace_ok_file,
        events_ok,
        snapshot_ok,
        viz_files,
    )


@app.cell
def _(ok_logging, ok_memory, ok_rows, ok_trace, ok_viz, render_checks):
    checks = {
        "rows == 5": ok_rows,
        "trace 3 batches": ok_trace,
        "memory 事件 >= 5": ok_memory,
        "logging observer 装配": ok_logging,
        "viz 三文件存在": ok_viz,
    }
    render_checks(checks)
    return checks


@app.cell
def _(
    checks,
    detail_csv_path,
    make_chapter_result,
    ok_logging,
    ok_memory,
    ok_rows,
    ok_trace,
    ok_viz,
    out_root_detail,
    rows,
    viz_files,
    yaml_path,
):
    passed = bool(all(checks.values()))
    summary = "rows={} trace={} memory_opt={} logging={} viz={}".format(ok_rows, ok_trace, ok_memory, ok_logging, ok_viz)
    # 对拍期望（教学 payload；headless 可经 details 键定位）
    expected = {"rows": 5, "trace_batches": 3, "memory_events_gte": 5, "logging_observer_wired": True, "viz_files_present": True}
    print("expected:", expected)

    chapter_result = make_chapter_result(
        passed=passed,
        summary=summary,
        details={
            "expected": expected,
            "yaml_path": str(yaml_path),
            "out_root_detail": str(out_root_detail),
            "detail_csv": str(detail_csv_path),
            "rows": len(rows),
            "viz": viz_files,
            "checks": {k: bool(v) for k, v in checks.items()},
        },
    )
    return chapter_result, passed, summary


@app.cell(hide_code=True)
def _(chapter_result, mo):
    mo.callout(
        mo.md("## {}: {}".format("✅ PASS" if chapter_result["passed"] else "❌ FAIL", chapter_result["summary"])),
        kind="success" if chapter_result["passed"] else "danger",
    )
    return


@app.cell(hide_code=True)
def _(chapter_result, mo):
    from scalim_misc.notebook_support.results_view import details_to_rows

    table_rows = details_to_rows(chapter_result["details"])
    mo.ui.table(table_rows, selection=None) if table_rows else mo.md("(无详情)")
    return


def run_chapter():
    """SSOT 入口：headless runner 与 pytest 通过此函数执行对拍。"""
    outputs, defs = app.run()
    return defs["chapter_result"]


if __name__ == "__main__":
    app.run()
