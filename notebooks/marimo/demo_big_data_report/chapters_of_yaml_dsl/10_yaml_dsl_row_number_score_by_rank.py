import marimo

import csv
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from scalim.dsl.by_yaml import compile as compile_yaml
from scalim.execution.run_ir import run_ir
from scalim_misc.demo_big_data_report.by_yaml_dsl.ecommerce_rank_score_oracle import verify_ecommerce_rank_score_csv_rows
from scalim_misc.demo_big_data_report.cases import build_test_config_small
from scalim_misc.demo_big_data_report.loaders import ECommerceConfig, get_config, set_config
from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult

__generated_with = "0.20.2"
app = marimo.App(width="full")

_EXAMPLE_ID = "demo_big_data_report/yaml_dsl_row_number_score_by_rank"
_ALLOWED_MODULES = frozenset(["scalim_misc.demo_big_data_report.loaders"])


def _read_csv_rows(path: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if not row:
                continue
            rows.append({str(k): str(v) if v is not None else "" for k, v in row.items()})
    return rows


def run_yaml_dsl_row_number_score_by_rank(
    cfg: Optional[ECommerceConfig] = None,
    *,
    yaml_path: Optional[Path] = None,
) -> ExampleResult:
    if cfg is None:
        cfg = build_test_config_small()
    if yaml_path is None:
        demo_dir = Path(__file__).resolve().parents[1]
        yaml_path = demo_dir / "chapters_of_yaml_dsl" / "declared_yaml_dsl" / "ecommerce_rank_score_report.yaml"

    prev = get_config()
    set_config(cfg)
    try:
        with tempfile.TemporaryDirectory(prefix="scalim-rank-score-") as tmpdir:
            tmp = Path(tmpdir)
            out_rank = tmp / "top2_by_region_category.csv"

            init_vars: Dict[str, object] = {"out_path_rank": str(out_rank)}

            try:
                compilation = compile_yaml(
                    str(yaml_path),
                    allowed_modules=_ALLOWED_MODULES,
                    init_vars=init_vars,
                )
                core = run_ir(compilation.demand_ir, compilation.request)
            except Exception as exc:  # noqa: BLE001
                return ExampleResult(
                    example_id=_EXAMPLE_ID,
                    passed=False,
                    kind=EXAMPLE_KIND_ORACLE,
                    summary="compile/run failed: {}: {}".format(type(exc).__name__, exc),
                    details={"exc_type": type(exc).__name__, "message": str(exc)},
                )

            rows = _read_csv_rows(out_rank) if out_rank.exists() else []
            ok_oracle, oracle_summary, oracle_details = verify_ecommerce_rank_score_csv_rows(actual_rows=rows, cfg=cfg)

            passed = bool(ok_oracle and rows and core.outputs)
            summary = "oracle={} rows={} outputs={} | {}".format(
                ok_oracle, len(rows), sorted(core.outputs.keys()) if core.outputs else None, oracle_summary
            )
            details: Dict[str, Any] = {
                "yaml_path": str(yaml_path),
                "rank_csv": str(out_rank),
                "rows": len(rows),
                "outputs": core.outputs,
                "oracle": oracle_details,
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
    return run_yaml_dsl_row_number_score_by_rank()


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / yaml_dsl_row_number_score_by_rank

        ## 背景

        电商大促复盘里,运营经常不仅要“看 Top 榜”,还要把 Top 榜转成可下游使用的 **积分/权重**：
        - Top2/Top5 固定行数(哪怕并列也要截断,保证报表版面稳定)
        - 同分并列要不要合并名次？（dense_rank vs row_number）

        ## 需求方提问（自然语言）

        运营负责人：我能不能在 YAML 里直接写出“排名 + TopK + 积分衰减”口径,让工程同学在 CI 里每天回归？

        ## 本章覆盖的 YAML DSL 能力

        - `row_number` + `partition_by`：分区内连续序号(1..N)
        - `dense_rank`：并列合并名次(1,1,2...)
        - `top_k_mode=rows`：强制固定 K 行(需要稳定 `order_by` tie-break)
        - `score_by_rank`：按名次生成积分(score = base - (rank - 1) * step)
        - `source`：字段显式标注来源(防止 fragments 复用漂移)

        ## 对拍点（deterministic）

        - YAML fixture：`chapters_of_yaml_dsl/declared_yaml_dsl/ecommerce_rank_score_report.yaml`
        - 纯 Python 真值：`scalim_misc.demo_big_data_report.by_yaml_dsl.ecommerce_rank_score_oracle:build_expected_rows_top2_by_region`
        - Gate：`just examples`

        SSOT:
        - `notebooks/marimo/demo_big_data_report/chapters_of_yaml_dsl/10_yaml_dsl_row_number_score_by_rank.py::run_yaml_dsl_row_number_score_by_rank`
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
    yaml_path = demo_dir / "chapters_of_yaml_dsl" / "declared_yaml_dsl" / "ecommerce_rank_score_report.yaml"
    return demo_dir, yaml_path


@app.cell(hide_code=True)
def _(mo, yaml_path):
    from scalim_misc.notebook_support.yaml_excerpt import excerpt_head

    mo.md("## Rank + Score demand YAML (head)")
    mo.md("```yaml\n{}\n```".format(excerpt_head(yaml_path, max_lines=140)))
    return (excerpt_head,)


@app.cell
def _(yaml_path):
    cfg = build_test_config_small()
    result = run_yaml_dsl_row_number_score_by_rank(cfg, yaml_path=yaml_path)
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
