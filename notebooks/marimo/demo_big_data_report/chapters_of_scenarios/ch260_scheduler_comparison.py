"""Cells-native marimo notebook: ch260_scheduler_comparison.

迁移对照:
  Before: 装配/运行虽在 cells,但无章节契约（无 expected 快照、无标准教学结构、
          chapter_result 用裸 dict 组装）
  After:  装配窥视 / 双 scheduler 运行 / 对拍断言全部在 cells 内逐步展开,
          run_chapter() 薄适配层 + make_chapter_result（r1114 expected 前缀键）
"""

import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / chapters_of_scenarios / ch260_scheduler_comparison

        对比 workflow 两种 scheduler preset（`pipeline` / `stage_barrier`）的吞吐/并行度差异。
        通过 loader 内 sleep 放大差异便于观察。

        ## 主线装配过程（每个步骤一个 cell，可就地修改重跑）

        1. 复杂可复用零件：`loaders.py` 的 medium/slow loader（sleep 模拟耗时）+ `Recorder` Observer
        2. 装配：写 demand / workflow YAML（3 个 run：a、x 并行，b depends_on a）
        3. **装配窥视**：渲染 YAML 内容与两种 scheduler preset（读者无需跳库）
        4. 双 scheduler 运行：同一 workflow 各跑一次，计时 + 事件采集
        5. 汇总：wall_s / max_concurrent / stage_gap
        6. 断言展开 + `make_chapter_result`（含 r1114 `expected` 快照）

        对拍入口: `run_chapter()` → `app.run()` → `chapter_result`
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
    from scalim_misc.notebook_support.pathing import ensure_repo_root_on_sys_path

    repo_root = ensure_repo_root_on_sys_path(__file__)
    return (repo_root,)


@app.cell
def _():
    import threading
    import time
    from pathlib import Path

    from scalim.dsl.yaml_dsl import DemandRunOptions, DemandRunSecurityOptions, WorkflowRunOptions, run_workflow
    from scalim.dsl.yaml_dsl.workflow_types import (
        PipelineSchedulerOptions,
        StageBarrierSchedulerOptions,
        WorkflowExecutionOptions,
        WorkflowRuntimeOptions,
    )
    from scalim.events import EventType
    from scalim.ob.observer import Observer
    from scalim_misc.notebook_support.chapter_result import make_chapter_result, render_checks

    return (
        DemandRunOptions,
        DemandRunSecurityOptions,
        EventType,
        Observer,
        Path,
        PipelineSchedulerOptions,
        StageBarrierSchedulerOptions,
        WorkflowExecutionOptions,
        WorkflowRuntimeOptions,
        WorkflowRunOptions,
        make_chapter_result,
        render_checks,
        run_workflow,
        threading,
        time,
    )


@app.cell
def _(repo_root):
    tmp_dir = repo_root / ".tmp" / "artifacts" / "demo_big_data_report"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    loaders_module = "scalim_misc.demo_big_data_report.stage_perf_loaders"
    return loaders_module, tmp_dir


@app.cell
def _(Path, loaders_module, tmp_dir):
    # ① 装配：写 3 个 demand YAML（a/x 用 medium loader，x 用 slow loader）+ 1 个 workflow YAML
    #   （b depends_on a，制造跨 stage 依赖）。
    def _w(path, text):
        path.write_text(text, encoding="utf-8")
        return path

    def _dyaml(name, ref):
        return _w(
            tmp_dir / f"{name}.yaml",
            f"""name: {name}\nmain_source:\n  source_id: orders\n  loader: {ref}\n  fields:\n    order_id:\n      extract: order_id\nsources: {{}}\noutputs: []\n""",
        )

    demand_a = _dyaml("a", f"{loaders_module}:load_orders_medium")
    demand_x = _dyaml("x", f"{loaders_module}:load_orders_slow")
    demand_b = _dyaml("b", f"{loaders_module}:load_orders_medium")
    wf = _w(
        tmp_dir / "workflow.yaml",
        "workflow:\n  runs:\n    - id: a\n      demand: a.yaml\n    - id: x\n      demand: x.yaml\n    - id: b\n      demand: b.yaml\n      depends_on:\n        - a\n",
    )
    workflow_path = str(wf)
    print(f"workflow written: {workflow_path}")
    return demand_a, demand_b, demand_x, wf, workflow_path


