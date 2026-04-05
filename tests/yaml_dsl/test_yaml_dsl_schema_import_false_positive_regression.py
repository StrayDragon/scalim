import json
from pathlib import Path

import jsonschema


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_demand_schema() -> dict:
    path = _repo_root() / "src" / "scalim" / "dsl" / "by_yaml" / "schema" / "demand.gen.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_demand_schema_book_kind_if_requires_kind() -> None:
    schema = _load_demand_schema()
    book = schema["definitions"]["book"]
    all_of = book.get("allOf") or []
    assert isinstance(all_of, list)

    checked = 0
    for item in all_of:
        if not isinstance(item, dict):
            continue
        if_schema = item.get("if") or {}
        if not isinstance(if_schema, dict):
            continue
        props = if_schema.get("properties") or {}
        if not isinstance(props, dict):
            continue
        kind = props.get("kind") or {}
        if not isinstance(kind, dict):
            continue
        if "const" not in kind:
            continue
        required = if_schema.get("required") or []
        assert isinstance(required, list)
        assert "kind" in required
        checked += 1

    assert checked >= 2


def test_demand_schema_import_based_book_mapping_does_not_require_budget() -> None:
    schema = _load_demand_schema()
    wrapper = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$ref": "#/definitions/book",
        "definitions": schema.get("definitions") or {},
    }

    data = {
        "$import": "fragments.report_book",
        "path": "./out.xlsx",
    }
    errors = list(jsonschema.Draft7Validator(wrapper).iter_errors(data))
    assert errors == [], [err.message for err in errors]
