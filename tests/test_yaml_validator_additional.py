import pytest

import scalim.dsl.by_yaml.config_parsing.validator as validator_module


def _base_config() -> dict:
    return {
        "name": "demo",
        "main_source": {
            "source_id": "orders",
            "loader": "tests.conftest.mock_loader",
            "fields": {"order_id": {"extract": "order_id"}},
        },
        "sources": {},
    }


def _ambiguous_sources_config() -> dict:
    return {
        "name": "demo",
        "main_source": {"source_id": "orders", "loader": "tests.conftest.mock_loader"},
        "sources": {
            "s1": {
                "loader": "tests.conftest.mock_loader",
                "key": "id",
                "bind": {"use_keys": {"param": "ids"}},
                "fields": {
                    "name": {
                        "extract": "name",
                        "relation": {"steps": [{"from": "orders.id", "to": "s1.id"}]},
                    }
                },
            },
            "s2": {
                "loader": "tests.conftest.mock_loader",
                "key": "id",
                "bind": {"use_keys": {"param": "ids"}},
                "fields": {
                    "name": {
                        "extract": "name",
                        "relation": {"steps": [{"from": "orders.id", "to": "s2.id"}]},
                    }
                },
            },
        },
    }


def _assert_validation_errors(config: dict, *expected_messages: str) -> None:
    validator = validator_module.ConfigValidator()

    with pytest.raises(validator_module.ConfigValidationError) as exc:
        validator.validate(config)

    errors = exc.value.errors
    for message in expected_messages:
        assert any(message in msg for msg in errors)


def test_validator_requires_output_fields_for_ambiguous_defs() -> None:
    config = _ambiguous_sources_config()
    config["output"] = {}
    _assert_validation_errors(config, "output.fields is required to disambiguate field 'name'")


def test_validator_output_fields_must_be_list() -> None:
    config = _base_config()
    config["output"] = {"fields": "order_id"}
    _assert_validation_errors(config, "output.fields must be a list")


def test_validator_output_fields_entry_invalid_type() -> None:
    config = _base_config()
    config["output"] = {"fields": [1]}
    _assert_validation_errors(config, "output.fields[0] must be explicit field object (field_id or field) or alias")


def test_validator_output_fields_requires_explicit_object_or_alias() -> None:
    config = _ambiguous_sources_config()
    config["output"] = {"fields": [{"name": {"name": "Name Override"}}]}
    _assert_validation_errors(config, "output.fields[0] must be explicit field object (field_id or field) or alias")


def test_validator_output_fields_signature_no_match() -> None:
    config = _base_config()
    config["output"] = {"fields": [{"field": "missing", "name": "Missing"}]}
    _assert_validation_errors(config, "Output field data_key 'missing' not found")


def test_validator_output_fields_data_key_ambiguous_requires_source() -> None:
    config = {
        "name": "demo",
        "main_source": {
            "source_id": "orders",
            "loader": "tests.conftest.mock_loader",
            "fields": {"order_id": {"extract": "id"}},
        },
        "sources": {
            "customers": {
                "loader": "tests.conftest.mock_loader",
                "key": "id",
                "bind": {"use_keys": {"param": "ids"}},
                "fields": {
                    "customer_id": {
                        "extract": "id",
                        "relation": {"steps": [{"from": "orders.order_id", "to": "customers.id"}]},
                    }
                },
            }
        },
        "output": {"fields": [{"field": "id"}]},
    }

    _assert_validation_errors(config, "Output field data_key 'id' is ambiguous; add source or use field_id")


def test_validator_output_fields_data_key_with_source() -> None:
    validator = validator_module.ConfigValidator()
    config = {
        "name": "demo",
        "main_source": {
            "source_id": "orders",
            "loader": "tests.conftest.mock_loader",
            "fields": {"order_id": {"extract": "id"}},
        },
        "sources": {
            "customers": {
                "loader": "tests.conftest.mock_loader",
                "key": "id",
                "bind": {"use_keys": {"param": "ids"}},
                "fields": {
                    "customer_id": {
                        "extract": "id",
                        "relation": {"steps": [{"from": "orders.order_id", "to": "customers.id"}]},
                    }
                },
            }
        },
        "output": {"fields": [{"field": "id", "source": "customers"}]},
    }

    validator.validate(config)


def test_validator_rejects_derived_source_field_id_overlap() -> None:
    config = _base_config()
    config["fields"] = {"order_id": {"compute": "1"}}
    _assert_validation_errors(config, "Field 'order_id' is defined as both source and derived")


def test_validator_source_field_value_cast_and_relation_type() -> None:
    config = _base_config()
    config["main_source"]["fields"] = {
        "bad_cast": {"extract": "order_id", "value_cast": "bad"},
        "bad_relation": {"extract": "order_id", "relation": []},
    }
    _assert_validation_errors(
        config,
        "invalid value_cast",
        "relation must be {steps: [...]",
    )


def test_validator_bind_and_lookup_cast_validation() -> None:
    config = {
        "name": "demo",
        "main_source": {"source_id": "orders", "loader": "tests.conftest.mock_loader"},
        "sources": {
            "s1": {
                "loader": "tests.conftest.mock_loader",
                "key": "id",
                "bind": {"use_keys": {"param": "", "as": "bad"}},
                "lookup_cast": "bad",
            }
        },
    }
    _assert_validation_errors(
        config,
        "bind.use_keys missing required 'param'",
        "bind.use_keys has invalid as",
        "lookup_cast must be a dictionary",
    )


