from typing import List

from scalim.dsl.by_yaml.schema_dsl.builder import SchemaBuilder


def test_schema_builder_schema_for_type_list_hits_container_branch() -> None:
    builder = SchemaBuilder()

    schema = builder._schema_for_type(List[str], allow_import=True)  # noqa: SLF001
    assert schema["type"] == "array"
    assert schema["items"] == {"type": "string"}
