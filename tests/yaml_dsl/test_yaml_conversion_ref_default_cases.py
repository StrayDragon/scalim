import pytest

from scalim.dsl.yaml_dsl.runtime.conversion import ConfigToIRConverter
from scalim.dsl.yaml_dsl.runtime.errors import ScalimConversionError
from scalim.dsl.yaml_dsl.schema_dsl.models import (
    DemandConfig,
    MainSourceConfig,
    RelationConfig,
    RelationStepConfig,
    SourceConfig,
    SourceFieldConfig,
)
from scalim.spec.ir import BuiltinCallableIdIr, FieldIr


def _make_main_source() -> MainSourceConfig:
    return MainSourceConfig(source_id="orders", loader="tests.fixtures.mock_loaders.mock_loader")


def _make_relation() -> dict:
    return {
        "r": RelationConfig(
            relation_id="r",
            steps=(
                RelationStepConfig(
                    from_="orders.cs_id",
                    to="cs.cs_id",
                ),
            ),
        )
    }


def _make_sources() -> dict:
    return {
        "cs": SourceConfig(
            source_id="cs",
            loader="tests.fixtures.mock_loaders.mock_loader",
            key="cs_id",
        )
    }


def _make_config(*, source_fields: dict, sources: dict = None, relations: dict = None) -> DemandConfig:
    return DemandConfig(
        name="demo",
        main_source=_make_main_source(),
        sources=sources or {},
        source_fields=source_fields,
        derived_fields={},
        source_field_id_map={},
        relations=relations or {},
    )


def test_converter_rejects_default_on_non_ref_field() -> None:
    converter = ConfigToIRConverter()
    config = _make_config(
        source_fields={
            "x": SourceFieldConfig(
                field_id="x",
                source="orders",
                extract="x",
                name="x",
                relation=None,
                value_cast=None,
                default=(
                    {
                        "when": "relation_miss",
                        "literal": 0,
                    },
                ),
            )
        }
    )

    with pytest.raises(ScalimConversionError, match=r"default is only allowed for ref fields"):
        converter.convert(config)


def test_converter_rejects_default_case_unknown_when() -> None:
    converter = ConfigToIRConverter()
    config = _make_config(
        source_fields={
            "metric": SourceFieldConfig(
                field_id="metric",
                source="cs",
                extract="metric",
                name="metric",
                relation="r",
                value_cast=None,
                default=(
                    {
                        "when": "hit_null",
                        "literal": 0,
                    },
                ),
            )
        },
        sources=_make_sources(),
        relations=_make_relation(),
    )

    with pytest.raises(ScalimConversionError, match=r"unsupported when"):
        converter.convert(config)


def test_converter_converts_default_literal_case() -> None:
    converter = ConfigToIRConverter()
    config = _make_config(
        source_fields={
            "metric": SourceFieldConfig(
                field_id="metric",
                source="cs",
                extract="metric",
                name="metric",
                relation="r",
                value_cast=None,
                default=(
                    {
                        "when": "relation_miss",
                        "literal": 0,
                    },
                ),
            )
        },
        sources=_make_sources(),
        relations=_make_relation(),
    )

    demand_ir = converter.convert(config)
    field = demand_ir.fields["metric"]
    assert isinstance(field, FieldIr)
    assert field.default_cases
    assert field.default_cases[0].kind == "literal"
    assert field.default_cases[0].literal == 0


def test_converter_rejects_default_call_by_invalid() -> None:
    converter = ConfigToIRConverter()
    config = _make_config(
        source_fields={
            "metric": SourceFieldConfig(
                field_id="metric",
                source="cs",
                extract="metric",
                name="metric",
                relation="r",
                value_cast=None,
                default=(
                    {
                        "when": "relation_miss",
                        "call_by": "^defaults/zero_of_value_cast",
                    },
                ),
            )
        },
        sources=_make_sources(),
        relations=_make_relation(),
    )

    with pytest.raises(ScalimConversionError, match=r"invalid call_by"):
        converter.convert(config)


def test_converter_converts_default_call_by_case() -> None:
    converter = ConfigToIRConverter()
    config = _make_config(
        source_fields={
            "metric": SourceFieldConfig(
                field_id="metric",
                source="cs",
                extract="metric",
                name="metric",
                relation="r",
                value_cast=None,
                default=(
                    {
                        "when": "relation_miss",
                        "call_by": "^defaults/zero_of_value_cast()",
                    },
                ),
            )
        },
        sources=_make_sources(),
        relations=_make_relation(),
    )

    demand_ir = converter.convert(config)
    field = demand_ir.fields["metric"]
    assert isinstance(field, FieldIr)
    assert field.default_cases
    assert field.default_cases[0].kind == "call_by"
    assert field.default_cases[0].call_by is not None
    assert isinstance(field.default_cases[0].call_by.reference, BuiltinCallableIdIr)
    assert field.default_cases[0].call_by.reference.callable_id == "defaults/zero_of_value_cast"
