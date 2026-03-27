import pytest

from scalim.dsl.by_yaml.config_parsing.errors import ScalimConfigValidationError
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


def test_loader_allows_outputs_fields_yaml_alias_items() -> None:
    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id: &order_id
      extract: order_id
    user_id:
      extract: user_id
    quantity: &quantity
      extract: quantity
    unit_price: &unit_price
      extract: unit_price
sources:
  users:
    loader: tests.conftest.mock_loader
    key: user_id
    fields:
      user_name: &user_name
        extract: name
        relation:
          steps:
            - from: orders.user_id
              to: users.user_id
fields:
  total: &total
    compute: "quantity * unit_price"
outputs:
  - name: detail
    container: {type: csv, path: ./out.csv}
    fields:
      - *order_id
      - *user_name
      - *total
"""
    loader = YamlDemandLoader()
    config = loader.load_string(yaml_content)

    assert len(config.outputs) == 1
    assert config.outputs[0].fields == ("order_id", "user_name", "total")


def test_loader_allows_outputs_fields_in_aggregate_output_and_resolves_alias() -> None:
    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    customer_id: &customer_id
      extract: customer_id
    amount:
      extract: amount
    channel:
      extract: channel
sources: {}
outputs:
  - name: summary
    container: {type: csv, path: ./out.csv}
    where: "channel == 'direct'"
    aggregate:
      group_by:
        - *customer_id
      fields:
        sum_amount: &sum_amount {sum: {field: amount}}
        rank: &rank {dense_rank: {by: *sum_amount}}
    fields:
      - *rank
      - *customer_id
      - *sum_amount
"""
    loader = YamlDemandLoader()
    config = loader.load_string(yaml_content)

    assert len(config.outputs) == 1
    assert config.outputs[0].aggregate is not None
    assert config.outputs[0].fields == ("rank", "customer_id", "sum_amount")


def test_loader_allows_outputs_fields_in_aggregate_output_content_match_when_identity_lost() -> None:
    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    customer_id:
      extract: customer_id
    amount:
      extract: amount
sources: {}
outputs:
  - name: summary
    container: {type: csv, path: ./out.csv}
    aggregate:
      group_by: [customer_id]
      fields:
        sum_amount: {sum: {field: amount}}
        rank: {dense_rank: {by: sum_amount}}
    fields:
      - {dense_rank: {by: sum_amount}}
      - {sum: {field: amount}}
"""
    loader = YamlDemandLoader()
    config = loader.load_string(yaml_content)

    assert len(config.outputs) == 1
    assert config.outputs[0].aggregate is not None
    assert config.outputs[0].fields == ("rank", "sum_amount")


def test_validator_rejects_outputs_fields_unknown_aggregate_out_field_id() -> None:
    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    customer_id:
      extract: customer_id
    amount:
      extract: amount
sources: {}
outputs:
  - name: summary
    container: {type: csv, path: ./out.csv}
    aggregate:
      group_by: [customer_id]
      fields:
        sum_amount: {sum: {field: amount}}
    fields: [customer_id, unknown]
    """
    loader = YamlDemandLoader()
    with pytest.raises(ValueError) as exc:
        loader.load_string(yaml_content)

    msg = str(exc.value)
    assert "outputs.summary.fields" in msg
    assert "reference unknown aggregate output fields" in msg


def test_loader_allows_outputs_fields_content_match_when_identity_lost() -> None:
    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    quantity: &quantity
      extract: quantity
sources: {}
outputs:
  - name: detail
    container: {type: csv, path: ./out.csv}
    fields:
      - {extract: quantity}
"""
    loader = YamlDemandLoader()
    config = loader.load_string(yaml_content)

    assert len(config.outputs) == 1
    assert config.outputs[0].fields == ("quantity",)


def test_validator_rejects_outputs_fields_object_when_ambiguous() -> None:
    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    a:
      extract: id
    b:
      extract: id
sources: {}
outputs:
  - name: detail
    container: {type: csv, path: ./out.csv}
    fields:
      - {extract: id}
"""
    loader = YamlDemandLoader()
    with pytest.raises(ScalimConfigValidationError) as exc:
        loader.load_string(yaml_content)

    assert any("outputs.0.fields.0" in msg for msg in exc.value.errors)
    assert any("ambiguous object entry" in msg for msg in exc.value.errors)
    assert any("a" in msg and "b" in msg for msg in exc.value.errors)


def test_validator_rejects_outputs_fields_object_when_not_found() -> None:
    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    quantity:
      extract: quantity
sources: {}
outputs:
  - name: detail
    container: {type: csv, path: ./out.csv}
    fields:
      - {extract: missing}
"""
    loader = YamlDemandLoader()
    with pytest.raises(ScalimConfigValidationError) as exc:
        loader.load_string(yaml_content)

    assert any("outputs.0.fields.0" in msg for msg in exc.value.errors)
    assert any("cannot resolve object to a unique field_id" in msg for msg in exc.value.errors)


def test_validator_rejects_outputs_fields_non_str_and_non_object_item() -> None:
    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
outputs:
  - name: detail
    container: {type: csv, path: ./out.csv}
    fields:
      - 1
"""
    loader = YamlDemandLoader()
    with pytest.raises(ScalimConfigValidationError) as exc:
        loader.load_string(yaml_content)

    assert any("outputs.0.fields.0" in msg for msg in exc.value.errors)
    assert any("must be field_id string" in msg for msg in exc.value.errors)


def test_validator_outputs_object_ref_check_skips_non_object_outputs_items() -> None:
    validator = ConfigValidator()
    config = {
        "name": "demo",
        "main_source": {"source_id": "orders", "loader": "tests.conftest.mock_loader"},
        "sources": {},
        "outputs": [1],
    }

    with pytest.raises(ScalimConfigValidationError):
        validator.validate(config)


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

    with pytest.raises(ScalimConfigValidationError) as exc:
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

    with pytest.raises(ScalimConfigValidationError) as exc:
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
