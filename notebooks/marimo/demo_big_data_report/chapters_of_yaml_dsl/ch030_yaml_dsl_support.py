import marimo

import csv
import tempfile
from pathlib import Path
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
from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult

__generated_with = "0.22.0"
app = marimo.App(width="full")

_EXAMPLE_ID = "demo_big_data_report/yaml_dsl_support"
_ALLOWED_MODULES = frozenset(["scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario"])


def _read_csv_rows(path: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if not row:
                continue
            rows.append({str(k): str(v) if v is not None else "" for k, v in row.items()})
    return rows


def run_yaml_dsl_support(
    *,
    yaml_path: Optional[Path] = None,
    init_vars: Optional[Dict[str, object]] = None,
) -> ExampleResult:
    if yaml_path is None:
        demo_dir = Path(__file__).resolve().parents[1]
        yaml_path = demo_dir / "chapters_of_yaml_dsl" / "declared_yaml_dsl" / "support" / "support_sla_report.yaml"

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

    with tempfile.TemporaryDirectory(prefix="scalim-support-") as tmpdir:
        tmp = Path(tmpdir)
        out_root = tmp / "out"

        init_vars = dict(init_vars or {})
        init_vars.update(
            {
                "out_root": str(out_root),
            }
        )

        try:
            run_result = run_yaml(
                str(yaml_path),
                options=DemandRunOptions(
                    security=DemandRunSecurityOptions(allowed_modules=_ALLOWED_MODULES),
                    template=DemandRunTemplateOptions(init_vars=init_vars),
                    runtime=DemandRunRuntimeOptions(
                        components=[guardrail_capture, row_gap_observer],
                        guardrails=guardrails_policy,
                        batch_size=None,
                    ),
                ),
            )
            core = run_result.core
        except Exception as exc:  # noqa: BLE001
            return ExampleResult(
                example_id=_EXAMPLE_ID,
                passed=False,
                kind=EXAMPLE_KIND_ORACLE,
                summary="compile/run failed: {}: {}".format(type(exc).__name__, exc),
                details={"exc_type": type(exc).__name__, "message": str(exc)},
            )

        latest = outputs_api.load_latest_outputs(out_root)
        out_detail = outputs_api.latest_file_path(out_root, file_id="detail_csv")
        out_metrics = outputs_api.latest_file_path(out_root, file_id="metrics_csv")

        detail_rows = _read_csv_rows(out_detail) if out_detail.exists() else []
        metrics_rows = _read_csv_rows(out_metrics) if out_metrics.exists() else []

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

        passed = bool(ok_oracle and ok_row_gap and ok_guardrails and core.outputs)
        summary = "oracle={} row_gap={} guardrails={} outputs={} | {}".format(
            ok_oracle,
            ok_row_gap,
            ok_guardrails,
            sorted(core.outputs.keys()) if core.outputs else None,
            oracle_summary,
        )

        details: Dict[str, Any] = {
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
        }
        return ExampleResult(
            example_id=_EXAMPLE_ID,
            passed=passed,
            kind=EXAMPLE_KIND_ORACLE,
            summary=summary,
            details=details,
        )


def run_chapter() -> ExampleResult:
    return run_yaml_dsl_support()


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

        ## 对拍点（deterministic）

        - YAML fixture：`chapters_of_yaml_dsl/declared_yaml_dsl/support/support_sla_report.yaml`
        - CSV oracle：`scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario:verify_support_outputs_csv_rows`
        - row_gap 断言：`expected_support_row_gap_totals`
        - guardrail code 断言：`expected_support_guardrail_codes`
        - Gate：`just examples`

        SSOT:
        - `notebooks/marimo/demo_big_data_report/chapters_of_yaml_dsl/ch030_yaml_dsl_support.py::run_yaml_dsl_support`
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

    _ = ensure_repo_root_on_sys_path(__file__)
    demo_dir = Path(__file__).resolve().parents[1]
    yaml_path = demo_dir / "chapters_of_yaml_dsl" / "declared_yaml_dsl" / "support" / "support_sla_report.yaml"
    return demo_dir, yaml_path


@app.cell(hide_code=True)
def _(mo, yaml_path):
    from scalim_misc.notebook_support.yaml_excerpt import excerpt_head

    mo.md("## Support demand YAML (head)")
    mo.md("```yaml\n{}\n```".format(excerpt_head(yaml_path, max_lines=140)))
    return (excerpt_head,)


@app.cell
def _(yaml_path):
    result = run_yaml_dsl_support(yaml_path=yaml_path)
    return (result,)


@app.cell(hide_code=True)
def _(mo, result):
    mo.callout(mo.md("## {}".format("PASS" if result.passed else "FAIL")), kind="success" if result.passed else "danger")
    mo.md("```\n{}\n```".format(result.summary))
    return


@app.cell(hide_code=True)
def _(mo, result):
    from scalim_misc.notebook_support.results_view import details_to_rows

    rows = details_to_rows(result.details)
    mo.ui.table(rows, selection=None)
    return (rows,)


if __name__ == "__main__":
    app.run()
