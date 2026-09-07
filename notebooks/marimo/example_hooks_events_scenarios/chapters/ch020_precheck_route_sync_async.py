"""Cells-native marimo notebook: ch020_precheck_route_sync_async.

迁移对照 (ch010 同款):
  Before: 薄壳 cells + support/precheck_route.py 持有全部主路径
  After:  路由决策/执行/断言全部在 cells 内;support 只留 fixtures/http_mock 零件
"""

import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # example_hooks_events_scenarios / ch020_precheck_route_sync_async

        演示：**应用层预估完成后 HTTP 分流**（不绑 Scalim `workflow_preflight`）。

        主线装配过程（每个步骤一个 cell，可就地修改重跑）：

        1. 定义零件：`estimate_job` 预估 + `route_and_maybe_run` 分流决策
        2. 启动本地 mock server（`POST /dispatch` 按 estimated_rows 判 sync/async）
        3. 写入 demand / workflow YAML fixtures（内容可见）
        4. 小任务（sync）→ 直接 `run` / `run_workflow`
        5. 大任务（async）→ 只入队 mock，不跑 Scalim（断言无产物文件）
        6. 断言展开（含 server 侧存在性核对，交互重跑幂等）

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
    from typing import Any, Dict, List, Optional

    from scalim.dsl import yaml_dsl as api
    from scalim.dsl.yaml_dsl.workflow_types import WorkflowExecutionOptions, WorkflowRunOptions, WorkflowRuntimeOptions
    from scalim_misc.notebook_support.chapter_result import make_chapter_result, render_checks
    from notebooks.marimo.example_hooks_events_scenarios.support.fixtures import (
        ALLOWED_MODULES,
        ASYNC_ESTIMATED_ROWS,
        SYNC_ESTIMATED_ROWS,
        write_minimal_demand_yaml,
        write_minimal_workflow_yaml,
    )
    from notebooks.marimo.example_hooks_events_scenarios.support.http_mock import (
        MockHttpServer,
        post_dispatch,
        start_mock_http_server,
    )

    _ = repo_root
    return (
        ALLOWED_MODULES,
        Any,
        ASYNC_ESTIMATED_ROWS,
        Dict,
        List,
        MockHttpServer,
        Optional,
        Path,
        SYNC_ESTIMATED_ROWS,
        WorkflowExecutionOptions,
        WorkflowRunOptions,
        WorkflowRuntimeOptions,
        api,
        make_chapter_result,
        post_dispatch,
        render_checks,
        start_mock_http_server,
        tempfile,
        write_minimal_demand_yaml,
        write_minimal_workflow_yaml,
    )