def test_validator_bind_requires_use_branch() -> None:
    config = _base_config()
    config["sources"] = {
        "s1": {
            "loader": "tests.conftest.mock_loader",
            "key": "id",
            "bind": {"param": "ids"},
            "fields": {
                "name": {
                    "extract": "name",
                    "relation": {"steps": [{"from": "orders.order_id", "to": "s1.id"}]},
                }
            },
        }
    }
    _assert_validation_errors(config, "bind must set one of 'use_rows' or 'use_keys'")


def test_validator_bind_rejects_both_use_branches() -> None:
    config = _base_config()
    config["sources"] = {
        "s1": {
            "loader": "tests.conftest.mock_loader",
            "key": "id",
            "bind": {"use_rows": {"param": "rows"}, "use_keys": {"param": "ids"}},
            "fields": {
                "name": {
                    "extract": "name",
                    "relation": {"steps": [{"from": "orders.order_id", "to": "s1.id"}]},
                }
            },
        }
    }
    _assert_validation_errors(config, "bind must not set both 'use_rows' and 'use_keys'")


def test_validator_main_source_order_by_valid() -> None:
    config = _base_config()
    config["main_source"]["order_by"] = ["order_id", "-order_id"]
    validator = validator_module.ConfigValidator()
    validator.validate(config)


def test_validator_main_source_order_by_invalid_entries() -> None:
    config = _base_config()
    config["main_source"]["order_by"] = "order_id"
    _assert_validation_errors(config, "main_source.order_by")

    config = _base_config()
    config["main_source"]["order_by"] = [1]
    _assert_validation_errors(config, "main_source.order_by[0]")

    config = _base_config()
    config["main_source"]["order_by"] = ["-"]
    _assert_validation_errors(config, "must be a non-empty string")

    config = _base_config()
    config["main_source"]["order_by"] = ["missing_field"]
    _assert_validation_errors(config, "not found in main_source.fields")


def test_validator_to_bind_rejects_both_use_branches() -> None:
    config = _base_config()
    config["sources"] = {"s1": {"loader": "tests.conftest.mock_loader", "key": "id"}}
    config["relations"] = {
        "r1": {
            "steps": [
                {
                    "from": "orders.order_id",
                    "to": "s1.id",
                    "to_bind": {"use_rows": {"param": "rows"}, "use_keys": {"param": "ids"}},
                }
            ]
        }
    }
    _assert_validation_errors(config, "bind must not set both 'use_rows' and 'use_keys'")


def test_validator_bind_use_rows_requires_dict() -> None:
    config = _base_config()
    config["sources"] = {
        "s1": {
            "loader": "tests.conftest.mock_loader",
            "key": "id",
            "bind": {"use_rows": "rows"},
            "fields": {},
        }
    }
    _assert_validation_errors(config, "bind.use_rows must be a dictionary")


def test_validator_bind_use_rows_requires_param() -> None:
    config = _base_config()
    config["sources"] = {
        "s1": {
            "loader": "tests.conftest.mock_loader",
            "key": "id",
            "bind": {"use_rows": {}},
            "fields": {},
        }
    }
    _assert_validation_errors(config, "bind.use_rows missing required 'param'")


def test_validator_bind_use_rows_invalid_cache_mode() -> None:
    config = _base_config()
    config["sources"] = {
        "s1": {
            "loader": "tests.conftest.mock_loader",
            "key": "id",
            "bind": {"use_rows": {"param": "rows", "cache_mode": "forever"}},
            "fields": {},
        }
    }
    _assert_validation_errors(config, "bind.use_rows has invalid cache_mode")


def test_validator_bind_use_keys_requires_dict() -> None:
    config = _base_config()
    config["sources"] = {
        "s1": {
            "loader": "tests.conftest.mock_loader",
            "key": "id",
            "bind": {"use_keys": "ids"},
            "fields": {},
        }
    }
    _assert_validation_errors(config, "bind.use_keys must be a dictionary")


def test_validator_bind_use_keys_unknown_keys() -> None:
    config = _base_config()
    config["sources"] = {
        "s1": {
            "loader": "tests.conftest.mock_loader",
            "key": "id",
            "bind": {"use_keys": {"param": "ids", "extra": "x"}},
            "fields": {},
        }
    }
    _assert_validation_errors(config, "bind.use_keys has unknown keys")


def test_validator_bind_rejects_rows_as() -> None:
    config = {
        "name": "demo",
        "main_source": {"source_id": "orders", "loader": "tests.conftest.mock_loader"},
        "sources": {
            "s1": {
                "loader": "tests.conftest.mock_loader",
                "key": "id",
                "bind": {"use_rows": {"param": "ids", "as": "set"}},
            }
        },
    }
    _assert_validation_errors(config, "bind.use_rows has unknown keys")


def test_validator_to_bind_rejects_rows_as() -> None:
    config = _base_config()
    config["sources"] = {"customers": {"loader": "tests.conftest.mock_loader", "key": "customer_id"}}
    config["relations"] = {
        "orders_to_customers": {
            "steps": [
                {
                    "from": "orders.customer_id",
                    "to": "customers.customer_id",
                    "to_bind": {"use_rows": {"param": "ids", "as": "set"}},
                }
            ]
        }
    }
    _assert_validation_errors(config, "bind.use_rows has unknown keys")
