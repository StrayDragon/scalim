import pytest

from scalim.dsl.by_yaml.runtime.conversion import ConfigToIRConverter
from scalim.dsl.by_yaml.runtime.errors import ConversionError
from scalim.dsl.by_yaml.runtime.references import PythonReferenceResolver
from scalim.dsl.by_yaml.runtime._internal.conversion_lookup import cast_int
from scalim.dsl.by_yaml.runtime._internal.conversion_sources import _ensure_field_value, _resolve_call_by_ctx_attr
from scalim.dsl.by_yaml.schema_dsl.models import (
    DemandConfig,
    DerivedFieldConfig,
    LookupCastConfig,
    MainSourceConfig,
    OutputConfig,
    RelationConfig,
    RelationStepConfig,
    SourceConfig,
    SourceFieldConfig,
)
from scalim.spec.ir.binding import LoaderIr
from scalim.spec.ir.relations import LookupStepIr
from scalim.spec.ir.sources import KeyIr, MainSourceIr, SourceIr


class _DerivedFieldsDict(dict):
    def __contains__(self, key):  # type: ignore[override]
        return True

    def get(self, key, default=None):  # type: ignore[override]
        return None


def _make_main_source() -> MainSourceConfig:
    return MainSourceConfig(source_id="orders", loader="tests.conftest.mock_loader")


def _make_source_field(field_id, source="orders", field=None, name="", relation=None):
    return SourceFieldConfig(
        field_id=field_id,
        source=source,
        field=field,
        name=name or field_id,
        relation=relation,
        value_cast=None,
    )


def _make_config(
    source_fields=None,
    derived_fields=None,
    sources=None,
    relations=None,
    output_fields=None,
    source_field_id_map=None,
):
    output = OutputConfig(fields=output_fields) if output_fields is not None else None
    return DemandConfig(
        name="demo",
        main_source=_make_main_source(),
        sources=sources or {},
        source_fields=source_fields or {},
        derived_fields=derived_fields or {},
        source_field_id_map=source_field_id_map or {},
        relations=relations or {},
        output=output,
    )


def _dummy_source_ir(source_id):
    loader_spec = LoaderIr(callable=lambda **_kwargs: {})
    return SourceIr(source_id=source_id, key=KeyIr(key="id", cast=None), loader_spec=loader_spec)


def test_converter_rejects_unknown_output_fields() -> None:
    config = _make_config(
        source_fields={"order_id": _make_source_field("order_id", field="order_id")},
        output_fields=["missing"],
    )
    converter = ConfigToIRConverter(resolver=PythonReferenceResolver(allowed_modules=frozenset(["tests"])))

    with pytest.raises(ConversionError, match="Output fields reference unknown fields"):
        converter.convert(config)


def test_converter_skips_unrequired_source_and_derived_fields() -> None:
    source_fields = {
        "order_id": _make_source_field("order_id", field="order_id"),
        "amount": _make_source_field("amount", field="amount"),
    }
    derived_fields = {
        "total": DerivedFieldConfig(field_id="total", name="total", compute="amount", depends_on=("amount",)),
        "unused": DerivedFieldConfig(field_id="unused", name="unused", compute="order_id", depends_on=("order_id",)),
    }
    config = _make_config(source_fields=source_fields, derived_fields=derived_fields, output_fields=["total"])
    converter = ConfigToIRConverter(resolver=PythonReferenceResolver(allowed_modules=frozenset(["tests"])))

    demand_ir = converter.convert(config)

    assert "order_id" not in demand_ir.fields
    assert "total" in demand_ir.fields
    assert "unused" not in demand_ir.fields


def test_converter_collects_nested_derived_dependencies() -> None:
    source_fields = {
        "amount": _make_source_field("amount", field="amount"),
    }
    derived_fields = {
        "net": DerivedFieldConfig(field_id="net", name="net", compute="amount", depends_on=("amount",)),
        "total": DerivedFieldConfig(field_id="total", name="total", compute="net", depends_on=("net",)),
    }
    config = _make_config(source_fields=source_fields, derived_fields=derived_fields, output_fields=["total"])
    converter = ConfigToIRConverter(resolver=PythonReferenceResolver(allowed_modules=frozenset(["tests"])))

    demand_ir = converter.convert(config)

    assert "amount" in demand_ir.fields
    assert "net" in demand_ir.fields
    assert "total" in demand_ir.fields


def test_resolve_required_field_ids_handles_missing_derived_entry() -> None:
    config = _make_config(output_fields=["ghost"])
    config = DemandConfig(
        name=config.name,
        main_source=config.main_source,
        sources=config.sources,
        source_fields=config.source_fields,
        derived_fields=_DerivedFieldsDict(),
        relations=config.relations,
        output=config.output,
    )
    converter = ConfigToIRConverter(resolver=PythonReferenceResolver(allowed_modules=frozenset(["tests"])))

    required = converter._resolve_required_field_ids(config)

    assert required == {"ghost"}


