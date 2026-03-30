import marimo

from typing import Any, Dict, List, Optional

from scalim.spec.ir import DerivedFieldIr, FieldIr, JoinConditionIr, RelationIr
from scalim_misc.demo_big_data_report.cases import build_test_config_small
from scalim_misc.demo_big_data_report.loaders import ECommerceConfig, get_config, set_config
from scalim_misc.demo_big_data_report.shared import build_ecommerce_model
from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult

__generated_with = "0.20.2"
app = marimo.App(width="full")


def run_diagnostics(cfg: Optional[ECommerceConfig] = None) -> ExampleResult:
    if cfg is None:
        cfg = build_test_config_small()
    prev = get_config()
    set_config(cfg)
    try:
        model = build_ecommerce_model(cfg)

        relation_fields: List[Dict[str, str]] = []
        for field_id, spec in model.fields.items():
            if not isinstance(spec, FieldIr) or not spec.relation:
                continue
            rel = spec.relation
            if isinstance(rel, JoinConditionIr):
                left = "{}.{}".format(rel.left.source.source_id, rel.left.field_name)
                right = "{}.{}".format(rel.right.source.source_id, rel.right.field_name)
                relation_fields.append({"field": field_id, "type": "single", "expr": "{} -> {}".format(left, right)})
                continue
            if isinstance(rel, RelationIr):
                conditions = []
                for cond in rel.conditions:
                    left = "{}.{}".format(cond.left.source.source_id, cond.left.field_name)
                    right = "{}.{}".format(cond.right.source.source_id, cond.right.field_name)
                    conditions.append("{} -> {}".format(left, right))
                relation_fields.append(
                    {"field": field_id, "type": "multi" if len(conditions) > 1 else "single", "expr": " AND ".join(conditions)}
                )
                continue

        derived_fields = [field_id for field_id, spec in model.fields.items() if isinstance(spec, DerivedFieldIr)]
        cached_sources = [source_id for source_id, source in model.sources.items() if source.is_preload_forever()]

        passed = bool(relation_fields and derived_fields)
        summary = "sources={} fields={} relation_fields={} derived_fields={} cached_sources={}".format(
            len(model.sources),
            len(model.fields),
            len(relation_fields),
            len(derived_fields),
            len(cached_sources),
        )

        details: Dict[str, Any] = {
            "sources": len(model.sources),
            "fields": len(model.fields),
            "relation_fields": relation_fields,
            "derived_fields": derived_fields,
            "cached_sources": cached_sources,
        }
        return ExampleResult(
            example_id="demo_big_data_report/ch080_diagnostics",
            passed=passed,
            kind=EXAMPLE_KIND_ORACLE,
            summary=summary,
            details=details,
        )
    finally:
        set_config(prev)


def run_chapter() -> ExampleResult:
    return run_diagnostics()


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / ch080_diagnostics

        本章目标:
        - 不执行引擎,对 IR/relations/derived 字段等做静态诊断统计

        SSOT:
        - `notebooks/marimo/demo_big_data_report/chapters_of_ir/ch080_diagnostics.py::run_diagnostics`

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

    repo_root = ensure_repo_root_on_sys_path(__file__)
    return (repo_root,)


@app.cell
def _():
    from scalim_misc.demo_big_data_report.cases import build_test_config_small

    cfg = build_test_config_small()
    result = run_diagnostics(cfg)
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
