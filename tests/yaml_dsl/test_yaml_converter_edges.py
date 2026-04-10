from decimal import Decimal

import pytest

from scalim.dsl.yaml_dsl.runtime.conversion import ConfigToIRConverter
from scalim.dsl.yaml_dsl.runtime.errors import ScalimConversionError
from scalim.dsl.yaml_dsl.runtime.references import SecurePythonReferenceResolver
from scalim.dsl.yaml_dsl.runtime.runtime_linking import _eval_call_by_value, resolve_runtime_bindings
from scalim.dsl.yaml_dsl.runtime._internal.conversion_lookup import LookupCastRegistry, VALUE_CASTS, cast_int
from scalim.dsl.yaml_dsl.runtime._internal.conversion_sources import _ensure_field_value
from scalim.dsl.yaml_dsl.schema_dsl.models import (
    DemandConfig,
    DerivedFieldConfig,
    MainSourceConfig,
    RelationConfig,
    RelationStepConfig,
    SourceConfig,
    SourceFieldConfig,
)
from scalim.spec.ir import CallByValueIr, ComputeCallContextIr, LookupStepIr
from scalim.spec.ir.binding import LoaderIr
from scalim.spec.ir.callable_refs import RuntimeHandleIdIr
from scalim.spec.ir.lookup_casts import LookupCastSpecIr
from scalim.spec.ir import KeyIr, MainSourceIr, SourceIr


class _DerivedFieldsDict(dict):
    def __contains__(self, key):  # type: ignore[override]
        return True

    def get(self, key, default=None):  # type: ignore[override]
        return None


def _make_main_source() -> MainSourceConfig:
    return MainSourceConfig(source_id="orders", loader="tests.fixtures.mock_loaders.mock_loader")


def _make_source_field(field_id, source="orders", extract=None, name="", relation=None):
    return SourceFieldConfig(
        field_id=field_id,
        source=source,
        extract=extract,
        name=name or field_id,
        relation=relation,
        value_cast=None,
    )


def _make_config(
    source_fields=None,
    derived_fields=None,
    sources=None,
    relations=None,
    source_field_id_map=None,
):
    return DemandConfig(
        name="demo",
        main_source=_make_main_source(),
        sources=sources or {},
        source_fields=source_fields or {},
        derived_fields=derived_fields or {},
        source_field_id_map=source_field_id_map or {},
        relations=relations or {},
    )


def _dummy_source_ir(source_id):
    loader_spec = LoaderIr(callable_ref=RuntimeHandleIdIr("dummy_loader:{}".format(source_id)))
    return SourceIr(source_id=source_id, key=KeyIr(key="id", cast=None), loader_spec=loader_spec)


def test_converter_does_not_filter_fields() -> None:
    source_fields = {
        "order_id": _make_source_field("order_id", extract="order_id"),
        "amount": _make_source_field("amount", extract="amount"),
    }
    derived_fields = {
        "total": DerivedFieldConfig(field_id="total", name="total", compute="amount", depends_on=("amount",)),
        "unused": DerivedFieldConfig(field_id="unused", name="unused", compute="order_id", depends_on=("order_id",)),
    }
    config = _make_config(source_fields=source_fields, derived_fields=derived_fields)
    converter = ConfigToIRConverter()

    demand_ir = converter.convert(config)

    assert set(demand_ir.fields.keys()) == {"order_id", "amount", "total", "unused"}


def test_converter_collects_nested_derived_dependencies() -> None:
    source_fields = {
        "amount": _make_source_field("amount", extract="amount"),
    }
    derived_fields = {
        "net": DerivedFieldConfig(field_id="net", name="net", compute="amount", depends_on=("amount",)),
        "total": DerivedFieldConfig(field_id="total", name="total", compute="net", depends_on=("net",)),
    }
    config = _make_config(source_fields=source_fields, derived_fields=derived_fields)
    converter = ConfigToIRConverter()

    demand_ir = converter.convert(config)

    assert "amount" in demand_ir.fields
    assert "net" in demand_ir.fields
    assert "total" in demand_ir.fields


