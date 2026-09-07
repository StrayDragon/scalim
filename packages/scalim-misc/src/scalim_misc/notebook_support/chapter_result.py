"""Cells-native chapter_result 组装助手（不依赖 marimo，headless 可导入）。

cells-native 章节的契约定式：

- 章节执行主路径位于 marimo cells 内，末尾 cell 产出 ``chapter_result`` 字典；
- 模块级 ``run_chapter()`` 薄适配层执行 ``app.run()`` 并从 ``defs`` 提取
  ``chapter_result``；
- ``ChapterRegistry._safe_run()`` 把该 dict 包装为 ``ExampleResult``（oracle 契约）。

本模块 MUST NOT 依赖 marimo，保证 ``just examples`` / pytest / 交互三种场景同源。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping

_ORACLE_KIND = "oracle"
_PASS_MARK = "✅"
_FAIL_MARK = "❌"


def make_chapter_result(
    *,
    passed: bool,
    summary: str,
    details: dict[str, Any] | None = None,
    kind: str = _ORACLE_KIND,
) -> dict[str, Any]:
    """组装标准 ``chapter_result`` 字典（契约：``{"passed", "summary", "details"}``）。

    Args:
        passed: 章节对拍是否通过。
        summary: 一行可读摘要（headless runner / pytest 直接展示）。
        details: 结构化细节，供 ``details_to_rows()`` 渲染为 notebook 表格。
        kind: 结果类别，默认 ``"oracle"``（与 ``ExampleResult.kind`` 对齐）。
    """
    return {
        "passed": bool(passed),
        "kind": str(kind),
        "summary": str(summary),
        "details": details,
    }


def render_checks(checks: Mapping[str, bool], *, printer: Any = print) -> None:
    """逐行打印断言清单（✅/❌），保证交互与 headless 两种模式观察点一致。

    断言展开建议放在 cells 内的独立 cell；断言须对交互重跑幂等
    （如 server 侧用「存在匹配」语义而非「精确计数」）。
    """
    for name, ok in checks.items():
        printer("{:>36}: {}".format(str(name), _PASS_MARK if bool(ok) else _FAIL_MARK))


def checks_passed(checks: Mapping[str, bool]) -> bool:
    """聚合断言清单：全部通过才为 True。"""
    return bool(checks) and all(bool(ok) for ok in checks.values())