import pytest

from scalim.dsl.yaml_dsl._internal.config_parsing.error_envelope import ScalimYamlValidationError
from scalim.dsl.yaml_dsl._internal.config_parsing.models import (
    AliasIndex,
    FieldDef,
    RawDemand,
    _add_field_def,
    _collect_derived_fields,
    _collect_main_source_fields,
    _collect_source_fields,
)
from scalim.dsl.yaml_dsl._internal.config_parsing.loader import YamlDemandLoader
from scalim.dsl.yaml_dsl.schema_dsl.constants import (
    DEFAULT_BATCH_SIZE,
    FIELD_KIND_DERIVED,
    FIELD_KIND_SOURCE,
)
from scalim.dsl.yaml_dsl.schema_dsl.models import (
    DERIVED_FIELD_KEYS,
    MAIN_SOURCE_KEYS,
)


def test_raw_demand_get_list_handles_non_list() -> None:
    raw = RawDemand.from_raw({"items": [1], "bad": "x"})
    assert raw.get_list("items") == [1]
    assert raw.get_list("bad") is None


def test_add_field_def_skips_non_dict() -> None:
    field_defs = []
    defs_by_id = {}
    alias_index = AliasIndex()

    _add_field_def(field_defs, defs_by_id, alias_index, "id", "source", ["bad"])

    assert field_defs == []
    assert defs_by_id == {}


def test_collect_fields_skip_missing_sections() -> None:
    raw = RawDemand.from_raw({})
    field_defs = []
    defs_by_id = {}
    alias_index = AliasIndex()

    _collect_main_source_fields(raw, "main", field_defs, defs_by_id, alias_index)
    _collect_source_fields(raw, field_defs, defs_by_id, alias_index)

    assert field_defs == []


def test_collect_source_fields_skips_non_dict_entries() -> None:
    raw = RawDemand.from_raw({"sources": {"s1": []}})
    field_defs = []
    defs_by_id = {}
    alias_index = AliasIndex()

    _collect_source_fields(raw, field_defs, defs_by_id, alias_index)

    assert field_defs == []


def test_collect_derived_fields_skips_non_dict_entries() -> None:
    raw = RawDemand.from_raw({"fields": {"bad": []}})
    field_defs = []
    defs_by_id = {}
    alias_index = AliasIndex()

    _collect_derived_fields(raw, field_defs, defs_by_id, alias_index)

    assert field_defs == []


def test_build_source_field_id_map_skips_empty_source_id() -> None:
    loader = YamlDemandLoader()
    field_def = FieldDef(field_id="id", kind=FIELD_KIND_SOURCE, data={}, source_id=None)

    assert loader._build_source_field_id_map([field_def]) == {}


def test_parse_main_source_missing_returns_default() -> None:
    loader = YamlDemandLoader()
    main_source = loader._parse_main_source(RawDemand.from_raw({}))

    assert main_source.source_id == ""
    assert main_source.loader == ""


def test_load_string_rejects_batch_size_runtime_policy_key() -> None:
    loader = YamlDemandLoader()
    with pytest.raises(ScalimYamlValidationError) as excinfo:
        _ = loader.load_string(
            """
name: demo
batch_size: null
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
sources: {}
""".lstrip()
        )

    assert any(env.path == "batch_size" for env in excinfo.value.errors)


def test_load_string_uses_default_batch_size_when_missing() -> None:
    loader = YamlDemandLoader()
    config = loader.load_string(
        """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
sources: {}
""".lstrip()
    )

    assert config.batch_size == DEFAULT_BATCH_SIZE


def test_parse_order_by_rejects_non_list() -> None:
    loader = YamlDemandLoader()

    with pytest.raises(TypeError, match="main_source.order_by must be a list"):
        loader._parse_order_by({MAIN_SOURCE_KEYS["order_by"]: "bad"})


def test_parse_order_by_rejects_non_string_items() -> None:
    loader = YamlDemandLoader()

    with pytest.raises(TypeError, match="main_source.order_by items must be strings"):
        loader._parse_order_by({MAIN_SOURCE_KEYS["order_by"]: [1]})


def test_parse_order_by_rejects_empty_items() -> None:
    loader = YamlDemandLoader()

    with pytest.raises(ValueError, match="main_source.order_by items must be non-empty strings"):
        loader._parse_order_by({MAIN_SOURCE_KEYS["order_by"]: [" "]})


