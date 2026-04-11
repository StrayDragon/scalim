from __future__ import annotations

from typing import Any, Dict

from scalim.dsl.yaml_dsl.schema_dsl import builder as schema_builder
from scalim.dsl.yaml_dsl.schema_dsl import doc_standardizer as hook


def test_schema_docs_standardizer_hook_noop_when_plugin_missing(monkeypatch) -> None:
    monkeypatch.setattr(hook, "load_schema_doc_standardizer_impl", lambda: None)
    schema: Dict[str, Any] = {"type": "object"}
    assert hook.maybe_standardize_schema_docs(schema) is schema


def test_schema_builder_schema_generation_does_not_require_scalim_misc(monkeypatch) -> None:
    monkeypatch.setattr(hook, "load_schema_doc_standardizer_impl", lambda: None)
    schema = schema_builder.SchemaBuilder().build_demand_schema()
    assert isinstance(schema, dict)
    assert schema.get("type") == "object"
