"""Cells-native marimo notebook: ch110_yaml_dsl_guardrails_compute_on_error.

迁移对照:
  Before: 模块级 run_*() 持全部逻辑;cells 薄壳
  After:  guardrails 装配、运行、compute_error 断言全部在 cells 内
"""

import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / yaml_dsl_guardrails_compute_on_error

        ## 回归点

        `GuardrailsComputePolicy(on_error="quiet")`：compute 除零错误被捕获为
        `compute_error` 信号，`risky_score` 置空不中断流程。

        - 对拍：`ticket_id=1001` 必然触发除零 → risky_score 为空；其余至少一个非空。

        ## 主线装配过程（每个步骤一个 cell，可就地修改重跑）

        1. 零件：GuardrailCaptureObserver + GuardrailsPolicy(fast_fail + compute quiet)
        2. `run` → detail CSV + guardrail 信号
        3. 断言：rows=5 + compute_error 信号 + 1001 行 risky_score 空白
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
    yaml_path = demo_dir / "chapters_of_yaml_dsl" / "declared_yaml_dsl" / "support" / "support_guardrails_compute_on_error.yaml"
    _ = repo_root
    return Path, demo_dir, yaml_path


@app.cell
def _(Path):
    import csv
    import tempfile
    from typing import Any, Dict, List, Optional, Sequence

    from scalim.dsl.yaml_dsl import DemandRunOptions, DemandRunRuntimeOptions, DemandRunSecurityOptions, DemandRunTemplateOptions
    from scalim.dsl.yaml_dsl import run as run_yaml
    from scalim.execution.guardrails import GuardrailsComputePolicy, GuardrailsPolicy
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
        GuardrailsComputePolicy,
        GuardrailsPolicy,
        List,
        Optional,
        Path,
        Sequence,
        csv,
        make_chapter_result,
        render_checks,
        run_yaml,
        tempfile,
    )


@app.cell
def _(Dict, List, Optional, Path, Sequence, csv, GuardrailCaptureObserver):
    # 零件: CSV 读取 / guardrail 信号提取
    def read_csv_rows(path: Path) -> List[Dict[str, str]]:
        rows: List[Dict[str, str]] = []
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                if not row:
                    continue
                rows.append({str(k): str(v) if v is not None else "" for k, v in row.items()})
        return rows

    def guardrail_codes(components: Optional[Sequence[object]]) -> List[str]:
        codes: List[str] = []
        for c in components or ():
            if isinstance(c, GuardrailCaptureObserver):
                codes.extend([s.code for s in c.signals if s.code])
        return sorted(set(codes))

    return guardrail_codes, read_csv_rows


@app.cell
def _(GuardrailCaptureObserver, GuardrailsComputePolicy, GuardrailsPolicy):
    guardrail_capture = GuardrailCaptureObserver()
    guardrails = GuardrailsPolicy(
        enabled=True,
        mode="fast_fail",
        compute=GuardrailsComputePolicy(on_error="quiet"),
    )
    return guardrail_capture, guardrails


@app.cell
def _(Path, tempfile):
    import atexit
    import shutil

    tmp = Path(tempfile.mkdtemp(prefix="scalim-guardrails-compute-"))
    atexit.register(lambda: shutil.rmtree(tmp, ignore_errors=True))
    out_root_detail = tmp / "out_detail"
    ALLOWED_MODULES = frozenset(["scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario"])
    print("tmp dir:", tmp)
    return ALLOWED_MODULES, out_root_detail, tmp


@app.cell
def _(
    ALLOWED_MODULES,
    DemandRunOptions,
    DemandRunRuntimeOptions,
    DemandRunSecurityOptions,
    DemandRunTemplateOptions,
    Dict,
    guardrail_capture,
    guardrails,
    out_root_detail,
    run_yaml,
    yaml_path,
):
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
def _(Path, core, guardrail_codes, guardrail_capture, read_csv_rows):
    detail_csv_path = Path(str((core.outputs or {}).get("detail") or ""))
    rows = read_csv_rows(detail_csv_path) if detail_csv_path.exists() else []
    codes = guardrail_codes([guardrail_capture])
    has_compute_error = "compute_error" in set(codes)
    print("rows =", len(rows), "codes =", codes)

    # 对拍: ticket_id=1001 必然触发除零 -> risky_score 为空;其余至少一个非空.
    by_id = {r.get("ticket_id") or "": r for r in rows}
    r_1001 = by_id.get("1001") or {}
    blank_for_1001 = (r_1001.get("risky_score") or "") == ""
    any_non_blank = any((r.get("risky_score") or "") != "" for r in rows if (r.get("ticket_id") or "") != "1001")
    return (
        blank_for_1001,
        any_non_blank,
        by_id,
        codes,
        detail_csv_path,
        has_compute_error,
        r_1001,
        rows,
    )


@app.cell
def _(any_non_blank, blank_for_1001, core, has_compute_error, render_checks, rows):
    checks = {
        "rows == 5": len(rows) == 5,
        "compute_error 信号捕获": has_compute_error,
        "1001 行 risky_score 空白": blank_for_1001,
        "其余行存在非空 risky_score": any_non_blank,
        "输出非空": bool(core.outputs),
    }
    render_checks(checks)
    return checks


@app.cell
def _(
    any_non_blank,
    blank_for_1001,
    checks,
    codes,
    core,
    detail_csv_path,
    has_compute_error,
    make_chapter_result,
    out_root_detail,
    r_1001,
    rows,
    yaml_path,
):
    passed = bool(all(checks.values()))
    summary = "rows={} compute_error={} blank_1001={} any_non_blank={} outputs={}".format(
        len(rows),
        has_compute_error,
        blank_for_1001,
        any_non_blank,
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
            "guardrail_codes": codes,
            "row_1001": r_1001,
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
