import json
from pathlib import Path

import jsonschema


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_demand_schema() -> dict:
    path = _repo_root() / "src" / "scalim" / "dsl" / "yaml_dsl" / "schema" / "demand.gen.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_demand_schema_book_schema_does_not_expose_legacy_kind_discriminator() -> None:
    schema = _load_demand_schema()
    book = schema["definitions"]["book"]
    props = book.get("properties") or {}
    assert isinstance(props, dict)
    assert "kind" not in props
    assert "xlsx" in props
    assert "xlsx_file" not in props
    assert "xlsx_memory" not in props
    assert "book_xlsx_file" not in schema["definitions"]
    assert "book_xlsx_memory" not in schema["definitions"]


def test_demand_schema_import_only_book_mapping_is_schema_valid() -> None:
    schema = _load_demand_schema()
    wrapper = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$ref": "#/definitions/book",
        "definitions": schema.get("definitions") or {},
    }

    data = {
        "$import": "fragments.report_book",
    }
    errors = list(jsonschema.Draft7Validator(wrapper).iter_errors(data))
    assert errors == [], [err.message for err in errors]


def test_demand_schema_import_based_book_mapping_allows_local_xlsx_override() -> None:
    schema = _load_demand_schema()
    wrapper = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$ref": "#/definitions/book",
        "definitions": schema.get("definitions") or {},
    }

    data = {
        "$import": "fragments.report_book",
        "xlsx": {"path": "./out"},
    }
    errors = list(jsonschema.Draft7Validator(wrapper).iter_errors(data))
    assert errors == [], [err.message for err in errors]


def test_demand_schema_rejects_removed_xlsx_file_alias() -> None:
    schema = _load_demand_schema()
    wrapper = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$ref": "#/definitions/book",
        "definitions": schema.get("definitions") or {},
    }

    data = {
        "xlsx_file": {"path": "./out"},
    }
    errors = list(jsonschema.Draft7Validator(wrapper).iter_errors(data))
    assert errors, "xlsx_file alias must be schema-invalid"


def test_demand_schema_branch_import_only_xlsx_mapping_does_not_require_path() -> None:
    schema = _load_demand_schema()
    wrapper = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$ref": "#/definitions/book",
        "definitions": schema.get("definitions") or {},
    }

    data = {
        "xlsx": {"$import": "fragments.report_book_xlsx"},
    }
    errors = list(jsonschema.Draft7Validator(wrapper).iter_errors(data))
    assert errors == [], [err.message for err in errors]
