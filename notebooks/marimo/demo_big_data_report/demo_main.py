import marimo

__generated_with = "0.23.14"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Scalim 唯一主线教程: `demo_big_data_report`

    本页只做三件事: 说明**链路结构** → 展示**第一口代码(投影)** → 一键跑完三条轨道对拍.
    每个可见 cell 都是能直接执行/就地改的实代码; 教学主体在 `chapters_*/*.py` 的 cells 里.

    结构(三条轨道, 一个套件):
    - `chapters_of_yaml_dsl/*.py`: YAML DSL + workflow 声明面章节(含 `run_chapter()` SSOT 入口)
    - `chapters_of_ir/*.py`: Python IR 装配面 + public API 面章节(ch010–ch120 / ch130–ch184)
    - `chapters_of_scenarios/*.py`: 应用场景面章节(ch210–ch260: hooks/events 与阶段调度)
    - `packages/scalim-misc/src/scalim_misc/`: 仅 loader 模块与对拍零件(不承载教学主流程)
    - `just examples`: 唯一 gate 入口(快速对拍,justfile 内联 runner)
    - `chapters_of_yaml_dsl/declared_yaml_dsl/ecommerce_report.yaml`: 唯一完整 YAML DSL 配置示例

    ## 与根 `README` 的对应(同一链路, 不是两套世界)

    | 读者旅程 | 本章套件 |
    | --- | --- |
    | README「可以用 Python 编写需求」 | `chapters_of_ir/ch010_basics.py`(代码块即其 cells 投影) |
    | README「也可以用 YAML DSL 配置需求」 | `chapters_of_yaml_dsl/ch005_yaml_dsl_min.py` + `declared_yaml_dsl/min_report.yaml` |
    | README「naive vs Scalim 内存对比」 | `chapters_of_ir/ch020_memory_compare.py` |
    | 完整能力面 | 三条轨道逐章递进, 终点是 9 源 `ecommerce_report.yaml` |

    刷新 README 注入区块: `just gen-readme-examples`(或 `just gen-docs`).
    """)
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    from pathlib import Path

    from scalim_misc.notebook_support.pathing import ensure_repo_root_on_sys_path

    # `marimo` 运行/导出时,显式把仓库根目录加入 `sys.path`,方便相对路径访问示例资源.
    repo_root = ensure_repo_root_on_sys_path(__file__)
    suite_dir = Path(__file__).parent
    yaml_path = suite_dir / "chapters_of_yaml_dsl" / "declared_yaml_dsl" / "ecommerce_report.yaml"
    _ = repo_root
    return (
        suite_dir,
        yaml_path,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---
    ## 轨道导航(枚举自三个 registry, 顺序与 `just examples` 一致)

    每章 notebook 同时承担两件事: **教学/交互**(过程 + UI + 失败定位) 与
    **集成对拍 SSOT**(提供 `run_chapter()` 给 `just examples`/pytest 复用).
    """)
    return


@app.cell
def _(mo):
    from notebooks.marimo.demo_big_data_report.chapters_of_ir.registry import all_chapter_ids as ir_chapter_ids
    from notebooks.marimo.demo_big_data_report.chapters_of_scenarios.registry import all_chapter_ids as scenario_chapter_ids
    from notebooks.marimo.demo_big_data_report.chapters_of_yaml_dsl.registry import all_chapter_ids as yaml_dsl_chapter_ids

    # 枚举三条轨道章节 id: 顺序 = 声明面 → 装配面 → 场景面
    tracks = (
        ("chapters_of_yaml_dsl(声明面)", yaml_dsl_chapter_ids()),
        ("chapters_of_ir(装配面)", ir_chapter_ids()),
        ("chapters_of_scenarios(场景面)", scenario_chapter_ids()),
    )
    nav_rows = [{"track": track, "chapter_id": chapter_id} for track, chapter_ids in tracks for chapter_id in chapter_ids]
    print("chapter total =", len(nav_rows))
    mo.ui.table(nav_rows, selection=None)
    return (nav_rows,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---
    ## 第一口代码 = 章节可见 cells 的投影(与根 `README` 同一函数、同一真相)

    下面每个 fence 由 `extract_visible_cell_sources()` 现场读章节文件生成:
    只取「非 `hide_code`」cell 的代码体, 略去 cell 顶层 `return`(marimo 的输出管道),
    所以 fence 本身也能当普通 `.py` 顺读. 想改就打开对应章节 notebook 就地重跑.
    """)
    return


@app.cell
def _(mo, suite_dir):
    from scalim_misc.notebook_support.cell_source import extract_visible_cell_sources

    _first_bite = (
        "chapters_of_ir/ch010_basics.py",
        "chapters_of_yaml_dsl/ch005_yaml_dsl_min.py",
        "chapters_of_ir/ch020_memory_compare.py",
    )

    _blocks = []
    for _rel in _first_bite:
        _cells = extract_visible_cell_sources(suite_dir / _rel)
        _blocks.append("**{}**:\n\n```python\n{}\n```".format(_rel, "\n\n\n".join(_cells)))
    mo.md("\n\n---\n\n".join(_blocks))
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---
    ## 本页自带的 `compile()` / `run()` 片段(保留为可提取的 skill 片段)
    """)
    return


