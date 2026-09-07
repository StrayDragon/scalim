"""Cells-native marimo notebook: ch010_post_export_upload (cells-native 改造示范).

设计目标:
- 全部内容在 marimo cells 内书写(渐进式探索 + 就地可视化)
- 通过 `chapter_result` 变量向 headless runner / pytest 暴露对拍结果
- `run_chapter()` 兼容层: `app.run()` → `chapter_result`
- 与现有 ChapterRegistry / just examples / pytest 完全兼容

迁移对照:
  Before: 薄壳 cells (import → call run_post_export_upload() → display),
          逻辑全部藏在 support/post_export_upload.py,交互打开 notebook 即 NameError
  After:  装配过程(observer 类 → mock server → fixtures → options → run → 断言)
          全部在 cells 内逐步展开;support 只留 http_mock/fixtures 零件;
          run_chapter() 作为薄兼容层调用 app.run()

本文件的模块级代码仅保留:
  - app = marimo.App(...)
  - run_chapter() 头兼容层
"""

import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


# ═══════════════════════════════════════════════════════════════
# Cell 1 — 教学目标
# ═══════════════════════════════════════════════════════════════


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # example_hooks_events_scenarios / ch010_post_export_upload

        演示：**导出物完成后上传到本地 HTTP mock server**。

        主线装配过程（每个步骤一个 cell，可就地修改重跑）：

        1. 定义 Observer 零件（`OUTPUT_TARGET_END` / `WORKFLOW_NODE_END`）
        2. 启动本地 mock server + 准备临时目录
        3. 写入 demand / workflow YAML fixtures（内容可见）
        4. 组装 `DemandRunOptions`（`RunOverrides` / `components` / `batch_size`）
        5. **Demand** 层运行 → Observer 捕获上传
        6. **Workflow** 层运行 → 同一 Observer + `WORKFLOW_NODE_END` 对照
        7. 断言展开（observer 捕获 vs server 实收 vs node 状态）

        注入边界:
        - demand 执行层事件 → `DemandRunRuntimeOptions.components`
        - workflow 编排层事件 → `WorkflowRunOptions.workflow_components`
        - `OUTPUT_TARGET_END` 在 Observer 目录内;`WORKFLOW_STARTED/FINISHED` 需启用 viz,
          无 viz 时用 `WORKFLOW_NODE_*` 对照编排层

        对拍入口: `run_chapter()` → `app.run()` → `chapter_result`

        Gate: `just examples` / `tests/integration/test_example_hooks_events_scenarios.py`
        """
    )
    return


# ═══════════════════════════════════════════════════════════════
# Cell 2 — marimo 自身
# ═══════════════════════════════════════════════════════════════


@app.cell
def _():
    import marimo as mo

    return (mo,)


# ═══════════════════════════════════════════════════════════════
# Cell 3 — 仓库路径设置(notebook 辅助;返回 repo_root 供下一 cell 显式依赖,
# 保证 import 前 sys.path 注入完成,script/交互两种模式都确定)
# ═══════════════════════════════════════════════════════════════


@app.cell
def _():
    from scalim_misc.notebook_support.pathing import ensure_repo_root_on_sys_path

    repo_root = ensure_repo_root_on_sys_path(__file__)
    return (repo_root,)


# ═══════════════════════════════════════════════════════════════
# Cell 4 — 业务 imports(scalim API + support 零件)
#
# app.run() 创建全新 __main__ 上下文,因此 imports 需在 cells 内完成。
# `scalim.*` import 保留在本文件,`report-notebooks-coverage` gate 仍可统计。
# ═══════════════════════════════════════════════════════════════


@app.cell
def _(repo_root):
    import tempfile
    from pathlib import Path
    from typing import Any, Dict, List, Optional, Set

    from scalim.dsl import yaml_dsl as api
    from scalim.dsl.yaml_dsl.workflow_types import WorkflowExecutionOptions, WorkflowRunOptions, WorkflowRuntimeOptions
    from scalim.events import Event, EventType
    from scalim.ob.observer import EventDispatchObserver, Observer
    from notebooks.marimo.example_hooks_events_scenarios.support.fixtures import (
        ALLOWED_MODULES,
        write_minimal_demand_yaml,
        write_minimal_workflow_yaml,
    )
    from notebooks.marimo.example_hooks_events_scenarios.support.http_mock import (
        MockHttpServer,
        build_upload_payload,
        post_upload,
        start_mock_http_server,
    )

    _ = repo_root
    return (
        ALLOWED_MODULES,
        Any,
        Dict,
        Event,
        EventDispatchObserver,
        EventType,
        List,
        MockHttpServer,
        Observer,
        Optional,
        Path,
        Set,
        WorkflowExecutionOptions,
        WorkflowRunOptions,
        WorkflowRuntimeOptions,
        api,
        build_upload_payload,
        post_upload,
        start_mock_http_server,
        tempfile,
        write_minimal_demand_yaml,
        write_minimal_workflow_yaml,
    )


# ═══════════════════════════════════════════════════════════════
# Cell 5 — 交互旋钮(永远显示;script 模式用默认值,交互模式可拖动重跑)
# ═══════════════════════════════════════════════════════════════


@app.cell
def _(mo):
    batch_size = mo.ui.slider(1, 50, value=10, step=1, label="batch_size（每批处理行数）")
    batch_size
    return (batch_size,)


# ═══════════════════════════════════════════════════════════════
# Cell 6 — Observer 零件(教学核心:事件如何被订阅与记录)
# ═══════════════════════════════════════════════════════════════


@app.cell
def _(Any, Dict, Event, EventDispatchObserver, EventType, List, Observer, Optional, Set, build_upload_payload, post_upload):
    # demand 层 Observer: 每个输出 target 关闭后,POST 元数据到 mock upload API
    class UploadOnOutputEnd(EventDispatchObserver):
        def __init__(self, *, base_url: str) -> None:
            self.event_types: Optional[Set[EventType]] = {EventType.OUTPUT_TARGET_END}
            self.base_url = str(base_url)
            self.uploaded: List[Dict[str, Any]] = []
            self.errors: List[str] = []

        def on_output_target_end(self, event: Event) -> None:
            body = event.payload
            payload = build_upload_payload(
                target_id=str(body.target_id),
                output_path=None if body.output_path is None else str(body.output_path),
                row_count=int(body.row_count),
            )
            try:
                _ = post_upload(self.base_url, payload)
                self.uploaded.append(payload)
            except Exception as exc:  # noqa: BLE001
                self.errors.append("{}: {}".format(type(exc).__name__, exc))

    # workflow 层 Observer: 记录 WORKFLOW_NODE_END(编排层常开事件)
    class WorkflowNodeEndMarker(Observer):
        def __init__(self) -> None:
            self.event_types: Optional[Set[EventType]] = {EventType.WORKFLOW_NODE_END}
            self.ends: List[Dict[str, Any]] = []

        def on_event(self, event: Any) -> None:
            if getattr(event, "event_type", None) != EventType.WORKFLOW_NODE_END:
                return
            payload = getattr(event, "payload", None)
            self.ends.append(
                {
                    "workflow_node_id": None if payload is None else str(getattr(payload, "workflow_node_id", None)),
                    "status": None if payload is None else str(getattr(payload, "status", None)),
                    "node_type": None if payload is None else str(getattr(payload, "node_type", None)),
                }
            )

    return UploadOnOutputEnd, WorkflowNodeEndMarker


# ═══════════════════════════════════════════════════════════════
# Cell 7 — 本地 mock server + 临时目录(atexit 清理)
# ═══════════════════════════════════════════════════════════════


@app.cell
def _(Path, start_mock_http_server, tempfile):
    import atexit
    import shutil

    server = start_mock_http_server()
    tmp = Path(tempfile.mkdtemp(prefix="scalim-hooks-ch010-"))
    atexit.register(server.stop)
    atexit.register(lambda: shutil.rmtree(tmp, ignore_errors=True))

    print("mock server: {}".format(server.base_url))
    print("endpoints:   POST /upload | POST /dispatch")
    print("tmp dir:     {}".format(tmp))

    return server, tmp


# ═══════════════════════════════════════════════════════════════
# Cell 8 — YAML fixtures(写入 + 内容可见)
# ═══════════════════════════════════════════════════════════════


@app.cell
def _(mo, tmp, write_minimal_demand_yaml, write_minimal_workflow_yaml):
    demand_path = write_minimal_demand_yaml(tmp / "demand.yaml")
    workflow_path = write_minimal_workflow_yaml(tmp / "workflow.yaml", demand_rel="demand.yaml")

    demand_yaml_text = demand_path.read_text(encoding="utf-8")
    workflow_yaml_text = workflow_path.read_text(encoding="utf-8")

    mo.md(
        "**demand.yaml**（3 行 items,输出字段由 RunOverrides 在运行时提供）:\n\n"
        "```yaml\n{}\n```\n\n"
        "**workflow.yaml**（单 run `main` → demand）:\n\n"
        "```yaml\n{}\n```".format(demand_yaml_text, workflow_yaml_text)
    )
    return demand_path, demand_yaml_text, workflow_path, workflow_yaml_text


# ═══════════════════════════════════════════════════════════════
# Cell 9 — 组装运行选项(RunOverrides + DemandRunOptions;batch_size 可调)
# ═══════════════════════════════════════════════════════════════


@app.cell
def _(ALLOWED_MODULES, Any, List, Path, api, batch_size):
    def demand_options(*, components: List[Any], output_root: Path) -> api.DemandRunOptions:
        overrides = api.RunOverrides.csv_file(
            output_root=str(output_root),
            fields=["item_id", "dim_id"],
            header_fields_output_by="name",
        )
        return api.DemandRunOptions(
            security=api.DemandRunSecurityOptions(allowed_modules=ALLOWED_MODULES),
            runtime=api.DemandRunRuntimeOptions(components=list(components), batch_size=int(batch_size.value)),
            outputs=api.DemandRunOutputOptions(overrides=overrides),
        )

    print("batch_size =", batch_size.value)
    print("组件注入点: DemandRunRuntimeOptions.components")
    print("输出:       CSV via RunOverrides.csv_file, header_fields_output_by='name'")

    return demand_options,


# ═══════════════════════════════════════════════════════════════
# Cell 10 — Demand 层运行(observer 接线 → run → 捕获上传)
# ═══════════════════════════════════════════════════════════════


@app.cell
def _(UploadOnOutputEnd, api, demand_options, demand_path, server, tmp):
    demand_obs = UploadOnOutputEnd(base_url=server.base_url)
    demand_result = api.run(
        str(demand_path),
        options=demand_options(components=[demand_obs], output_root=tmp / "demand_out"),
    )

    print("demand total_rows =", demand_result.total_rows)
    print("demand output     =", demand_result.output_path or "(内存)")
    print("observer uploaded =", len(demand_obs.uploaded))
    print("observer errors   =", demand_obs.errors)
    for _item in demand_obs.uploaded:
        print("  -", _item)

    return demand_obs, demand_result


# ═══════════════════════════════════════════════════════════════
# Cell 11 — Workflow 层运行(同一 Observer 挂在 demand.runtime.components;
# WorkflowNodeEndMarker 挂 workflow_components 对照编排层)
# ═══════════════════════════════════════════════════════════════


@app.cell
def _(UploadOnOutputEnd, WorkflowNodeEndMarker, WorkflowExecutionOptions, WorkflowRunOptions, WorkflowRuntimeOptions, api, demand_options, server, tmp, workflow_path):
    workflow_obs = UploadOnOutputEnd(base_url=server.base_url)
    workflow_node_end = WorkflowNodeEndMarker()
    workflow_result = api.run_workflow(
        str(workflow_path),
        options=WorkflowRunOptions(
            demand=demand_options(components=[workflow_obs], output_root=tmp / "workflow_out"),
            runtime=WorkflowRuntimeOptions(
                execution=WorkflowExecutionOptions(max_concurrency=1, failure_policy="all_fail"),
            ),
            workflow_components=(workflow_node_end,),
        ),
    )

    print("workflow_result:", workflow_result)
    print("observer uploaded =", len(workflow_obs.uploaded))
    print("observer errors   =", workflow_obs.errors)
    print("node ends         =", len(workflow_node_end.ends))
    for _item in workflow_node_end.ends:
        print("  -", _item)

    return workflow_node_end, workflow_obs, workflow_result


# ═══════════════════════════════════════════════════════════════
# Cell 12 — 证据核对(observer 捕获 vs server 实收 vs node 状态)
# ═══════════════════════════════════════════════════════════════


@app.cell
def _(demand_obs, mo, server, workflow_node_end, workflow_obs):
    server_uploads = list(server.state.uploads)
    node_ends = list(workflow_node_end.ends)
    main_ok = any(e.get("workflow_node_id") == "main" and e.get("status") == "ok" for e in node_ends)

    tab_demand = mo.ui.table(list(demand_obs.uploaded), selection=None, label="demand observer 捕获")
    tab_workflow = mo.ui.table(list(workflow_obs.uploaded), selection=None, label="workflow observer 捕获")
    tab_server = mo.ui.table(server_uploads, selection=None, label="mock server 实收")
    tab_nodes = mo.ui.table(node_ends, selection=None, label="WORKFLOW_NODE_END 流")

    mo.ui.tabs(
        {
            "demand uploads": tab_demand,
            "workflow uploads": tab_workflow,
            "server 实收": tab_server,
            "node 事件流": tab_nodes,
        }
    )
    mo.md("→ node `main/ok` 已捕获: {}".format("✅" if main_ok else "❌"))

    return main_ok, node_ends, server_uploads


# ═══════════════════════════════════════════════════════════════
# Cell 13 — 断言展开(server 侧用「存在匹配」语义,交互重跑不累积误判)
# ═══════════════════════════════════════════════════════════════


@app.cell
def _(Any, List, demand_obs, demand_result, main_ok, server_uploads, workflow_node_end, workflow_obs, workflow_result):
    demand_uploads = list(demand_obs.uploaded)
    workflow_uploads = list(workflow_obs.uploaded)

    def _upload_ok(items: List[Any]) -> bool:
        return bool(items) and all(u.get("output_path") and int(u.get("row_count") or 0) == 3 for u in items)

    def _received_by_server(obs_uploads: List[Any]) -> bool:
        return all(
            any(
                s.get("target_id") == u.get("target_id") and int(s.get("row_count") or -1) == int(u.get("row_count") or 0)
                for s in server_uploads
            )
            for u in obs_uploads
        )

    checks = {
        "demand rows == 3": demand_result.total_rows == 3,
        "demand uploads ok": _upload_ok(demand_uploads),
        "demand upload size > 0": all(int(u.get("size") or 0) > 0 for u in demand_uploads),
        "demand observer 无错误": not demand_obs.errors,
        "workflow 运行成功": workflow_result is not None,
        "workflow uploads ok": _upload_ok(workflow_uploads),
        "workflow observer 无错误": not workflow_obs.errors,
        "node main/ok": main_ok,
        "server 收到 demand uploads": _received_by_server(demand_uploads),
        "server 收到 workflow uploads": _received_by_server(workflow_uploads),
    }
    for name, _ok in checks.items():
        print("{:>32}: {}".format(name, "✅" if _ok else "❌"))

    return checks, demand_uploads, workflow_uploads


# ═══════════════════════════════════════════════════════════════
# Cell 14 — 汇总 chapter_result(CI 提取点)
#
# 命名约定: chapter_result(非 _ 前缀,app.run() 的 defs 可见)
# 契约: {"passed": bool, "summary": str, "details": dict|None}
# ═══════════════════════════════════════════════════════════════


@app.cell
def _(batch_size, checks, demand_obs, demand_result, demand_uploads, node_ends, server_uploads, workflow_obs, workflow_uploads):
    passed = bool(all(checks.values()))
    summary = (
        "demand_rows={} demand_uploads={} workflow_uploads={} "
        "workflow_node_ends={} main_ok={} server_uploads={} errors_d={} errors_w={} batch_size={}"
    ).format(
        demand_result.total_rows,
        len(demand_uploads),
        len(workflow_uploads),
        len(node_ends),
        checks["node main/ok"],
        len(server_uploads),
        demand_obs.errors,
        workflow_obs.errors,
        batch_size.value,
    )

    chapter_result = {
        "passed": passed,
        "summary": summary,
        "details": {
            "batch_size": batch_size.value,
            "demand_uploads": demand_uploads,
            "workflow_uploads": workflow_uploads,
            "workflow_node_ends": node_ends,
            "server_uploads": server_uploads,
            "checks": {name: bool(ok) for name, ok in checks.items()},
            "injection": {
                "demand": "DemandRunRuntimeOptions.components → OUTPUT_TARGET_END",
                "workflow_demand_layer": "WorkflowRunOptions.demand.runtime.components → OUTPUT_TARGET_END",
                "workflow_orchestration": "WorkflowRunOptions.workflow_components → WORKFLOW_NODE_END",
            },
        },
    }

    return chapter_result, passed, summary


# ═══════════════════════════════════════════════════════════════
# Cell 15 — 结果展示(交互时可看到)
# ═══════════════════════════════════════════════════════════════


@app.cell(hide_code=True)
def _(chapter_result, mo):
    ok = chapter_result["passed"]
    mo.callout(
        mo.md("## {}: {}".format("✅ PASS" if ok else "❌ FAIL", chapter_result["summary"])),
        kind="success" if ok else "danger",
    )
    return


# ═══════════════════════════════════════════════════════════════
# Cell 16 — 详情表格
# ═══════════════════════════════════════════════════════════════


@app.cell(hide_code=True)
def _(chapter_result, mo):
    from scalim_misc.notebook_support.results_view import details_to_rows

    rows = details_to_rows(chapter_result["details"])
    mo.ui.table(rows, selection=None) if rows else mo.md("(无详情)")
    return


# ═══════════════════════════════════════════════════════════════
# 兼容层: 模块级 SSOT 入口
#
# ChapterRegistry → import 本模块 → 查找 run_chapter() → 调用
# 内部调用 app.run(),从 defs 提取 chapter_result dict。
# ChapterRegistry._safe_run() 自动将 dict 包装为 ExampleResult。
# ═══════════════════════════════════════════════════════════════


def run_chapter():
    """SSOT 入口: headless runner / pytest 通过此函数执行对拍。

    Returns:
        dict: chapter_result,至少包含 {"passed": bool, "summary": str}
    """
    outputs, defs = app.run()
    return defs["chapter_result"]


if __name__ == "__main__":
    app.run()