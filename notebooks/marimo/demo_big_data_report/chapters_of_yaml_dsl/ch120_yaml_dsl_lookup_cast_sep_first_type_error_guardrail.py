"""Cells-native marimo notebook: ch120_yaml_dsl_lookup_cast_sep_first_type_error_guardrail.

迁移对照:
  Before: 模块级 run_*() 持全部逻辑;cells 薄壳
  After:  guardrails 装配、运行、type_error 断言全部在 cells 内
"""

import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / yaml_dsl_lookup_cast_sep_first_type_error_guardrail

        ## 回归点

        lookup cast 分隔符首字符类型错误：`GuardrailsRelationsPolicy(type_error_max_rate=0)`
        捕获 `relation_type_error_rate_exceeded`，`2002` 行 cast 失败 → agent_team 为空，
        `2001` 行正常 → agent_team="team-a"。

        ## 主线装配过程（每个步骤一个 cell，可就地修改重跑）

        1. 零件：GuardrailCaptureObserver + GuardrailsPolicy(quiet + type_error_max_rate=0)
        2. `run` → detail CSV + guardrail 信号
        3. 断言：rows=3 + type_error 信号 + 2001/2002 对拍
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
    from pathlib import Path

    from scalim_misc.notebook_support.pathing import ensure_repo_root_on_sys_path

    repo_root = ensure_repo_root_on_sys_path(__file__)
    demo_dir = Path(__file__).resolve().parents[1]
    yaml_path = (
        demo_dir / "chapters_of_yaml_dsl" / "declared_yaml_dsl" / "support" / "support_lookup_cast_sep_first_type_error_guardrail.yaml"
    )
    _ = repo_root
    return Path, demo_dir, yaml_path


@app.cell
def _(Path):
    import csv
    import tempfile
    from typing import Any, Dict, List, Optional

    from scalim.dsl.yaml_dsl import DemandRunOptions, DemandRunRuntimeOptions, DemandRunSecurityOptions, DemandRunTemplateOptions
    from scalim.dsl.yaml_dsl import run as run_yaml
    from scalim.execution.guardrails import GuardrailsPolicy, GuardrailsRelationsPolicy
    from scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario import GuardrailCaptureObserver
    from scalim_misc.notebook_support.chapter_result import make_chapter_result, render_checks

    return (
        Any,
        DemandRunOptions,
        DemandRunRuntimeOptions,
        DemandRunSecurityOptions,
        DemandRunTemplateOptions,
        Dict,
        GuardrailCaptureObserver,
        GuardrailsPolicy,
        GuardrailsRelationsPolicy,
        List,
        Optional,
        Path,
        csv,
        make_chapter_result,
        render_checks,
        run_yaml,
        tempfile,
    )


@app.cell
def _(Dict, List, Path, csv):
    # 零件: CSV 读取
    def read_csv_rows(path: Path) -> List[Dict[str, str]]:
        rows: List[Dict[str, str]] = []
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                if not row:
                    continue
                rows.append({str(k): str(v) if v is not None else "" for k, v in row.items()})
        return rows

    return read_csv_rows


@app.cell
def _(GuardrailCaptureObserver, GuardrailsPolicy, GuardrailsRelationsPolicy):
    guardrail_capture = GuardrailCaptureObserver()
    guardrails = GuardrailsPolicy(
        enabled=True,
        mode="quiet",
        relations=GuardrailsRelationsPolicy(type_error_max_rate=0),
    )
    return guardrail_capture, guardrails


@app.cell
def _(Path, tempfile):
    import atexit
    import shutil

    tmp = Path(tempfile.mkdtemp(prefix="scalim-lookup-cast-"))
    atexit.register(lambda: shutil.rmtree(tmp, ignore_errors=True))
    out_root_detail = tmp / "out_detail"
    ALLOWED_MODULES = frozenset(["scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario"])
    print("tmp dir:", tmp)
    return ALLOWED_MODULES, out_root_detail, tmp


@app.cell
def _(ALLOWED_MODULES, DemandRunOptions, DemandRunRuntimeOptions, DemandRunSecurityOptions, DemandRunTemplateOptions, Dict, guardrail_capture, guardrails, out_root_detail, run_yaml, yaml_path):
    init_vars: Dict[str, object] = {"out_path_detail": str(out_root_detail)}
    result = run_yaml(
        str(yaml_path),
        options=DemandRunOptions(
            security=DemandRunSecurityOptions(allowed_modules=ALLOWED_MODULES),
            template=DemandRunTemplateOptions(init_vars=init_vars),
            runtime=DemandRunRuntimeOptions(
                components=[guardrail_capture],
                batch_size=2,
                guardrails=guardrails,
            ),
        ),
    )
    core = result.core
    print("total_rows =", core.total_rows)
    return core, init_vars, result


@app.cell
def _(Path, core, guardrail_capture, read_csv_rows):
    detail_csv_path = Path(str((core.outputs or {}).get("detail") or ""))
    rows = read_csv_rows(detail_csv_path) if detail_csv_path.exists() else []
    got_codes = {s.code for s in guardrail_capture.signals if s.code}
    has_type_error_guardrail = "relation_type_error_rate_exceeded" in got_codes
    print("rows =", len(rows), "codes =", sorted(got_codes))

    by_ticket = {r.get("ticket_id") or "": r for r in rows}
    ok_2001 = (by_ticket.get("2001") or {}).get("agent_team") == "team-a"
    ok_2002 = (by_ticket.get("2002") or {}).get("agent_team") == ""

    return (
        by_ticket,
        detail_csv_path,
        got_codes,
        has_type_error_guardrail,
        ok_2001,
        ok_2002,
        rows,
    )


@app.cell
def _(core, has_type_error_guardrail, ok_2001, ok_2002, render_checks, rows):
    checks = {
        "rows == 3": len(rows) == 3,
        "type_error guardrail 信号": has_type_error_guardrail,
        "2001 行 team-a": ok_2001,
        "2002 行 cast 失败为空": ok_2002,
        "输出非空": bool(core.outputs),
    }
    render_checks(checks)
    return checks


@app.cell
def _(by_ticket, checks, core, detail_csv_path, got_codes, has_type_error_guardrail, make_chapter_result, ok_2001, ok_2002, out_root_detail, rows, yaml_path):
    passed = bool(all(checks.values()))
    summary = "rows={} type_error_guardrail={} ok_2001={} ok_2002={} outputs={}".format(
        len(rows),
        has_type_error_guardrail,
        ok_2001,
        ok_2002,
        sorted(core.outputs.keys()) if core.outputs else None,
    )
    chapter_result = make_chapter_result(
        passed=passed,
        summary=summary,
        details={
            "yaml_path": str(yaml_path),
            "out_root_detail": str(out_root_detail),
            "detail_csv": str(detail_csv_path),
            "rows": len(rows),
            "guardrail_codes": sorted(got_codes),
            "row_2001": by_ticket.get("2001"),
            "row_2002": by_ticket.get("2002"),
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