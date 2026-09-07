"""Cells-native marimo notebook: ch030_upload_retry.

迁移对照 (ch010 同款):
  Before: 薄壳 cells + support/upload_retry.py 持有全部主路径
  After:  Observer 重试/装配/断言全部在 cells 内;support 只留 fixtures/http_mock 零件
"""

import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # example_hooks_events_scenarios / ch030_upload_retry

        演示：**上传遇瞬态 503 时应用侧重试至成功**（重试逻辑在 Observer 应用代码里，
        Scalim 只负责投递 `OUTPUT_TARGET_END`）。

        主线装配过程（每个步骤一个 cell，可就地修改重跑）：

        1. 定义零件：`UploadWithRetry` Observer（3 次尝试,记录 attempts 序列）
        2. 启动 mock server（前 2 次上传返回 503,第 3 次 200）
        3. 写入 demand YAML；组装 `DemandRunOptions`
        4. 运行 demand → Observer 重试并捕获上传
        5. 证据核对：attempts 序列 [503, 503, 200] + server 实收
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
    from scalim.events import Event, EventType
    from scalim.ob.observer import EventDispatchObserver
    from scalim_misc.notebook_support.chapter_result import make_chapter_result, render_checks
    from notebooks.marimo.example_hooks_events_scenarios.support.fixtures import ALLOWED_MODULES, write_minimal_demand_yaml
    from notebooks.marimo.example_hooks_events_scenarios.support.http_mock import (
        build_upload_payload,
        post_upload_with_status,
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
        Optional,
        Path,
        Set,
        api,
        build_upload_payload,
        make_chapter_result,
        post_upload_with_status,
        render_checks,
        start_mock_http_server,
        tempfile,
        write_minimal_demand_yaml,
    )


@app.cell
def _(ALLOWED_MODULES, Any, Event, EventDispatchObserver, EventType, List, Optional, Path, Set, api, build_upload_payload, post_upload_with_status):
    # 零件: 应用侧重试 Observer — 前几次 503 自动重试,记录完整 attempts 序列
    class UploadWithRetry(EventDispatchObserver):
        def __init__(self, *, base_url: str, max_attempts: int = 3) -> None:
            self.event_types: Optional[Set[EventType]] = {EventType.OUTPUT_TARGET_END}
            self.base_url = str(base_url)
            self.max_attempts = int(max_attempts)
            self.attempts: List[Dict[str, Any]] = []
            self.uploaded: List[Dict[str, Any]] = []
            self.errors: List[str] = []

        def on_output_target_end(self, event: Event) -> None:
            body = event.payload
            payload = build_upload_payload(
                target_id=str(body.target_id),
                output_path=None if body.output_path is None else str(body.output_path),
                row_count=int(body.row_count),
            )
            last_error: Optional[str] = None
            for attempt in range(1, self.max_attempts + 1):
                status, data = post_upload_with_status(self.base_url, payload)
                self.attempts.append({"attempt": attempt, "status": status, "body": data})
                if status == 200:
                    self.uploaded.append(payload)
                    return
                last_error = "status={} body={!r}".format(status, data)
            self.errors.append(last_error or "upload failed")

    # 零件: 运行选项工厂
    def demand_options(*, components: List[Any], output_root: Path) -> api.DemandRunOptions:
        overrides = api.RunOverrides.csv_file(
            output_root=str(output_root),
            fields=["item_id", "dim_id"],
            header_fields_output_by="name",
        )
        return api.DemandRunOptions(
            security=api.DemandRunSecurityOptions(allowed_modules=ALLOWED_MODULES),
            runtime=api.DemandRunRuntimeOptions(components=list(components), batch_size=10),
            outputs=api.DemandRunOutputOptions(overrides=overrides),
        )

    return UploadWithRetry, demand_options


@app.cell
def _(Path, start_mock_http_server, tempfile):
    import atexit
    import shutil

    # 前 2 次上传返回 503,之后恢复 200
    server = start_mock_http_server(upload_failures_remaining=2, upload_fail_status=503)
    tmp = Path(tempfile.mkdtemp(prefix="scalim-hooks-ch030-"))
    atexit.register(server.stop)
    atexit.register(lambda: shutil.rmtree(tmp, ignore_errors=True))

    print("mock server:", server.base_url)
    print("故障注入:   前 2 次 POST /upload → 503,之后 200")
    return server, tmp


@app.cell
def _(mo, tmp, write_minimal_demand_yaml):
    demand_path = write_minimal_demand_yaml(tmp / "demand.yaml")
    demand_yaml_text = demand_path.read_text(encoding="utf-8")

    mo.md("**demand.yaml**:\n\n```yaml\n{}\n```".format(demand_yaml_text))
    return demand_path, demand_yaml_text


@app.cell
def _(UploadWithRetry, demand_options, api, demand_path, server, tmp):
    obs = UploadWithRetry(base_url=server.base_url, max_attempts=3)
    result = api.run(
        str(demand_path),
        options=demand_options(components=[obs], output_root=tmp / "out"),
    )

    print("total_rows =", result.total_rows)
    print("attempts   =", [(a["attempt"], a["status"]) for a in obs.attempts])
    print("uploaded   =", len(obs.uploaded))
    print("errors     =", obs.errors)

    return obs, result


@app.cell
def _(mo, obs, server):
    mo.ui.tabs(
        {
            "observer attempts": mo.ui.table(list(obs.attempts), selection=None),
            "observer uploaded": mo.ui.table(list(obs.uploaded), selection=None),
            "server upload_attempts": mo.ui.table(list(server.state.upload_attempts), selection=None),
            "server uploads": mo.ui.table(list(server.state.uploads), selection=None),
        }
    )
    return


@app.cell
def _(obs, render_checks, result, server):
    # 断言展开: observer 实例每次运行重建,精确序列幂等;server 侧用存在匹配
    server_has_payload = any(
        s.get("target_id") == u.get("target_id") and int(s.get("row_count") or -1) == int(u.get("row_count") or 0)
        for u in obs.uploaded
        for s in server.state.uploads
    )

    checks = {
        "rows == 3": result.total_rows == 3,
        "uploaded == 1": len(obs.uploaded) == 1,
        "无错误": not obs.errors,
        "attempts == [503, 503, 200]": [a["status"] for a in obs.attempts] == [503, 503, 200],
        "重试次数 == 3": len(obs.attempts) == 3,
        "server 实收该 payload": server_has_payload,
        "server 收到 >=3 次尝试": len(server.state.upload_attempts) >= 3,
    }
    render_checks(checks)
    return checks


@app.cell
def _(checks, make_chapter_result, obs, result, server):
    passed = bool(all(checks.values()))
    summary = "rows={} attempts={} statuses={} uploaded={} errors={}".format(
        result.total_rows,
        len(obs.attempts),
        [a["status"] for a in obs.attempts],
        len(obs.uploaded),
        obs.errors,
    )
    chapter_result = make_chapter_result(
        passed=passed,
        summary=summary,
        details={
            "attempts": list(obs.attempts),
            "uploaded": list(obs.uploaded),
            "server_uploads": list(server.state.uploads),
            "server_upload_attempts": list(server.state.upload_attempts),
            "checks": {k: bool(v) for k, v in checks.items()},
            "note": "retry lives in Observer application code; Scalim only delivers OUTPUT_TARGET_END",
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