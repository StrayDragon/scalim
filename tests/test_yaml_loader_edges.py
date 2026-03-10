import io

import pytest

from scalim.dsl.by_yaml.config_parsing.errors import ConfigValidationError
from scalim.dsl.by_yaml.config_parsing.loader import YamlDemandLoader


def _assert_load_string_errors(yaml_content: str, *expected_messages: str) -> None:
    loader = YamlDemandLoader()

    with pytest.raises(ConfigValidationError) as exc:
        loader.load_string(yaml_content)

    for message in expected_messages:
        assert any(message in msg for msg in exc.value.errors)


def test_loader_reads_from_stream_and_skips_invalid_sections() -> None:
    loader = YamlDemandLoader()

    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
sources: []
fields: []
relations: []
"""
    with pytest.raises(ConfigValidationError) as exc:
        loader.load(io.StringIO(yaml_content))

    assert any("'relations' must be a dictionary" in msg for msg in exc.value.errors)
    assert any("'fields' must be a dictionary" in msg for msg in exc.value.errors)


def test_loader_rejects_non_mapping_root() -> None:
    loader = YamlDemandLoader()

    with pytest.raises(TypeError, match="mapping"):
        loader.load_string("- item")


def test_loader_skips_invalid_source_and_field_entries() -> None:
    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id:
      extract: order_id
sources:
  good:
    loader: tests.conftest.mock_loader
    key: id
    bind:
      use_keys:
        param: ids
  bad: []
fields:
  bad_field: 1
"""
    _assert_load_string_errors(
        yaml_content,
        "Source 'bad' must be a dictionary",
        "Field 'bad_field' must be a dictionary",
    )


def test_loader_parses_relation_steps() -> None:
    loader = YamlDemandLoader()

    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    region_id:
      extract: region_id
    institution_id:
      extract: institution_id
sources:
  mapping:
    loader: tests.conftest.mock_loader
    key: map_id
    bind: {use_keys: {param: ids}}
    fields:
      region_id:
        extract: region_id
      institution_id:
        extract: institution_id
      customer_id:
        extract: customer_id
  customers:
    loader: tests.conftest.mock_loader
    key: customer_id
    bind: {use_keys: {param: ids}}
relations:
  r1:
    steps:
      - from: [orders.region_id, orders.institution_id]
        to: [mapping.region_id, mapping.institution_id]
      - from: mapping.customer_id
        to: customers.customer_id
output:
  fields:
    - field_id: region_id
      source: orders
"""
    config = loader.load_string(yaml_content)

    relation = config.relations["r1"]
    assert len(relation.steps) == 2
    first_step = relation.steps[0]
    assert first_step.from_ == ("orders.region_id", "orders.institution_id")
    assert first_step.to == ("mapping.region_id", "mapping.institution_id")


def test_loader_parses_observability_with_defaults() -> None:
    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
sources: {}
observability:
  performance:
    enabled: true
    metrics: duration
    sampling_interval: bad
    report: invalid
    thresholds: invalid
"""
    _assert_load_string_errors(yaml_content, "Schema validation error")


def test_loader_parses_relations_observability_config() -> None:
    loader = YamlDemandLoader()

    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
sources: {}
observability:
  relations:
    enabled: true
    sampling_rate: 0.05
    log_type_mismatch: false
    max_samples: 50
    report:
      format: json
      output: ./relations.json
"""
    config = loader.load_string(yaml_content)

    relations = config.observability.relations if config.observability else None
    assert relations is not None
    assert relations.enabled is True
    assert relations.sampling_rate == 0.05
    assert relations.log_type_mismatch is False
    assert relations.max_samples == 50
    assert relations.report is not None
    assert relations.report.format == "json"
    assert relations.report.output == "./relations.json"


def test_loader_parses_relations_observability_invalid_values() -> None:
    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
sources: {}
observability:
  relations:
    enabled: true
    sampling_rate: bad
    max_samples: bad
    report: invalid
"""
    _assert_load_string_errors(yaml_content, "Schema validation error")


def test_loader_parses_performance_thresholds() -> None:
    loader = YamlDemandLoader()

    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
sources: {}
observability:
  performance:
    enabled: true
    thresholds:
      batch_duration_warn: 0.5
      memory_increase_warn: 1.0
"""
    config = loader.load_string(yaml_content)

    perf = config.observability.performance if config.observability else None
    assert perf is not None
    assert perf.thresholds is not None
    assert perf.thresholds.batch_duration_warn == 0.5
    assert perf.thresholds.memory_increase_warn == 1.0


def test_loader_parses_metrics_list_and_report() -> None:
    loader = YamlDemandLoader()

    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
sources: {}
observability:
  performance:
    enabled: true
    metrics:
      - duration
      - memory
    report:
      format: json
      output: ./perf.json
      include_details: true
"""
    config = loader.load_string(yaml_content)

    perf = config.observability.performance if config.observability else None
    assert perf is not None
    assert perf.metrics == ("duration", "memory")
    assert perf.report is not None
    assert perf.report.format == "json"
    assert perf.report.output == "./perf.json"
    assert perf.report.include_details is True


def test_loader_skips_invalid_relation_entries() -> None:
    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
sources: {}
relations:
  bad: 1
  good:
    steps:
      - from: orders.customer_id
        to: customers.customer_id
"""
    _assert_load_string_errors(yaml_content, "Relation 'bad' must be a dictionary")
