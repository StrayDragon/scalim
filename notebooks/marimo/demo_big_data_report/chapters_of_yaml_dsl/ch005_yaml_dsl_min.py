"""Cells-native marimo notebook: ch005_yaml_dsl_min.

角色: README「第一口」的 YAML DSL 侧 —— 主线 canonical 报表(`ch010`)的两源极简切片.
链路: `declared_yaml_dsl/min_report.yaml` → `compile()` 语义校验 → `run()` 取行 → 对拍.
"""

import marimo

__generated_with = "0.23.14"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / ch005_yaml_dsl_min

        最小可跑 **YAML DSL**（假数据闭环）: 一张主源表 + 一张维表 + 一个派生字段 + 一个 csv 输出.

        它就是 `ch010` 完整电商报表(`ecommerce_report.yaml`)的**极简切片**: 同一套写法, 只保留 4 个面
        (`main_source` / `sources` + `relations` / `fields` / `outputs` + `resources`).

        主线装配过程(每个步骤一个 cell, 可就地修改重跑):

        1. 定位最小 YAML SSOT 并展示内容
        2. `compile()`: schema 校验 + 语义校验(不执行)
        3. `run()`: 显式 `CaptureRows` + 输出重定向到临时目录
        4. 期望 vs 实际对拍(3 行; `methods = {card, cash}`; `total_amount = amount * 2`)

        对拍入口: `run_chapter()` → `app.run()` → `chapter_result`
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
    from pathlib import Path

    from scalim_misc.notebook_support.pathing import ensure_repo_root_on_sys_path

    repo_root = ensure_repo_root_on_sys_path(__file__)
    yaml_path = Path(__file__).resolve().parents[1] / "chapters_of_yaml_dsl" / "declared_yaml_dsl" / "min_report.yaml"
    loader_module = "scalim_misc.demo_big_data_report.min_loaders"
    _ = repo_root
    return loader_module, yaml_path


@app.cell
def _():
    from scalim.dsl.yaml_dsl import (
        CaptureRows,
        DemandRunOptions,
        DemandRunOutputOptions,
        DemandRunSecurityOptions,
        FileResourceOverride,
        ResourcesOverride,
        RunOverrides,
        compile,
        run,
    )
    from scalim_misc.notebook_support.chapter_result import make_chapter_result, render_checks

    return (
        CaptureRows,
        DemandRunOptions,
        DemandRunOutputOptions,
        DemandRunSecurityOptions,
        FileResourceOverride,
        ResourcesOverride,
        RunOverrides,
        compile,
        make_chapter_result,
        render_checks,
        run,
    )


@app.cell
def _(mo, yaml_path):
    # ① 配置即真相: 直接展示 YAML SSOT 文件内容
    mo.md("**min_report.yaml**:\n\n```yaml\n{}\n```".format(yaml_path.read_text(encoding="utf-8")))
    return


@app.cell
def _(DemandRunSecurityOptions, DemandRunOptions, compile, loader_module, yaml_path):
    # ② compile(): 只做 schema + 语义校验, 返回编译产物(不执行)
    #    loader 模块需要显式 allowlist(安全边界: 只允许已知 loader 模块)
    compilation = compile(
        str(yaml_path),
        options=DemandRunOptions(security=DemandRunSecurityOptions(allowed_modules=frozenset([loader_module]))),
    )
    config = compilation.config
    print("compiled demand:", config.name, "main_source =", config.main_source.source_id, "sources =", list(config.sources))
    return (config,)


@app.cell(hide_code=True)
def _(config, mo):
    # 编译产物 = 声明式 YAML 的规范化视图(源字段带 source/relation, 派生字段带 compute)
    rows = [{"kind": "source", "field_id": fid, "name": f.name, "detail": f.source} for fid, f in config.source_fields.items()]
    rows.extend({"kind": "derived", "field_id": fid, "name": f.name, "detail": f.compute or ""} for fid, f in config.derived_fields.items())
    mo.vstack(
        [
            mo.md(
                "**编译产物窥视**(读者无需跳库): `demand={}` · `relations={}` · `outputs={}`".format(
                    config.name, list(config.relations), [o.name for o in config.outputs]
                )
            ),
            mo.ui.table(rows, selection=None),
        ]
    )
    return


