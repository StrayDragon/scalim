import importlib

import pytest

from scalim.dsl.by_yaml._internal.config_parsing.errors import ScalimConfigValidationError
from scalim.dsl.by_yaml._internal.config_parsing.validator import ConfigValidator
from tests.support.testing_utils import missing_optional_dependency


def _base_config() -> dict:
    return {
        "name": "demo",
        "main_source": {
            "source_id": "orders",
            "loader": "tests.fixtures.mock_loaders.mock_loader",
            "fields": {
                "order_id": {"extract": "order_id"},
                "customer_id": {"extract": "customer_id"},
            },
        },
        "sources": {
            "customers": {
                "loader": "tests.fixtures.mock_loaders.mock_loader",
                "key": "customer_id",
                "params": {"ids": {"$keys": {"as": "set"}}},
                "fields": {
                    "customer_name": {
                        "extract": "customer_name",
                        "relation": {"steps": [{"from": "orders.customer_id", "to": "customers.customer_id"}]},
                    }
                },
            }
        },
        "fields": {},
        "relations": {
            "orders_to_customers": {
                "steps": [{"from": "orders.customer_id", "to": "customers.customer_id"}],
            }
        },
    }


def _assert_validation_errors(config: dict, expected_substrings: list) -> None:
    validator = ConfigValidator()
    with pytest.raises(ScalimConfigValidationError) as exc:
        validator.validate(config)
    errors = exc.value.errors
    for substring in expected_substrings:
        assert any(substring in msg for msg in errors)


def _config_source_errors() -> dict:
    return {
        "name": "demo",
        "main_source": {
            "source_id": "orders",
            "loader": "tests.fixtures.mock_loaders.mock_loader",
            "fields": {"order_id": {"extract": "order_id"}},
        },
        "sources": {"s1": {}},
    }


def _config_legacy_fields() -> dict:
    return {
        "name": "demo",
        "main_source": {"source_id": "orders", "loader": "tests.fixtures.mock_loaders.mock_loader"},
        "sources": {"customers": {"loader": "tests.fixtures.mock_loaders.mock_loader", "pk": "customer_id"}},
        "fields": {"customer_name": {"from": "customers.name"}},
    }


def _config_relation_id_string() -> dict:
    config = _base_config()
    config["sources"]["customers"]["fields"]["customer_name"]["relation"] = "missing_relation"
    return config


def _config_relation_id_string_empty() -> dict:
    config = _base_config()
    config["sources"]["customers"]["fields"]["customer_name"]["relation"] = "   "
    return config


def _config_main_source_missing_fields() -> dict:
    return {
        "name": "demo",
        "main_source": {},
        "sources": {"customers": {"loader": "tests.fixtures.mock_loaders.mock_loader", "key": "customer_id"}},
    }


def _config_main_source_invalid_loader_reference() -> dict:
    return {
        "name": "demo",
        "main_source": {"source_id": "orders", "loader": "bad ref"},
        "sources": {},
    }


def _config_field_requires_via_when_no_path() -> dict:
    return {
        "name": "demo",
        "main_source": {"source_id": "orders", "loader": "tests.fixtures.mock_loaders.mock_loader"},
        "sources": {
            "customers": {
                "loader": "tests.fixtures.mock_loaders.mock_loader",
                "key": "customer_id",
                "params": {"ids": {"$keys": {"as": "set"}}},
                "fields": {"customer_name": {"extract": "customer_name"}},
            }
        },
    }


def _config_field_ambiguous_paths_requires_via() -> dict:
    config = _base_config()
    config["relations"] = {
        "r1": {"steps": [{"from": "orders.customer_id", "to": "customers.customer_id"}]},
        "r2": {"steps": [{"from": "orders.customer_id", "to": "customers.customer_id"}]},
    }
    config["sources"]["customers"]["fields"]["customer_name"].pop("relation")
    return config


def _config_relation_step_to_bind_is_rejected() -> dict:
    config = _base_config()
    config["relations"]["orders_to_customers"]["steps"][0]["to_bind"] = {"use_keys": {"param": "ids"}}
    return config


def _config_lookup_cast_invalid_name() -> dict:
    config = _base_config()
    config["relations"]["orders_to_customers"]["steps"][0]["lookup_cast"] = {"name": "bad"}
    return config


