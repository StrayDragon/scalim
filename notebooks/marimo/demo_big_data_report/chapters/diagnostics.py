from __future__ import annotations

from typing import Any, Dict, List

from scalim.spec.ir import DerivedFieldIr, FieldIr, JoinConditionIr, RelationIr

from notebooks.marimo.demo_big_data_report._loaders import ECommerceConfig, set_config
from notebooks.marimo.demo_big_data_report._shared import build_ecommerce_model

from ._types import ChapterResult


def run_diagnostics(cfg: ECommerceConfig) -> ChapterResult:
    """不执行引擎,仅对 IR 模型做静态诊断统计."""
    set_config(cfg)
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
    return ChapterResult(chapter_id="diagnostics", passed=passed, summary=summary, details=details)
