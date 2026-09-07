"""Cells-native marimo notebook: ch050_workflow_viz_finished.

迁移对照 (ch010 同款):
  Before: 薄壳 cells + support/workflow_viz_finished.py 持有全部主路径
  After:  LifecycleMarker 零件、viz 配置、装配、断言全部在 cells 内
"""

import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # example_hooks_events_scenarios / ch050_workflow_viz_finished

        演示：**启用 workflow viz 后收到 `WORKFLOW_STARTED` / `WORKFLOW_FINISHED`**。

        主线装配过程（每个步骤一个 cell，可就地修改重跑）：

        1. 定义零件：`WorkflowLifecycleMarker` Observer（记录生命周期事件）
        2. 写入 demand / workflow YAML；组装带 `VizObserverConfig` 的选项
        3. 运行 workflow → viz 事件流落盘 + Observer 捕获 STARTED/FINISHED
        4. 证据核对：seen 序列 + viz_events 文件
        5. 断言展开 → chapter_result

        注意: 无 viz 时 `WORKFLOW_STARTED/FINISHED` 不发 —— 用 `WORKFLOW_NODE_*` 替代(见 ch010)。

        Gate: `just examples` / `tests/integration/test_example_hooks_events_scenarios.py`
        """
    )
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    from scalim_misc.notebook_support.pathing import ensure_repo_root_on_sys_path

    repo_root = ensure_repo_root_on_sys_path(__file__)
    return (repo_root,)


@app.cell
def _(repo_root):
    import tempfile
    from dataclasses import replace
    from pathlib import Path
    from typing import Any, Dict, List, Optional, Set

    from scalim.dsl import yaml_dsl as api
    from scalim.dsl.yaml_dsl.workflow_types import WorkflowExecutionOptions, WorkflowRunOptions, WorkflowRuntimeOptions
    from scalim.events import EventType
    from scalim.ob.observer import Observer
    from scalim.ob.presets.viz import VizObserverConfig
    from scalim_misc.notebook_support.chapter_result import make_chapter_result, render_checks
    from notebooks.marimo.example_hooks_events_scenarios.support.fixtures import (
        ALLOWED_MODULES,
        write_minimal_demand_yaml,
        write_minimal_workflow_yaml,
    )

    _ = repo_root
    return (
        ALLOWED_MODULES,
        Any,
        Dict,
        EventType,
        List,
        Observer,
        Optional,
        Path,
        Set,
        VizObserverConfig,
        WorkflowExecutionOptions,
        WorkflowRunOptions,
        WorkflowRuntimeOptions,
        api,
        make_chapter_result,
        render_checks,
        replace,
        tempfile,
        write_minimal_demand_yaml,
        write_minimal_workflow_yaml,
    )


@app.cell
def _(Any, Dict, EventType, List, Observer, Optional, Set):
    # 零件: 记录 WORKFLOW_STARTED / WORKFLOW_FINISHED(仅启用 workflow viz 时发出)
    class WorkflowLifecycleMarker(Observer):
        def __init__(self) -> None:
            self.event_types: Optional[Set[EventType]] = {
                EventType.WORKFLOW_STARTED,
                EventType.WORKFLOW_FINISHED,
            }
            self.started = 0
            self.finished = 0
            self.last_finished_status: Optional[str] = None
            self.seen: List[str] = []

        def on_event(self, event: Any) -> None:
            event_type = getattr(event, "event_type", None)
            if event_type == EventType.WORKFLOW_STARTED:
                self.started += 1
                self.seen.append("workflow_started")
                return
            if event_type == EventType.WORKFLOW_FINISHED:
                self.finished += 1
                self.seen.append("workflow_finished")
                payload = getattr(event, "payload", None)
                self.last_finished_status = None if payload is None else str(getattr(payload, "status", None))

    # 零件: 运行选项工厂 — 开启 viz 是收到生命周期事件的必要条件
    def demand_options(*, output_root: Path, viz_dir: Path) -> api.DemandRunOptions:
        csv = api.RunOverrides.csv_file(
            output_root=str(output_root),
            fields=["item_id", "dim_id"],
            header_fields_output_by="name",
        )
        overrides = replace(
            csv,
            viz_config=VizObserverConfig(
                output_dir=str(viz_dir),
                payload_policy="summary",
                run_name="hooks-events-workflow-viz",
            ),
        )
        return api.DemandRunOptions(
            security=api.DemandRunSecurityOptions(allowed_modules=ALLOWED_MODULES),
            runtime=api.DemandRunRuntimeOptions(batch_size=10),
            outputs=api.DemandRunOutputOptions(overrides=overrides),
        )

    return WorkflowLifecycleMarker, demand_options


@app.cell
def _(Path, tempfile):
    import atexit
    import shutil

    tmp = Path(tempfile.mkdtemp(prefix="scalim-hooks-ch050-"))
    atexit.register(lambda: shutil.rmtree(tmp, ignore_errors=True))
    print("tmp dir:", tmp)
    return (tmp,)


@app.cell
def _(mo, tmp, write_minimal_demand_yaml, write_minimal_workflow_yaml):
    demand_path = write_minimal_demand_yaml(tmp / "demand.yaml")
    workflow_path = write_minimal_workflow_yaml(tmp / "workflow.yaml", demand_rel="demand.yaml")

    demand_yaml_text = demand_path.read_text(encoding="utf-8")
    workflow_yaml_text = workflow_path.read_text(encoding="utf-8")

    mo.md("**demand.yaml**:\n\n```yaml\n{}\n```\n\n**workflow.yaml**:\n\n```yaml\n{}\n```".format(demand_yaml_text, workflow_yaml_text))
    return demand_path, demand_yaml_text, workflow_path, workflow_yaml_text


@app.cell
def _(
    WorkflowLifecycleMarker,
    WorkflowExecutionOptions,
    WorkflowRunOptions,
    WorkflowRuntimeOptions,
    api,
    demand_options,
    demand_path,
    tmp,
    workflow_path,
):
    viz_dir = tmp / "viz"
    marker = WorkflowLifecycleMarker()

    result = api.run_workflow(
        str(workflow_path),
        options=WorkflowRunOptions(
            demand=demand_options(output_root=tmp / "out", viz_dir=viz_dir),
            runtime=WorkflowRuntimeOptions(
                execution=WorkflowExecutionOptions(max_concurrency=1, failure_policy="all_fail"),
            ),
            workflow_components=(marker,),
        ),
    )

    viz_events = list(viz_dir.rglob("viz_events.jsonl"))
    print("started =", marker.started, "finished =", marker.finished, "status =", marker.last_finished_status)
    print("seen    =", marker.seen)
    print("viz_events_files =", len(viz_events))

    return marker, result, viz_dir, viz_events


@app.cell
def _(marker, mo, viz_dir, viz_events):
    mo.ui.tabs(
        {
            "生命周期事件流": mo.ui.table([{"seen": s} for s in marker.seen], selection=None),
            "viz 事件文件": mo.ui.table([{"file": str(p.relative_to(viz_dir))} for p in viz_events], selection=None),
        }
    )
    return


@app.cell
def _(marker, render_checks, result, viz_events):
    checks = {
        "workflow 运行成功": result is not None,
        "started == 1": marker.started == 1,
        "finished == 1": marker.finished == 1,
        "finished status == ok": marker.last_finished_status == "ok",
        "seen 序列正确": marker.seen == ["workflow_started", "workflow_finished"],
        "viz 事件落盘": len(viz_events) >= 1,
    }
    render_checks(checks)
    return checks


@app.cell
def _(checks, make_chapter_result, marker, viz_events):
    passed = bool(all(checks.values()))
    summary = "started={} finished={} status={} viz_events_files={} seen={}".format(
        marker.started,
        marker.finished,
        marker.last_finished_status,
        len(viz_events),
        marker.seen,
    )
    chapter_result = make_chapter_result(
        passed=passed,
        summary=summary,
        details={
            "seen": list(marker.seen),
            "finished_status": marker.last_finished_status,
            "viz_events": [str(p) for p in viz_events],
            "checks": {k: bool(v) for k, v in checks.items()},
            "note": (
                "WORKFLOW_STARTED/FINISHED require workflow viz "
                "(demand.outputs.overrides.viz_config.output_dir); "
                "without viz use WORKFLOW_NODE_* instead (see ch010)"
            ),
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

    rows = details_to_rows(chapter_result["details"])
    mo.ui.table(rows, selection=None) if rows else mo.md("(无详情)")
    return


def run_chapter():
    """SSOT 入口: headless runner / pytest 通过此函数执行对拍。"""
    outputs, defs = app.run()
    return defs["chapter_result"]


if __name__ == "__main__":
    app.run()
