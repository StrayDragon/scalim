import pytest

from scalim.dsl.by_yaml.runtime.conversion import ConfigToIRConverter
from scalim.dsl.by_yaml.config_parsing.loader import YamlDemandLoader
from scalim.dsl.by_yaml.runtime.references import PythonReferenceResolver
from scalim.dsl.by_yaml.config_parsing.errors import ConfigValidationError
from scalim.dsl.by_yaml.runtime.errors import ConversionError
from scalim.dsl.by_yaml.schema_dsl.models import DemandConfig, MainSourceConfig, OutputConfig
from scalim.spec.ir.fields import DerivedFieldIr, FieldIr


def _load_config(yaml_content: str):
    loader = YamlDemandLoader()
    return loader.load_string(yaml_content)


def test_converter_filters_output_fields_and_infers_relation() -> None:
    yaml_content = """
name: test
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id: &order_id
      extract: order_id
    customer_id:
      extract: customer_id
    amount:
      extract: amount
sources:
  customers:
    loader: tests.conftest.mock_loader
    key: customer_id
    bind: {use_keys: {param: ids}}
    fields:
      customer_name: &customer_name
        extract: customer_name
relations:
  r1:
    steps:
      - from: orders.customer_id
        to: customers.customer_id
output:
  fields:
    - *order_id
    - *customer_name
"""
    config = _load_config(yaml_content)
    converter = ConfigToIRConverter(resolver=PythonReferenceResolver(allowed_modules=frozenset(["tests"])))
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
  loader: tests.conftest.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
output:
  fields:
    - field_id: missing_field
"""
    loader = YamlDemandLoader()

    with pytest.raises(ConfigValidationError) as exc:
        loader.load_string(yaml_content)

    assert any("Output field 'missing_field' not found" in msg for msg in exc.value.errors)


def test_converter_multi_field_lookup_cast() -> None:
    yaml_content = """
name: test
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id:
      extract: order_id
sources:
  mapping:
    loader: tests.conftest.mock_loader
    key: [region_id, institution_id]
    lookup_cast: {name: int}
"""
    config = _load_config(yaml_content)
    converter = ConfigToIRConverter(resolver=PythonReferenceResolver(allowed_modules=frozenset(["tests"])))
    demand_ir = converter.convert(config)

    mapping_source = demand_ir.sources["mapping"]
    assert mapping_source.key.cast(["1", "2"]) == (1, 2)


def test_converter_keeps_order_by_fields_outside_output() -> None:
    yaml_content = """
name: test
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  order_by:
    - order_id
  fields:
    order_id: &order_id
      extract: order_id
    customer_id:
      extract: customer_id
sources:
  customers:
    loader: tests.conftest.mock_loader
    key: customer_id
    bind: {use_keys: {param: ids}}
    fields:
      customer_name: &customer_name
        extract: customer_name
relations:
  r1:
    steps:
      - from: orders.customer_id
        to: customers.customer_id
output:
  fields:
    - *customer_name
"""
    config = _load_config(yaml_content)
    converter = ConfigToIRConverter(resolver=PythonReferenceResolver(allowed_modules=frozenset(["tests"])))
    demand_ir = converter.convert(config)

    assert "order_id" in demand_ir.fields
    assert "customer_name" in demand_ir.fields


def test_converter_marks_constant_compute_when_compute_has_no_deps() -> None:
    yaml_content = """
name: test
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
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
    converter = ConfigToIRConverter(resolver=PythonReferenceResolver(allowed_modules=frozenset(["tests"])))
    demand_ir = converter.convert(config)

    const_field = demand_ir.fields["const"]
    assert isinstance(const_field, DerivedFieldIr)
    assert const_field.is_constant_compute is True


def test_converter_resolve_required_field_ids_ignores_empty_order_by() -> None:
    converter = ConfigToIRConverter(resolver=PythonReferenceResolver(allowed_modules=frozenset(["tests"])))
    config = DemandConfig(
        main_source=MainSourceConfig(
            source_id="orders",
            loader="tests.conftest.mock_loader",
            order_by=(" ",),
        ),
        output=OutputConfig(fields=["order_id"]),
    )

    required = converter._resolve_required_field_ids(config)
    assert required == {"order_id"}


def test_converter_rejects_invalid_order_by_entry() -> None:
    converter = ConfigToIRConverter(resolver=PythonReferenceResolver(allowed_modules=frozenset(["tests"])))

    with pytest.raises(ConversionError, match="order_by contains invalid field"):
        converter._convert_main_source_order_by(("-",))


def test_source_id_format_validation_valid() -> None:
    from scalim.dsl.by_yaml.runtime.conversion import _validate_source_id

    _validate_source_id("orders", "test")
    _validate_source_id("orders_2024", "test")
    _validate_source_id("_orders", "test")
    _validate_source_id("O123", "test")


def test_source_id_format_validation_invalid() -> None:
    from scalim.dsl.by_yaml.runtime.conversion import _validate_source_id

    for source_id in ("123-invalid", "order-id", ""):
        with pytest.raises(ConversionError, match="source_id.*must match pattern"):
            _validate_source_id(source_id, "test")
