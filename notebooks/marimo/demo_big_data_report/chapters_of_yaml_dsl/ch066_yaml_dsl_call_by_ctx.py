"""Cells-native marimo notebook: ch066_yaml_dsl_call_by_ctx.

迁移对照:
  Before: 模块级 run_*() 持全部逻辑;cells 薄壳
  After:  $ctx 演示 YAML(行列表 join)、编译/运行/CSV 断言全部在 cells 内
"""

import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / yaml_dsl_call_by_ctx

        ## 测试场景

        `call_by` 中 `$ctx` 的各种用法：
        1. `$ctx` 传递整个上下文对象
        2. `$ctx.row_id` / `$ctx.batch_num` / `$ctx.field_id`
        3. `$ctx.deps` 依赖项 / `$ctx.values` 字段值字典
        4. 混合字段值与 `$ctx`

        ## 主线装配过程（每个步骤一个 cell，可就地修改重跑）

        1. 内联演示 YAML（行列表 join + `$ctx` 7 个测试字段）
        2. `compile` + `run_ir` → 输出 CSV
        3. 断言：输出非空 + 行数 > 0
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
    from scalim_misc.notebook_support.pathing import ensure_repo_root_on_sys_path

    repo_root = ensure_repo_root_on_sys_path(__file__)
    _ = repo_root
    return (repo_root,)


@app.cell
def _():
    import csv
    import tempfile
    from pathlib import Path
    from typing import Any, Dict, List

    from scalim.dsl.yaml_dsl import DemandRunOptions, DemandRunRuntimeOptions, DemandRunSecurityOptions, DemandRunTemplateOptions
    from scalim.dsl.yaml_dsl import compile as compile_yaml
    from scalim.execution import run_ir
    from scalim_misc.notebook_support.chapter_result import make_chapter_result, render_checks

    return (
        Any,
        DemandRunOptions,
        DemandRunRuntimeOptions,
        DemandRunSecurityOptions,
        DemandRunTemplateOptions,
        Dict,
        List,
        Path,
        compile_yaml,
        csv,
        make_chapter_result,
        render_checks,
        run_ir,
        tempfile,
    )


@app.cell
def _(Path, tempfile):
    import atexit
    import shutil

    tmp = Path(tempfile.mkdtemp(prefix="scalim-yaml-call-by-ctx-"))
    atexit.register(lambda: shutil.rmtree(tmp, ignore_errors=True))
    out_root = tmp / "out"
    ALLOWED_MODULES = frozenset(["scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario"])
    print("tmp dir:", tmp)
    return ALLOWED_MODULES, out_root, tmp


@app.cell
def _(Path, tmp):
    # 内联演示 YAML（行列表 join：规避 marimo 对多行字符串内缩进的变换）
    yaml_file = tmp / "test_ctx.yaml"
    yaml_lines = [
        "name: yaml_dsl_call_by_ctx_demo",
        "",
        "main_source:",
        "  source_id: tickets",
        '  loader: "scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario:load_support_tickets"',
        "  fields:",
        "    ticket_id: {extract: ticket_id, name: 工单ID, value_cast: int}",
        "    category: {extract: category, name: 分组名}",
        "    priority: {extract: priority, name: 优先级}",
        "",
        "fields:",
        "  _test_full_ctx:",
        "    name: 完整上下文测试",
        '    call_by: "scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario:test_full_context(ticket_id=ticket_id, ctx=$ctx)"',
        "",
        "  _test_row_id:",
        "    name: 行ID测试",
        '    call_by: "scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario:test_row_id(ticket_id=ticket_id, row_id=$ctx.row_id)"',
        "",
        "  _test_batch_num:",
        "    name: 批次号测试",
        '    call_by: "scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario:test_batch_num(ticket_id=ticket_id, batch_num=$ctx.batch_num)"',
        "",
        "  _test_field_id:",
        "    name: 字段ID测试",
        '    call_by: "scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario:test_field_id(ticket_id=ticket_id, field_id=$ctx.field_id)"',
        "",
        "  _test_deps:",
        "    name: 依赖项测试",
        '    call_by: "scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario:test_deps(ticket_id=ticket_id, deps=$ctx.deps)"',
        "",
        "  _test_values:",
        "    name: 值字典测试",
        '    call_by: "scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario:test_values(ticket_id=ticket_id, values=$ctx.values)"',
        "",
        "  _enriched_status:",
        "    name: 增强状态",
        '    call_by: "scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario:enrich_status_with_context(category=category, priority=priority, ctx=$ctx)"',
        "",
        "resources:",
        "  files:",
        "    detail_csv:",
        "      csv_file:",
        "        path: {$init_var: out_root}",
        "        encoding: utf-8",
        "",
        "outputs:",
        "  - name: detail",
        "    to: {file: detail_csv}",
        "    write:",
        "      header_fields_output_by: field_id",
        "      include_header: true",
        "    fields: [ticket_id, category, priority, _test_full_ctx, _test_row_id, _test_batch_num, _test_field_id, _test_deps, _test_values, _enriched_status]",
    ]
    yaml_file.write_text("\n".join(yaml_lines), encoding="utf-8")
    print("yaml_file:", yaml_file)
    return yaml_file, yaml_lines


@app.cell
def _(ALLOWED_MODULES, DemandRunOptions, DemandRunRuntimeOptions, DemandRunSecurityOptions, DemandRunTemplateOptions, Dict, Path, compile_yaml, out_root, run_ir, yaml_file):
    # 编译 + 运行
    init_vars: Dict[str, object] = {"out_root": str(out_root)}
    compilation = compile_yaml(
        str(yaml_file),
        options=DemandRunOptions(
            security=DemandRunSecurityOptions(allowed_modules=ALLOWED_MODULES),
            template=DemandRunTemplateOptions(init_vars=init_vars),
            runtime=DemandRunRuntimeOptions(batch_size=2),
        ),
    )
    core = run_ir(compilation.demand_ir, compilation.request)
    outputs = sorted(core.outputs.keys()) if core.outputs else []
    detail_path = Path(str(core.outputs.get("detail"))) if core.outputs and core.outputs.get("detail") else None
    print("outputs     =", outputs)
    print("detail_path =", detail_path)
    return core, detail_path, init_vars, outputs


@app.cell
def _(List, csv, detail_path, outputs):
    # CSV 读取（$ctx 各字段应已写入输出）
    def _read_csv_rows(path: Path) -> List[Dict[str, str]]:
        rows: List[Dict[str, str]] = []
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                if not row:
                    continue
                rows.append({str(k): str(v) if v is not None else "" for k, v in row.items()})
        return rows

    rows = _read_csv_rows(detail_path) if detail_path and detail_path.exists() else []
    ok = bool(len(rows) > 0 and len(outputs) > 0)
    print("rows =", len(rows), "ok =", ok)
    return ok, rows


@app.cell
def _(ok, render_checks):
    checks = {"$ctx 全用法运行成功（输出+行非空）": ok}
    render_checks(checks)
    return checks


@app.cell
def _(checks, detail_path, make_chapter_result, ok, outputs, out_root, rows, yaml_file):
    passed = bool(all(checks.values()))
    summary = "rows={} outputs={} exc=none".format(len(rows), outputs)
    chapter_result = make_chapter_result(
        passed=passed,
        summary=summary,
        details={
            "yaml_path": str(yaml_file),
            "out_root": str(out_root),
            "detail_csv": str(detail_path) if detail_path else None,
            "rows": len(rows),
            "outputs": outputs,
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