@app.cell(hide_code=True)
def _(demand_a, mo, wf):
    # ② 装配窥视：YAML 内容与 scheduler preset 直接可见，读者无需跳库。
    #   - loaders 是可复用零件（sleep 模拟耗时），经 `loaders_module:函数` 引用进 demand。
    #   - `PipelineSchedulerOptions`: 跨 stage 流水推进（b 在 a 完成后即可启动）。
    #   - `StageBarrierSchedulerOptions`: stage 间栅栏同步（stage 0 全部结束后才进 stage 1）。
    mo.vstack(
        [
            mo.md("**装配窥视（读者无需跳库）**——workflow / demand YAML："),
            mo.md("```yaml\n" + wf.read_text(encoding="utf-8") + "```"),
            mo.md("```yaml\n" + demand_a.read_text(encoding="utf-8") + "```"),
        ]
    )
    return


@app.cell
def _(EventType, Observer, threading):
    # ③ 零件：Recorder Observer 记录 WORKFLOW_NODE_START/END/CANCELLED 事件流。
    class Recorder(Observer):
        event_types = {EventType.WORKFLOW_NODE_START, EventType.WORKFLOW_NODE_END, EventType.WORKFLOW_NODE_CANCELLED}

        def __init__(self):
            self._lock = threading.Lock()
            self.events: list = []

        def on_event(self, event):
            with self._lock:
                self.events.append(event)

    return (Recorder,)


@app.cell
def _(
    DemandRunOptions,
    DemandRunSecurityOptions,
    PipelineSchedulerOptions,
    Recorder,
    StageBarrierSchedulerOptions,
    WorkflowExecutionOptions,
    WorkflowRuntimeOptions,
    WorkflowRunOptions,
    loaders_module,
    run_workflow,
    time,
    workflow_path,
):
    # ④ 双 scheduler 运行：同一 workflow 各跑一次（pipeline vs stage_barrier），计时 + 事件采集。
    #   - scheduler 经 `WorkflowRuntimeOptions.execution.scheduler` 注入。
    #   - Recorder 经 `WorkflowRunOptions.workflow_components` 挂到编排层。
    def run_once(mode, max_concurrency=2):
        rec = Recorder()
        dopt = DemandRunOptions(security=DemandRunSecurityOptions(allowed_modules=frozenset([loaders_module])))
        sched = StageBarrierSchedulerOptions() if mode == "stage_barrier" else PipelineSchedulerOptions()
        rt = WorkflowRuntimeOptions(
            execution=WorkflowExecutionOptions(max_concurrency=max_concurrency, failure_policy="all_fail"), scheduler=sched
        )
        t0 = time.perf_counter()
        run_workflow(workflow_path, options=WorkflowRunOptions(demand=dopt, runtime=rt, workflow_components=(rec,)))
        return {"schedule_mode": mode, "wall_s": time.perf_counter() - t0, "events": list(rec.events)}

    pipeline_run = run_once("pipeline")
    barrier_run = run_once("stage_barrier")
    print(f"pipeline: {pipeline_run['wall_s']:.3f}s  barrier: {barrier_run['wall_s']:.3f}s")
    return barrier_run, pipeline_run


