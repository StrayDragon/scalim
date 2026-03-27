import copy

import pytest

import scalim.dsl.by_yaml.config_parsing.validator as validator_module
from scalim.dsl.by_yaml.runtime.conversion import ConfigToIRConverter
from scalim.dsl.by_yaml.runtime.errors import ConversionError, ResolverError
from scalim.dsl.by_yaml.runtime.references import PythonReferenceResolver, SecurePythonReferenceResolver
from scalim.dsl.by_yaml.schema_dsl.models import (
    DemandConfig,
    InlineRelationConfig,
    MainSourceConfig,
    RelationConfig,
    RelationStepConfig,
    SourceConfig,
    SourceFieldConfig,
)
from scalim.dsl.by_yaml.config_parsing.errors import ConfigValidationError
from scalim.dsl.by_yaml.config_parsing.validator import ConfigValidator, HAS_JSONSCHEMA
from scalim.spec.ir.fields import FieldIr

_ORDER_LOADER = "scalim_misc.example_report_ir:DAL.paged_get_order_list"
_CUSTOMER_LOADER = "scalim_misc.example_report_ir:BLL.get_customer_info_from_api_of_kw_params"


def _require_jsonschema() -> None:
    if not HAS_JSONSCHEMA or validator_module.jsonschema is None:
        pytest.skip("jsonschema not available")


def _base_validator_config() -> dict:
    return {
        "name": "demo",
        "main_source": {
            "source_id": "orders",
            "loader": _ORDER_LOADER,
            "fields": {
                "order_id": {"extract": "order_id"},
                "customer_id": {"extract": "customer_id"},
            },
        },
        "sources": {
            "customers": {
                "loader": _CUSTOMER_LOADER,
                "key": "customer_id",
                "params": {"ids": {"$keys": {"as": "set"}}},
                "fields": {
                    "customer_name": {
                        "extract": "customer_name",
                        "relation": {"steps": [{"from": "orders.customer_id", "to": "customers.customer_id"}]},
                    }
                },
            },
        },
        "relations": {
            "orders_to_customers": {"steps": [{"from": "orders.customer_id", "to": "customers.customer_id"}]},
        },
    }


def _base_converter_config() -> DemandConfig:
    return DemandConfig(
        name="demo",
        main_source=MainSourceConfig(source_id="orders", loader=_ORDER_LOADER),
        sources={
            "customers": SourceConfig(source_id="customers", loader=_CUSTOMER_LOADER, key="customer_id"),
        },
        source_fields={
            "order_id": SourceFieldConfig(field_id="order_id", source="orders", extract="order_id"),
            "customer_name": SourceFieldConfig(
                field_id="customer_name",
                source="customers",
                extract="customer_name",
                relation=InlineRelationConfig(steps=(RelationStepConfig(from_="orders.customer_id", to="customers.customer_id"),)),
            ),
        },
        relations={
            "r1": RelationConfig(
                relation_id="r1",
                steps=(RelationStepConfig(from_="orders.customer_id", to="customers.customer_id"),),
            ),
        },
    )