def test_converter_step_to_field_tuple() -> None:
    sources = {
        "mapping": SourceConfig(
            source_id="mapping",
            loader="tests.conftest.mock_loader",
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
    converter = ConfigToIRConverter(resolver=PythonReferenceResolver(allowed_modules=frozenset(["tests"])))

    converter.convert(config)

    step = converter._relation_steps["r1"][0][2]
    assert isinstance(step, LookupStepIr)
    assert step.to_field == ("region_id", "institution_id")


def test_converter_source_field_missing_source_or_field() -> None:
    converter = ConfigToIRConverter(resolver=PythonReferenceResolver(allowed_modules=frozenset(["tests"])))
    converter._main_source_ir = MainSourceIr(source_id="orders", loader=lambda: [])

    cases = [
        (_make_source_field("bad", source="", field="id"), "missing source"),
        (_make_source_field("", source="orders", field=None), "missing field"),
    ]
    for source_field, match in cases:
        with pytest.raises(ConversionError, match=match):
            converter._convert_source_field(source_field, _make_config())


def test_converter_lookup_steps_return_none_when_no_main_source() -> None:
    converter = ConfigToIRConverter(resolver=PythonReferenceResolver(allowed_modules=frozenset(["tests"])))
    target_source = _dummy_source_ir("customers")

    result = converter._resolve_lookup_steps(_make_source_field("name", source="customers", field="name"), _make_config(), target_source)

    assert result is None


def test_converter_lookup_steps_return_none_for_main_source_target() -> None:
    converter = ConfigToIRConverter(resolver=PythonReferenceResolver(allowed_modules=frozenset(["tests"])))
    converter._main_source_ir = MainSourceIr(source_id="orders", loader=lambda: [])
    target_source = _dummy_source_ir("orders")

    result = converter._resolve_lookup_steps(
        _make_source_field("order_id", source="orders", field="order_id"), _make_config(), target_source
    )

    assert result is None


def test_converter_infer_unique_path_edges() -> None:
    converter = ConfigToIRConverter(resolver=PythonReferenceResolver(allowed_modules=frozenset(["tests"])))
    dummy_step = LookupStepIr(from_field="id", to_source=_dummy_source_ir("orders"))
    converter._relation_steps = {
        "loop": [("orders", "orders", dummy_step)],
    }

    assert converter._infer_unique_path("orders", "orders") == []

    with pytest.raises(ConversionError, match="No relation path found"):
        converter._infer_unique_path("orders", "customers")


def test_converter_parse_source_field_expr_errors() -> None:
    converter = ConfigToIRConverter(resolver=PythonReferenceResolver(allowed_modules=frozenset(["tests"])))

    for expr in ("invalid", "source."):
        with pytest.raises(ConversionError, match="Invalid field reference"):
            converter._parse_source_field_expr(expr)


def test_converter_resolves_relation_field_id_to_data_key() -> None:
    sources = {
        "products": SourceConfig(
            source_id="products",
            loader="tests.conftest.mock_loader",
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
    converter = ConfigToIRConverter(resolver=PythonReferenceResolver(allowed_modules=frozenset(["tests"])))

    converter.convert(config)

    step = converter._relation_steps["r1"][0][2]
    assert step.from_field == "category_id"
    assert step.to_field == "category_id"


def test_converter_relation_field_falls_back_to_data_key_when_field_id_missing() -> None:
    sources = {
        "products": SourceConfig(
            source_id="products",
            loader="tests.conftest.mock_loader",
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
    converter = ConfigToIRConverter(resolver=PythonReferenceResolver(allowed_modules=frozenset(["tests"])))

    converter.convert(config)

    step = converter._relation_steps["r1"][0][2]
    assert step.from_field == "category_id"
    assert step.to_field == "category_id"


def test_converter_rejects_ambiguous_relation_field_id() -> None:
    sources = {
        "products": SourceConfig(
            source_id="products",
            loader="tests.conftest.mock_loader",
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
    converter = ConfigToIRConverter(resolver=PythonReferenceResolver(allowed_modules=frozenset(["tests"])))

    with pytest.raises(ConversionError, match="ambiguous"):
        converter.convert(config)


def test_converter_parse_step_field_tuple_errors() -> None:
    converter = ConfigToIRConverter(resolver=PythonReferenceResolver(allowed_modules=frozenset(["tests"])))

    cases = [
        (("a.id", "b.id"), "Step fields must reference the same source"),
        ((), "Empty step field list"),
    ]
    for fields, match in cases:
        with pytest.raises(ConversionError, match=match):
            converter._parse_step_field(fields)


def test_converter_value_and_lookup_cast_edges() -> None:
    converter = ConfigToIRConverter(resolver=PythonReferenceResolver(allowed_modules=frozenset(["tests"])))

    value_cast = converter._get_value_cast_fn("int")
    assert value_cast("1") == 1

    lookup_cast = converter._get_lookup_cast_fn(LookupCastConfig(name="sep_first", sep=","), is_multi=False)
    assert lookup_cast(None) is None
    assert lookup_cast(" , ") is None
    assert lookup_cast("1,2") == "1"

    multi_cast = converter._get_lookup_cast_fn(LookupCastConfig(name="sep_first", sep=","), is_multi=True)
    assert multi_cast("bad") is None
    assert multi_cast(["", "1"]) is None


def test_converter_lookup_cast_registry_uninitialized_and_cast_int_type_error() -> None:
    converter = ConfigToIRConverter(resolver=PythonReferenceResolver(allowed_modules=frozenset(["tests"])))
    converter._lookup_casts = None

    with pytest.raises(ConversionError, match="Lookup cast registry is not initialized"):
        converter._get_lookup_cast_fn(LookupCastConfig(name="auto", sep=None), is_multi=False)

    with pytest.raises(TypeError, match="Unsupported int cast value type"):
        cast_int(object())


def test_conversion_source_helpers_raise_on_invalid_runtime_values() -> None:
    with pytest.raises(TypeError, match="returned unsupported type"):
        _ensure_field_value(object(), field_id="status_name", producer="call_by")

    with pytest.raises(AttributeError, match="call_by context missing attribute"):
        _resolve_call_by_ctx_attr(object(), "row_id")