def test_converter_compute_accepts_decimal_result_from_dec_helper() -> None:
    source_fields = {
        "amount": _make_source_field("amount", extract="amount"),
        "tax": _make_source_field("tax", extract="tax"),
    }
    derived_fields = {
        "total": DerivedFieldConfig(field_id="total", name="total", compute="dec(amount) + dec(tax)", depends_on=("amount", "tax")),
    }
    config = _make_config(source_fields=source_fields, derived_fields=derived_fields)
    converter = ConfigToIRConverter()

    demand_ir = converter.convert(config)

    bindings = resolve_runtime_bindings(
        demand_ir,
        resolver=SecurePythonReferenceResolver(allowed_modules=frozenset(["tests.fixtures"])),
    )
    total_calc = bindings.derived_calculators["total"]
    assert total_calc(0.1, "0.2") == Decimal("0.3")


def test_converter_step_to_field_tuple() -> None:
    sources = {
        "mapping": SourceConfig(
            source_id="mapping",
            loader="tests.fixtures.mock_loaders.mock_loader",
            key="id",
        )
    }
    relations = {
        "r1": RelationConfig(
            relation_id="r1",
            steps=(
                RelationStepConfig(
                    from_=("orders.region_id", "orders.institution_id"),
                    to=("mapping.region_id", "mapping.institution_id"),
                ),
            ),
        )
    }
    config = _make_config(sources=sources, relations=relations)
    converter = ConfigToIRConverter()

    converter.convert(config)

    step = converter._relation_steps["r1"][0][2]
    assert isinstance(step, LookupStepIr)
    assert step.to_field == ("region_id", "institution_id")


def test_converter_source_field_missing_source_or_extract() -> None:
    converter = ConfigToIRConverter()
    converter._main_source_ir = MainSourceIr(source_id="orders", loader_ref=RuntimeHandleIdIr("main_source:orders"))

    cases = [
        (_make_source_field("bad", source="", extract="id"), "missing source"),
        (_make_source_field("", source="orders", extract=None), "missing extract"),
    ]
    for source_field, match in cases:
        with pytest.raises(ScalimConversionError, match=match):
            converter._convert_source_field(source_field, _make_config())


def test_converter_rejects_invalid_source_field_extract_expression() -> None:
    config = _make_config(
        source_fields={"bad": _make_source_field("bad", extract="a..b")},
    )
    converter = ConfigToIRConverter()

    with pytest.raises(ScalimConversionError, match="invalid extract"):
        converter.convert(config)


def test_converter_lookup_steps_return_none_when_no_main_source() -> None:
    converter = ConfigToIRConverter()
    target_source = _dummy_source_ir("customers")

    result = converter._resolve_lookup_steps(_make_source_field("name", source="customers", extract="name"), _make_config(), target_source)

    assert result is None


def test_converter_lookup_steps_return_none_for_main_source_target() -> None:
    converter = ConfigToIRConverter()
    converter._main_source_ir = MainSourceIr(source_id="orders", loader_ref=RuntimeHandleIdIr("main_source:orders"))
    target_source = _dummy_source_ir("orders")

    result = converter._resolve_lookup_steps(
        _make_source_field("order_id", source="orders", extract="order_id"), _make_config(), target_source
    )

    assert result is None


def test_converter_infer_unique_path_edges() -> None:
    converter = ConfigToIRConverter()
    dummy_step = LookupStepIr(from_field="id", to_source=_dummy_source_ir("orders"))
    converter._relation_steps = {
        "loop": [("orders", "orders", dummy_step)],
    }

    assert converter._infer_unique_path("orders", "orders") == []

    with pytest.raises(ScalimConversionError, match="No relation path found"):
        converter._infer_unique_path("orders", "customers")


def test_converter_parse_source_field_expr_errors() -> None:
    converter = ConfigToIRConverter()

    for expr in ("invalid", "source."):
        with pytest.raises(ScalimConversionError, match="Invalid field reference"):
            converter._parse_source_field_expr(expr)


