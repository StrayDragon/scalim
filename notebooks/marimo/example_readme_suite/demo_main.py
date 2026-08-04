import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # Examples suite: `example_readme_suite`

        根 README 假数据示例的 **可校验 marimo 套件**（最小 Python / YAML + 内存对比）。

        | 角色 | 路径 |
        | --- | --- |
        | 章节 SSOT | `chapters/ch*.py`（`run_chapter`） |
        | 共享实现 | `support/` |
        | 公开页注入/图 | `support/inject.py` + `just gen-readme-examples` |
        | Gate | `just examples`（纳入 `just qa`） |

        不替代主线 `demo_big_data_report`。
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

    _ = ensure_repo_root_on_sys_path(__file__)
    return


@app.cell(hide_code=True)
def _(mo):
    from pathlib import Path

    chapters_dir = Path(__file__).parent / "chapters"
    chapter_files = sorted([p.name for p in chapters_dir.glob("ch*.py")])
    lines = ["- `chapters/{}`".format(name) for name in chapter_files]
    mo.md("## 章节\n\n" + "\n".join(lines))
    return chapter_files, chapters_dir


@app.cell(hide_code=True)
def _(mo):
    mo.md("## 一键跑完（与 `just examples` 同源）")
    return


@app.cell
def _():
    from notebooks.marimo.example_readme_suite.chapters.registry import run_all_chapters

    chapter_results = run_all_chapters()
    return (chapter_results,)


@app.cell
def _(chapter_results, mo):
    rows = [
        {
            "chapter": str(r.example_id),
            "passed": bool(r.passed),
            "summary": str(r.summary or "")[:160],
        }
        for r in chapter_results
    ]
    mo.ui.table(rows)
    return (rows,)


if __name__ == "__main__":
    app.run()
