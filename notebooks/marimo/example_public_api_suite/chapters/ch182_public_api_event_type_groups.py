"""Cells-native marimo notebook: ch182_public_api_event_type_groups.

迁移对照:
  Before: 模块级 run_public_api_event_type_groups() 持全部逻辑;cells 薄壳
  After:  type_groups 分组收集 + 6 对预期断言在 cells 内
"""

import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # example_public_api_suite / ch182_public_api_event_type_groups

        本章目标:
        - `scalim.events.type_groups` 目录分组（pipeline/loader/field/workflow 等）
        - 自省收集分组内 EventType 枚举 + 关键对拍（与 `EventType` 常量一致）

        ## 主线装配过程（每个步骤一个 cell，可就地修改重跑）

        1. 遍历 `type_groups.__all__` 递归收集 EventType
        2. 6 对关键引用对拍（pipeline.start / loader.call / field.compute / workflow...）
        3. 断言：全枚举值有效 + 无新值 + 对拍一致
        4. 汇总 chapter_result

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
    from typing import Any, Dict, List

    from scalim.events import EventType, type_groups
    from scalim_misc.notebook_support.chapter_result import make_chapter_result, render_checks

    return Any, Dict, EventType, List, make_chapter_result, render_checks, type_groups


@app.cell
def _(Any, EventType, List, render_checks, type_groups):
    # 零件: 递归收集 node 中的 EventType
    def collect_event_types(node: Any) -> List[EventType]:
        if isinstance(node, EventType):
            return [node]
        if hasattr(node, "__dict__"):
            out: List[EventType] = []
            for value in getattr(node, "__dict__", {}).values():
                out.extend(collect_event_types(value))
            return out
        return []

    # 收集: type_groups.__all__ 下所有分组
    values: List[EventType] = []
    for group_name in type_groups.__all__:
        values.extend(collect_event_types(getattr(type_groups, group_name)))

    expected_pairs = [
        ("pipeline.start", type_groups.pipeline.start, EventType.PIPELINE_START),
        ("pipeline.end", type_groups.pipeline.end, EventType.PIPELINE_END),
        ("loader.call", type_groups.loader.call, EventType.LOADER_CALL),
        ("field.compute", type_groups.field.compute, EventType.FIELD_COMPUTE),
        ("workflow.node.start", type_groups.workflow.node.start, EventType.WORKFLOW_NODE_START),
        ("workflow.node.end", type_groups.workflow.node.end, EventType.WORKFLOW_NODE_END),
    ]

    pairs_ok = all(left == right for _, left, right in expected_pairs)
    print("values =", len(values), "unique =", len(set(values)), "pairs_ok =", pairs_ok)
    return expected_pairs, pairs_ok, values


@app.cell
def _(EventType, pairs_ok, render_checks, values):
    valid_enum_values = all(isinstance(v, EventType) for v in values)
    no_new_values = set(values).issubset(set(EventType))
    checks = {
        "分组收集非空": bool(values),
        "全部为 EventType 枚举": valid_enum_values,
        "无目录外新值": no_new_values,
        "6 对关键引用一致": pairs_ok,
    }
    render_checks(checks)
    return checks, no_new_values, valid_enum_values


@app.cell
def _(checks, expected_pairs, make_chapter_result, pairs_ok, values):
    passed = bool(all(checks.values()))
    summary = "values={} unique={} pairs_ok={}".format(len(values), len(set(values)), pairs_ok)
    # 对拍期望（教学 payload；headless 可经 details 键定位）
    expected = {"groups_nonempty": True, "all_event_type_enum": True, "no_unknown_values": True, "key_pairs_consistent": True}
    print("expected:", expected)

    chapter_result = make_chapter_result(
        passed=passed,
        summary=summary,
        details={
            "expected": expected,
            "pairs": [{"id": k, "value": str(left), "expected": str(right), "ok": left == right} for k, left, right in expected_pairs],
            "unique_values": sorted({str(v) for v in values}),
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
