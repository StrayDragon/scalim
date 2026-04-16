import marimo

import csv
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from scalim.dsl.yaml_dsl import DemandRunOptions, DemandRunRuntimeOptions, DemandRunSecurityOptions, DemandRunTemplateOptions
from scalim.dsl.yaml_dsl import run as run_yaml
from scalim.execution.loader_retry import LoaderRetryPoliciesSpec, LoaderRetryPolicySpec
from scalim.shortcuts.resources import outputs as outputs_api
from scalim_misc.demo_big_data_report.by_yaml_dsl.ads_scenario import (
    get_ads_creatives_retry_counter_calls,
    reset_ads_creatives_retry_counter_calls,
    should_retry_ads_transient,
    verify_ads_outputs_csv_rows,
)
from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult

__generated_with = "0.20.2"
app = marimo.App(width="full")

_EXAMPLE_ID = "demo_big_data_report/yaml_dsl_ads"
_ALLOWED_MODULES = frozenset(["scalim_misc.demo_big_data_report.by_yaml_dsl.ads_scenario"])


def _read_csv_rows(path: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if not row:
                continue
            rows.append({str(k): str(v) if v is not None else "" for k, v in row.items()})
    return rows


def run_yaml_dsl_ads(
    *,
    yaml_path: Optional[Path] = None,
    init_vars: Optional[Dict[str, object]] = None,
) -> ExampleResult:
    if yaml_path is None:
        demo_dir = Path(__file__).resolve().parents[1]
        yaml_path = demo_dir / "chapters_of_yaml_dsl" / "declared_yaml_dsl" / "ads" / "ads_campaign_report.yaml"

    reset_ads_creatives_retry_counter_calls()
    with tempfile.TemporaryDirectory(prefix="scalim-ads-") as tmpdir:
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
                        batch_size=10,
                        loader_retry=LoaderRetryPoliciesSpec(
                            default=LoaderRetryPolicySpec(
                                enabled=True,
                                should_retry=should_retry_ads_transient,
                                max_attempts=2,
                                max_elapsed_seconds=2,
                                backoff="fixed",
                                base_delay_seconds=0,
                                max_delay_seconds=0,
                                jitter=False,
                            )
                        ),
                    ),
                ),
            )
        except Exception as exc:  # noqa: BLE001
            return ExampleResult(
                example_id=_EXAMPLE_ID,
                passed=False,
                kind=EXAMPLE_KIND_ORACLE,
                summary="run failed: {}: {}".format(type(exc).__name__, exc),
                details={"exc_type": type(exc).__name__, "message": str(exc)},
            )

        latest = outputs_api.load_latest_outputs(out_root)
        out_detail_all = outputs_api.latest_file_path(out_root, file_id="detail_all_csv")
        out_detail_clicks = outputs_api.latest_file_path(out_root, file_id="detail_clicks_csv")
        out_metrics = outputs_api.latest_file_path(out_root, file_id="metrics_by_campaign_csv")

        detail_all_rows = _read_csv_rows(out_detail_all) if out_detail_all.exists() else []
        detail_clicks_rows = _read_csv_rows(out_detail_clicks) if out_detail_clicks.exists() else []
        metrics_rows = _read_csv_rows(out_metrics) if out_metrics.exists() else []

        ok_oracle, oracle_summary, oracle_details = verify_ads_outputs_csv_rows(
            actual_detail_all=detail_all_rows,
            actual_detail_clicks=detail_clicks_rows,
            actual_metrics_by_campaign=metrics_rows,
        )
        retry_calls = get_ads_creatives_retry_counter_calls()

        passed = bool(ok_oracle and retry_calls == 2 and run_result.core.outputs)
        summary = "oracle={} retry_calls={} outputs={} | {}".format(
            ok_oracle,
            retry_calls,
            sorted(run_result.core.outputs.keys()) if run_result.core.outputs else None,
            oracle_summary,
        )

        details: Dict[str, Any] = {
            "yaml_path": str(yaml_path),
            "outputs": run_result.core.outputs,
            "out_root": str(out_root),
            "run_id": latest.run_id,
            "detail_all_csv": str(out_detail_all),
            "detail_clicks_csv": str(out_detail_clicks),
            "metrics_by_campaign_csv": str(out_metrics),
            "retry_calls": retry_calls,
            "oracle": oracle_details,
        }
        return ExampleResult(
            example_id=_EXAMPLE_ID,
            passed=passed,
            kind=EXAMPLE_KIND_ORACLE,
            summary=summary,
            details=details,
        )


def run_chapter() -> ExampleResult:
    return run_yaml_dsl_ads()


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / yaml_dsl_ads

        ## 背景

        假设增长团队要做“投放日报”：曝光日志是主表，还要关联 adgroup/campaign/creative 维表与 click/conversion 事件。

        ## 需求方提问（自然语言）

        投放同学：我想要两份输出：
        1) 全量明细（用于抽样核对）
        2) 只看点击明细（用于排查素材/人群）
        同时按 Campaign 聚合出 CTR/CVR/ROAS。

        ## 方案选择（取舍）

        - SQL：需要数仓与埋点口径治理
        - 纯 Python：灵活但不易审计与回归
        - **YAML DSL（本章）**：把“关联 + 多输出 + 聚合指标 + retry”收敛成可校验配置

        ## 对拍点（deterministic）

        - YAML fixture：`chapters_of_yaml_dsl/declared_yaml_dsl/ads/ads_campaign_report.yaml`
        - oracle：`scalim_misc.demo_big_data_report.by_yaml_dsl.ads_scenario:verify_ads_outputs_csv_rows`
        - retry 断言：`load_ads_creatives` 首次抛 transient error，重试后成功（calls=2）
        - Gate：`just examples`

        SSOT:
        - `notebooks/marimo/demo_big_data_report/chapters_of_yaml_dsl/ch020_yaml_dsl_ads.py::run_yaml_dsl_ads`
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
    yaml_path = demo_dir / "chapters_of_yaml_dsl" / "declared_yaml_dsl" / "ads" / "ads_campaign_report.yaml"
    return demo_dir, yaml_path


@app.cell(hide_code=True)
def _(mo, yaml_path):
    from scalim_misc.notebook_support.yaml_excerpt import excerpt_head

    mo.md("## Ads demand YAML (head)")
    mo.md("```yaml\n{}\n```".format(excerpt_head(yaml_path, max_lines=120)))
    return (excerpt_head,)


@app.cell
def _(yaml_path):
    result = run_yaml_dsl_ads(yaml_path=yaml_path)
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