@pytest.mark.parametrize(
    "raise_validation_error",
    [False, True],
    ids=["ignore-exception", "schema-validation-error"],
)
def test_validator_schema_validation_paths(raise_validation_error: bool) -> None:
    _require_jsonschema()
    config = _base_validator_config()

    def _raise_exception(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise Exception("boom")

    def _raise_validation(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise validator_module.jsonschema.ValidationError("bad schema")

    validator = ConfigValidator(
        jsonschema_validate_fn=_raise_validation if raise_validation_error else _raise_exception,
    )

    if raise_validation_error:
        with pytest.raises(ConfigValidationError) as exc_info:
            validator.validate(config)
        assert any("Schema validation error" in error for error in exc_info.value.errors)
    else:
        validator.validate(config)


def test_validator_loader_reference_variants() -> None:
    validator = ConfigValidator()

    assert validator._is_valid_loader_ref("module.path:obj.method") is True
    assert validator._is_valid_loader_ref("module:attr:extra") is False
    assert validator._is_valid_loader_ref("module.:attr") is False
    assert validator._is_valid_loader_ref("module:attr-name") is False
    assert validator._is_valid_loader_ref("module") is False
    assert validator._is_valid_loader_ref("module.1.func") is False
    assert validator._is_valid_loader_ref("module..func") is False


def test_resolver_error_paths_and_allowlist() -> None:
    resolver = PythonReferenceResolver()

    for ref in ("json:loads:extra", "json:missing_attr", "json:__doc__", "json.__doc__"):
        with pytest.raises(ResolverError):
            resolver.resolve(ref)

    resolver = PythonReferenceResolver(allowed_functions=frozenset(["json:dumps"]))
    import json

    assert resolver.resolve("json.dumps") is json.dumps

    with pytest.raises(ResolverError):
        resolver.resolve("json.loads")


def test_resolver_caches_reference() -> None:
    resolver = PythonReferenceResolver()
    first = resolver.resolve("json.dumps")
    second = resolver.resolve("json.dumps")

    assert first is second
    assert "json.dumps" in resolver._cache


def test_secure_resolver_rejects_invalid_and_patterns() -> None:
    resolver = SecurePythonReferenceResolver()

    for ref in ("invalid", "safe.module:lambda"):
        with pytest.raises(ResolverError):
            resolver.resolve(ref)


def test_secure_resolver_rejects_dangerous_module_parts() -> None:
    resolver = SecurePythonReferenceResolver()

    for ref, match in (("safe.__evil:func", "危险模式 '__'"), ("lambda.safe:func", "危险模式 'lambda'")):
        with pytest.raises(ResolverError, match=match):
            resolver.resolve(ref)


def _assert_conversion_error(config: DemandConfig, match: str) -> None:
    converter = ConfigToIRConverter(
        resolver=SecurePythonReferenceResolver(allowed_modules=frozenset(["scalim_misc"])),
    )
    with pytest.raises(ConversionError, match=match):
        converter.convert(config)


def _config_missing_main_source_id() -> DemandConfig:
    return DemandConfig(name="demo", main_source=MainSourceConfig())


def _config_main_source_missing_loader() -> DemandConfig:
    return DemandConfig(name="demo", main_source=MainSourceConfig(source_id="orders"))


def _config_main_source_conflicts_with_sources() -> DemandConfig:
    config = copy.deepcopy(_base_converter_config())
    config.sources["orders"] = SourceConfig(source_id="orders", loader=_ORDER_LOADER, key="order_id")
    return config


def _config_field_unknown_source() -> DemandConfig:
    config = copy.deepcopy(_base_converter_config())
    config.source_fields["order_id"] = SourceFieldConfig(field_id="order_id", source="missing", extract="order_id")
    return config


def _config_unknown_relation_ref() -> DemandConfig:
    config = copy.deepcopy(_base_converter_config())
    config.source_fields["customer_name"] = SourceFieldConfig(
        field_id="customer_name",
        source="customers",
        extract="customer_name",
        relation="missing",
    )
    return config


def _config_ambiguous_path() -> DemandConfig:
    config = copy.deepcopy(_base_converter_config())
    config.relations["r2"] = RelationConfig(
        relation_id="r2",
        steps=(RelationStepConfig(from_="orders.customer_id", to="customers.customer_id"),),
    )
    config.source_fields["customer_name"] = SourceFieldConfig(
        field_id="customer_name",
        source="customers",
        extract="customer_name",
    )
    return config


def _config_inline_steps_unknown_source() -> DemandConfig:
    config = copy.deepcopy(_base_converter_config())
    config.source_fields["customer_name"] = SourceFieldConfig(
        field_id="customer_name",
        source="customers",
        extract="customer_name",
        relation=InlineRelationConfig(
            steps=(RelationStepConfig(from_="orders.customer_id", to="missing.customer_id"),),
        ),
    )
    return config


@pytest.mark.parametrize(
    "config_factory,match",
    [
        (_config_missing_main_source_id, "source_id"),
        (_config_main_source_missing_loader, "loader"),
        (_config_main_source_conflicts_with_sources, "conflicts with sources"),
        (_config_field_unknown_source, "unknown source"),
        (_config_unknown_relation_ref, "Unsupported relation reference"),
        (_config_ambiguous_path, "Ambiguous relation paths"),
        (_config_inline_steps_unknown_source, "unknown source"),
    ],
    ids=[
        "missing-main-source-id",
        "missing-main-source-loader",
        "main-source-conflicts",
        "unknown-source",
        "unknown-relation-ref",
        "ambiguous-path",
        "inline-steps-unknown-source",
    ],
)
def test_converter_validation_errors(config_factory, match: str) -> None:
    _assert_conversion_error(config_factory(), match)


def test_converter_infers_unique_path() -> None:
    converter = ConfigToIRConverter(
        resolver=SecurePythonReferenceResolver(allowed_modules=frozenset(["scalim_misc"])),
    )
    config = copy.deepcopy(_base_converter_config())
    config.source_fields["customer_name"] = SourceFieldConfig(
        field_id="customer_name",
        source="customers",
        extract="customer_name",
    )

    demand = converter.convert(config)
    field = demand.fields["customer_name"]
    assert isinstance(field, FieldIr)
    assert field.lookup_steps is not None
    assert len(field.lookup_steps) == 1


def test_converter_resolves_relation_reference() -> None:
    converter = ConfigToIRConverter(
        resolver=SecurePythonReferenceResolver(allowed_modules=frozenset(["scalim_misc"])),
    )
    config = copy.deepcopy(_base_converter_config())
    config.source_fields["customer_name"] = SourceFieldConfig(
        field_id="customer_name",
        source="customers",
        extract="customer_name",
        relation="r1",
    )

    demand = converter.convert(config)
    field = demand.fields["customer_name"]
    assert isinstance(field, FieldIr)
    assert field.lookup_steps is not None
    assert len(field.lookup_steps) == 1
