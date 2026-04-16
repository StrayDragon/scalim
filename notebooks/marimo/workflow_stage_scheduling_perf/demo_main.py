import marimo

__generated_with = "0.20.2"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # 示例: `pipeline` vs `stage_barrier` 的性能印象

        目标:
        - 给出一个**可运行**的 `workflow` 示例,对比两种 scheduler preset 的“吞吐/等待”差异
        - 通过 `sleep` 放大差异,让结论在本机跑一次就能看见(不追求微基准的纳秒精度)

        核心结论(先看):
        - `pipeline`: 吞吐更好,当 `deps` 已满足且 worker 有空闲时,允许下一阶段节点提前启动(与用户“阶段屏障”直觉不一致)
        - `stage_barrier`: 可预期性更好,严格等待当前阶段全终态后才推进下一阶段(通常会牺牲一部分重叠执行带来的吞吐)
        """
    )
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    import sys
    import time
    from pathlib import Path

    from scalim_misc.notebook_support.pathing import ensure_repo_root_on_sys_path

    repo_root = ensure_repo_root_on_sys_path(__file__)
    _ = sys
    return Path, repo_root, time


@app.cell
def _(Path, repo_root):
    tmp_dir = repo_root / ".tmp" / "artifacts" / "workflow_stage_scheduling_perf"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    return (tmp_dir,)


@app.cell
def _(Path, tmp_dir):
    loaders_module = "notebooks.marimo.workflow_stage_scheduling_perf.loaders"
    demand_dir = tmp_dir / "yaml"
    demand_dir.mkdir(parents=True, exist_ok=True)

    def _write_text(path: Path, text: str) -> Path:
        path.write_text(text, encoding="utf-8")
        return path

    def _write_demand_yaml(*, name: str, loader_ref: str) -> Path:
        return _write_text(
            demand_dir / "{}.yaml".format(str(name)),
            (
                """
name: {name}
main_source:
  source_id: orders
  loader: {loader_ref}
  fields:
    order_id:
      extract: order_id
sources: {{}}
outputs: []
"""
            )
            .format(name=str(name), loader_ref=str(loader_ref))
            .lstrip(),
        )

    demand_a = _write_demand_yaml(name="a", loader_ref="{}:load_orders_medium".format(loaders_module))
    demand_x = _write_demand_yaml(name="x", loader_ref="{}:load_orders_slow".format(loaders_module))
    demand_b = _write_demand_yaml(name="b", loader_ref="{}:load_orders_medium".format(loaders_module))

    workflow_yaml = _write_text(
        demand_dir / "workflow.yaml",
        (
            """
workflow:
  runs:
    - id: a
      demand: a.yaml
    - id: x
      demand: x.yaml
    - id: b
      demand: b.yaml
      depends_on:
        - a
