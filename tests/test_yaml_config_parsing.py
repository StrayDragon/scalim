import pytest

from scalim.dsl.by_yaml.config_parsing.models import (
    AliasIndex,
    FieldDef,
    RawDemand,
    _add_field_def,
    _collect_derived_fields,
    _collect_main_source_fields,
    _collect_source_fields,
)
from scalim.dsl.by_yaml.config_parsing.loader import YamlDemandLoader
from scalim.dsl.by_yaml.schema_dsl.constants import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_PERF_SAMPLING_INTERVAL,
    DEFAULT_RELATION_MAX_SAMPLES,
    DEFAULT_RELATION_SAMPLING_RATE,
    FIELD_KIND_DERIVED,
    FIELD_KIND_SOURCE,
)
from scalim.dsl.by_yaml.schema_dsl.models import (
    DERIVED_FIELD_KEYS,
    LOGGING_KEYS,
    LoggingConfig,
    MAIN_SOURCE_KEYS,
    MEMORY_OPTIMIZATION_KEYS,
    PERFORMANCE_KEYS,
    RELATIONS_CONFIG_KEYS,
    ROW_GAP_KEYS,
    TRACE_KEYS,
    RowGapConfig,
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


def test_load_string_preserves_explicit_null_batch_size() -> None:
    loader = YamlDemandLoader()
    config = loader.load_string(
        """
name: demo
batch_size: null
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
sources: {}
""".lstrip()
    )

    assert config.batch_size is None


def test_load_string_uses_default_batch_size_when_missing() -> None:
    loader = YamlDemandLoader()
    config = loader.load_string(
        """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
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
    from scalim.dsl.by_yaml.config_parsing.security import is_constant_compute_expression

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


def test_parse_relations_observability_defaults_on_invalid_values() -> None:
    loader = YamlDemandLoader()
    relations = loader._parse_relations_observability(
        {
            RELATIONS_CONFIG_KEYS["sampling_rate"]: "bad",
            RELATIONS_CONFIG_KEYS["max_samples"]: "bad",
        }
    )

    assert relations.sampling_rate == DEFAULT_RELATION_SAMPLING_RATE
    assert relations.max_samples == DEFAULT_RELATION_MAX_SAMPLES


def test_parse_performance_handles_string_metrics_and_sampling_default() -> None:
    loader = YamlDemandLoader()
    performance = loader._parse_performance(
        {
            PERFORMANCE_KEYS["metrics"]: "duration",
            PERFORMANCE_KEYS["sampling_interval"]: "bad",
        }
    )

    assert performance.metrics == ("duration",)
    assert performance.sampling_interval == DEFAULT_PERF_SAMPLING_INTERVAL


def test_parse_lookup_chunk_size_guardrails() -> None:
    loader = YamlDemandLoader()

    assert loader._parse_lookup_chunk_size(None) is None
    assert loader._parse_lookup_chunk_size(True) is None
    assert loader._parse_lookup_chunk_size(False) is None
    assert loader._parse_lookup_chunk_size([]) is None
    assert loader._parse_lookup_chunk_size({}) is None
    assert loader._parse_lookup_chunk_size("bad") is None
    assert loader._parse_lookup_chunk_size("3") == 3
    assert loader._parse_lookup_chunk_size(2.8) == 2
    assert loader._parse_lookup_chunk_size(4) == 4


def test_parse_logging_trace_row_gap_and_memory_opt_observability() -> None:
    loader = YamlDemandLoader()

    logging_cfg = loader._parse_logging_observability({LOGGING_KEYS["enabled"]: False})
    assert logging_cfg.enabled is False
    assert logging_cfg.renderer == LoggingConfig().renderer

    logging_cfg = loader._parse_logging_observability({LOGGING_KEYS["renderer"]: "logger"})
    assert logging_cfg.renderer == "logger"

    logging_cfg = loader._parse_logging_observability({LOGGING_KEYS["renderer"]: "not-a-renderer"})
    assert logging_cfg.renderer == LoggingConfig().renderer

    trace_cfg = loader._parse_trace_observability({TRACE_KEYS["enabled"]: True})
    assert trace_cfg.enabled is True

    row_gap_cfg = loader._parse_row_gap_observability(
        {
            ROW_GAP_KEYS["enabled"]: True,
            ROW_GAP_KEYS["primary_loader_name"]: "primary",
            ROW_GAP_KEYS["data_loader_names"]: ["a", "b"],
            ROW_GAP_KEYS["sample_limit"]: 3,
        }
    )
    assert row_gap_cfg.enabled is True
    assert row_gap_cfg.primary_loader_name == "primary"
    assert row_gap_cfg.data_loader_names == ("a", "b")
    assert row_gap_cfg.sample_limit == 3

    row_gap_cfg = loader._parse_row_gap_observability(
        {
            ROW_GAP_KEYS["data_loader_names"]: "solo",
            ROW_GAP_KEYS["sample_limit"]: "bad",
        }
    )
    assert row_gap_cfg.data_loader_names == ("solo",)
    assert row_gap_cfg.sample_limit == 5

    row_gap_cfg = loader._parse_row_gap_observability(
        {
            ROW_GAP_KEYS["data_loader_names"]: 123,
        }
    )
    assert row_gap_cfg.data_loader_names == RowGapConfig().data_loader_names

    memory_cfg = loader._parse_memory_opt_observability(
        {
            MEMORY_OPTIMIZATION_KEYS["enabled"]: True,
            MEMORY_OPTIMIZATION_KEYS["auto_report"]: True,
            MEMORY_OPTIMIZATION_KEYS["max_fields"]: "bad",
        }
    )
    assert memory_cfg.enabled is True
    assert memory_cfg.auto_report is True
    assert memory_cfg.max_fields == 0
