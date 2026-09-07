"""Cells-native marimo notebook: ch020_yaml_dsl_ads.

迁移对照:
  Before: 模块级 run_yaml_dsl_ads() 持全部逻辑;cells 薄壳
  After:  retry 装配/运行/输出读取/oracle 全部在 cells 内
"""

import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


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

        ## 主线装配过程（每个步骤一个 cell，可就地修改重跑）

        1. 配置 retry 策略（loader_retry：transient 重试 max_attempts=2）
        2. `run`：加载 ads YAML → 3 个输出文件（detail_all / detail_clicks / metrics）
        3. 输出定位（`shortcuts.resources.outputs`）+ CSV 读取
        4. oracle 对拍 + retry 调用次数断言（calls=2）
        5. 汇总 chapter_result

        ## 对拍点（deterministic）

        - YAML fixture：`chapters_of_yaml_dsl/declared_yaml_dsl/ads/ads_campaign_report.yaml`
        - oracle：`scalim_misc.demo_big_data_report.by_yaml_dsl.ads_scenario:verify_ads_outputs_csv_rows`
        - retry 断言：`load_ads_creatives` 首次抛 transient error，重试后成功（calls=2）
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
    yaml_path = demo_dir / "chapters_of_yaml_dsl" / "declared_yaml_dsl" / "ads" / "ads_campaign_report.yaml"
    _ = repo_root
    return Path, demo_dir, yaml_path


@app.cell(hide_code=True)
def _(mo, yaml_path):
    from scalim_misc.notebook_support.yaml_excerpt import excerpt_head

    mo.md("## Ads demand YAML (head)")
    mo.md("```yaml\n{}\n```".format(excerpt_head(yaml_path, max_lines=120)))
    return (excerpt_head,)


@app.cell
def _():
    import csv
    import tempfile
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
    from scalim_misc.notebook_support.chapter_result import make_chapter_result, render_checks

    return (
        Any,
        DemandRunOptions,
        DemandRunRuntimeOptions,
        DemandRunSecurityOptions,
        DemandRunTemplateOptions,
        Dict,
        List,
        LoaderRetryPoliciesSpec,
        LoaderRetryPolicySpec,
        Optional,
        csv,
        get_ads_creatives_retry_counter_calls,
        make_chapter_result,
        outputs_api,
        render_checks,
        reset_ads_creatives_retry_counter_calls,
        run_yaml,
        should_retry_ads_transient,
        tempfile,
        verify_ads_outputs_csv_rows,
    )


@app.cell
def _(Path, reset_ads_creatives_retry_counter_calls, tempfile):
    import atexit
    import shutil

    reset_ads_creatives_retry_counter_calls()
    tmp = Path(tempfile.mkdtemp(prefix="scalim-ads-"))
    atexit.register(lambda: shutil.rmtree(tmp, ignore_errors=True))
    out_root = tmp / "out"
    print("out_root:", out_root)
    return out_root, tmp


@app.cell
def _(DemandRunOptions, DemandRunRuntimeOptions, DemandRunSecurityOptions, DemandRunTemplateOptions, LoaderRetryPoliciesSpec, LoaderRetryPolicySpec, out_root, run_yaml, should_retry_ads_transient, yaml_path):
    # 装配: retry 策略(load_ads_creatives 首次 transient 失败,重试 2 次内成功)
    init_vars = {"out_root": str(out_root)}
    allowed_modules = frozenset(["scalim_misc.demo_big_data_report.by_yaml_dsl.ads_scenario"])

    run_result = run_yaml(
        str(yaml_path),
        options=DemandRunOptions(
            security=DemandRunSecurityOptions(allowed_modules=allowed_modules),
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

    print("total_rows =", run_result.total_rows)
    print("outputs    =", sorted(run_result.core.outputs.keys()) if run_result.core.outputs else None)
    return allowed_modules, init_vars, run_result


@app.cell
def _(Path, csv, outputs_api, out_root, run_result):
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
    out_detail_all = outputs_api.latest_file_path(out_root, file_id="detail_all_csv")
    out_detail_clicks = outputs_api.latest_file_path(out_root, file_id="detail_clicks_csv")
    out_metrics = outputs_api.latest_file_path(out_root, file_id="metrics_by_campaign_csv")

    detail_all_rows = _read_csv_rows(out_detail_all) if out_detail_all.exists() else []
    detail_clicks_rows = _read_csv_rows(out_detail_clicks) if out_detail_clicks.exists() else []
    metrics_rows = _read_csv_rows(out_metrics) if out_metrics.exists() else []

    print("detail_all rows   =", len(detail_all_rows))
    print("detail_clicks rows=", len(detail_clicks_rows))
    print("metrics rows      =", len(metrics_rows))
    print("run_id            =", latest.run_id)

    return (
        detail_all_rows,
        detail_clicks_rows,
        latest,
        metrics_rows,
        out_detail_all,
        out_detail_clicks,
        out_metrics,
    )


@app.cell
def _(detail_all_rows, detail_clicks_rows, get_ads_creatives_retry_counter_calls, metrics_rows, render_checks, run_result, verify_ads_outputs_csv_rows):
    ok_oracle, oracle_summary, oracle_details = verify_ads_outputs_csv_rows(
        actual_detail_all=detail_all_rows,
        actual_detail_clicks=detail_clicks_rows,
        actual_metrics_by_campaign=metrics_rows,
    )
    retry_calls = get_ads_creatives_retry_counter_calls()

    checks = {
        "csv oracle 对拍通过": ok_oracle,
        "retry calls == 2": retry_calls == 2,
        "输出非空": bool(run_result.core.outputs),
    }
    render_checks(checks)
    return checks, ok_oracle, oracle_details, oracle_summary, retry_calls


@app.cell
def _(checks, latest, make_chapter_result, ok_oracle, oracle_details, oracle_summary, out_detail_all, out_detail_clicks, out_metrics, out_root, retry_calls, run_result, yaml_path):
    passed = bool(all(checks.values()))
    summary = "oracle={} retry_calls={} outputs={} | {}".format(
        ok_oracle,
        retry_calls,
        sorted(run_result.core.outputs.keys()) if run_result.core.outputs else None,
        oracle_summary,
    )
    chapter_result = make_chapter_result(
        passed=passed,
        summary=summary,
        details={
            "yaml_path": str(yaml_path),
            "outputs": run_result.core.outputs,
            "out_root": str(out_root),
            "run_id": latest.run_id,
            "detail_all_csv": str(out_detail_all),
            "detail_clicks_csv": str(out_detail_clicks),
            "metrics_by_campaign_csv": str(out_metrics),
            "retry_calls": retry_calls,
            "oracle": oracle_details,
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

    detail_rows = details_to_rows(chapter_result["details"])
    mo.ui.table(detail_rows, selection=None) if detail_rows else mo.md("(无详情)")
    return


def run_chapter():
    """SSOT 入口：headless runner 与 pytest 通过此函数执行对拍。"""
    outputs, defs = app.run()
    return defs["chapter_result"]


if __name__ == "__main__":
    app.run()