@app.cell
def _(ALLOWED_MODULES, Dict, List, MockHttpServer, Optional, Path, api, post_dispatch):
    # 零件: 应用层预估(非 Scalim workflow_preflight)
    def estimate_job(*, estimated_rows: int) -> Dict[str, Any]:
        return {"estimated_rows": int(estimated_rows), "estimated_duration_secs": max(1, int(estimated_rows) // 1000)}

    # 零件: 同名路由封装 — 小任务 sync 直跑 demand/workflow,大任务 async 只入队
    def route_and_maybe_run(
        *,
        server: MockHttpServer,
        job_id: str,
        estimated_rows: int,
        entrypoint: str,
        demand_path: Path,
        workflow_path: Path,
        output_root: Path,
        async_queue: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        estimate = estimate_job(estimated_rows=estimated_rows)
        decision = post_dispatch(
            server.base_url,
            {"job_id": job_id, "entrypoint": entrypoint, **estimate},
        )
        mode = str(decision.get("mode") or "")
        record: Dict[str, Any] = {
            "job_id": job_id,
            "entrypoint": entrypoint,
            "estimate": estimate,
            "mode": mode,
            "ran": False,
            "total_rows": None,
            "enqueued": False,
        }
        if mode == "async":
            async_queue.append({"job_id": job_id, "entrypoint": entrypoint, "estimate": estimate})
            record["enqueued"] = True
            return record

        if mode != "sync":
            msg = "unexpected dispatch mode: {!r}".format(mode)  # force-en
            raise RuntimeError(msg)  # force-en

        if entrypoint == "demand":
            result = api.run(str(demand_path), options=_demand_options(output_root=output_root))
            record["ran"] = True
            record["total_rows"] = int(result.total_rows)
            return record

        if entrypoint == "workflow":
            wf = api.run_workflow(
                str(workflow_path),
                options=WorkflowRunOptions(
                    demand=_demand_options(output_root=output_root),
                    runtime=WorkflowRuntimeOptions(
                        execution=WorkflowExecutionOptions(max_concurrency=1, failure_policy="all_fail"),
                    ),
                ),
            )
            total_rows = 0
            for outcome in wf.outcomes:
                if outcome.error is None and outcome.result is not None:
                    total_rows += int(outcome.result.total_rows)
            record["ran"] = True
            record["total_rows"] = total_rows
            return record

        msg = "unknown entrypoint: {!r}".format(entrypoint)  # force-en
        raise RuntimeError(msg)  # force-en

    # 零件: 运行选项工厂(demand 与 workflow 共用)
    def _demand_options(*, output_root: Path) -> "api.DemandRunOptions":
        overrides = api.RunOverrides.csv_file(
            output_root=str(output_root),
            fields=["item_id", "dim_id"],
            header_fields_output_by="name",
        )
        return api.DemandRunOptions(
            security=api.DemandRunSecurityOptions(allowed_modules=ALLOWED_MODULES),
            runtime=api.DemandRunRuntimeOptions(batch_size=10),
            outputs=api.DemandRunOutputOptions(overrides=overrides),
        )

    return _demand_options, estimate_job, route_and_maybe_run


@app.cell
def _(Path, start_mock_http_server, tempfile):
    import atexit
    import shutil

    server = start_mock_http_server(async_rows_threshold=100)
    tmp = Path(tempfile.mkdtemp(prefix="scalim-hooks-ch020-"))
    atexit.register(server.stop)
    atexit.register(lambda: shutil.rmtree(tmp, ignore_errors=True))

    print("mock server:", server.base_url)
    print("async 阈值:  estimated_rows >= 100 → async")
    print("tmp dir:", tmp)
    return server, tmp


@app.cell
def _(mo, tmp, write_minimal_demand_yaml, write_minimal_workflow_yaml):
    demand_path = write_minimal_demand_yaml(tmp / "demand.yaml")
    workflow_path = write_minimal_workflow_yaml(tmp / "workflow.yaml", demand_rel="demand.yaml")

    demand_yaml_text = demand_path.read_text(encoding="utf-8")
    workflow_yaml_text = workflow_path.read_text(encoding="utf-8")

    mo.md("**demand.yaml**:\n\n```yaml\n{}\n```\n\n**workflow.yaml**:\n\n```yaml\n{}\n```".format(demand_yaml_text, workflow_yaml_text))
    return demand_path, demand_yaml_text, workflow_path, workflow_yaml_text


@app.cell
def _(ASYNC_ESTIMATED_ROWS, Any, Dict, List, SYNC_ESTIMATED_ROWS, demand_path, route_and_maybe_run, server, tmp, workflow_path):
    # sync 小任务: 直跑 demand 与 workflow
    async_queue: List[Dict[str, Any]] = []

    sync_demand = route_and_maybe_run(
        server=server,
        job_id="sync-demand",
        estimated_rows=SYNC_ESTIMATED_ROWS,
        entrypoint="demand",
        demand_path=demand_path,
        workflow_path=workflow_path,
        output_root=tmp / "sync_demand_out",
        async_queue=async_queue,
    )
    sync_workflow = route_and_maybe_run(
        server=server,
        job_id="sync-workflow",
        estimated_rows=SYNC_ESTIMATED_ROWS,
        entrypoint="workflow",
        demand_path=demand_path,
        workflow_path=workflow_path,
        output_root=tmp / "sync_workflow_out",
        async_queue=async_queue,
    )

    print("sync-demand :", sync_demand)
    print("sync-workflow:", sync_workflow)

    return async_queue, sync_demand, sync_workflow


@app.cell
def _(ASYNC_ESTIMATED_ROWS, async_queue, demand_path, route_and_maybe_run, server, tmp, workflow_path):
    # async 大任务: 只入队 mock,不跑 Scalim
    async_demand = route_and_maybe_run(
        server=server,
        job_id="async-demand",
        estimated_rows=ASYNC_ESTIMATED_ROWS,
        entrypoint="demand",
        demand_path=demand_path,
        workflow_path=workflow_path,
        output_root=tmp / "async_demand_out",
        async_queue=async_queue,
    )
    async_workflow = route_and_maybe_run(
        server=server,
        job_id="async-workflow",
        estimated_rows=ASYNC_ESTIMATED_ROWS,
        entrypoint="workflow",
        demand_path=demand_path,
        workflow_path=workflow_path,
        output_root=tmp / "async_workflow_out",
        async_queue=async_queue,
    )

    print("async-demand :", async_demand)
    print("async-workflow:", async_workflow)

    return async_demand, async_workflow


@app.cell
def _(async_demand, async_queue, async_workflow, mo, server, sync_demand, sync_workflow):
    mo.ui.tabs(
        {
            "sync demand": mo.ui.table([sync_demand], selection=None),
            "sync workflow": mo.ui.table([sync_workflow], selection=None),
            "async demand": mo.ui.table([async_demand], selection=None),
            "async workflow": mo.ui.table([async_workflow], selection=None),
            "mock 入队队列": mo.ui.table(list(async_queue), selection=None),
            "server dispatches": mo.ui.table(list(server.state.dispatches), selection=None),
        }
    )
    return


@app.cell
def _(async_demand, async_queue, async_workflow, render_checks, server, sync_demand, sync_workflow, tmp):
    # 断言展开: server 侧用「job_id 存在匹配」语义,交互重跑不累积误判
    async_files = list((tmp / "async_demand_out").rglob("*")) + list((tmp / "async_workflow_out").rglob("*"))
    async_files = [p for p in async_files if p.is_file()]
    dispatched_jobs = [str(d.get("request", {}).get("job_id", "")) for d in server.state.dispatches]

    checks = {
        "sync-demand mode=sync": sync_demand["mode"] == "sync" and sync_demand["ran"] and sync_demand["total_rows"] == 3,
        "sync-workflow mode=sync": sync_workflow["mode"] == "sync" and sync_workflow["ran"] and sync_workflow["total_rows"] == 3,
        "async-demand mode=async 仅入队": async_demand["mode"] == "async" and async_demand["enqueued"] and not async_demand["ran"],
        "async-workflow mode=async 仅入队": async_workflow["mode"] == "async" and async_workflow["enqueued"] and not async_workflow["ran"],
        "入队队列长度 == 2": len(async_queue) == 2,
        "async 无产物文件": len(async_files) == 0,
        "server 收到 4 次 dispatch": len(server.state.dispatches) >= 4,
        "4 个 job_id 均被 dispatch": all(
            job in dispatched_jobs for job in ["sync-demand", "sync-workflow", "async-demand", "async-workflow"]
        ),
    }
    render_checks(checks)

    return async_files, checks


@app.cell
def _(async_demand, async_files, async_queue, async_workflow, checks, make_chapter_result, server, sync_demand, sync_workflow):
    passed = bool(all(checks.values()))
    summary = "sync_rows={}/{} queue={} dispatches={} async_files={}".format(
        sync_demand.get("total_rows"),
        sync_workflow.get("total_rows"),
        len(async_queue),
        len(server.state.dispatches),
        len(async_files),
    )
    chapter_result = make_chapter_result(
        passed=passed,
        summary=summary,
        details={
            "sync_demand": sync_demand,
            "sync_workflow": sync_workflow,
            "async_demand": async_demand,
            "async_workflow": async_workflow,
            "async_queue": list(async_queue),
            "dispatches": list(server.state.dispatches),
            "checks": {k: bool(v) for k, v in checks.items()},
            "note": "precheck is app-layer estimate→HTTP; same router wraps demand run and workflow run_workflow",
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