def test_collect_order_by_field_defs_skips_missing_and_invalid_entries() -> None:
    loader = YamlDemandLoader()

    raw_missing = RawDemand.from_raw({})
    assert loader._collect_order_by_field_defs(raw_missing, "orders", {}) == []

    raw_invalid = RawDemand.from_raw({"main_source": {"order_by": [1, "", "-"]}})
    assert loader._collect_order_by_field_defs(raw_invalid, "orders", {}) == []


def test_parse_sources_handles_missing_and_invalid_entries() -> None:
    loader = YamlDemandLoader()

    assert loader._parse_sources(RawDemand.from_raw({})) == {}

    parsed = loader._parse_sources(RawDemand.from_raw({"sources": {"bad": []}}))
    assert parsed == {}


def test_collect_required_field_defs_unknown_dependency() -> None:
    loader = YamlDemandLoader()
    derived = FieldDef(
        field_id="calc",
        kind=FIELD_KIND_DERIVED,
        data={
            DERIVED_FIELD_KEYS["compute"]: "missing",
        },
    )

    with pytest.raises(ValueError, match="unknown field"):
        loader._collect_required_field_defs([derived], {})


def test_collect_required_field_defs_ambiguous_dependency() -> None:
    loader = YamlDemandLoader()
    derived = FieldDef(
        field_id="calc",
        kind=FIELD_KIND_DERIVED,
        data={
            DERIVED_FIELD_KEYS["compute"]: "dup",
        },
    )
    dup_a = FieldDef(field_id="dup", kind=FIELD_KIND_SOURCE, data={}, source_id="a")
    dup_b = FieldDef(field_id="dup", kind=FIELD_KIND_SOURCE, data={}, source_id="b")

    with pytest.raises(ValueError, match="ambiguous field"):
        loader._collect_required_field_defs([derived], {"dup": [dup_a, dup_b]})


def test_infer_derived_dependencies_empty_compute_returns_empty_list() -> None:
    loader = YamlDemandLoader()
    assert loader._infer_derived_dependencies("calc", {DERIVED_FIELD_KEYS["compute"]: ""}) == []


def test_infer_derived_dependencies_rejects_depends_on() -> None:
    loader = YamlDemandLoader()
    with pytest.raises(ValueError, match="does not allow 'depends_on'"):
        loader._infer_derived_dependencies("calc", {"depends_on": ["a"], DERIVED_FIELD_KEYS["compute"]: "a"})


def test_constant_compute_expression_syntax_error_returns_false() -> None:
    from scalim.dsl.yaml_dsl._internal.config_parsing.security import is_constant_compute_expression

    assert is_constant_compute_expression("1 +") is False


def test_parse_relation_ref_resolves_string_id() -> None:
    loader = YamlDemandLoader()

    raw = RawDemand.from_raw(
        {
            "relations": {
                "rel1": {
                    "steps": [
                        {
                            "from": "orders.order_id",
                            "to": "customers.customer_id",
                        }
                    ]
                }
            }
        }
    )
    relations = loader._parse_relations(raw)
    inline = loader._parse_relation_ref("rel1", relations=relations)
    assert inline is not None
    assert inline.steps == relations["rel1"].steps


def test_parse_relation_ref_empty_string_returns_none() -> None:
    loader = YamlDemandLoader()

    assert loader._parse_relation_ref("   ", relations={}) is None


def test_parse_relation_ref_unknown_id_is_rejected() -> None:
    loader = YamlDemandLoader()

    with pytest.raises(ValueError, match="Unknown relation id"):
        loader._parse_relation_ref("missing", relations={})


def test_parse_relations_skips_non_dict_entries() -> None:
    loader = YamlDemandLoader()
    raw = RawDemand.from_raw({"relations": {"r1": []}})

    assert loader._parse_relations(raw) == {}


def test_parse_steps_handles_invalid_inputs() -> None:
    loader = YamlDemandLoader()

    assert loader._parse_steps("bad") == ()
    assert loader._parse_steps(["bad"]) == ()


def test_load_string_rejects_lookup_chunk_size_with_lookup_chunking_hint() -> None:
    loader = YamlDemandLoader()
    with pytest.raises(ScalimYamlValidationError) as excinfo:
        _ = loader.load_string(
            """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
sources:
  customers:
    loader: tests.fixtures.mock_loaders.mock_loader
    key: customer_id
    lookup_chunk_size: 10
""".lstrip()
        )

    msg = "\n".join(env.message for env in excinfo.value.errors)
    assert "lookup_chunk_size" in msg
    assert "LookupChunking" in msg
    assert any(env.path == "sources.customers.lookup_chunk_size" for env in excinfo.value.errors)
