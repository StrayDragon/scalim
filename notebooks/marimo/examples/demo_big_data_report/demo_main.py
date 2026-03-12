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
        - `chapters/`: 每个章节一个可调用的 `run_*()` 函数
        - `run_examples.py`: `just examples` 的 gate 入口(快速对拍)
        - `by_yaml_dsl/ecommerce_report.yaml`: 唯一完整 YAML DSL 配置示例
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

    # `marimo` 运行/导出时,显式把仓库根目录加入 `sys.path`,确保 `notebooks.*` 可被导入.
    repo_root = Path(__file__).resolve().parents[4]
    repo_root_str = str(repo_root)
    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)

    return Path


@app.cell
def _(Path):
    demo_dir = Path(__file__).parent
    yaml_path = demo_dir / "by_yaml_dsl" / "ecommerce_report.yaml"
    return demo_dir, yaml_path


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
    import yaml

    from scalim.dsl.by_yaml.config_parsing.errors import ConfigValidationError
    from scalim.dsl.by_yaml.config_parsing.loader import YamlDemandLoader
    from scalim.dsl.by_yaml.config_parsing.validator import ConfigValidator

    # 先加载 YAML 内容
    with open(yaml_path, "r", encoding="utf-8") as _f:
        yaml_config = yaml.safe_load(_f)

    # 使用 ConfigValidator 验证配置
    validator = ConfigValidator()
    try:
        validator.validate(yaml_config)
        print("✅ ConfigValidator 验证通过!")
        validation_passed = True
    except ConfigValidationError as e:
        print("❌ ConfigValidator 验证失败:", e)
        for _err in e.errors[:5]:
            print("   -", _err)
        validation_passed = False

    # 然后使用 YamlDemandLoader 加载
    loader = YamlDemandLoader()
    demand_config = loader.load(str(yaml_path))
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
def _():
    from notebooks.marimo.examples.demo_big_data_report.chapters.registry import run_all_chapters

    chapter_results = run_all_chapters()
    return chapter_results


@app.cell
def _(chapter_results, mo):
    rows = [{"chapter": r.chapter_id, "passed": r.passed, "summary": r.summary.splitlines()[0]} for r in chapter_results]
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
    from scalim.dsl.by_yaml import run
    from scalim.sinks.sink_memory import InMemoryRowSink

    # 注意: `run()` 需要 `allowlist` 配置
    _loaders_module = "notebooks.marimo.examples.demo_big_data_report._loaders"

    try:
        sink = InMemoryRowSink()
        _runtime_vars = {"order_ids": []}
        result = run(
            str(yaml_path),
            allowed_modules=frozenset([_loaders_module]),
            sink=sink,
            runtime_vars=_runtime_vars,
        )
        print("✅ `run()` 执行成功!")
        print("   总行数:", result.total_rows)
        print("   输出路径:", result.output_path or "(内存)")
    except Exception as e:
        print("⚠️ `run()` 执行失败:", e)
        result = None
    # endregion

    _ = Path
    return result


if __name__ == "__main__":
    app.run()
