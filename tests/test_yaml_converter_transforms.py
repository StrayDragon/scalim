from decimal import Decimal

import pytest

from scalim.dsl.by_yaml.config_parsing.security import SecureComputeEngine
from scalim.dsl.by_yaml.config_parsing.error_envelope import ScalimYamlValidationError
from scalim.dsl.by_yaml.runtime.conversion import ConfigToIRConverter
from scalim.dsl.by_yaml.runtime.errors import ScalimConversionError
from scalim.dsl.by_yaml.config_parsing.loader import YamlDemandLoader
from scalim.dsl.by_yaml.runtime.references import PythonReferenceResolver
from scalim.dsl.by_yaml.runtime._internal.conversion_lookup import cast_str
from scalim.dsl.by_yaml.runtime._internal.conversion_lookup import cast_decimal
from scalim.dsl.by_yaml.schema_dsl.models import LookupCastConfig
from scalim.spec.ir.binding import LoaderCallContextIr
from tests.yaml_fixtures import make_yaml_config


def _load_config(yaml_content: str):
    loader = YamlDemandLoader()
    return loader.load_string(yaml_content)


def test_keys_directive_as_list_builds_list_params() -> None:
    yaml_content = make_yaml_config(
        name="binding_as_list",
        main_source="""
source_id: orders
loader: "scalim_misc.example_report_ir:DAL.paged_get_order_list"
fields:
  order_id:
    extract: order_id
  customer_id:
    extract: customer_id
""",
        sources="""
customers:
  loader: "scalim_misc.example_report_ir:BLL.get_customer_info_from_api_of_kw_params"
  key: customer_id
  params:
    ids: {$keys: {as: list}}
  fields:
    customer_name:
      extract: customer_name
      relation: *orders_to_customers
""",
        relations="""
orders_to_customers: &orders_to_customers
  steps:
    - from: orders.customer_id
      to: customers.customer_id
    """,
    )
    config = _load_config(yaml_content)
    converter = ConfigToIRConverter(
        resolver=PythonReferenceResolver(allowed_modules=frozenset(["scalim_misc.example_report_ir"])),
    )
    demand_ir = converter.convert(config)

    bind = demand_ir.sources["customers"].bind
    assert bind is not None

    ctx = LoaderCallContextIr(is_ref_loader=True, lookup_keys={1, 2, 3})
    _, kwargs = bind.params_builder(ctx)
    assert isinstance(kwargs["ids"], list)
    assert kwargs["ids"] == [1, 2, 3]


def test_rows_directive_passes_batch_rows() -> None:
    yaml_content = make_yaml_config(
        name="binding_rows",
        main_source="""
source_id: orders
loader: "scalim_misc.example_report_ir:DAL.paged_get_order_list"
fields:
  order_id:
    extract: order_id
  region_id:
    extract: region_id
""",
        sources="""
regions:
  loader: "scalim_misc.example_report_ir:DAL.get_country_info_of_concrete_params"
  key: region_id
  params:
    rows: {$rows: {cache_mode: batch}}
  fields:
    region_name:
      extract: name
      relation: *orders_to_regions
""",
        relations="""
orders_to_regions: &orders_to_regions
  steps:
    - from: orders.region_id
      to: regions.region_id
    """,
    )
    config = _load_config(yaml_content)
    converter = ConfigToIRConverter(
        resolver=PythonReferenceResolver(allowed_modules=frozenset(["scalim_misc.example_report_ir"])),
    )
    demand_ir = converter.convert(config)

    bind = demand_ir.sources["regions"].bind
    assert bind is not None

    ctx = LoaderCallContextIr(is_ref_loader=True, batch_rows=[{"region_id": 1}, {"region_id": 2}])
    _, kwargs = bind.params_builder(ctx)
    assert kwargs["rows"] == [{"region_id": 1}, {"region_id": 2}]


def test_unknown_value_cast_raises() -> None:
    yaml_content = make_yaml_config(
        name="value_cast_invalid",
        main_source="""
source_id: orders
loader: "scalim_misc.example_report_ir:DAL.paged_get_order_list"
fields:
  order_id:
    extract: order_id
    value_cast: not_supported
    """,
        sources="{}",
    )
    loader = YamlDemandLoader()
    with pytest.raises(ScalimYamlValidationError) as exc:
        loader.load_string(yaml_content)

    assert any("invalid value_cast" in env.message for env in exc.value.errors)


