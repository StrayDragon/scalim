import pytest

from scalim.dsl.by_yaml.config_parsing.errors import ConfigValidationError
from scalim.dsl.by_yaml.config_parsing.loader import YamlDemandLoader
from scalim.dsl.by_yaml.config_parsing.validator import ConfigValidator


def test_loader_parses_outputs_fields_and_injects_dependencies() -> None:
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
    channel: &channel
      extract: channel
sources: {}
fields:
  total: &total
    name: Total
    compute: "quantity * unit_price"
outputs:
  - name: detail
    container: {type: csv, path: ./out.csv}
    fields: [order_id, total]
  - name: direct_detail
    from: detail
    where: "extra == 1"
"""
    loader = YamlDemandLoader()
    config = loader.load_string(yaml_content)

    assert len(config.outputs) == 2
    assert config.outputs[0].name == "detail"
    assert config.outputs[0].fields == ("order_id", "total")
    assert config.outputs[1].name == "direct_detail"
    assert config.outputs[1].fields == ("order_id", "total")
    assert config.outputs[1].requires == ("extra",)

    assert "order_id" in config.source_fields
    assert "quantity" in config.source_fields
    assert "unit_price" in config.source_fields
    assert "extra" in config.source_fields  # injected by outputs.*.where requires
    assert "channel" not in config.source_fields
    assert config.derived_fields["total"].name == "Total"


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


def test_validator_rejects_duplicate_field_ids_across_sources() -> None:
    validator = ConfigValidator()
    config = {
        "name": "demo",
        "main_source": {
            "source_id": "orders",
            "loader": "tests.conftest.mock_loader",
            "fields": {"id": {"extract": "id"}},
        },
        "sources": {
            "s1": {
                "loader": "tests.conftest.mock_loader",
                "key": "id",
                "params": {"ids": {"$keys": {"as": "set"}}},
                "fields": {"name": {"extract": "name", "relation": {"steps": [{"from": "orders.id", "to": "s1.id"}]}}},
            },
            "s2": {
                "loader": "tests.conftest.mock_loader",
                "key": "id",
                "params": {"ids": {"$keys": {"as": "set"}}},
                "fields": {"name": {"extract": "name", "relation": {"steps": [{"from": "orders.id", "to": "s2.id"}]}}},
            },
        },
    }

    with pytest.raises(ConfigValidationError) as exc:
        validator.validate(config)

    assert any("Field 'name' is defined multiple times" in msg for msg in exc.value.errors)


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
    }

    validator.validate(config)
