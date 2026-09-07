"""Cells-native marimo notebook: ch140_workflow_cache_pool_pin.

迁移对照:
  Before: 模块级 run_*() 持全部逻辑;cells 薄壳
  After:  两个 cache_pool 对照运行、cache 信号断言全部在 cells 内
"""

import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / workflow_cache_pool_pin

        ## 回归点

        cache_pool `pin` 语义对照：
        - 基线（无 pin）：引用计数归零 → `refcount_zero` 淘汰
        - 启用 pin（preload_forever + source_id）：仅 `workflow_end` 统一释放，
          release 事件 `is_pinned=True`

        ## 主线装配过程（每个步骤一个 cell，可就地修改重跑）

        1. 零件：jsonl 读取 / cache 信号提取 / viz 路径定位
        2. 基线运行（no_pin）→ 收集 evict/release 信号
        3. pin 运行 → 收集信号
        4. 断言：refcount_zero 仅基线出现、workflow_end 仅 pin 出现、is_pinned 标志
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
    workflow_yaml_no_pin = demo_dir / "chapters_of_yaml_dsl" / "declared_yaml_dsl" / "workflow_fixture.yaml"
    workflow_yaml_pin = demo_dir / "chapters_of_yaml_dsl" / "declared_yaml_dsl" / "workflow_fixture_cache_pool_pin.yaml"
    _ = repo_root
    return Path, demo_dir, workflow_yaml_no_pin, workflow_yaml_pin


@app.cell
def _(Path):
    import json
    import tempfile
    from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

    from scalim.dsl.yaml_dsl import (
        DemandRunOptions,
        DemandRunOutputOptions,
        DemandRunSecurityOptions,
        DemandRunTemplateOptions,
        RunOverrides,
        WorkflowRunOptions,
        run_workflow,
    )
    from scalim.dsl.yaml_dsl.workflow_types import WorkflowCachePoolPin, WorkflowCachePoolPreloadForeverShared, WorkflowRuntimeOptions
    from scalim.ob.presets.viz import VizObserverConfig
    from scalim_misc.demo_big_data_report.cases import build_test_config_small
    from scalim_misc.demo_big_data_report.loaders import (
        ECommerceConfig,
        reset_workflow_preload_counter_calls,
        set_config,
    )
    from scalim_misc.notebook_support.chapter_result import make_chapter_result, render_checks

    return (
        Any,
        DemandRunOptions,
        DemandRunOutputOptions,
        DemandRunSecurityOptions,
        DemandRunTemplateOptions,
        Dict,
        ECommerceConfig,
        List,
        Mapping,
        Optional,
        Path,
        RunOverrides,
        Sequence,
        Tuple,
        VizObserverConfig,
        WorkflowCachePoolPin,
        WorkflowCachePoolPreloadForeverShared,
        WorkflowRunOptions,
        WorkflowRuntimeOptions,
        build_test_config_small,
        json,
        make_chapter_result,
        render_checks,
        reset_workflow_preload_counter_calls,
        run_workflow,
        set_config,
        tempfile,
    )


@app.cell
def _(Any, Dict, List, Mapping, Path, Sequence, Tuple, json):
    # 零件: jsonl 读取 / cache 信号提取 / viz 路径定位
    def read_jsonl(path: Path) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        if not path.exists():
            return events
        for line in path.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if not text:
                continue
            events.append(json.loads(text))
        return events

    def workflow_events_path(base_dir: Path) -> Path:
        return base_dir / "scalim-viz" / "workflow" / "viz_events.jsonl"

    def extract_cache_signals(events: Sequence[Mapping[str, Any]]) -> Tuple[List[str], List[str]]:
        reasons: List[str] = []
        release_is_pinned: List[str] = []
        for e in events:
            if not isinstance(e, dict):
                continue
            event_type = str(e.get("event_type") or "")
            payload = e.get("payload") or {}
            if not isinstance(payload, dict):
                continue
            if event_type == "workflow_cache_evict":
                reasons.append(str(payload.get("reason") or ""))
            if event_type == "workflow_cache_release":
                release_is_pinned.append(str(payload.get("is_pinned") or ""))
        return reasons, release_is_pinned

    return extract_cache_signals, read_jsonl, workflow_events_path


@app.cell
def _(Path, build_test_config_small, reset_workflow_preload_counter_calls, set_config, tempfile):
    import atexit
    import shutil

    cfg = build_test_config_small()
    set_config(cfg)
    ALLOWED_MODULES = frozenset(["scalim_misc.demo_big_data_report.loaders"])
    reset_workflow_preload_counter_calls()

    tmp = Path(tempfile.mkdtemp(prefix="scalim-wf-pin-"))
    atexit.register(lambda: shutil.rmtree(tmp, ignore_errors=True))
    viz_no_pin = tmp / "no_pin"
    viz_pin = tmp / "pin"
    print("tmp dir:", tmp)
    return ALLOWED_MODULES, cfg, tmp, viz_no_pin, viz_pin


