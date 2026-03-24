import marimo

import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from scalim.dsl.by_yaml import compile as compile_yaml
from scalim.dsl.by_yaml import run as run_yaml
from scalim.sinks.sink_memory import InMemoryRowSink
from scalim.typedefs import RowData
from scalim_misc.demo_big_data_report.cases import build_test_config_small
from scalim_misc.demo_big_data_report.loaders import ECommerceConfig, get_config, set_config
from scalim_misc.demo_big_data_report.shared import TARGET_FIELDS_FULL
from scalim_misc.demo_big_data_report.verification import VerificationResult, verify_scalim_output
from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult

__generated_with = "0.20.2"
app = marimo.App(width="full")
_EXAMPLE_ID = "demo_big_data_report/yaml_dsl_ecommerce"


def _extract_verifiable_fields(rows: Sequence[RowData]) -> List[str]:
    if not rows:
        return []
    keys = set(rows[0].keys())
    return [field for field in TARGET_FIELDS_FULL if field in keys]


def run_yaml_dsl_ecommerce(
    cfg: Optional[ECommerceConfig] = None,
    *,
    yaml_path: Optional[Path] = None,
    init_vars: Optional[Dict[str, object]] = None,
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
        init_vars = init_vars or {"order_ids": []}

        # 1) `compile`: 语义校验 + 生成编译产物(执行请求等),供下游运行入口复用
        try:
            compilation = compile_yaml(
                str(yaml_path),
                allowed_modules=allowed_modules,
                init_vars=init_vars,
            )
        except Exception as exc:
            summary = "compile failed: {}".format(exc)
            return ExampleResult(
                example_id=_EXAMPLE_ID,
                passed=False,
                kind=EXAMPLE_KIND_ORACLE,
                summary=summary,
                details={"error": str(exc)},
            )

        demand_config = compilation.config

        # 2) `run`: 用内存 `sink` 获取行数据
        sink = InMemoryRowSink()
        start = time.time()
        result = run_yaml(
            str(yaml_path),
            allowed_modules=allowed_modules,
            sink=sink,
            init_vars=init_vars,
        )
        elapsed = time.time() - start

        rows = sink.get_data()
        if not rows:
            return ExampleResult(
                example_id=_EXAMPLE_ID,
                passed=False,
                kind=EXAMPLE_KIND_ORACLE,
                summary="YAML run produced no rows",
                details={"duration_seconds": elapsed, "result": result},
            )

        # 3) `rows-binding` 对拍字段校验(来自唯一完整 YAML 示例)
        match_fields = ["rows_name_match", "rows_level_match"]
        mismatch = 0
        for row in rows:
            for field in match_fields:
                if not row.get(field):
                    mismatch += 1
                    break

        # 4) 基于纯 Python 对照组对拍(只检查可验证字段子集)
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
            example_id=_EXAMPLE_ID,
            passed=passed,
            kind=EXAMPLE_KIND_ORACLE,
            summary=summary,
            details=details,
        )
    finally:
        set_config(prev)


def run_chapter() -> ExampleResult:
    return run_yaml_dsl_ecommerce()


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / yaml_dsl_ecommerce

        ## 背景

        假设我们在做电商订单报表：订单主表 + 多张维表（客户/产品/促销/支付/物流/仓库/区域/区域定价）。

        ## 需求方提问（自然语言）

        运营同学：能不能每天给我一份 Excel，既有订单明细，也有按区域/品类的汇总 Top 榜？

        ## 方案选择（取舍）

        - 纯 Python 脚本：快，但复用/审计/编辑器提示差，容易 drift
        - SQL：依赖数仓与口径治理，落地成本高
        - **YAML DSL（本章）**：把“需求→配置→可回归对拍”收敛到一个可校验的需求文件

        ## 对拍点（deterministic）

        - YAML SSOT：`notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml`
        - oracle：`scalim_misc.demo_big_data_report.verification.verify_scalim_output`
        - Gate：`just examples`

        SSOT:
        - `notebooks/marimo/demo_big_data_report/chapters/01_yaml_dsl_ecommerce.py::run_yaml_dsl_ecommerce`
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
    result = run_yaml_dsl_ecommerce(cfg, yaml_path=yaml_path)
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
