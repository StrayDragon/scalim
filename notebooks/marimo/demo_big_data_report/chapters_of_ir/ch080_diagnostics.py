"""Cells-native: ch080_diagnostics — static IR diagnostics (no engine run)."""
import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""# Diagnostics: Static IR inspection

不执行引擎，对 IR model 做静态诊断统计（fields, relations, derived, cached）。""")
    return


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _():
    from scalim_misc.notebook_support.pathing import ensure_repo_root_on_sys_path
    ensure_repo_root_on_sys_path(__file__)
    return


@app.cell
def _():
    from typing import Dict, List

    from scalim.spec.ir import DerivedFieldIr, FieldIr, JoinConditionIr, RelationIr
    from scalim_misc.demo_big_data_report.cases import build_test_config_small
    from scalim_misc.demo_big_data_report.shared import build_ecommerce_model
    return (
        DerivedFieldIr, Dict, FieldIr, JoinConditionIr, List, RelationIr,
        build_ecommerce_model, build_test_config_small,
    )


@app.cell
def _(build_ecommerce_model, build_test_config_small):
    cfg = build_test_config_small()
    model = build_ecommerce_model(cfg)
    print("sources={} fields={}".format(len(model.sources), len(model.fields)))
    return cfg, model


@app.cell
def _(DerivedFieldIr, FieldIr, JoinConditionIr, List, RelationIr, model):
    """Inspect model: relation fields, derived fields, cached sources."""
    relation_fields: list = []
    for field_id, spec in model.fields.items():
        if not isinstance(spec, FieldIr) or not spec.relation:
            continue
        rel = spec.relation
        if isinstance(rel, JoinConditionIr):
            left = "{}.{}".format(rel.left.source.source_id, rel.left.field_name)
            right = "{}.{}".format(rel.right.source.source_id, rel.right.field_name)
            relation_fields.append({"field": field_id, "type": "single", "expr": "{} -> {}".format(left, right)})
        elif isinstance(rel, RelationIr):
            conditions = []
            for cond in rel.conditions:
                left = "{}.{}".format(cond.left.source.source_id, cond.left.field_name)
                right = "{}.{}".format(cond.right.source.source_id, cond.right.field_name)
                conditions.append("{} -> {}".format(left, right))
            relation_fields.append({"field": field_id, "type": "multi" if len(conditions) > 1 else "single",
                                    "expr": " AND ".join(conditions)})

    derived_fields = [fid for fid, spec in model.fields.items() if isinstance(spec, DerivedFieldIr)]
    cached_sources = [sid for sid, src in model.sources.items() if src.is_preload_forever()]

    passed = bool(relation_fields and derived_fields)
    summary = "sources={} fields={} relation_fields={} derived_fields={} cached_sources={}".format(
        len(model.sources), len(model.fields), len(relation_fields), len(derived_fields), len(cached_sources))

    chapter_result = {
        "passed": passed,
        "summary": summary,
        "details": {"sources": len(model.sources), "fields": len(model.fields),
                    "relation_fields": relation_fields, "derived_fields": derived_fields,
                    "cached_sources": cached_sources},
    }
    return chapter_result, derived_fields, passed, relation_fields, summary


@app.cell(hide_code=True)
def _(chapter_result, mo):
    ok = chapter_result["passed"]
    mo.callout(mo.md("## {}: {}".format("✅ PASS" if ok else "❌ FAIL", chapter_result["summary"])),
               kind="success" if ok else "danger")
    return


@app.cell(hide_code=True)
def _(chapter_result, mo):
    mo.md("### Relation fields")
    mo.ui.table(chapter_result["details"]["relation_fields"][:20], selection=None)
    return


def run_chapter():
    outputs, defs = app.run()
    return defs["chapter_result"]


if __name__ == "__main__":
    app.run()
