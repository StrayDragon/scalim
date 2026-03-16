import marimo

import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from scalim.dsl.by_yaml import compile as compile_yaml
from scalim.dsl.by_yaml import run as run_yaml
from scalim.dsl.by_yaml.config_parsing.errors import ConfigValidationError
from scalim.dsl.by_yaml.config_parsing.imports import load_and_expand_imports
from scalim.dsl.by_yaml.config_parsing.loader import YamlDemandLoader
from scalim.dsl.by_yaml.config_parsing.validator import ConfigValidator
from scalim.sinks.sink_memory import InMemoryRowSink
from scalim.typedefs import RowData
from scalim_misc.demo_big_data_report.cases import build_test_config_small
from scalim_misc.demo_big_data_report.loaders import ECommerceConfig, get_config, set_config
from scalim_misc.demo_big_data_report.shared import TARGET_FIELDS_FULL
from scalim_misc.demo_big_data_report.verification import VerificationResult, verify_scalim_output
from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult

__generated_with = "0.20.2"
app = marimo.App(width="full")


def _extract_verifiable_fields(rows: Sequence[RowData]) -> List[str]:
    if not rows:
        return []
    keys = set(rows[0].keys())
    return [field for field in TARGET_FIELDS_FULL if field in keys]


def run_yaml_dsl(
    cfg: Optional[ECommerceConfig] = None,
    *,
    yaml_path: Optional[Path] = None,
    runtime_vars: Optional[Dict[str, object]] = None,
) -> ExampleResult:
    if cfg is None:
        cfg = build_test_config_small()
    if yaml_path is None:
        demo_dir = Path(__file__).resolve().parents[1]
        yaml_path = demo_dir / "by_yaml_dsl" / "ecommerce_report.yaml"
    prev = get_config()
    set_config(cfg)
    try:
        loader_module = "scalim_misc.demo_big_data_report.loaders"
        allowed_modules = frozenset([loader_module])
        runtime_vars = runtime_vars or {"order_ids": []}

        # 1) 语义校验: ConfigValidator + YamlDemandLoader
        validator = ConfigValidator()
        yaml_config = load_and_expand_imports(yaml_path)
        try:
            validator.validate(yaml_config)
        except ConfigValidationError as exc:
            summary = "ConfigValidator failed: {}".format(exc)
            return ExampleResult(
                example_id="demo_big_data_report/yaml_dsl",
                passed=False,
                kind=EXAMPLE_KIND_ORACLE,
                summary=summary,
                details={"errors": getattr(exc, "errors", None)},
            )

        demand_config = YamlDemandLoader().load(str(yaml_path))

        # 2) `compile`: 确保能生成 `IR`/`request`
        compilation = compile_yaml(
            str(yaml_path),
            allowed_modules=allowed_modules,
            runtime_vars=runtime_vars,
        )

        # 3) `run`: 用内存 `sink` 获取行数据
        sink = InMemoryRowSink()
        start = time.time()
        result = run_yaml(
            str(yaml_path),
            allowed_modules=allowed_modules,
            sink=sink,
            runtime_vars=runtime_vars,
        )
        elapsed = time.time() - start

        rows = sink.get_data()
        if not rows:
            return ExampleResult(
                example_id="demo_big_data_report/yaml_dsl",
                passed=False,
                kind=EXAMPLE_KIND_ORACLE,
                summary="YAML run produced no rows",
                details={"duration_seconds": elapsed, "result": result},
            )

        # 4) `rows-binding` 对拍字段校验(来自唯一完整 YAML 示例)
        match_fields = ["rows_name_match", "rows_level_match"]
        mismatch = 0
        for row in rows:
            for field in match_fields:
                if not row.get(field):
                    mismatch += 1
                    break

        # 5) 基于纯 Python 对照组对拍(只检查可验证字段子集)
        fields_to_check = _extract_verifiable_fields(rows)
        verification: VerificationResult = verify_scalim_output(rows, fields_to_check=fields_to_check)

        passed = bool(verification.passed and mismatch == 0)
        summary = "rows={} elapsed={:.3f}s verify={} rows_match_failures={}".format(len(rows), elapsed, verification.passed, mismatch)
        if mismatch:
            summary = summary + "\nrows match fields failed on {} rows".format(mismatch)
        if not verification.passed:
            summary = summary + "\n" + verification.summary

        details: Dict[str, Any] = {
            "duration_seconds": elapsed,
            "rows": len(rows),
            "result": result,
            "demand_config": demand_config,
            "compilation": compilation,
            "verification": verification,
            "fields_checked": fields_to_check,
            "rows_match_failures": mismatch,
        }
        return ExampleResult(
            example_id="demo_big_data_report/yaml_dsl",
            passed=passed,
            kind=EXAMPLE_KIND_ORACLE,
            summary=summary,
            details=details,
        )
    finally:
        set_config(prev)


def run_chapter() -> ExampleResult:
    return run_yaml_dsl()


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / yaml_dsl

        本章目标:
        - 演示 canonical YAML 的加载/编译/执行闭环(含对拍)
        - 作为 YAML DSL 语义回归的可交互入口

        SSOT:
        - `notebooks/marimo/demo_big_data_report/chapters/yaml_dsl.py::run_yaml_dsl`

        Gate:
        - `just examples`（跑全量）
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
    yaml_path = demo_dir / "by_yaml_dsl" / "ecommerce_report.yaml"
    return demo_dir, yaml_path


@app.cell(hide_code=True)
def _(mo, yaml_path):
    from scalim_misc.notebook_support.yaml_excerpt import excerpt_by_regex

    snippet = excerpt_by_regex(
        yaml_path,
        start_regex=r"^imports:",
        end_regex=r"^# ==============================================================================",
        max_lines=80,
    )
    mo.md("## Canonical YAML 片段：`imports`")
    mo.md("```yaml\n{}\n```".format(snippet))
    return excerpt_by_regex, snippet


@app.cell
def _(yaml_path):
    cfg = build_test_config_small()
    result = run_yaml_dsl(cfg, yaml_path=yaml_path)
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
