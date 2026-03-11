import marimo

__generated_with = "0.19.9"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # 多输出组合与派生汇总

        这个示例演示 `output_composition` 的 `IR/Python-only` 链路:

        - 同一次运行写入同一个 workbook 的 `Detail` / `Summary` / `Meta` / `Audit`
        - 明细 sheet 用纯 Python 对照组做字段级对拍
        - 汇总 sheet 用“从明细手工聚合”的方式再做一次对拍
        """
    )
    return


@app.cell
def _():
    import sys as _sys
    import tempfile
    from pathlib import Path as _Path

    _this_dir = _Path(__file__).parent
    if str(_this_dir) not in _sys.path:
        _sys.path.insert(0, str(_this_dir))

    from _derived_outputs_demo import run_derived_outputs_demo

    with tempfile.TemporaryDirectory() as tmpdir:
        workbook_path = _Path(tmpdir) / "derived_outputs_demo.xlsx"
        demo_result = run_derived_outputs_demo(str(workbook_path))

        print("✅ 工作簿路径:", demo_result.workbook_path)
        print("✅ 工作表列表:", demo_result.sheet_names)
        print("✅ 明细对拍:", demo_result.detail_verification.summary)
        print("✅ 汇总对拍:", demo_result.summary_message)

        detail_preview = demo_result.detail_rows[:10]
        summary_preview = demo_result.summary_rows
        outputs = demo_result.outputs

    return detail_preview, outputs, summary_preview


@app.cell(hide_code=True)
def _(detail_preview, mo, outputs, summary_preview):
    mo.vstack(
        [
            mo.md("## 输出路径"),
            mo.ui.table([{"target_id": key, "path": value} for key, value in sorted(outputs.items())], selection=None),
            mo.md("## 明细预览"),
            mo.ui.table(detail_preview, selection=None),
            mo.md("## 汇总预览"),
            mo.ui.table(summary_preview, selection=None),
        ]
    )
    return


if __name__ == "__main__":
    app.run()
