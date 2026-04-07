import io

import pytest

from scalim.dsl.yaml_dsl._internal.config_parsing.error_envelope import ScalimYamlValidationError
from scalim.dsl.yaml_dsl._internal.config_parsing.loader import YamlDemandLoader


def _assert_load_string_errors(yaml_content: str, *expected_messages: str) -> None:
    loader = YamlDemandLoader()

    with pytest.raises(ScalimYamlValidationError) as exc:
        loader.load_string(yaml_content)

    for message in expected_messages:
        assert any(message in env.message for env in exc.value.errors)


def test_loader_reads_from_stream_and_skips_invalid_sections() -> None:
    loader = YamlDemandLoader()

    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
sources: []
fields: []
relations: []
"""
    with pytest.raises(ScalimYamlValidationError) as exc:
        loader.load(io.StringIO(yaml_content))

    assert any("'relations' must be a dictionary" in env.message for env in exc.value.errors)
    assert any("'fields' must be a dictionary" in env.message for env in exc.value.errors)


def test_loader_rejects_non_mapping_root() -> None:
    loader = YamlDemandLoader()

    with pytest.raises(ScalimYamlValidationError) as exc:
        loader.load_string("- item")
    assert any("mapping" in env.message for env in exc.value.errors)


def test_loader_skips_invalid_source_and_field_entries() -> None:
    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
sources:
  good:
    loader: tests.fixtures.mock_loaders.mock_loader
    key: id
    params:
      ids: {$keys: {as: set}}
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
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    region_id:
      extract: region_id
    institution_id:
      extract: institution_id
sources:
  mapping:
    loader: tests.fixtures.mock_loaders.mock_loader
    key: map_id
    params:
      ids: {$keys: {as: set}}
    fields:
      mapping_region_id:
        extract: region_id
      mapping_institution_id:
        extract: institution_id
      mapping_customer_id:
        extract: customer_id
  customers:
    loader: tests.fixtures.mock_loaders.mock_loader
    key: customer_id
    params:
      ids: {$keys: {as: set}}
relations:
  r1:
    steps:
      - from: [orders.region_id, orders.institution_id]
        to: [mapping.mapping_region_id, mapping.mapping_institution_id]
      - from: mapping.mapping_customer_id
        to: customers.customer_id
"""
    config = loader.load_string(yaml_content)

    relation = config.relations["r1"]
    assert len(relation.steps) == 2
    first_step = relation.steps[0]
    assert first_step.from_ == ("orders.region_id", "orders.institution_id")
    assert first_step.to == ("mapping.mapping_region_id", "mapping.mapping_institution_id")


def test_loader_ignores_legacy_observability_and_emits_migration_warning(caplog: object) -> None:
    import logging

    loader = YamlDemandLoader()

    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
sources: {}
observability:
  performance:
    enabled: true
    sampling_interval: bad
  relations:
    enabled: true
    sampling_rate: bad
  viz:
    enabled: true
    output_dir: ./tmp
"""

    caplog.set_level(logging.WARNING)
    config = loader.load_string(yaml_content)
    assert config.name == "demo"
    assert any("Legacy YAML key 'observability' is no longer supported" in str(r.message) for r in caplog.records)


def test_loader_skips_invalid_relation_entries() -> None:
    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
sources: {}
relations:
  bad: 1
  good:
    steps:
      - from: orders.customer_id
        to: customers.customer_id
"""
    _assert_load_string_errors(yaml_content, "Relation 'bad' must be a dictionary")
