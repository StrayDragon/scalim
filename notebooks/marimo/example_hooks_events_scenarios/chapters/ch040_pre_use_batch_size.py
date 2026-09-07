"""Cells-native marimo notebook: ch040_pre_use_batch_size.

迁移对照 (ch010 同款):
  Before: 薄壳 cells + support/pre_use_batch_size.py 持有全部主路径
  After:  Hook/Probe 零件、装配、断言全部在 cells 内;fixtures 仍是零件
"""

import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # example_hooks_events_scenarios / ch040_pre_use_batch_size

        演示：**`pre_use_batch_size` 策略信号改写 batch_size**（仅当
        `DemandRunRuntimeOptions.batch_size=UNSET` 时触发）。

        主线装配过程（每个步骤一个 cell，可就地修改重跑）：

        1. 定义零件：`ForceBatchSizeHook`（策略改写）+ `BatchSizeProbe`（记录实际生效值）
        2. 写入 demand / workflow YAML；组装带 `UNSET` 的选项
        3. demand 运行 → Hook 改写 + Probe 记录 `PIPELINE_START.batch_size`
        4. workflow 运行 → 同一机制对照编排层
        5. 拖 slider 改覆盖值 → 观察 pipeline 实际生效值跟随变化
        6. 断言展开 → chapter_result

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
    from pathlib import Path
    from typing import Any, Dict, List, Optional, Set

    from scalim.dsl import yaml_dsl as api
    from scalim.dsl.yaml_dsl import UNSET
    from scalim.dsl.yaml_dsl.workflow_types import WorkflowExecutionOptions, WorkflowRunOptions, WorkflowRuntimeOptions
    from scalim.events import Event, EventType
    from scalim.hooks import BaseHook
    from scalim.ob.observer import EventDispatchObserver
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
        BaseHook,
        Dict,
        Event,
        EventDispatchObserver,
        EventType,
        List,
        Optional,
        Path,
        Set,
        UNSET,
        WorkflowExecutionOptions,
        WorkflowRunOptions,
        WorkflowRuntimeOptions,
        api,
        make_chapter_result,
        render_checks,
        tempfile,
        write_minimal_demand_yaml,
        write_minimal_workflow_yaml,
    )


@app.cell
def _(mo):
    override_batch_size = mo.ui.slider(1, 10, value=2, step=1, label="覆盖 batch_size（Hook 写入值）")
    override_batch_size
    return (override_batch_size,)


@app.cell
def _(Any, BaseHook, Dict, Event, EventDispatchObserver, EventType, List, Optional, Set):
    # 零件: 策略 Hook — 在 run_ir 前改写 batch_size
    class ForceBatchSizeHook(BaseHook):
        def __init__(self, *, next_value: int, reason: str) -> None:
            self.next_value = int(next_value)
            self.reason = str(reason)
            self.calls = 0
            self.last_prev: Optional[int] = None
            self.last_next: Optional[int] = None
            self.history_len = 0

        def on_pre_use_batch_size(self, decision: Any) -> None:
            self.calls += 1
            self.last_prev = None if decision.value is None else int(decision.value)
            decision.override(self.next_value, reason=self.reason)
            self.last_next = None if decision.value is None else int(decision.value)
            self.history_len = len(decision.history)

    # 零件: Probe — 从 PIPELINE_START 记录实际生效 batch_size
    class BatchSizeProbe(EventDispatchObserver):
        def __init__(self) -> None:
            self.event_types: Optional[Set[EventType]] = {EventType.PIPELINE_START}
            self.batch_sizes: List[Optional[int]] = []

        def on_pipeline_start(self, event: Event) -> None:
            body = event.payload
            raw = getattr(body, "batch_size", None)
            self.batch_sizes.append(None if raw is None else int(raw))

    return BatchSizeProbe, ForceBatchSizeHook


@app.cell
def _(ALLOWED_MODULES, List, Path, UNSET, api, override_batch_size):
    # 零件: 运行选项工厂 — batch_size 显式 UNSET,让 pre_use_batch_size 信号生效
    def demand_options(*, components: List[Any], output_root: Path) -> api.DemandRunOptions:
        overrides = api.RunOverrides.csv_file(
            output_root=str(output_root),
            fields=["item_id", "dim_id"],
            header_fields_output_by="name",
        )
        return api.DemandRunOptions(
            security=api.DemandRunSecurityOptions(allowed_modules=ALLOWED_MODULES),
            runtime=api.DemandRunRuntimeOptions(components=list(components), batch_size=UNSET),
            outputs=api.DemandRunOutputOptions(overrides=overrides),
        )

    print("override_batch_size =", override_batch_size.value)
    print("batch_size=UNSET → pre_use_batch_size 信号触发;Hook 写入", override_batch_size.value)
    return (demand_options,)


