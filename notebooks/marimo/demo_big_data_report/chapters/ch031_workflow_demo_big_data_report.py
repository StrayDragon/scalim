import marimo

import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

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
from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult

__generated_with = "0.20.2"
app = marimo.App(width="full")


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
        workflow_yaml_path = demo_dir / "by_yaml_dsl" / "workflow_demo_big_data_report.yaml"

    prev = get_config()
    set_config(cfg)
    try:
        allowed_modules = frozenset(["scalim_misc.demo_big_data_report.loaders"])
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

            try:
                result = run_workflow(
                    str(wf_copy),
                    allowed_modules=allowed_modules,
                    init_vars={"order_ids": []},
                    path_aliases={"@": str(repo_root)},
                )
            except Exception as exc:  # noqa: BLE001
                summary = "workflow failed: {}: {}".format(type(exc).__name__, exc)
                return ExampleResult(
                    example_id="demo_big_data_report/ch031_workflow_demo_big_data_report",
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

            artifacts_ok = bool(detail_csv.exists() and metrics_csv.exists() and report_xlsx.exists())
            passed = bool(not errors and preload_calls == 1 and artifacts_ok and verification.passed)

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

            details: Dict[str, Any] = {
                "output_dir": str(out_dir),
                "detail_csv": str(detail_csv),
                "metrics_csv": str(metrics_csv),
                "report_xlsx": str(report_xlsx),
                "verification": verification,
                "errors": errors,
                "outcomes": result.outcomes,
            }
            return ExampleResult(
                example_id="demo_big_data_report/ch031_workflow_demo_big_data_report",
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
        # demo_big_data_report / ch031_workflow_demo_big_data_report

        本章目标:
        - 构造一个更贴近真实使用的 workflow YAML demo(资源 + writes + cache_pool)
        - 覆盖 `depends_on` + `$ctx` 注入 + workflow-managed temp outputs
        - 提供**纯 Python 对照组**对拍入口(作为 `just examples` 的 oracle)

        SSOT:
        - `notebooks/marimo/demo_big_data_report/chapters/ch031_workflow_demo_big_data_report.py::run_workflow_demo_big_data_report`

        Gate:
        - `just examples`
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
    workflow_yaml_path = demo_dir / "by_yaml_dsl" / "workflow_demo_big_data_report.yaml"
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
