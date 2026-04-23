import pytest

from scalim.dsl.yaml_dsl.runtime.conversion import ConfigToIRConverter
from scalim.dsl.yaml_dsl._internal.config_parsing.loader import YamlDemandLoader
from scalim.dsl.yaml_dsl.runtime.errors import ScalimConversionError
from scalim.spec.ir import DerivedFieldIr, FieldIr, LookupCastSpecIr


def _load_config(yaml_content: str):
    loader = YamlDemandLoader()
    return loader.load_string(yaml_content)


def test_converter_filters_output_fields_and_infers_relation() -> None:
    yaml_content = """
name: test
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id: &order_id
      extract: order_id
    customer_id:
      extract: customer_id
    amount:
      extract: amount
sources:
  customers:
    loader: tests.fixtures.mock_loaders.mock_loader
    key: customer_id
    params:
      ids: {$keys: {as: set}}
    fields:
      customer_name: &customer_name
        extract: customer_name
relations:
  r1:
    steps:
      - from: orders.customer_id
        to: customers.customer_id
resources:
  files:
    detail_csv: {csv_file: {path: ./out}}
outputs:
  - name: detail
    to: {file: detail_csv}
    fields: [order_id, customer_name]
"""
    config = _load_config(yaml_content)
    converter = ConfigToIRConverter()
    demand_ir = converter.convert(config)

    field_ids = set(demand_ir.fields.keys())
    assert field_ids == {"order_id", "customer_name"}

    customer_field = demand_ir.fields["customer_name"]
    assert isinstance(customer_field, FieldIr)
    assert customer_field.lookup_steps is not None
    assert customer_field.lookup_steps[0].from_field == "customer_id"


def test_loader_rejects_unknown_output_field() -> None:
    yaml_content = """
name: test
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
resources:
  files:
    detail_csv: {csv_file: {path: ./out}}
outputs:
  - name: detail
    to: {file: detail_csv}
    fields: [missing_field]
"""
    with pytest.raises(ValueError, match=r"outputs\.detail\.fields reference unknown fields: missing_field"):
        _ = _load_config(yaml_content)


def test_converter_multi_field_lookup_cast() -> None:
    yaml_content = """
name: test
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
sources:
  mapping:
    loader: tests.fixtures.mock_loaders.mock_loader
    key: [region_id, institution_id]
    lookup_cast: {int: {}}
"""
    config = _load_config(yaml_content)
    converter = ConfigToIRConverter()
    demand_ir = converter.convert(config)

    mapping_source = demand_ir.sources["mapping"]
    assert mapping_source.key.cast == LookupCastSpecIr(name="int", sep=None)


def test_converter_keeps_order_by_fields_outside_output() -> None:
    yaml_content = """
name: test
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  order_by:
    - order_id
  fields:
    order_id: &order_id
      extract: order_id
    customer_id:
      extract: customer_id
sources:
  customers:
    loader: tests.fixtures.mock_loaders.mock_loader
    key: customer_id
    params:
      ids: {$keys: {as: set}}
    fields:
      customer_name: &customer_name
        extract: customer_name
relations:
  r1:
    steps:
      - from: orders.customer_id
        to: customers.customer_id
resources:
  files:
    detail_csv: {csv_file: {path: ./out}}
outputs:
  - name: detail
    to: {file: detail_csv}
    fields: [customer_name]
"""
    config = _load_config(yaml_content)
    converter = ConfigToIRConverter()
    demand_ir = converter.convert(config)

    assert "order_id" in demand_ir.fields
    assert "customer_name" in demand_ir.fields


def test_converter_marks_constant_compute_when_compute_has_no_deps() -> None:
    yaml_content = """
name: test
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
fields:
  const:
    name: Const
    compute: "1 + 2"
"""
    config = _load_config(yaml_content)
    converter = ConfigToIRConverter()
    demand_ir = converter.convert(config)

    const_field = demand_ir.fields["const"]
    assert isinstance(const_field, DerivedFieldIr)
    assert const_field.is_constant_compute is True


def test_converter_rejects_invalid_order_by_entry() -> None:
    converter = ConfigToIRConverter()

    with pytest.raises(ScalimConversionError, match="order_by contains invalid field"):
        converter._convert_main_source_order_by(("-",))


def test_source_id_format_validation_valid() -> None:
    from scalim.dsl.yaml_dsl.runtime.conversion import _validate_source_id

    _validate_source_id("orders", "test")
    _validate_source_id("orders_2024", "test")
    _validate_source_id("_orders", "test")
    _validate_source_id("O123", "test")


def test_source_id_format_validation_invalid() -> None:
    from scalim.dsl.yaml_dsl.runtime.conversion import _validate_source_id

    for source_id in ("123-invalid", "order-id", ""):
        with pytest.raises(ScalimConversionError, match="source_id.*must match pattern"):
            _validate_source_id(source_id, "test")