def test_converter_resolves_relation_field_id_to_data_key() -> None:
    sources = {
        "products": SourceConfig(
            source_id="products",
            loader="tests.fixtures.mock_loaders.mock_loader",
            key="product_id",
        )
    }
    relations = {
        "r1": RelationConfig(
            relation_id="r1",
            steps=(
                RelationStepConfig(
                    from_="orders.product_category_id",
                    to="products.product_category_id",
                ),
            ),
        )
    }
    source_field_id_map = {
        "orders": {"product_category_id": "category_id"},
        "products": {"product_category_id": "category_id"},
    }
    config = _make_config(sources=sources, relations=relations, source_field_id_map=source_field_id_map)
    converter = ConfigToIRConverter()

    converter.convert(config)

    step = converter._relation_steps["r1"][0][2]
    assert step.from_field == "category_id"
    assert step.to_field == "category_id"


def test_converter_relation_field_falls_back_to_data_key_when_field_id_missing() -> None:
    sources = {
        "products": SourceConfig(
            source_id="products",
            loader="tests.fixtures.mock_loaders.mock_loader",
            key="product_id",
        )
    }
    relations = {
        "r1": RelationConfig(
            relation_id="r1",
            steps=(
                RelationStepConfig(
                    from_="orders.category_id",
                    to="products.category_id",
                ),
            ),
        )
    }
    source_field_id_map = {
        "products": {"product_category_id": "category_id"},
    }
    config = _make_config(sources=sources, relations=relations, source_field_id_map=source_field_id_map)
    converter = ConfigToIRConverter()

    converter.convert(config)

    step = converter._relation_steps["r1"][0][2]
    assert step.from_field == "category_id"
    assert step.to_field == "category_id"


def test_converter_rejects_ambiguous_relation_field_id() -> None:
    sources = {
        "products": SourceConfig(
            source_id="products",
            loader="tests.fixtures.mock_loaders.mock_loader",
            key="product_id",
        )
    }
    relations = {
        "r1": RelationConfig(
            relation_id="r1",
            steps=(
                RelationStepConfig(
                    from_="orders.product_id",
                    to="products.category_id",
                ),
            ),
        )
    }
    source_field_id_map = {
        "products": {"category_id": "category_id_v2", "product_category_id": "category_id"},
    }
    config = _make_config(sources=sources, relations=relations, source_field_id_map=source_field_id_map)
    converter = ConfigToIRConverter()

    with pytest.raises(ScalimConversionError, match="ambiguous"):
        converter.convert(config)


def test_converter_parse_step_field_tuple_errors() -> None:
    converter = ConfigToIRConverter()

    cases = [
        (("a.id", "b.id"), "Step fields must reference the same source"),
        ((), "Empty step field list"),
    ]
    for fields, match in cases:
        with pytest.raises(ScalimConversionError, match=match):
            converter._parse_step_field(fields)


def test_converter_value_and_lookup_cast_edges() -> None:
    value_cast = VALUE_CASTS["int"]
    assert value_cast("1") == 1

    registry = LookupCastRegistry()
    lookup_cast = registry.build(LookupCastSpecIr(name="sep_first", sep=","), is_multi=False)
    assert lookup_cast(None) is None
    assert lookup_cast(" , ") is None
    assert lookup_cast("1,2") == "1"

    multi_cast = registry.build(LookupCastSpecIr(name="sep_first", sep=","), is_multi=True)
    assert multi_cast("bad") is None
    assert multi_cast(["", "1"]) is None


def test_converter_lookup_cast_registry_and_cast_int_type_error() -> None:
    registry = LookupCastRegistry()
    with pytest.raises(ScalimConversionError, match="Unknown lookup_cast"):
        _ = registry.build(LookupCastSpecIr(name="unknown"), is_multi=False)

    with pytest.raises(TypeError, match="Unsupported int cast value type"):
        cast_int(object())


def test_conversion_source_helpers_raise_on_invalid_runtime_values() -> None:
    with pytest.raises(TypeError, match="unsupported value type"):
        _ensure_field_value(object(), field_id="status_name", producer="call_by")

    with pytest.raises(AttributeError, match="has no attribute 'missing'"):
        _eval_call_by_value(
            CallByValueIr(kind="ctx_attr", value="missing"),
            field_id="status_name",
            dep_values={},
            ctx=ComputeCallContextIr(row_id="row", batch_num=1, field_id="status_name", deps=(), values={}),
        )
