"""Cells-native marimo notebook: ch030_yaml_dsl_support.

迁移对照:
  Before: 模块级 run_yaml_dsl_support() 持全部逻辑;cells 薄壳
  After:  guardrails/row_gap 装配、运行、oracle 全部在 cells 内
"""

import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / yaml_dsl_support

        ## 背景

        假设客服系统的工单（tickets）是主表，需要关联 customers/agents 维表，并产出：
        - 明细：方便抽样排查与回溯
        - 聚合：按团队统计工单量与 SLA 超时

        ## 需求方提问（自然语言）

        客服负责人：我希望在 CI 里也能稳定暴露两类问题：
        1) 工单是否缺少关键字段（例如 agent_id 为空）
        2) 维表加载是否存在缺口（请求了多少 keys，实际返回多少）

        ## 方案选择（取舍）

        - 纯 Python：可做，但难以形成“配置即回归”
        - **YAML DSL（本章）**：用 runtime guardrails + runtime `components=[RowGapObserver(...), ...]` 把问题变成确定性信号

        ## 主线装配过程（每个步骤一个 cell，可就地修改重跑）

        1. 零件：GuardrailCaptureObserver（信号捕获）+ RowGapObserver（维表缺口）
        2. 装配 GuardrailsPolicy（loader/relations 校验）+ `run`
        3. 输出定位 + CSV 读取
        4. oracle 对拍 + row_gap totals + guardrail codes 三路断言
        5. 汇总 chapter_result

        ## 对拍点（deterministic）

        - YAML fixture：`chapters_of_yaml_dsl/declared_yaml_dsl/support/support_sla_report.yaml`
        - CSV oracle：`scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario:verify_support_outputs_csv_rows`
        - row_gap 断言：`expected_support_row_gap_totals`
        - guardrail code 断言：`expected_support_guardrail_codes`
        - Gate：`just examples`
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
    yaml_path = demo_dir / "chapters_of_yaml_dsl" / "declared_yaml_dsl" / "support" / "support_sla_report.yaml"
    _ = repo_root
    return Path, demo_dir, yaml_path


@app.cell(hide_code=True)
def _(mo, yaml_path):
    from scalim_misc.notebook_support.yaml_excerpt import excerpt_head

    mo.md("## Support demand YAML (head)")
    mo.md("```yaml\n{}\n```".format(excerpt_head(yaml_path, max_lines=140)))
    return (excerpt_head,)


@app.cell
def _():
    import csv
    import tempfile
    from typing import Any, Dict, List, Optional

    from scalim.dsl.yaml_dsl import DemandRunOptions, DemandRunRuntimeOptions, DemandRunSecurityOptions, DemandRunTemplateOptions
    from scalim.dsl.yaml_dsl import run as run_yaml
    from scalim.execution.guardrails import GuardrailsLoaderPolicy, GuardrailsPolicy, GuardrailsRelationsPolicy
    from scalim.ob.presets.row_gap import RowGapObserver
    from scalim.shortcuts.resources import outputs as outputs_api
    from scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario import (
        GuardrailCaptureObserver,
        expected_support_guardrail_codes,
        expected_support_row_gap_totals,
        verify_support_outputs_csv_rows,
    )
    from scalim_misc.notebook_support.chapter_result import make_chapter_result, render_checks

    return (
        Any,
        DemandRunOptions,
        DemandRunRuntimeOptions,
        DemandRunSecurityOptions,
        DemandRunTemplateOptions,
        Dict,
        GuardrailCaptureObserver,
        GuardrailsLoaderPolicy,
        GuardrailsPolicy,
        GuardrailsRelationsPolicy,
        List,
        Optional,
        RowGapObserver,
        csv,
        expected_support_guardrail_codes,
        expected_support_row_gap_totals,
        make_chapter_result,
        outputs_api,
        render_checks,
        run_yaml,
        tempfile,
        verify_support_outputs_csv_rows,
    )


@app.cell
def _(GuardrailCaptureObserver, GuardrailsLoaderPolicy, GuardrailsPolicy, GuardrailsRelationsPolicy, RowGapObserver):
    # 零件: guardrail 信号捕获 + row_gap 缺口观察(教学核心,逻辑可见)
    guardrail_capture = GuardrailCaptureObserver()
    row_gap_observer = RowGapObserver(
        primary_loader_name="tickets",
        data_loader_names=["customers", "agents"],
        sample_limit=3,
    )
    guardrails_policy = GuardrailsPolicy(
        enabled=True,
        mode="quiet",
        loader=GuardrailsLoaderPolicy(
            validate_result=True,
            required_fields=("ticket_id", "customer_id", "agent_id"),
            on_transform_error="quiet",
        ),
        relations=GuardrailsRelationsPolicy(null_key_max_rate=0.0),
    )
    return guardrail_capture, guardrails_policy, row_gap_observer


@app.cell
def _(Path, tempfile):
    import atexit
    import shutil

    tmp = Path(tempfile.mkdtemp(prefix="scalim-support-"))
    atexit.register(lambda: shutil.rmtree(tmp, ignore_errors=True))
    out_root = tmp / "out"
    print("out_root:", out_root)
    return out_root, tmp


