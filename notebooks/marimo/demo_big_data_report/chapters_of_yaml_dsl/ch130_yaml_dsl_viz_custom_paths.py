"""Cells-native marimo notebook: ch130_yaml_dsl_viz_custom_paths.

迁移对照:
  Before: 模块级 run_*() 持全部逻辑;cells 薄壳
  After:  viz 自定义路径配置、运行、产物/snapshot 校验全部在 cells 内
"""

import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / yaml_dsl_viz_custom_paths

        ## 回归点

        `VizObserverConfig` 自定义路径（output_path/snapshot_path/trace）：
        viz 事件/snapshot/trace 落在指定文件，snapshot meta 携带 run_name/env。

        ## 主线装配过程（每个步骤一个 cell，可就地修改重跑）

        1. 装配 `RunOverrides(viz_config=...)`（3 个自定义路径）
        2. `run` → detail CSV + viz 三文件
        3. 断言：行数 + 三文件非空 + snapshot meta(run_name/env)
        4. 汇总 chapter_result

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
    yaml_path = demo_dir / "chapters_of_yaml_dsl" / "declared_yaml_dsl" / "support" / "support_viz_custom_paths.yaml"
    _ = repo_root
    return Path, demo_dir, yaml_path


@app.cell
def _(Path):
    import csv
    import json
    import tempfile
    from typing import Any, Dict, List, Optional

    from scalim.dsl.yaml_dsl import (
        DemandRunOptions,
        DemandRunOutputOptions,
        DemandRunRuntimeOptions,
        DemandRunSecurityOptions,
        DemandRunTemplateOptions,
        RunOverrides,
        run as run_yaml,
    )
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
        List,
        Optional,
        Path,
        RunOverrides,
        VizObserverConfig,
        csv,
        json,
        make_chapter_result,
        render_checks,
        run_yaml,
        tempfile,
    )


@app.cell
def _(Dict, List, Path, csv):
    # 零件: CSV 读取
    def read_csv_rows(path: Path) -> List[Dict[str, str]]:
        rows: List[Dict[str, str]] = []
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                if not row:
                    continue
                rows.append({str(k): str(v) if v is not None else "" for k, v in row.items()})
        return rows

    return read_csv_rows


@app.cell
def _(Path, tempfile):
    import atexit
    import shutil

    tmp = Path(tempfile.mkdtemp(prefix="scalim-viz-custom-"))
    atexit.register(lambda: shutil.rmtree(tmp, ignore_errors=True))
    out_root_detail = tmp / "out_detail"
    viz_events = tmp / "viz_events.jsonl"
    viz_snapshot = tmp / "viz_snapshot.json"
    viz_trace = tmp / "viz_trace.jsonl"
    ALLOWED_MODULES = frozenset(["scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario"])
    print("tmp dir:", tmp)
    return ALLOWED_MODULES, out_root_detail, tmp, viz_events, viz_snapshot, viz_trace


@app.cell
def _(ALLOWED_MODULES, Dict, DemandRunOptions, DemandRunOutputOptions, DemandRunRuntimeOptions, DemandRunSecurityOptions, DemandRunTemplateOptions, RunOverrides, VizObserverConfig, out_root_detail, run_yaml, viz_events, viz_snapshot, viz_trace, yaml_path):
    # 装配: viz 自定义路径
    init_vars: Dict[str, object] = {"out_path_detail": str(out_root_detail)}
    overrides = RunOverrides(
        viz_config=VizObserverConfig(
            output_path=str(viz_events),
            snapshot_path=str(viz_snapshot),
            trace_enabled=True,
            payload_policy="sample",
            sample_size=2,
            append=False,
            run_name="support-viz-custom-paths",
            env="ci",
        )
    )
    result = run_yaml(
        str(yaml_path),
        options=DemandRunOptions(
            security=DemandRunSecurityOptions(allowed_modules=ALLOWED_MODULES),
            template=DemandRunTemplateOptions(init_vars=init_vars),
            runtime=DemandRunRuntimeOptions(batch_size=2),
            outputs=DemandRunOutputOptions(overrides=overrides),
        ),
    )
    core = result.core
    print("total_rows =", core.total_rows)
    return core, init_vars, overrides, result


@app.cell
def _(Any, Dict, Path, core, json, read_csv_rows, viz_events, viz_snapshot, viz_trace):
    # 产物定位 + snapshot meta 校验
    detail_csv_path = Path(str((core.outputs or {}).get("detail") or ""))
    rows = read_csv_rows(detail_csv_path) if detail_csv_path.exists() else []
    events_ok = viz_events.exists() and viz_events.stat().st_size > 0
    snapshot_ok = viz_snapshot.exists() and viz_snapshot.stat().st_size > 0
    trace_ok = viz_trace.exists() and viz_trace.stat().st_size > 0

    snapshot_meta: Dict[str, Any] = {}
    if snapshot_ok:
        snapshot_meta = json.loads(viz_snapshot.read_text(encoding="utf-8")).get("meta") or {}
    viz_meta = snapshot_meta.get("viz") if isinstance(snapshot_meta, dict) else {}
    run_name_ok = isinstance(viz_meta, dict) and viz_meta.get("run_name") == "support-viz-custom-paths"
    env_ok = isinstance(viz_meta, dict) and viz_meta.get("env") == "ci"
    print("rows=", len(rows), "events=", events_ok, "snapshot=", snapshot_ok, "trace=", trace_ok)
    return (
        detail_csv_path,
        env_ok,
        events_ok,
        rows,
        run_name_ok,
        snapshot_ok,
        snapshot_meta,
        trace_ok,
        viz_meta,
    )


@app.cell
def _(core, env_ok, events_ok, render_checks, rows, run_name_ok, snapshot_ok, trace_ok):
    checks = {
        "rows == 5": len(rows) == 5,
        "viz events 文件非空": events_ok,
        "viz snapshot 文件非空": snapshot_ok,
        "viz trace 文件非空": trace_ok,
        "snapshot run_name 正确": run_name_ok,
        "snapshot env 正确": env_ok,
        "输出非空": bool(core.outputs),
    }
    render_checks(checks)
    return checks


@app.cell
def _(checks, core, detail_csv_path, env_ok, events_ok, make_chapter_result, out_root_detail, rows, run_name_ok, snapshot_ok, trace_ok, viz_events, viz_meta, viz_snapshot, viz_trace, yaml_path):
    passed = bool(all(checks.values()))
    summary = "rows={} events={} snapshot={} trace={} run_name={} env={} outputs={}".format(
        len(rows),
        events_ok,
        snapshot_ok,
        trace_ok,
        run_name_ok,
        env_ok,
        sorted(core.outputs.keys()) if core.outputs else None,
    )
    chapter_result = make_chapter_result(
        passed=passed,
        summary=summary,
        details={
            "yaml_path": str(yaml_path),
            "out_root_detail": str(out_root_detail),
            "detail_csv": str(detail_csv_path),
            "rows": len(rows),
            "viz_paths": {
                "events": str(viz_events),
                "snapshot": str(viz_snapshot),
                "trace": str(viz_trace),
            },
            "snapshot_meta_viz": viz_meta,
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