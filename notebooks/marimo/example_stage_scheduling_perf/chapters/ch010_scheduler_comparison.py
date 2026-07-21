"""Cells-native: ch010 — pipeline vs stage_barrier scheduler comparison."""
import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""# Pipeline vs Stage Barrier scheduler

对比 workflow 两种 scheduler preset 的吞吐/并行度差异。通过 sleep 放大差异便于观察。""")
    return


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _():
    from scalim_misc.notebook_support.pathing import ensure_repo_root_on_sys_path
    ensure_repo_root_on_sys_path(__file__)
    return


@app.cell
def _():
    import sys, time, threading
    from pathlib import Path
    from typing import Any, Dict, List

    from scalim.dsl.yaml_dsl import DemandRunOptions, DemandRunSecurityOptions, WorkflowRunOptions, run_workflow
    from scalim.dsl.yaml_dsl.workflow_types import (
        PipelineSchedulerOptions, StageBarrierSchedulerOptions,
        WorkflowExecutionOptions, WorkflowRuntimeOptions,
    )
    from scalim.events import Event, EventType
    from scalim.ob.observer import Observer
    return (
        Any, DemandRunOptions, DemandRunSecurityOptions, Dict, Event, EventType, List,
        Observer, Path, PipelineSchedulerOptions, StageBarrierSchedulerOptions,
        WorkflowExecutionOptions, WorkflowRuntimeOptions, WorkflowRunOptions,
        run_workflow, sys, threading, time,
    )


@app.cell
def _(Path, sys):
    repo_root = Path(__file__).resolve().parents[3]
    tmp_dir = repo_root / ".tmp" / "artifacts" / "example_stage_scheduling_perf"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    loaders_module = "notebooks.marimo.example_stage_scheduling_perf.loaders"
    _ = sys
    return loaders_module, repo_root, tmp_dir


@app.cell
def _(Path, loaders_module, tmp_dir):
    def _w(path, text):
        path.write_text(text, encoding="utf-8"); return path
    def _dyaml(name, ref):
        return _w(tmp_dir / f"{name}.yaml", f"""name: {name}\nmain_source:\n  source_id: orders\n  loader: {ref}\n  fields:\n    order_id:\n      extract: order_id\nsources: {{}}\noutputs: []\n""")
    _dyaml("a", f"{loaders_module}:load_orders_medium")
    _dyaml("x", f"{loaders_module}:load_orders_slow")
    _dyaml("b", f"{loaders_module}:load_orders_medium")
    wf = _w(tmp_dir / "workflow.yaml", "workflow:\n  runs:\n    - id: a\n      demand: a.yaml\n    - id: x\n      demand: x.yaml\n    - id: b\n      demand: b.yaml\n      depends_on:\n        - a\n")
    workflow_path = str(wf)
    print(f"workflow written: {workflow_path}")
    return workflow_path


@app.cell
def _(EventType, List, Observer, Event, threading):
    class Recorder(Observer):
        event_types = {EventType.WORKFLOW_NODE_START, EventType.WORKFLOW_NODE_END, EventType.WORKFLOW_NODE_CANCELLED}
        def __init__(self):
            self._lock = threading.Lock()
            self.events: list = []
        def on_event(self, event):
            with self._lock: self.events.append(event)
    return (Recorder,)


@app.cell
def _(
    DemandRunOptions, DemandRunSecurityOptions, PipelineSchedulerOptions, Recorder,
    StageBarrierSchedulerOptions, WorkflowExecutionOptions, WorkflowRuntimeOptions,
    WorkflowRunOptions, loaders_module, run_workflow, time, workflow_path,
):
    def run_once(mode, max_concurrency=2):
        rec = Recorder()
        dopt = DemandRunOptions(security=DemandRunSecurityOptions(allowed_modules=frozenset([loaders_module])))
        sched = StageBarrierSchedulerOptions() if mode == "stage_barrier" else PipelineSchedulerOptions()
        rt = WorkflowRuntimeOptions(execution=WorkflowExecutionOptions(max_concurrency=max_concurrency, failure_policy="all_fail"), scheduler=sched)
        t0 = time.perf_counter()
        run_workflow(workflow_path, options=WorkflowRunOptions(demand=dopt, runtime=rt, workflow_components=(rec,)))
        return {"schedule_mode": mode, "wall_s": time.perf_counter() - t0, "events": list(rec.events)}

    pipeline_run = run_once("pipeline")
    barrier_run = run_once("stage_barrier")
    print(f"pipeline: {pipeline_run['wall_s']:.3f}s  barrier: {barrier_run['wall_s']:.3f}s")
    return barrier_run, pipeline_run, run_once


@app.cell
def _(EventType, barrier_run, pipeline_run):
    def summarize(run):
        events = list(run.get("events") or [])
        starts, ends, stages = {}, {}, {}
        for e in events:
            p = e.to_dict().get("payload") or {}
            nid = str(p.get("workflow_node_id", "")).strip()
            if not nid: continue
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
            rows.append({"node_id": nid, "stage": stages.get(nid), "start_s": round(ts - base, 4), "end_s": round(te - base, 4), "dur_s": round(te - ts, 4)})
        max_conc = 0; running = 0
        marks = sorted([(ts, 1) for ts in starts.values()] + [(te, -1) for te in ends.values()], key=lambda x: x[0])
        for _, d in marks: running += d; max_conc = max(max_conc, running)
        s0_end = max(ends.get(nid, 0.0) for nid, s in stages.items() if s == 0) if any(s == 0 for s in stages.values()) else None
        s1_start = min(starts.get(nid, float("inf")) for nid, s in stages.items() if s == 1) if any(s == 1 for s in stages.values()) else None
        gap = float(s1_start - s0_end) if s0_end is not None and s1_start is not None and s1_start != float("inf") else None
        return {"schedule_mode": run["schedule_mode"], "wall_s": run["wall_s"], "max_concurrent": max_conc, "stage_gap_s": gap, "rows": rows}

    ps = summarize(pipeline_run)
    bs = summarize(barrier_run)
    return bs, ps


@app.cell
def _(bs, ps):
    passed = ps["wall_s"] > 0 and bs["wall_s"] > 0
    summary = f"pipeline: wall={ps['wall_s']:.3f}s max_conc={ps['max_concurrent']} gap={ps['stage_gap_s']}  barrier: wall={bs['wall_s']:.3f}s max_conc={bs['max_concurrent']} gap={bs['stage_gap_s']}"
    chapter_result = {"passed": passed, "summary": summary, "details": {"pipeline": ps, "barrier": bs}}
    return chapter_result, passed, summary


@app.cell(hide_code=True)
def _(chapter_result, mo):
    ok = chapter_result["passed"]
    mo.callout(mo.md(f"## {'✅ PASS' if ok else '❌ FAIL'}: {chapter_result['summary']}"), kind="success" if ok else "danger")
    return


@app.cell(hide_code=True)
def _(bs, mo, ps):
    mo.md("## Pipeline vs Stage Barrier")
    mo.ui.table([{"mode": "pipeline", "wall_s": round(ps["wall_s"], 3), "max_concurrent": ps["max_concurrent"], "stage_gap_s": ps["stage_gap_s"]}, {"mode": "stage_barrier", "wall_s": round(bs["wall_s"], 3), "max_concurrent": bs["max_concurrent"], "stage_gap_s": bs["stage_gap_s"]}], selection=None)
    return


def run_chapter():
    outputs, defs = app.run()
    return defs["chapter_result"]


if __name__ == "__main__":
    app.run()
