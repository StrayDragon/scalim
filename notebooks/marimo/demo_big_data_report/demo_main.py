import marimo

__generated_with = "0.20.2"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # Scalim 唯一主线教程: `demo_big_data_report`

        目标:
        - 给读者一条**唯一主线**把 Scalim 的关键能力串起来
        - 章节代码可复用: 既能演示,也能当集成对拍 runner 的实现

        结构:
        - `chapters_of_yaml_dsl/*.py`: YAML DSL + workflow 章节(含 `run_<chapter_id>()` SSOT 入口)
        - `chapters_of_ir/*.py`: IR 主线章节(含 `run_chapter()`/`run_*()` SSOT 入口)
        - `packages/scalim-misc/src/scalim_misc/demo_big_data_report/`: fixtures/oracle/工具函数(不承载教学主流程)
        - `just examples`: 唯一 gate 入口(快速对拍,justfile 内联 runner)
        - `chapters_of_yaml_dsl/declared_yaml_dsl/ecommerce_report.yaml`: 唯一完整 YAML DSL 配置示例
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

    # `marimo` 运行/导出时,显式把仓库根目录加入 `sys.path`,方便相对路径访问示例资源.
    repo_root = ensure_repo_root_on_sys_path(__file__)
    _ = sys
    return Path, repo_root


@app.cell
def _(Path, repo_root):
    demo_dir = Path(__file__).parent
    chapters_of_yaml_dsl_dir = demo_dir / "chapters_of_yaml_dsl"
    declared_yaml_dsl_dir = chapters_of_yaml_dsl_dir / "declared_yaml_dsl"
    yaml_path = declared_yaml_dsl_dir / "ecommerce_report.yaml"
    chapters_of_ir_dir = demo_dir / "chapters_of_ir"
    _ = repo_root
    return chapters_of_ir_dir, chapters_of_yaml_dsl_dir, declared_yaml_dsl_dir, demo_dir, yaml_path


@app.cell(hide_code=True)
def _(chapters_of_ir_dir, chapters_of_yaml_dsl_dir, mo):
    yaml_chapter_files = []
    if chapters_of_yaml_dsl_dir.exists():
        yaml_chapter_files = sorted([p.name for p in chapters_of_yaml_dsl_dir.glob("*.py")])

    ir_chapter_files = []
    if chapters_of_ir_dir.exists():
        ir_chapter_files = sorted([p.name for p in chapters_of_ir_dir.glob("*.py")])

    lines = ["- `chapters_of_yaml_dsl/{}`".format(name) for name in yaml_chapter_files]
    lines.extend(["- `chapters_of_ir/{}`".format(name) for name in ir_chapter_files])
    mo.md(
        r"""
        ---
        ## 章节导航

        每章 notebook 同时承担两件事:

        1) **教学/交互**: 展示过程 + UI 组件 + 失败定位
        2) **集成对拍 SSOT**: 提供 `run_<chapter_id>()` 供 `just examples`/pytest 复用
        """
    )
    if lines:
        mo.md("\n".join(lines))
    else:
        mo.callout(mo.md("章节目录尚未生成。"), kind="warn")
    return ir_chapter_files, lines, yaml_chapter_files


@app.cell(hide_code=True)
def _(mo, yaml_path):
    mo.md(
        r"""
        ---
        ## YAML DSL: 语义校验 + 加载
        """
    )
    mo.md("YAML 文件: `{}`".format(yaml_path.name))
    return


@app.cell
def _(yaml_path):
    # region SCALIM-SKILL:example-full:constraints
    from scalim.dsl.yaml_dsl import DemandRunOptions, DemandRunSecurityOptions, compile

    _loaders_module = "scalim_misc.demo_big_data_report.loaders"

    try:
        allowed_modules = frozenset([_loaders_module])
        compilation = compile(
            str(yaml_path),
            options=DemandRunOptions(security=DemandRunSecurityOptions(allowed_modules=allowed_modules)),
        )
        print("✅ `compile()` 校验/加载通过!")
        validation_passed = True
        demand_config = compilation.config
    except Exception as e:
        print("❌ `compile()` 校验/加载失败:", e)
        validation_passed = False
        demand_config = None
    # endregion

    _ = validation_passed
    return demand_config


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
def _(yaml_path):
    from notebooks.marimo.demo_big_data_report.chapters_of_ir.registry import run_all_chapters as run_all_ir_chapters
    from notebooks.marimo.demo_big_data_report.chapters_of_yaml_dsl.registry import run_all_chapters as run_all_yaml_dsl_chapters

    _ = yaml_path
    chapter_results = run_all_yaml_dsl_chapters() + run_all_ir_chapters()
    return chapter_results


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
    return rows


@app.cell(hide_code=True)
def _(chapter_results, mo):
    ok = all(r.passed for r in chapter_results)
    mo.callout(
        mo.md("## {}".format("🎉 全部章节对拍通过" if ok else "❌ 存在章节失败")),
        kind="success" if ok else "danger",
    )
    return ok


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        ---
        ## `run()` 便捷函数示例(保留为可提取的 skill 片段)
        """
    )
    return


@app.cell
def _(Path, yaml_path):
    # region SCALIM-SKILL:example-full:run-yaml
    from scalim.dsl.yaml_dsl import (
        CaptureRows,
        DemandRunOptions,
        DemandRunOutputOptions,
        DemandRunSecurityOptions,
        DemandRunTemplateOptions,
        run,
    )

    # 注意: `run()` 需要 `allowlist` 配置
    _loaders_module = "scalim_misc.demo_big_data_report.loaders"

    try:
        allowed_modules = frozenset([_loaders_module])
        _init_vars = {"order_ids": []}
        result = run(
            str(yaml_path),
            options=DemandRunOptions(
                security=DemandRunSecurityOptions(allowed_modules=allowed_modules),
                template=DemandRunTemplateOptions(init_vars=_init_vars),
                outputs=DemandRunOutputOptions(capture=CaptureRows()),
            ),
        )
        print("✅ `run()` 执行成功!")
        print("   总行数:", result.total_rows)
        print("   输出路径:", result.output_path or "(内存)")
        print("   captured_rows:", "enabled" if result.captured_rows is not None else "disabled")
    except Exception as e:
        print("⚠️ `run()` 执行失败:", e)
        result = None
    # endregion

    _ = Path
    return result


if __name__ == "__main__":
    app.run()