@app.cell
def _(
    DemandRunOptions,
    DemandRunRuntimeOptions,
    DemandRunSecurityOptions,
    DemandRunTemplateOptions,
    guardrail_capture,
    guardrails_policy,
    out_root,
    row_gap_observer,
    run_yaml,
    yaml_path,
):
    init_vars = {"out_root": str(out_root)}
    allowed_modules = frozenset(["scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario"])

    run_result = run_yaml(
        str(yaml_path),
        options=DemandRunOptions(
            security=DemandRunSecurityOptions(allowed_modules=allowed_modules),
            template=DemandRunTemplateOptions(init_vars=init_vars),
            runtime=DemandRunRuntimeOptions(
                components=[guardrail_capture, row_gap_observer],
                guardrails=guardrails_policy,
                batch_size=None,
            ),
        ),
    )
    core = run_result.core

    print("total_rows =", run_result.total_rows)
    print("outputs    =", sorted(core.outputs.keys()) if core.outputs else None)
    return allowed_modules, core, init_vars, run_result


@app.cell
def _(Path, csv, outputs_api, out_root):
    # 输出定位 + CSV 读取(下游 oracle 的输入)
    def _read_csv_rows(path: Path) -> List[Dict[str, str]]:
        rows: List[Dict[str, str]] = []
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                if not row:
                    continue
                rows.append({str(k): str(v) if v is not None else "" for k, v in row.items()})
        return rows

    latest = outputs_api.load_latest_outputs(out_root)
    out_detail = outputs_api.latest_file_path(out_root, file_id="detail_csv")
    out_metrics = outputs_api.latest_file_path(out_root, file_id="metrics_csv")

    detail_rows = _read_csv_rows(out_detail) if out_detail.exists() else []
    metrics_rows = _read_csv_rows(out_metrics) if out_metrics.exists() else []

    print("detail rows =", len(detail_rows))
    print("metrics rows=", len(metrics_rows))
    print("run_id      =", latest.run_id)

    return detail_rows, latest, metrics_rows, out_detail, out_metrics


@app.cell
def _(
    List,
    detail_rows,
    expected_support_guardrail_codes,
    expected_support_row_gap_totals,
    guardrail_capture,
    metrics_rows,
    render_checks,
    row_gap_observer,
    verify_support_outputs_csv_rows,
):
    ok_oracle, oracle_summary, oracle_details = verify_support_outputs_csv_rows(
        actual_detail=detail_rows,
        actual_metrics_by_team=metrics_rows,
    )

    row_gap_totals = {
        "total_expected": int(row_gap_observer.total_expected),
        "total_actual": int(row_gap_observer.total_actual),
        "total_missing": int(row_gap_observer.total_missing),
    }
    expected_totals = expected_support_row_gap_totals()
    ok_row_gap = bool(row_gap_totals == expected_totals)

    expected_codes = set(expected_support_guardrail_codes())
    got_codes = {s.code for s in guardrail_capture.signals if s.code}
    ok_guardrails = expected_codes.issubset(got_codes)

    checks = {
        "csv oracle 对拍通过": ok_oracle,
        "row_gap totals 一致": ok_row_gap,
        "guardrail codes 覆盖": ok_guardrails,
    }
    render_checks(checks)
    print("row_gap:", row_gap_totals)
    print("guardrails got:", sorted(got_codes))
    return (
        checks,
        expected_codes,
        expected_totals,
        got_codes,
        ok_guardrails,
        ok_oracle,
        ok_row_gap,
        oracle_details,
        oracle_summary,
        row_gap_totals,
    )


@app.cell
def _(
    checks,
    core,
    expected_codes,
    expected_totals,
    got_codes,
    guardrail_capture,
    latest,
    make_chapter_result,
    ok_guardrails,
    ok_oracle,
    ok_row_gap,
    oracle_details,
    oracle_summary,
    out_detail,
    out_metrics,
    out_root,
    row_gap_totals,
    yaml_path,
):
    passed = bool(all(checks.values()))
    summary = "oracle={} row_gap={} guardrails={} outputs={} | {}".format(
        ok_oracle,
        ok_row_gap,
        ok_guardrails,
        sorted(core.outputs.keys()) if core.outputs else None,
        oracle_summary,
    )
    chapter_result = make_chapter_result(
        passed=passed,
        summary=summary,
        details={
            "yaml_path": str(yaml_path),
            "outputs": core.outputs,
            "out_root": str(out_root),
            "run_id": latest.run_id,
            "detail_csv": str(out_detail),
            "metrics_csv": str(out_metrics),
            "oracle": oracle_details,
            "row_gap": row_gap_totals,
            "row_gap_expected": expected_totals,
            "guardrail_codes": sorted(got_codes),
            "guardrail_expected_codes": sorted(expected_codes),
            "guardrail_signals": [s.payload for s in guardrail_capture.signals[:10]],
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
