from typing import Any, Dict

from scalim.dsl.yaml_dsl.schema_dsl import constants as schema_constants
from scalim.dsl.yaml_dsl.schema_dsl import workflow_ssot


def _as_dict(value: Any) -> Dict[str, Any]:
    assert isinstance(value, dict)
    return value


def test_import_schema_fragments_live_in_core_and_are_descriptive() -> None:
    ref = _as_dict(schema_constants.IMPORT_REF_SCHEMA)
    assert isinstance(ref.get("description"), str) and ref["description"].strip()
    assert isinstance(ref.get("markdownDescription"), str) and ref["markdownDescription"].strip()
    assert isinstance(ref.get("oneOf"), list)

    imports = _as_dict(schema_constants.IMPORTS_SCHEMA)
    assert isinstance(imports.get("description"), str) and imports["description"].strip()
    assert isinstance(imports.get("markdownDescription"), str) and imports["markdownDescription"].strip()
    assert isinstance(imports.get("propertyNames"), dict)
    assert isinstance(imports.get("additionalProperties"), dict)


def test_workflow_schema_fragments_live_in_core_and_are_descriptive() -> None:
    workflow = _as_dict(workflow_ssot.build_workflow_workflow_schema())
    props = _as_dict(workflow.get("properties"))

    runs = _as_dict(props.get("runs"))
    items = _as_dict(runs.get("items"))
    item_props = _as_dict(items.get("properties"))
    demand = _as_dict(item_props.get("demand"))
    assert isinstance(demand.get("description"), str) and str(demand["description"]).strip()
    assert isinstance(demand.get("markdownDescription"), str) and str(demand["markdownDescription"]).strip()

    resources = _as_dict(props.get("resources"))
    assert isinstance(resources.get("description"), str) and str(resources["description"]).strip()
    assert isinstance(resources.get("markdownDescription"), str) and str(resources["markdownDescription"]).strip()


def test_workflow_schema_meta_is_core_ssot() -> None:
    meta = _as_dict(schema_constants.WORKFLOW_SCHEMA_META)
    assert meta.get("$schema") == "http://json-schema.org/draft-07/schema#"
    assert isinstance(meta.get("$id"), str) and str(meta["$id"]).strip()
    assert isinstance(meta.get("title"), str) and str(meta["title"]).strip()
    assert isinstance(meta.get("description"), str) and str(meta["description"]).strip()
