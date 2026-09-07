"""Cells-native 章节 notebook 模板（金标准: example_hooks_events_scenarios/chapters/ch010_post_export_upload.py）。

用途: 新建/迁移章节时的骨架参考。本文件位于 `_templates/`，不会被
`just examples` 的 suite 发现（非 demo_/example_ 前缀）也不会被
`chapters*/registry.py` 收录 —— 仅文档用途。

cells-native 契约（llmanspec/specs/examples-marimo/examples-marimo.feature
@req:r497 / r1111 / r1112）:
1. 执行主路径（scalim 调用装配、参数组装、中间产物展示、断言展开）位于 marimo cells 内
2. 模块级仅保留 `app = marimo.App(...)` + 薄 `run_chapter()`（app.run() + defs["chapter_result"]）
3. 末尾 cell 产出 `chapter_result = {"passed", "summary", "details"}` 供 headless 提取
4. 交互 UI 控件始终展示；headless/script 模式用控件默认值自动执行（同源）
5. 可复用零件（fixtures/mock/类）可留 support/，但不得承载执行主路径
"""

import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


# Cell 1 — 教学目标（mo.md：主题、主线装配步骤、Gate 入口）


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # <suite> / <chapter_id>

        演示：**一句话主题**。

        主线装配过程（每个步骤一个 cell，可就地修改重跑）：
        1. 定义零件（Observer/Hook/options 工厂）
        2. fixtures / mock 准备（内容可见）
        3. 组装运行选项
        4. 执行 → 中间产物
        5. 断言展开 → chapter_result

        对拍入口: `run_chapter()` → `app.run()` → `chapter_result`
        Gate: `just examples`
        """
    )
    return


# Cell 2 — marimo 自身


@app.cell
def _():
    import marimo as mo

    return (mo,)


# Cell 3 — 仓库路径设置（返回 repo_root，供下一 cell 显式依赖保证 import 顺序）


@app.cell
def _():
    from scalim_misc.notebook_support.pathing import ensure_repo_root_on_sys_path

    repo_root = ensure_repo_root_on_sys_path(__file__)
    return (repo_root,)


# Cell 4 — 业务 imports（scalim API + support 零件；`scalim.*` import 保留供覆盖 gate 统计）


@app.cell
def _(repo_root):
    import tempfile
    from pathlib import Path
    from typing import Any, Dict, List, Optional, Set

    from scalim.dsl import yaml_dsl as api
    from scalim.events import Event, EventType
    from scalim.ob.observer import Observer
    from scalim_misc.notebook_support.chapter_result import make_chapter_result, render_checks

    _ = repo_root
    return (
        Any,
        Dict,
        Event,
        EventType,
        List,
        Observer,
        Optional,
        Path,
        Set,
        api,
        make_chapter_result,
        render_checks,
        tempfile,
    )


# Cell 5 — 交互旋钮（永远展示；script 模式用默认值）


@app.cell
def _(mo):
    knob = mo.ui.slider(1, 100, value=10, step=1, label="示例旋钮（每批处理行数）")
    knob
    return (knob,)


# Cell 6 — 零件定义（教学核心：Observer/Hook/options 工厂，逻辑可见）


@app.cell
def _(Event, EventType, List, Observer, Optional, Set):
    class SampleObserver(Observer):
        def __init__(self) -> None:
            self.event_types: Optional[Set[EventType]] = {EventType.LOADER_CALL}
            self.events: List[Event] = []

        def on_event(self, event: Event) -> None:
            if event.event_type is EventType.LOADER_CALL:
                self.events.append(event)

    return (SampleObserver,)


# Cell 7 — fixtures / mock 准备（内容可见）


@app.cell
def _(Path, tempfile):
    import shutil

    tmp = Path(tempfile.mkdtemp(prefix="scalim-template-"))
    print("tmp dir:", tmp)
    return tmp,


# Cell 8 — 组装运行选项（knob.value 参与装配）


@app.cell
def _(knob):
    print("knob value =", knob.value)
    return


# Cell 9 — 执行 + 中间产物（每步打印/表格展示）


@app.cell
def _():
    result = None  # 替换为真实 scalim 调用
    print("总行数:", result)
    return (result,)


# Cell 10 — 断言展开（幂等：交互重跑不累积误判）


@app.cell
def _(result, render_checks):
    checks = {
        "示例断言 A": result is not None,
        "示例断言 B": True,
    }
    render_checks(checks)
    return (checks,)


# Cell 11 — 汇总 chapter_result（CI 提取点；契约 {"passed","summary","details"}）


@app.cell
def _(checks, make_chapter_result):
    chapter_result = make_chapter_result(
        passed=all(checks.values()),
        summary="示例 summary",
        details={"checks": {k: bool(v) for k, v in checks.items()}},
    )
    return (chapter_result,)


# Cell 12 — 结果展示（交互时可看到）


@app.cell(hide_code=True)
def _(chapter_result, mo):
    mo.callout(
        mo.md("## {}: {}".format("✅ PASS" if chapter_result["passed"] else "❌ FAIL", chapter_result["summary"])),
        kind="success" if chapter_result["passed"] else "danger",
    )
    return


# Cell 13 — 详情表格


@app.cell(hide_code=True)
def _(chapter_result, mo):
    from scalim_misc.notebook_support.results_view import details_to_rows

    rows = details_to_rows(chapter_result["details"])
    mo.ui.table(rows, selection=None) if rows else mo.md("(无详情)")
    return


# 兼容层: 模块级 SSOT 入口（ChapterRegistry → run_chapter() → app.run() → defs["chapter_result"]）


def run_chapter():
    """SSOT 入口: headless runner / pytest 通过此函数执行对拍。"""
    outputs, defs = app.run()
    return defs["chapter_result"]


if __name__ == "__main__":
    app.run()