"""
        ).lstrip(),
    )

    _ = (demand_a, demand_b, demand_x)
    return demand_dir, loaders_module, workflow_yaml


@app.cell
def _():
    import threading
    from typing import Any, Dict, List

    from scalim.dsl.yaml_dsl import RunOptions, run_workflow
    from scalim.dsl.yaml_dsl.workflow_types import (
        PipelineSchedulerOptions,
        StageBarrierSchedulerOptions,
        WorkflowExecutionOptions,
        WorkflowRuntimeOptions,
    )
    from scalim.events import (
        EVENT_WORKFLOW_NODE_CANCELLED,
        EVENT_WORKFLOW_NODE_END,
        EVENT_WORKFLOW_NODE_START,
        Event,
    )
    from scalim.ob.observer import Observer

    return (
        Any,
        Dict,
        EVENT_WORKFLOW_NODE_CANCELLED,
        EVENT_WORKFLOW_NODE_END,
        EVENT_WORKFLOW_NODE_START,
        Event,
        List,
        Observer,
        PipelineSchedulerOptions,
        RunOptions,
        StageBarrierSchedulerOptions,
        WorkflowExecutionOptions,
        WorkflowRuntimeOptions,
        run_workflow,
        threading,
    )


@app.cell
def _(EVENT_WORKFLOW_NODE_CANCELLED, EVENT_WORKFLOW_NODE_END, EVENT_WORKFLOW_NODE_START, List, Observer, Event, threading):
    class _WorkflowNodeEventRecorder(Observer):
        event_types = {
            EVENT_WORKFLOW_NODE_START,
            EVENT_WORKFLOW_NODE_END,
            EVENT_WORKFLOW_NODE_CANCELLED,
        }

        def __init__(self) -> None:
            self._lock = threading.Lock()
            self.events: List[Event] = []

        def on_event(self, event) -> None:  # type: ignore[override]
            with self._lock:
                self.events.append(event)

    return (_WorkflowNodeEventRecorder,)


@app.cell
def _(
    PipelineSchedulerOptions,
    RunOptions,
    StageBarrierSchedulerOptions,
    WorkflowExecutionOptions,
    WorkflowRuntimeOptions,
    _WorkflowNodeEventRecorder,
    loaders_module,
    run_workflow,
    time,
    workflow_yaml,
):
    def _run_once(*, schedule_mode: str, max_concurrency: int = 2) -> dict:
        recorder = _WorkflowNodeEventRecorder()

        run_options = RunOptions(
            allowed_modules=frozenset([str(loaders_module)]),
            components=[recorder],
        )
        if str(schedule_mode) == "stage_barrier":
            scheduler = StageBarrierSchedulerOptions()
        else:
            scheduler = PipelineSchedulerOptions()

        runtime_options = WorkflowRuntimeOptions(
            execution=WorkflowExecutionOptions(
                max_concurrency=int(max_concurrency),
                failure_policy="all_fail",
            ),
            scheduler=scheduler,
        )

        t0 = time.perf_counter()
        _ = run_workflow(str(workflow_yaml), options=run_options, workflow_runtime_options=runtime_options)
        t1 = time.perf_counter()
        return {
            "schedule_mode": str(schedule_mode),
            "wall_s": float(t1 - t0),
            "events": list(recorder.events),
        }

    return (_run_once,)


@app.cell
def _(EVENT_WORKFLOW_NODE_CANCELLED, EVENT_WORKFLOW_NODE_END, EVENT_WORKFLOW_NODE_START, _run_once):
    pipeline_run = _run_once(schedule_mode="pipeline")
    stage_barrier_run = _run_once(schedule_mode="stage_barrier")
    _ = (EVENT_WORKFLOW_NODE_CANCELLED, EVENT_WORKFLOW_NODE_END, EVENT_WORKFLOW_NODE_START)
    return pipeline_run, stage_barrier_run


@app.cell
def _(Any, Dict, EVENT_WORKFLOW_NODE_CANCELLED, EVENT_WORKFLOW_NODE_END, EVENT_WORKFLOW_NODE_START, mo, pipeline_run, stage_barrier_run):
    def _summarize_run(run: dict) -> Dict[str, Any]:
        events = list(run.get("events") or [])
        start_by_node_id: Dict[str, float] = {}
        end_by_node_id: Dict[str, float] = {}
        stage_by_node_id: Dict[str, int] = {}
        end_status_by_node_id: Dict[str, str] = {}

        for e in events:
            if e.event_type not in {EVENT_WORKFLOW_NODE_START, EVENT_WORKFLOW_NODE_END, EVENT_WORKFLOW_NODE_CANCELLED}:
                continue
            payload = e.to_dict().get("payload") or {}
            node_id = str(payload.get("workflow_node_id") or "").strip()
            if not node_id:
                continue
            if payload.get("stage") is not None:
                try:
                    stage_by_node_id[node_id] = int(payload.get("stage"))
                except Exception:
                    pass
            if e.event_type == EVENT_WORKFLOW_NODE_START:
                start_by_node_id[node_id] = float(e.timestamp)
            elif e.event_type == EVENT_WORKFLOW_NODE_END:
                end_by_node_id[node_id] = float(e.timestamp)
                end_status_by_node_id[node_id] = str(payload.get("status") or "unknown")
            elif e.event_type == EVENT_WORKFLOW_NODE_CANCELLED:
                end_by_node_id[node_id] = float(e.timestamp)
                end_status_by_node_id[node_id] = str(payload.get("reason") or "cancelled")

        if start_by_node_id:
            t_base = min(start_by_node_id.values())
        elif end_by_node_id:
            t_base = min(end_by_node_id.values())
        else:
            t_base = 0.0

        rows = []
        for node_id, t_start in sorted(start_by_node_id.items(), key=lambda kv: kv[1]):
            t_end = float(end_by_node_id.get(node_id, t_start))
            rows.append(
                {
                    "node_id": node_id,
                    "stage": stage_by_node_id.get(node_id),
                    "start_s": round(float(t_start - t_base), 4),
                    "end_s": round(float(t_end - t_base), 4),
                    "dur_s": round(float(t_end - t_start), 4),
                    "end": end_status_by_node_id.get(node_id, ""),
                }
            )

        # 并行度: 用 `start`/`end` 事件做离线估算(只用于“印象”,不保证与 `worker` 实际占用 100% 等价)
        marks = []
        for node_id, t_start in start_by_node_id.items():
            marks.append((float(t_start), +1, node_id))
        for node_id, t_end in end_by_node_id.items():
            marks.append((float(t_end), -1, node_id))
        marks.sort(key=lambda x: (x[0], -x[1]))
        running = 0
        max_running = 0
        for _ts, delta, _node_id in marks:
            running += int(delta)
            max_running = max(max_running, running)

        stage0_end = None
        stage1_start = None
        if stage_by_node_id:
            stage0_nodes = [nid for nid, st in stage_by_node_id.items() if int(st) == 0]
            stage1_nodes = [nid for nid, st in stage_by_node_id.items() if int(st) == 1]
            if stage0_nodes:
                stage0_end = max(float(end_by_node_id.get(nid, 0.0)) for nid in stage0_nodes)
            if stage1_nodes:
                stage1_start = min(float(start_by_node_id.get(nid, 0.0)) for nid in stage1_nodes)

        gap_s = None
        if stage0_end is not None and stage1_start is not None:
            gap_s = float(stage1_start - stage0_end)

        return {
            "schedule_mode": str(run.get("schedule_mode") or ""),
            "wall_s": float(run.get("wall_s") or 0.0),
            "max_running_est": int(max_running),
            "stage0_to_stage1_gap_s": gap_s,
            "rows": rows,
        }

    pipeline_summary = _summarize_run(pipeline_run)
    stage_barrier_summary = _summarize_run(stage_barrier_run)

    summary_rows = [
        {
            "schedule_mode": pipeline_summary["schedule_mode"],
            "wall_s": round(float(pipeline_summary["wall_s"]), 4),
            "max_running_est": int(pipeline_summary["max_running_est"]),
            "stage0->stage1_gap_s": round(float(pipeline_summary["stage0_to_stage1_gap_s"]), 4)
            if pipeline_summary["stage0_to_stage1_gap_s"] is not None
            else None,
        },
        {
            "schedule_mode": stage_barrier_summary["schedule_mode"],
            "wall_s": round(float(stage_barrier_summary["wall_s"]), 4),
            "max_running_est": int(stage_barrier_summary["max_running_est"]),
            "stage0->stage1_gap_s": round(float(stage_barrier_summary["stage0_to_stage1_gap_s"]), 4)
            if stage_barrier_summary["stage0_to_stage1_gap_s"] is not None
            else None,
        },
    ]

    _ = (EVENT_WORKFLOW_NODE_CANCELLED, EVENT_WORKFLOW_NODE_END, EVENT_WORKFLOW_NODE_START)
    return pipeline_summary, stage_barrier_summary, summary_rows


@app.cell(hide_code=True)
def _(mo, summary_rows):
    mo.md(
        r"""
        ---
        ## 汇总对比(一次运行)

        说明:
        - `wall_s`: 端到端耗时(含编译/调度/执行)
        - `max_running_est`: 基于 workflow node start/end 事件估算的最大并行度(用于“印象”)
        - `stage0->stage1_gap_s`: 估算的阶段边界间隔(负数表示有重叠;正数表示等待)
        """
    )
    mo.ui.table(summary_rows, selection=None)
    return


@app.cell(hide_code=True)
def _(mo, pipeline_summary):
    mo.md(
        r"""
        ---
        ## `pipeline` 事件时间线(节点级)
        """
    )
    mo.ui.table(pipeline_summary["rows"], selection=None)
    return


@app.cell(hide_code=True)
def _(mo, stage_barrier_summary):
    mo.md(
        r"""
        ---
        ## `stage_barrier` 事件时间线(节点级)
        """
    )
    mo.ui.table(stage_barrier_summary["rows"], selection=None)
    return


if __name__ == "__main__":
    app.run()