@app.cell
def _(
    CaptureRows,
    DemandRunOptions,
    DemandRunOutputOptions,
    DemandRunSecurityOptions,
    FileResourceOverride,
    ResourcesOverride,
    RunOverrides,
    loader_module,
    run,
    yaml_path,
):
    # ③ run(): 输出重定向到临时目录 + 捕获行(内存), 用于对拍
    import tempfile
    from pathlib import Path as _Path

    with tempfile.TemporaryDirectory(prefix="scalim-min-report-") as tmp:
        out_root = _Path(tmp) / "output"
        out_root.mkdir(parents=True, exist_ok=True)
        overrides = RunOverrides(
            resources=ResourcesOverride(
                files={"detail_csv": FileResourceOverride(kind="csv_file", path=str(out_root))},
            )
        )
        result = run(
            str(yaml_path),
            options=DemandRunOptions(
                security=DemandRunSecurityOptions(allowed_modules=frozenset([loader_module])),
                outputs=DemandRunOutputOptions(capture=CaptureRows(), overrides=overrides),
            ),
        )
    captured_rows = list(result.captured_rows.iter_row_data()) if result.captured_rows is not None else []
    total_rows = int(result.total_rows)
    print("total_rows =", total_rows)
    return captured_rows, total_rows


@app.cell
def _(captured_rows, mo, total_rows):
    # ④ 期望 vs 实际(期望值是教学 payload, 直接写在 cells 里)
    expected_rows = [
        {"order_id": 1, "method": "card", "total_amount": 20.0},
        {"order_id": 2, "method": "cash", "total_amount": 41.0},
        {"order_id": 3, "method": "card", "total_amount": 14.0},
    ]
    keys = ("order_id", "method", "total_amount")
    actual_rows = sorted(
        ({k: row.get(k) for k in keys} for row in captured_rows),
        key=lambda row: row["order_id"],
    )
    methods = {str(row.get("method")) for row in captured_rows}
    mo.vstack(
        [
            mo.md("**期望 vs 实际**(关联 `method` + 计算 `total_amount = amount * 2`):"),
            mo.ui.table(
                [{"kind": "期望", **row} for row in expected_rows] + [{"kind": "实际", **row} for row in actual_rows],
                selection=None,
            ),
        ]
    )
    return actual_rows, expected_rows, methods


@app.cell
def _(actual_rows, expected_rows, make_chapter_result, methods, render_checks, total_rows):
    # ⑤ 对拍断言 + 结构化 chapter_result
    checks = {
        "YAML 运行 3 行": total_rows == 3,
        "methods = {card, cash}": methods == {"card", "cash"},
        "期望行完全一致": actual_rows == expected_rows,
    }
    render_checks(checks)
    passed = bool(all(checks.values()))
    summary = "rows={} methods={}".format(total_rows, sorted(methods))

    # 对拍期望(教学 payload; headless 可经 details["expected"] 键定位)
    expected = {"rows": 3, "methods": ["card", "cash"], "total_amount_first": 20.0}
    print("expected:", expected)

    chapter_result = make_chapter_result(
        passed=passed,
        summary=summary,
        details={
            "expected": expected,
            "rows": total_rows,
            "methods": sorted(methods),
            "expected_rows": expected_rows,
            "actual_rows": actual_rows,
            "checks": {k: bool(v) for k, v in checks.items()},
        },
    )
    return (chapter_result,)


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

    detail_rows = details_to_rows(chapter_result["details"])
    mo.ui.table(detail_rows, selection=None) if detail_rows else mo.md("(无详情)")
    return


def run_chapter():
    """SSOT 入口：headless runner 与 pytest 通过此函数执行对拍。"""
    outputs, defs = app.run()
    return defs["chapter_result"]


if __name__ == "__main__":
    app.run()
