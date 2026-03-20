import marimo

__generated_with = "0.20.2"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # Examples suite: `example_public_api_suite`

        这是一套 **回归/覆盖优先** 的示例套件，用于把 `scalim.*` 的稳定公开入口模块 `__all__` 做 deterministic 覆盖，
        并提供扩展点（hook/observer/events/components 注入）的最小闭环示例。

        目标读者: 工程同学（写 YAML / 维护集成回归）。

        Gate:
        - `just examples`
        - 或直接运行：`python notebooks/marimo/run_examples.py --suite example_public_api_suite`
        """
    )
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    import sys
    from pathlib import Path

    from scalim_misc.notebook_support.pathing import ensure_repo_root_on_sys_path

    repo_root = ensure_repo_root_on_sys_path(__file__)
    _ = sys
    return Path, repo_root


@app.cell
def _(Path, repo_root):
    suite_dir = Path(__file__).parent
    chapters_dir = suite_dir / "chapters"
    _ = repo_root
    return chapters_dir, suite_dir


@app.cell(hide_code=True)
def _(chapters_dir, mo):
    chapter_files = []
    if chapters_dir.exists():
        chapter_files = sorted([p.name for p in chapters_dir.glob("*.py") if p.name != "registry.py"])

    lines = ["- `chapters/{}`".format(name) for name in chapter_files]
    mo.md(
        r"""
        ---
        ## 章节导航

        每章 notebook 同时承担两件事:

        1) **教学/交互入口**: 展示执行结果与失败定位
        2) **集成对拍 SSOT**: 提供 `run_<chapter_id>()`（或 `run_chapter()`）供 `just examples`/pytest 复用
        """
    )
    if lines:
        mo.md("\n".join(lines))
    else:
        mo.callout(mo.md("`chapters/` 目录尚未生成。"), kind="warn")
    return chapter_files, lines


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        ---
        ## 一键跑完所有章节(对拍/集成验证同源)
        """
    )
    return


@app.cell
def _():
    from notebooks.marimo.example_public_api_suite.chapters.registry import run_all_chapters

    chapter_results = run_all_chapters()
    return (chapter_results,)


@app.cell
def _(chapter_results, mo):
    rows = [
        {
            "chapter": str(r.example_id).split("/", 1)[1] if "/" in str(r.example_id) else str(r.example_id),
            "passed": r.passed,
            "summary": str(r.summary or "").splitlines()[0] if r.summary else "",
        }
        for r in chapter_results
    ]
    mo.ui.table(rows, selection=None)
    return (rows,)


@app.cell(hide_code=True)
def _(chapter_results, mo):
    ok = all(r.passed for r in chapter_results)
    mo.callout(
        mo.md("## {}".format("🎉 全部章节对拍通过" if ok else "❌ 存在章节失败")),
        kind="success" if ok else "danger",
    )
    return (ok,)


if __name__ == "__main__":
    app.run()
