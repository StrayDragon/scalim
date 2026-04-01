import marimo

import csv
import os
import tempfile
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from scalim.dsl.by_yaml import run_workflow
from scalim_misc.demo_big_data_report.cases import build_test_config_small
from scalim_misc.demo_big_data_report.loaders import (
    ECommerceConfig,
    get_config,
    get_workflow_preload_counter_calls,
    reset_workflow_preload_counter_calls,
    set_config,
)
from scalim_misc.demo_big_data_report.shared import TARGET_FIELDS_FULL
from scalim_misc.demo_big_data_report.verification import VerificationResult, verify_scalim_output_csv
from scalim_misc.examples.oracle import diff_first_mismatch, stable_sort_rows
from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult

__generated_with = "0.20.2"
app = marimo.App(width="full")
_EXAMPLE_ID = "demo_big_data_report/workflow_demo_big_data_report"


def _read_csv_rows(path: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if not row:
                continue
            rows.append({str(k): str(v) if v is not None else "" for k, v in row.items()})
    return rows


def _build_expected_metrics_rows(*, detail_rows: Sequence[Mapping[str, str]]) -> List[Dict[str, str]]:
    by_region: Dict[str, Dict[str, Any]] = {}
    for row in detail_rows:
        region = str(row.get("region_name_display") or "")
        acc = by_region.setdefault(region, {"region_name_display": region, "order_cnt": 0, "sum_order_amount": Decimal("0")})
        acc["order_cnt"] = int(acc["order_cnt"]) + 1
        try:
            amount = Decimal(str(row.get("order_amount") or "0"))
        except Exception:  # noqa: BLE001
            amount = Decimal("0")
        acc["sum_order_amount"] = acc["sum_order_amount"] + amount

    rows: List[Dict[str, str]] = []
    for region, acc in by_region.items():
        rows.append(
            {
                "region_name_display": region,
                "order_cnt": str(acc["order_cnt"]),
                "sum_order_amount": str(acc["sum_order_amount"]),
            }
        )
    return rows


def run_workflow_demo_big_data_report(
    cfg: Optional[ECommerceConfig] = None,
    *,
    workflow_yaml_path: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    clean_output_dir: bool = True,
) -> ExampleResult:
    if cfg is None:
        cfg = build_test_config_small()
    if workflow_yaml_path is None:
        demo_dir = Path(__file__).resolve().parents[1]
        workflow_yaml_path = demo_dir / "chapters_of_yaml_dsl" / "declared_yaml_dsl" / "workflow_demo_big_data_report.yaml"

    prev = get_config()
    set_config(cfg)
    try:
        allowed_modules = frozenset(["scalim_misc.demo_big_data_report.loaders", "scalim.workflow.loaders"])
        repo_root = Path(__file__).resolve().parents[4]
        reset_workflow_preload_counter_calls()

        def _run_in_dir(out_dir: Path) -> ExampleResult:
            if clean_output_dir:
                for filename in ("detail.csv", "metrics.csv", "report.xlsx", "workflow.yaml"):
                    try:
                        (out_dir / filename).unlink()
                    except FileNotFoundError:
                        pass
                    except OSError:
                        pass

            wf_copy = out_dir / "workflow.yaml"
            wf_copy.write_text(workflow_yaml_path.read_text(encoding="utf-8"), encoding="utf-8")

            demand_dir = workflow_yaml_path.parent
            for demand_filename in (
                "workflow_demo_big_data_report_detail_demand.yaml",
                "workflow_demo_big_data_report_metrics_demand.yaml",
            ):
                (out_dir / demand_filename).write_text((demand_dir / demand_filename).read_text(encoding="utf-8"), encoding="utf-8")

            try:
                prev_cwd = os.getcwd()
                os.chdir(str(out_dir))
                try:
                    result = run_workflow(
                        str(wf_copy),
                        allowed_modules=allowed_modules,
                        init_vars={"order_ids": []},
                        batch_size=30,
                        path_aliases={"@": str(repo_root)},
                        allowed_yaml_roots=(str(repo_root),),
                    )
                finally:
                    os.chdir(prev_cwd)
            except Exception as exc:  # noqa: BLE001
                summary = "workflow failed: {}: {}".format(type(exc).__name__, exc)
                return ExampleResult(
                    example_id=_EXAMPLE_ID,
                    passed=False,
                    kind=EXAMPLE_KIND_ORACLE,
                    summary=summary,
                    details={"exc_type": type(exc).__name__},
                )

            errors = result.errors()
            preload_calls = get_workflow_preload_counter_calls()

            detail_csv = out_dir / "detail.csv"
            metrics_csv = out_dir / "metrics.csv"
            report_xlsx = out_dir / "report.xlsx"

            verification: VerificationResult
            if detail_csv.exists():
                verification = verify_scalim_output_csv(detail_csv, fields_to_check=TARGET_FIELDS_FULL)
            else:
                verification = VerificationResult(
                    passed=False,
                    total_rows=0,
                    checked_rows=0,
                    mismatches=[],
                    summary="Missing detail.csv",
                )

            metrics_ok = False
            metrics_summary = "missing metrics.csv"
            if detail_csv.exists() and metrics_csv.exists():
                detail_rows = _read_csv_rows(detail_csv)
                actual_metrics = stable_sort_rows(_read_csv_rows(metrics_csv), by=("region_name_display",))
                expected_metrics = stable_sort_rows(_build_expected_metrics_rows(detail_rows=detail_rows), by=("region_name_display",))
                metrics_ok, metrics_summary = diff_first_mismatch(
                    actual_metrics,
                    expected_metrics,
                    fields=("region_name_display", "order_cnt", "sum_order_amount"),
                )

            artifacts_ok = bool(detail_csv.exists() and metrics_csv.exists() and report_xlsx.exists())
            passed = bool(not errors and preload_calls == 1 and artifacts_ok and verification.passed and metrics_ok)

            summary = "errors={} preload_calls={} artifacts_ok={} verify={}".format(
                len(errors),
                preload_calls,
                artifacts_ok,
                verification.passed,
            )
            if errors:
                summary = summary + "\nfirst_error: {} {}".format(errors[0].exc_type, errors[0].message)
            if not verification.passed:
                summary = summary + "\n" + verification.summary
            if not metrics_ok:
                summary = summary + "\nmetrics: " + metrics_summary

            details: Dict[str, Any] = {
                "output_dir": str(out_dir),
                "detail_csv": str(detail_csv),
                "metrics_csv": str(metrics_csv),
                "report_xlsx": str(report_xlsx),
                "verification": verification,
                "metrics": {"passed": metrics_ok, "summary": metrics_summary},
                "errors": errors,
                "outcomes": result.outcomes,
            }
            return ExampleResult(
                example_id=_EXAMPLE_ID,
                passed=passed,
                kind=EXAMPLE_KIND_ORACLE,
                summary=summary,
                details=details,
            )

        if output_dir is not None:
            out_dir = Path(str(output_dir)).expanduser().resolve()
            out_dir.mkdir(parents=True, exist_ok=True)
            return _run_in_dir(out_dir)

        with tempfile.TemporaryDirectory(prefix="scalim-demo-wf-") as temp_dir:
            out_dir = Path(temp_dir).resolve()
            return _run_in_dir(out_dir)
    finally:
        set_config(prev)


def run_chapter() -> ExampleResult:
    return run_workflow_demo_big_data_report()


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / workflow_demo_big_data_report

        ## 背景

        workflow fixture 能证明“能跑”，但真实使用通常还会涉及：
        - resources（sheetbook/csv 等资源托管）
        - writes（把上游 output 写入到资源）
        - depends_on（显式 DAG）
        - workflow 内置 `loader`（从共享 `sheetbook` 读取上游 rows）
        - cache_pool（workflow-scope cache，共享 `preload_forever`）

        ## 需求方提问（自然语言）

        业务方：能给一个更像生产的 workflow demo 吗？我想在 PR 里改 YAML 后能稳定对拍。

        ## 对拍点（deterministic）

        - workflow YAML：`chapters_of_yaml_dsl/declared_yaml_dsl/workflow_demo_big_data_report.yaml`
        - 断言：
          - `depends_on` + `scalim.workflow.loaders.sheetbook_sheet_rows` 链路可跑通（detail → metrics）
          - 产物存在：`detail.csv` / `metrics.csv` / `report.xlsx`
          - `cache_pool` 生效：`preload_forever` 共享 loader 仅调用 1 次
          - 明细 CSV 与纯 Python 对照组一致：`verify_scalim_output_csv`
        - Gate：`just examples`

        SSOT:
        - `notebooks/marimo/demo_big_data_report/chapters_of_yaml_dsl/ch050_workflow_demo_big_data_report.py::run_workflow_demo_big_data_report`
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
    workflow_yaml_path = demo_dir / "chapters_of_yaml_dsl" / "declared_yaml_dsl" / "workflow_demo_big_data_report.yaml"
    return demo_dir, workflow_yaml_path


@app.cell(hide_code=True)
def _(mo, workflow_yaml_path):
    from scalim_misc.notebook_support.yaml_excerpt import excerpt_head

    mo.md("## Workflow YAML")
    mo.md("```yaml\n{}\n```".format(excerpt_head(workflow_yaml_path, max_lines=160)))
    return (excerpt_head,)


@app.cell
def _(workflow_yaml_path):
    cfg = build_test_config_small()
    output_dir = Path(__file__).resolve().parents[4] / ".tmp" / "artifacts" / "demo_big_data_report" / "workflow_demo_big_data_report"
    result = run_workflow_demo_big_data_report(cfg, workflow_yaml_path=workflow_yaml_path, output_dir=output_dir)
    return cfg, result


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
