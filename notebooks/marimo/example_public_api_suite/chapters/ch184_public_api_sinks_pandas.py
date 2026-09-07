"""Cells-native marimo notebook: ch184_public_api_sinks_pandas.

迁移对照:
  Before: 模块级 run_public_api_sinks_pandas() 持全部逻辑;cells 薄壳
  After:  PandasRowSink 闭环在 cells 内
"""

import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # example_public_api_suite / ch184_public_api_sinks_pandas

        本章目标:
        - `PandasRowSink` 最小闭环：write_batch → to_dataframe → 行/列对拍

        ## 主线装配过程（每个步骤一个 cell，可就地修改重跑）

        1. `PandasRowSink(field_names=["id", "value"])` + write_batch
        2. `to_dataframe()`（pandas 为可选依赖，缺失时预期失败）
        3. 断言：行相等 + 列顺序
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

    from scalim.sinks.pandas import PandasRowSink
    from scalim_misc.notebook_support.chapter_result import make_chapter_result, render_checks

    return Any, Dict, List, PandasRowSink, make_chapter_result, render_checks


@app.cell
def _(Any, Dict, List):
    # 零件: 行归一化(id/value 转 int)
    def normalize_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        for row in rows:
            out: Dict[str, Any] = dict(row)
            if "id" in out and out["id"] is not None:
                out["id"] = int(out["id"])
            if "value" in out and out["value"] is not None:
                out["value"] = int(out["value"])
            normalized.append(out)
        return normalized

    return normalize_rows


@app.cell
def _(PandasRowSink):
    sink = PandasRowSink(field_names=["id", "value"])
    sink.write_batch([{"id": 1, "value": 10}, {"id": 2, "value": 20}])
    return sink


@app.cell
def _(normalize_rows, render_checks, sink):
    try:
        df = sink.to_dataframe()
    except ImportError as exc:  # noqa: BLE001 — pandas 可选依赖缺失预期
        df = None
        print("pandas 缺失:", exc)
    rows = normalize_rows(df.to_dict(orient="records")) if df is not None else []
    checks = {
        "pandas 可选依赖可用": df is not None,
        "rows 对拍一致": rows == [{"id": 1, "value": 10}, {"id": 2, "value": 20}],
        "列顺序 == [id, value]": df is not None and list(df.columns) == ["id", "value"],
    }
    render_checks(checks)
    return checks, df, rows


@app.cell
def _(checks, df, make_chapter_result, rows):
    passed = bool(all(checks.values()))
    summary = "rows={} columns={}".format(len(rows), ",".join([str(c) for c in df.columns]))
    chapter_result = make_chapter_result(
        passed=passed,
        summary=summary,
        details={
            "rows": rows,
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
