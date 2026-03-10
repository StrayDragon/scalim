import yaml

import pytest

from scalim.dsl.by_yaml.config_parsing.errors import ConfigValidationError
from scalim.dsl.by_yaml.config_parsing.loader import YamlDemandLoader
from scalim.dsl.by_yaml.config_parsing.validator import ConfigValidator


def test_loader_parses_output_fields_and_dependencies() -> None:
    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id: &order_id
      extract: order_id
      name: Order ID
    quantity: &quantity
      extract: quantity
    unit_price: &unit_price
      extract: unit_price
    extra: &extra
      extract: extra
sources: {}
fields:
  total: &total
    name: Total
    compute: "quantity * unit_price"
output:
  fields:
    - *order_id
    - field_id: total
      name: Total Override
"""
    loader = YamlDemandLoader()
    config = loader.load_string(yaml_content)

    assert config.output is not None
    assert config.output.fields == ["order_id", "total"]
    assert "order_id" in config.source_fields
    assert "quantity" in config.source_fields
    assert "unit_price" in config.source_fields
    assert "extra" not in config.source_fields
    assert config.derived_fields["total"].name == "Total Override"


def test_validator_allows_missing_top_level_fields() -> None:
    validator = ConfigValidator()
    config = {
        "name": "demo",
        "main_source": {"source_id": "orders", "loader": "tests.conftest.mock_loader"},
        "sources": {},
    }

    validator.validate(config)


def test_validator_rejects_top_level_source_fields() -> None:
    validator = ConfigValidator()
    config = {
        "name": "demo",
        "main_source": {"source_id": "orders", "loader": "tests.conftest.mock_loader"},
        "sources": {},
        "fields": {"order_id": {"extract": "order_id"}},
    }

    with pytest.raises(ConfigValidationError) as exc:
        validator.validate(config)

    assert any("Derived field 'order_id' must declare compute/call_by" in msg for msg in exc.value.errors)


def test_validator_output_fields_accepts_alias_and_explicit() -> None:
    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id: &order_id
      extract: order_id
      name: Order ID
    order_date: &order_date
      extract: order_date
      name: Order Date
sources: {}
fields:
  total: &total
    name: Total
    compute: "order_id + 1"
output:
  fields:
    - *order_id
    - *order_date
    - field_id: total
      name: Total Override
"""
    config = yaml.safe_load(yaml_content)
    validator = ConfigValidator()
    validator.validate(config)


def test_validator_output_fields_ambiguous_across_sources() -> None:
    validator = ConfigValidator()
    config = {
        "name": "demo",
        "main_source": {"source_id": "orders", "loader": "tests.conftest.mock_loader"},
        "sources": {
            "s1": {
                "loader": "tests.conftest.mock_loader",
                "key": "id",
                "bind": {"param": "ids"},
                "fields": {"name": {"extract": "name", "relation": {"steps": [{"from": "orders.id", "to": "s1.id"}]}}},
            },
            "s2": {
                "loader": "tests.conftest.mock_loader",
                "key": "id",
                "bind": {"param": "ids"},
                "fields": {"name": {"extract": "name", "relation": {"steps": [{"from": "orders.id", "to": "s2.id"}]}}},
            },
        },
        "output": {"fields": [{"field_id": "name"}]},
    }

    with pytest.raises(ConfigValidationError) as exc:
        validator.validate(config)

    assert any("Output field 'name' is ambiguous; add source to explicit field_id object" in msg for msg in exc.value.errors)


def test_validator_v3_allows_duplicate_field_values_in_source() -> None:
    validator = ConfigValidator()
    config = {
        "name": "demo",
        "main_source": {
            "source_id": "orders",
            "loader": "tests.conftest.mock_loader",
            "fields": {
                "id_a": {"extract": "id"},
                "id_b": {"extract": "id"},
            },
        },
        "sources": {},
        "output": {"fields": [{"field_id": "id_a"}]},
    }

    validator.validate(config)