@app.cell
def _(yaml_path):
    # region SCALIM-SKILL:example-full:constraints
    from scalim.dsl.yaml_dsl import (
        DemandRunOptions,
        DemandRunSecurityOptions,
        DemandRunTemplateOptions,
        compile,
    )

    _loaders_module = "scalim_misc.demo_big_data_report.loaders"

    try:
        allowed_modules = frozenset([_loaders_module])
        compilation = compile(
            str(yaml_path),
            options=DemandRunOptions(
                security=DemandRunSecurityOptions(allowed_modules=allowed_modules),
                # 该 YAML 的 `main_source.params.ids` 是模板占位, 由 Python 侧注入(声明面不含具体 id)
                template=DemandRunTemplateOptions(init_vars={"order_ids": []}),
            ),
        )
        print("✅ `compile()` 校验/加载通过!")
        validation_passed = True
        demand_config = compilation.config
        print(
            "   demand:",
            demand_config.name,
            "| main_source:",
            demand_config.main_source.source_id,
            "| 字段数:",
            len(demand_config.source_fields) + len(demand_config.derived_fields),
        )
    except Exception as e:
        print("❌ `compile()` 校验/加载失败:", e)
        validation_passed = False
        demand_config = None
    # endregion

    _ = validation_passed
    return DemandRunOptions, DemandRunSecurityOptions, DemandRunTemplateOptions


@app.cell
def _(DemandRunOptions, DemandRunSecurityOptions, DemandRunTemplateOptions, yaml_path):
    # region SCALIM-SKILL:example-full:run-yaml
    from scalim.dsl.yaml_dsl import CaptureRows, DemandRunOutputOptions, run

    # 注意: `run()` 需要 `allowlist` 配置
    # 复用上方 `compile()` 单元已导入的选项类; 避免同名变量跨单元重复定义
    _loaders_module = "scalim_misc.demo_big_data_report.loaders"

    try:
        _allowed_modules = frozenset([_loaders_module])
        _init_vars = {"order_ids": []}
        result = run(
            str(yaml_path),
            options=DemandRunOptions(
                security=DemandRunSecurityOptions(allowed_modules=_allowed_modules),
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

    return (result,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---
    ## 一键跑完三条轨道(对拍/集成验证同源)
    """)
    return


@app.cell
def _():
    from notebooks.marimo.demo_big_data_report.chapters_of_ir.registry import run_all_chapters as run_all_ir_chapters
    from notebooks.marimo.demo_big_data_report.chapters_of_scenarios.registry import run_all_chapters as run_all_scenario_chapters
    from notebooks.marimo.demo_big_data_report.chapters_of_yaml_dsl.registry import run_all_chapters as run_all_yaml_dsl_chapters

    # 三条轨道一次跑完: 声明面 → 装配面 → 场景面
    chapter_results = run_all_yaml_dsl_chapters() + run_all_ir_chapters() + run_all_scenario_chapters()
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
    return


if __name__ == "__main__":
    app.run()
