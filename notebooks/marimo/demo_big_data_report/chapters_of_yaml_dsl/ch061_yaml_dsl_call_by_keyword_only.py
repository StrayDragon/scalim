"""Cells-native marimo notebook: ch061_yaml_dsl_call_by_keyword_only.

迁移对照:
  Before: 模块级 run_yaml_dsl_call_by_keyword_only() 持全部逻辑;cells 薄壳
  After:  bad/good YAML、编译断言、运行断言全部在 cells 内
"""

import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / yaml_dsl_call_by_keyword_only

        ## 回归点

        `call_by` 位置参数不应“绕过” `keyword-only` 签名。

        - `call_by: "...:is_valid_group(group_name)"` 必须在编译期 `fast-fail`
          （`函数签名不匹配` + `too many positional arguments`）
        - `call_by: "...:is_valid_group(group_name=group_name)"` 可正常运行

        ## 主线装配过程（每个步骤一个 cell，可就地修改重跑）

        1. 内联 bad / good 两份 demand YAML（内容可见）
        2. bad：`compile` 预期 fast-fail → 检查错误文案
        3. good：`compile` + `run_ir` → 检查输出行
        4. 断言展开 → chapter_result

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

    tmp = Path(tempfile.mkdtemp(prefix="scalim-yaml-call-by-kwonly-"))
    atexit.register(lambda: shutil.rmtree(tmp, ignore_errors=True))
    out_root = tmp / "out"
    ALLOWED_MODULES = frozenset(["scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario"])
    print("tmp dir:", tmp)
    return ALLOWED_MODULES, out_root, tmp


@app.cell
def _(Dict, Path, tmp):
    # 内联 YAML：bad（位置参数调 keyword-only）vs good（关键字参数）
    init_vars: Dict[str, object] = {"out_root": str(tmp / "out")}
    bad_yaml = tmp / "bad_call_by.yaml"
    good_yaml = tmp / "good_call_by.yaml"

    bad_yaml_lines = [
        "name: yaml_dsl_call_by_keyword_only_bad",
        "",
        "main_source:",
        "  source_id: tickets",
        '  loader: "scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario:load_support_tickets"',
        "  fields:",
        "    ticket_id: {extract: ticket_id, name: 工单ID, value_cast: int}",
        "    group_name: {extract: category, name: 分组名}",
        "",
        "fields:",
        "  _is_valid_group:",
        "    name: 是否合法分组",
        '    call_by: "scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario:is_valid_group(group_name)"',
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
        "    where: _is_valid_group",
        "    fields: [ticket_id, group_name, _is_valid_group]",
    ]
    bad_yaml.write_text("\n".join(bad_yaml_lines), encoding="utf-8")

    good_yaml_lines = [
        "name: yaml_dsl_call_by_keyword_only_good",
        "",
        "main_source:",
        "  source_id: tickets",
        '  loader: "scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario:load_support_tickets"',
        "  fields:",
        "    ticket_id: {extract: ticket_id, name: 工单ID, value_cast: int}",
        "    group_name: {extract: category, name: 分组名}",
        "",
        "fields:",
        "  _is_valid_group:",
        "    name: 是否合法分组",
        '    call_by: "scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario:is_valid_group(group_name=group_name)"',
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
        "    where: _is_valid_group",
        "    fields: [ticket_id, group_name, _is_valid_group]",
    ]
    good_yaml.write_text("\n".join(good_yaml_lines), encoding="utf-8")
    print("bad_yaml :", bad_yaml)
    print("good_yaml:", good_yaml)
    return bad_yaml, good_yaml, init_vars


@app.cell
def _(
    DemandRunOptions,
    DemandRunRuntimeOptions,
    DemandRunSecurityOptions,
    DemandRunTemplateOptions,
    ALLOWED_MODULES,
    bad_yaml,
    compile_yaml,
    init_vars,
):
    # bad：预期编译期 fast-fail（捕获预期异常做断言）
    bad_exc_msg = ""
    bad_fast_failed = False
    try:
        _ = compile_yaml(
            str(bad_yaml),
            options=DemandRunOptions(
                security=DemandRunSecurityOptions(allowed_modules=ALLOWED_MODULES),
                template=DemandRunTemplateOptions(init_vars=init_vars),
                runtime=DemandRunRuntimeOptions(batch_size=2),
            ),
        )
    except Exception as exc:  # noqa: BLE001 — 预期异常：断言编译期拒绝
        bad_exc_msg = str(exc)
        bad_fast_failed = bool(("函数签名不匹配" in bad_exc_msg) and ("too many positional arguments" in bad_exc_msg))

    print("bad_fast_failed =", bad_fast_failed)
    print("bad_exc_message =", bad_exc_msg[:160])
    return bad_exc_msg, bad_fast_failed


@app.cell
def _(
    DemandRunOptions,
    DemandRunRuntimeOptions,
    DemandRunSecurityOptions,
    DemandRunTemplateOptions,
    ALLOWED_MODULES,
    Path,
    compile_yaml,
    good_yaml,
    init_vars,
    run_ir,
):
    # good：正常编译 + run_ir
    compilation = compile_yaml(
        str(good_yaml),
        options=DemandRunOptions(
            security=DemandRunSecurityOptions(allowed_modules=ALLOWED_MODULES),
            template=DemandRunTemplateOptions(init_vars=init_vars),
            runtime=DemandRunRuntimeOptions(batch_size=2),
        ),
    )
    core = run_ir(compilation.demand_ir, compilation.request)
    good_outputs = sorted(core.outputs.keys()) if core.outputs else []
    detail_path = None if core.outputs is None else core.outputs.get("detail")
    out_detail = Path(str(detail_path)) if detail_path else None
    print("good_outputs =", good_outputs)
    return core, good_outputs, out_detail


@app.cell
def _(List, csv, good_outputs, out_detail):
    # 读取 good 输出 CSV
    def _read_csv_rows(path: Path) -> List[Dict[str, str]]:
        rows: List[Dict[str, str]] = []
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                if not row:
                    continue
                rows.append({str(k): str(v) if v is not None else "" for k, v in row.items()})
        return rows

    good_rows = _read_csv_rows(out_detail) if out_detail is not None and out_detail.exists() else []
    good_ok = bool(len(good_rows) == 5 and good_outputs)
    print("good_rows =", len(good_rows), "ok =", good_ok)
    return good_rows, good_ok


@app.cell
def _(bad_fast_failed, good_ok, render_checks):
    checks = {
        "bad 编译期 fast-fail": bad_fast_failed,
        "good 编译+运行成功": good_ok,
    }
    render_checks(checks)
    return checks


@app.cell
def _(bad_exc_msg, bad_fast_failed, checks, good_ok, good_outputs, good_rows, make_chapter_result, out_detail, out_root, tmp):
    passed = bool(all(checks.values()))
    summary = "bad_fast_failed={} good_rows={} outputs={}".format(bad_fast_failed, len(good_rows), good_outputs)
    chapter_result = make_chapter_result(
        passed=passed,
        summary=summary,
        details={
            "bad_yaml_path": str(tmp / "bad_call_by.yaml"),
            "bad_exc_message": bad_exc_msg,
            "good_yaml_path": str(tmp / "good_call_by.yaml"),
            "out_root": str(out_root),
            "detail_csv": str(out_detail) if out_detail is not None else None,
            "good_rows": len(good_rows),
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