@app.cell
def _(EventType, barrier_run, pipeline_run):
    # ⑤ 汇总：从事件流还原节点时间线（start/end/duration）与峰值并发、stage 间隙。
    def summarize(run):
        events = list(run.get("events") or [])
        starts, ends, stages = {}, {}, {}
        for e in events:
            p = e.to_dict().get("payload") or {}
            nid = str(p.get("workflow_node_id", "")).strip()
            if not nid:
                continue
            if "stage" in p and p["stage"] is not None:
                stages[nid] = int(p["stage"])
            if e.event_type == EventType.WORKFLOW_NODE_START:
                starts[nid] = float(e.timestamp)
            elif e.event_type in (EventType.WORKFLOW_NODE_END, EventType.WORKFLOW_NODE_CANCELLED):
                ends[nid] = float(e.timestamp)
        base = min(starts.values()) if starts else 0.0
        rows = []
        for nid, ts in sorted(starts.items(), key=lambda kv: kv[1]):
            te = ends.get(nid, ts)
            rows.append(
                {
                    "node_id": nid,
                    "stage": stages.get(nid),
                    "start_s": round(ts - base, 4),
                    "end_s": round(te - base, 4),
                    "dur_s": round(te - ts, 4),
                }
            )
        max_conc = 0
        running = 0
        marks = sorted([(ts, 1) for ts in starts.values()] + [(te, -1) for te in ends.values()], key=lambda x: x[0])
        for _, d in marks:
            running += d
            max_conc = max(max_conc, running)
        s0_end = max(ends.get(nid, 0.0) for nid, s in stages.items() if s == 0) if any(s == 0 for s in stages.values()) else None
        s1_start = (
            min(starts.get(nid, float("inf")) for nid, s in stages.items() if s == 1) if any(s == 1 for s in stages.values()) else None
        )
        gap = float(s1_start - s0_end) if s0_end is not None and s1_start is not None and s1_start != float("inf") else None
        return {
            "schedule_mode": run["schedule_mode"],
            "wall_s": run["wall_s"],
            "max_concurrent": max_conc,
            "stage_gap_s": gap,
            "rows": rows,
        }

    ps = summarize(pipeline_run)
    bs = summarize(barrier_run)
    return bs, ps


@app.cell
def _(bs, make_chapter_result, ps, render_checks):
    # ⑥ 断言展开 + chapter_result（r1114 `expected` 快照）。
    checks = {
        "pipeline 节点数 == 3": len(ps["rows"]) == 3,
        "stage_barrier 节点数 == 3": len(bs["rows"]) == 3,
        "pipeline wall_s > 0": ps["wall_s"] > 0,
        "stage_barrier wall_s > 0": bs["wall_s"] > 0,
    }
    render_checks(checks)

    passed = bool(all(checks.values()))
    summary = "pipeline: wall={:.3f}s max_conc={}  barrier: wall={:.3f}s max_conc={}".format(
        ps["wall_s"],
        ps["max_concurrent"],
        bs["wall_s"],
        bs["max_concurrent"],
    )
    # 对拍期望（教学 payload；headless 可经 details 键定位）
    expected = {"nodes_per_mode": 3, "wall_s_positive": True}
    print("expected:", expected)

    chapter_result = make_chapter_result(
        passed=passed,
        summary=summary,
        details={
            "expected": expected,
            "pipeline": {k: v for k, v in ps.items() if k != "rows"},
            "stage_barrier": {k: v for k, v in bs.items() if k != "rows"},
            "pipeline_rows": ps["rows"],
            "stage_barrier_rows": bs["rows"],
            "checks": {k: bool(v) for k, v in checks.items()},
        },
    )
    return chapter_result, passed


@app.cell(hide_code=True)
def _(chapter_result, mo):
    ok = chapter_result["passed"]
    mo.callout(mo.md(f"## {'✅ PASS' if ok else '❌ FAIL'}: {chapter_result['summary']}"), kind="success" if ok else "danger")
    return


@app.cell(hide_code=True)
def _(bs, mo, ps):
    mo.md("## Pipeline vs Stage Barrier")
    mo.ui.table(
        [
            {
                "mode": "pipeline",
                "wall_s": round(ps["wall_s"], 3),
                "max_concurrent": ps["max_concurrent"],
                "stage_gap_s": ps["stage_gap_s"],
            },
            {
                "mode": "stage_barrier",
                "wall_s": round(bs["wall_s"], 3),
                "max_concurrent": bs["max_concurrent"],
                "stage_gap_s": bs["stage_gap_s"],
            },
        ],
        selection=None,
    )
    return


def run_chapter():
    """SSOT 入口：headless runner 与 pytest 通过此函数执行对拍。"""
    outputs, defs = app.run()
    return defs["chapter_result"]


if __name__ == "__main__":
    app.run()