def _config_derived_field_depends_on_invalid_type() -> dict:
    config = _base_config()
    config["fields"]["profit"] = {"compute": "amount - cost", "depends_on": "amount"}
    return config


def _config_derived_field_compute_invalid_syntax() -> dict:
    config = _base_config()
    config["fields"]["profit"] = {"compute": "amount +"}
    return config


def _config_derived_field_compute_unknown_name() -> dict:
    config = _base_config()
    config["fields"]["profit"] = {"compute": "amount + cost"}
    return config


@pytest.mark.parametrize(
    "config_factory,expected_substrings",
    [
        (
            _config_source_errors,
            [
                "missing required field 'loader'",
                "missing required field 'key'",
            ],
        ),
        (
            _config_legacy_fields,
            [
                "Legacy field 'sources.customers.pk'",
                "Legacy field 'fields.customer_name.from'",
            ],
        ),
        (_config_relation_id_string, ["unknown relation id", "missing 'relations.missing_relation'"]),
        (_config_relation_id_string_empty, ["non-empty relation id"]),
        (
            _config_main_source_missing_fields,
            [
                "Main source missing required field 'source_id'",
                "Main source missing required field 'loader'",
            ],
        ),
        (_config_main_source_invalid_loader_reference, ["主数据源的 loader 引用"]),
        (_config_field_requires_via_when_no_path, ["has no relation path"]),
        (_config_field_ambiguous_paths_requires_via, ["ambiguous relation paths"]),
        (_config_relation_step_to_bind_is_rejected, ["to_bind"]),
        (_config_lookup_cast_invalid_name, ["lookup_cast has invalid name"]),
        (_config_derived_field_depends_on_invalid_type, ["does not allow 'depends_on'"]),
        (_config_derived_field_compute_invalid_syntax, ["invalid compute expression"]),
        (_config_derived_field_compute_unknown_name, ["depends on unknown field 'amount'"]),
    ],
    ids=[
        "source-errors",
        "legacy-fields",
        "relation-id-string",
        "relation-id-string-empty",
        "main-source-missing-fields",
        "main-source-invalid-loader",
        "field-requires-via",
        "field-ambiguous-paths",
        "relation-step-to-bind",
        "lookup-cast-invalid-name",
        "derived-depends-on-invalid-type",
        "derived-compute-invalid-syntax",
        "derived-compute-unknown-field",
    ],
)
def test_validator_reports_errors(config_factory, expected_substrings) -> None:
    _assert_validation_errors(config_factory(), expected_substrings)


def test_validator_errors_include_paths() -> None:
    validator = ConfigValidator()
    with pytest.raises(ScalimConfigValidationError) as exc:
        validator.validate(_config_main_source_invalid_loader_reference())
    assert any(msg.startswith("main_source.loader: ") for msg in exc.value.errors)


def test_validator_errors_are_truncated_but_issues_are_preserved() -> None:
    validator = ConfigValidator(max_validation_error_lines=1)
    with pytest.raises(ScalimConfigValidationError) as exc:
        validator.validate(_config_source_errors())

    error_issues = [issue for issue in exc.value.issues if getattr(issue, "severity", None) == "error"]
    assert len(error_issues) > 1
    assert len(exc.value.errors) == 1
    assert "Configuration validation failed with {} error(s)".format(len(error_issues)) in str(exc.value)
    assert len(exc.value.issues) > len(exc.value.errors)


def test_validator_derived_field_compute_allows_not() -> None:
    validator = ConfigValidator()
    config = _base_config()
    config["main_source"]["fields"]["is_active"] = {"extract": "is_active"}
    config["fields"]["inactive"] = {"compute": "not is_active"}

    validator.validate(config)


def test_validator_import_error_path(monkeypatch) -> None:
    import scalim.dsl.by_yaml._internal.config_parsing.validator as validator_mod

    with missing_optional_dependency(monkeypatch, "jsonschema"):
        reloaded = importlib.reload(validator_mod)
        assert reloaded.HAS_JSONSCHEMA is False
        assert reloaded.jsonschema is None
    importlib.reload(validator_mod)


def test_validator_rejects_non_positive_max_validation_error_lines() -> None:
    with pytest.raises(ValueError, match="max_validation_error_lines must be >= 1"):
        _ = ConfigValidator(max_validation_error_lines=0)