@app.cell
def _(Path, tempfile):
    import atexit
    import shutil

    tmp = Path(tempfile.mkdtemp(prefix="scalim-hooks-ch040-"))
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
def _(BatchSizeProbe, ForceBatchSizeHook, api, demand_options, demand_path, override_batch_size, tmp):
    demand_hook = ForceBatchSizeHook(next_value=int(override_batch_size.value), reason="demo-demand")
    demand_probe = BatchSizeProbe()
    demand_result = api.run(
        str(demand_path),
        options=demand_options(components=[demand_hook, demand_probe], output_root=tmp / "demand_out"),
    )

    print("demand rows            =", demand_result.total_rows)
    print("hook calls             =", demand_hook.calls)
    print("hook prev → next       =", demand_hook.last_prev, "→", demand_hook.last_next)
    print("pipeline batch_size    =", demand_probe.batch_sizes)

    return demand_hook, demand_probe, demand_result


@app.cell
def _(
    BatchSizeProbe,
    ForceBatchSizeHook,
    WorkflowExecutionOptions,
    WorkflowRunOptions,
    WorkflowRuntimeOptions,
    api,
    demand_options,
    override_batch_size,
    tmp,
    workflow_path,
):
    workflow_hook = ForceBatchSizeHook(next_value=int(override_batch_size.value), reason="demo-workflow")
    workflow_probe = BatchSizeProbe()
    workflow_result = api.run_workflow(
        str(workflow_path),
        options=WorkflowRunOptions(
            demand=demand_options(components=[workflow_hook, workflow_probe], output_root=tmp / "workflow_out"),
            runtime=WorkflowRuntimeOptions(
                execution=WorkflowExecutionOptions(max_concurrency=1, failure_policy="all_fail"),
            ),
        ),
    )

    print(
        "workflow rows          =",
        sum(int(o.result.total_rows) for o in workflow_result.outcomes if o.error is None and o.result is not None),
    )
    print("workflow hook calls    =", workflow_hook.calls)
    print("workflow pipeline batch=", workflow_probe.batch_sizes)

    return workflow_hook, workflow_probe, workflow_result


@app.cell
def _(demand_hook, demand_probe, demand_result, override_batch_size, render_checks, workflow_hook, workflow_probe, workflow_result):
    # 断言展开: 所有观察对象每次运行重建,精确断言幂等
    checks = {
        "demand rows == 3": demand_result.total_rows == 3,
        "demand hook 调用 1 次": demand_hook.calls == 1,
        "demand hook 写入覆盖值": demand_hook.last_next == int(override_batch_size.value),
        "demand hook 历史长度 == 1": demand_hook.history_len == 1,
        "demand pipeline 生效值一致": demand_probe.batch_sizes == [int(override_batch_size.value)],
        "workflow 运行成功": workflow_result is not None,
        "workflow hook 调用 1 次": workflow_hook.calls == 1,
        "workflow hook 写入覆盖值": workflow_hook.last_next == int(override_batch_size.value),
        "workflow pipeline 生效值一致": workflow_probe.batch_sizes == [int(override_batch_size.value)],
    }
    render_checks(checks)
    return checks


@app.cell
def _(checks, demand_hook, demand_probe, make_chapter_result, override_batch_size, workflow_hook, workflow_probe):
    passed = bool(all(checks.values()))
    summary = "demand_hook_calls={} demand_batch={} demand_pipeline_batch={} workflow_hook_calls={} workflow_pipeline_batch={}".format(
        demand_hook.calls,
        demand_hook.last_next,
        demand_probe.batch_sizes,
        workflow_hook.calls,
        workflow_probe.batch_sizes,
    )
    # 对拍期望（教学 payload；headless 可经 details 键定位）
    expected = {
        "demand_rows": 3,
        "demand_hook_calls": 1,
        "demand_hook_history_len": 1,
        "workflow_runs_ok": True,
        "workflow_hook_calls": 1,
        "hook_writes_override_value": True,
        "pipeline_effective_value_matches_override": True,
    }
    print("expected:", expected)

    chapter_result = make_chapter_result(
        passed=passed,
        summary=summary,
        details={
            "expected": expected,
            "override_batch_size": int(override_batch_size.value),
            "demand": {
                "hook_calls": demand_hook.calls,
                "prev": demand_hook.last_prev,
                "next": demand_hook.last_next,
                "pipeline_batch_sizes": list(demand_probe.batch_sizes),
            },
            "workflow": {
                "hook_calls": workflow_hook.calls,
                "prev": workflow_hook.last_prev,
                "next": workflow_hook.last_next,
                "pipeline_batch_sizes": list(workflow_probe.batch_sizes),
            },
            "checks": {k: bool(v) for k, v in checks.items()},
            "note": "explicit DemandRunRuntimeOptions.batch_size skips the signal; leave UNSET to opt-in",
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