@pytest.mark.parametrize(
    "value_cast,input_value,expected",
    [
        ("int", "3", 3),
        ("str", 3, "3"),
        ("decimal", "3.50", Decimal("3.50")),
        ("decimal", 0.1, Decimal("0.1")),
        ("int", None, None),
        ("str", None, None),
        ("decimal", None, None),
    ],
    ids=["int-cast", "str-cast", "decimal-str", "decimal-float", "int-none", "str-none", "decimal-none"],
)
def test_converter_value_cast_applies(value_cast: str, input_value, expected) -> None:
    yaml_content = make_yaml_config(
        name="value_cast_valid",
        main_source="""
source_id: orders
loader: "tests.conftest.mock_loader"
fields:
  order_id:
    extract: order_id
    value_cast: {value_cast}
""".format(value_cast=value_cast),
        sources="{}",
    )
    loader = YamlDemandLoader()
    config = loader.load_string(yaml_content)
    converter = ConfigToIRConverter(resolver=PythonReferenceResolver(allowed_modules=frozenset(["tests"])))
    demand_ir = converter.convert(config)

    field = demand_ir.fields["order_id"]
    assert field.transform is not None
    assert field.transform(input_value) == expected


def test_value_cast_str_none_does_not_break_compute_if_falsy_guard() -> None:
    # Regression: before the fix, cast_str(None) == "None" (truthy), which would make the expression take the true-branch
    # and crash at float("None").
    engine = SecureComputeEngine()
    calc = engine.compile(
        "str(round(float(ratio) * 100, 2)) + '%' if ratio else '0.0%'",
        ("ratio",),
    )
    assert calc(cast_str(None)) == "0.0%"


def test_cast_decimal_variants_and_errors() -> None:
    assert cast_decimal(Decimal("1.23")) == Decimal("1.23")
    assert cast_decimal(True) == Decimal(1)
    assert cast_decimal(False) == Decimal(0)
    assert cast_decimal(3) == Decimal(3)
    assert cast_decimal("   ") is None

    with pytest.raises(ValueError, match="Invalid decimal string literal"):
        _ = cast_decimal("bad-decimal")

    class _WeirdFloat(float):
        def __str__(self) -> str:
            return "not-a-number"

    with pytest.raises(ValueError, match="Invalid decimal float literal"):
        _ = cast_decimal(_WeirdFloat(1.0))

    with pytest.raises(TypeError, match="Unsupported decimal cast value type"):
        _ = cast_decimal([1])  # type: ignore[arg-type]


def test_converter_private_value_cast_raises() -> None:
    converter = ConfigToIRConverter(resolver=PythonReferenceResolver(allowed_modules=frozenset(["tests"])))

    with pytest.raises(ScalimConversionError, match="Unknown value_cast"):
        converter._get_value_cast_fn("bad")


def test_unknown_lookup_cast_raises() -> None:
    yaml_content = make_yaml_config(
        name="lookup_cast_invalid",
        main_source="""
source_id: orders
loader: "scalim_misc.example_report_ir:DAL.paged_get_order_list"
fields:
  order_id:
    extract: order_id
""",
        sources="""
customers:
  loader: "scalim_misc.example_report_ir:BLL.get_customer_info_from_api_of_kw_params"
  key: customer_id
  fields:
    customer_name:
      extract: customer_name
      relation: *orders_to_customers
""",
        relations="""
orders_to_customers: &orders_to_customers
  steps:
    - from: orders.customer_id
      to: customers.customer_id
      lookup_cast:
        name: bad
    """,
    )
    loader = YamlDemandLoader()
    with pytest.raises(ScalimYamlValidationError) as exc:
        loader.load_string(yaml_content)

    assert any("lookup_cast has invalid name" in env.message for env in exc.value.errors)


def test_converter_private_lookup_cast_raises() -> None:
    converter = ConfigToIRConverter(resolver=PythonReferenceResolver(allowed_modules=frozenset(["tests"])))
    lookup_cast = LookupCastConfig(name="bad", sep=None)

    with pytest.raises(ScalimConversionError, match="Unknown lookup_cast"):
        converter._get_lookup_cast_fn(lookup_cast, is_multi=False)