@app.cell
def _(
    ALLOWED_MODULES,
    DemandRunOptions,
    DemandRunOutputOptions,
    DemandRunSecurityOptions,
    DemandRunTemplateOptions,
    RunOverrides,
    VizObserverConfig,
    WorkflowCachePoolPreloadForeverShared,
    WorkflowRunOptions,
    WorkflowRuntimeOptions,
    run_workflow,
    viz_no_pin,
    workflow_yaml_no_pin,
):
    # 基线: 无 pin -> refcount_zero 淘汰
    _ = run_workflow(
        str(workflow_yaml_no_pin),
        options=WorkflowRunOptions(
            demand=DemandRunOptions(
                security=DemandRunSecurityOptions(allowed_modules=ALLOWED_MODULES),
                template=DemandRunTemplateOptions(init_vars={"order_ids": []}),
                outputs=DemandRunOutputOptions(overrides=RunOverrides(viz_config=VizObserverConfig(output_dir=str(viz_no_pin)))),
            ),
            runtime=WorkflowRuntimeOptions(
                cache_pool=WorkflowCachePoolPreloadForeverShared(max_entries=16),
            ),
        ),
    )
    return


@app.cell
def _(
    ALLOWED_MODULES,
    DemandRunOptions,
    DemandRunOutputOptions,
    DemandRunSecurityOptions,
    DemandRunTemplateOptions,
    RunOverrides,
    VizObserverConfig,
    WorkflowCachePoolPin,
    WorkflowCachePoolPreloadForeverShared,
    WorkflowRunOptions,
    WorkflowRuntimeOptions,
    run_workflow,
    viz_pin,
    workflow_yaml_pin,
):
    # 启用 pin: 引用计数归零不淘汰, workflow_end 统一释放
    _ = run_workflow(
        str(workflow_yaml_pin),
        options=WorkflowRunOptions(
            demand=DemandRunOptions(
                security=DemandRunSecurityOptions(allowed_modules=ALLOWED_MODULES),
                template=DemandRunTemplateOptions(init_vars={"order_ids": []}),
                outputs=DemandRunOutputOptions(overrides=RunOverrides(viz_config=VizObserverConfig(output_dir=str(viz_pin)))),
            ),
            runtime=WorkflowRuntimeOptions(
                cache_pool=WorkflowCachePoolPreloadForeverShared(
                    max_entries=16,
                    pin=(WorkflowCachePoolPin(kind="preload_forever", source_id="preload_counter"),),
                ),
            ),
        ),
    )
    return


@app.cell
def _(extract_cache_signals, read_jsonl, viz_no_pin, viz_pin, workflow_events_path):
    events_no_pin = read_jsonl(workflow_events_path(viz_no_pin))
    reasons_no_pin, releases_no_pin = extract_cache_signals(events_no_pin)
    events_pin = read_jsonl(workflow_events_path(viz_pin))
    reasons_pin, releases_pin = extract_cache_signals(events_pin)
    print("no_pin reasons:", reasons_no_pin)
    print("pin   reasons:", reasons_pin)
    return events_no_pin, events_pin, reasons_no_pin, reasons_pin, releases_no_pin, releases_pin


@app.cell
def _(render_checks, reasons_no_pin, reasons_pin, releases_no_pin, releases_pin):
    ok_no_pin = "refcount_zero" in set(reasons_no_pin)
    ok_pin = ("workflow_end" in set(reasons_pin)) and ("refcount_zero" not in set(reasons_pin))
    ok_release_flag = ("True" in set(releases_pin)) and ("True" not in set(releases_no_pin))
    checks = {
        "基线出现 refcount_zero 淘汰": ok_no_pin,
        "pin 仅 workflow_end 释放": ok_pin,
        "release is_pinned 标志正确": ok_release_flag,
    }
    render_checks(checks)
    return checks, ok_no_pin, ok_pin, ok_release_flag


@app.cell
def _(
    checks,
    events_no_pin,
    events_pin,
    make_chapter_result,
    ok_no_pin,
    ok_pin,
    ok_release_flag,
    reasons_no_pin,
    reasons_pin,
    releases_no_pin,
    releases_pin,
    viz_no_pin,
    viz_pin,
    workflow_yaml_no_pin,
    workflow_yaml_pin,
):
    passed = bool(all(checks.values()))
    summary = "no_pin={} pin={} release_is_pinned={}".format(ok_no_pin, ok_pin, ok_release_flag)
    # 对拍期望（教学 payload；headless 可经 details 键定位）
    expected = {"no_pin_refcount_zero_evict": True, "pin_released_only_at_workflow_end": True, "release_unpinned_flag_ok": True}
    print("expected:", expected)

    chapter_result = make_chapter_result(
        passed=passed,
        summary=summary,
        details={
            "expected": expected,
            "workflow_yaml_no_pin": str(workflow_yaml_no_pin),
            "workflow_yaml_pin": str(workflow_yaml_pin),
            "viz_dirs": {"no_pin": str(viz_no_pin), "pin": str(viz_pin)},
            "evict_reasons": {"no_pin": reasons_no_pin, "pin": reasons_pin},
            "release_is_pinned": {"no_pin": releases_no_pin, "pin": releases_pin},
            "events_count": {"no_pin": len(events_no_pin), "pin": len(events_pin)},
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
