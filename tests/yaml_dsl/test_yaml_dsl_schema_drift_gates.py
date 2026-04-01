import json
from pathlib import Path


_NUMERIC_CONSTRAINT_KEYS = ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum")
_NUMERIC_TYPES = ("number", "integer")


def _iter_numeric_constraint_issues(value: object, *, path: str):
    if isinstance(value, dict):
        keys = set(value)
        if keys.intersection(_NUMERIC_CONSTRAINT_KEYS):
            raw_type = value.get("type")
            types = []
            if isinstance(raw_type, str):
                types = [raw_type]
            elif isinstance(raw_type, list):
                types = [item for item in raw_type if isinstance(item, str)]

            if not any(item in _NUMERIC_TYPES for item in types):
                constraints = {k: value.get(k) for k in _NUMERIC_CONSTRAINT_KEYS if k in value}
                yield path, constraints, raw_type

        for k, v in value.items():
            yield from _iter_numeric_constraint_issues(v, path="{}.{}".format(path, k))
        return

    if isinstance(value, list):
        for idx, item in enumerate(value):
            yield from _iter_numeric_constraint_issues(item, path="{}[{}]".format(path, idx))
        return


def _contains_key(value: object, key: str) -> bool:
    if isinstance(value, dict):
        if key in value:
            return True
        return any(_contains_key(v, key) for v in value.values())
    if isinstance(value, list):
        return any(_contains_key(item, key) for item in value)
    return False


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_schema(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def test_yaml_dsl_schema_numeric_constraints_are_typed() -> None:
    schema_dir = _repo_root() / "src" / "scalim" / "dsl" / "by_yaml" / "schema"
    schemas = [
        schema_dir / "demand.gen.json",
        schema_dir / "workflow.gen.json",
    ]

    issues = []
    for schema_path in schemas:
        data = _load_schema(schema_path)
        issues.extend([(schema_path.name,) + item for item in _iter_numeric_constraint_issues(data, path="$")])

    assert issues == [], "Found numeric constraints without numeric type: {}".format(issues[:10])


def test_workflow_schema_does_not_expose_import_syntax() -> None:
    schema_dir = _repo_root() / "src" / "scalim" / "dsl" / "by_yaml" / "schema"
    workflow_schema = _load_schema(schema_dir / "workflow.gen.json")

    assert _contains_key(workflow_schema, "$import") is False

    resources = workflow_schema["definitions"]["resources"]
    keys = set(resources.get("properties", {}))
    assert keys == {"books", "files"}
