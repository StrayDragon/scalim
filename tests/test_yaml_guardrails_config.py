import pytest

import scalim.dsl.by_yaml.config_parsing.validator as validator_module
from scalim.dsl.by_yaml.config_parsing.errors import ConfigValidationError
from scalim.dsl.by_yaml.config_parsing.loader import YamlDemandLoader
from scalim.dsl.by_yaml.config_parsing.validator import ConfigValidator, HAS_JSONSCHEMA


def _require_jsonschema() -> None:
    if not HAS_JSONSCHEMA or validator_module.jsonschema is None:
        pytest.skip("jsonschema not available")


def _base_config() -> dict:
    return {
        "name": "demo",
        "main_source": {
            "source_id": "orders",
            "loader": "tests.conftest:mock_loader",
            "fields": {
                "order_id": {"extract": "order_id"},
                "customer_id": {"extract": "customer_id"},
            },
        },
        "sources": {},
    }


def test_yaml_schema_accepts_guardrails_config() -> None:
    _require_jsonschema()
    validator = ConfigValidator()
    config = _base_config()
    config["guardrails"] = {
        "enabled": True,
        "mode": "fast_fail",
        "loader": {"validate_result": True, "required_fields": ["order_id"], "on_transform_error": "quiet"},
        "relations": {"null_key_max_rate": 0.1, "type_error_max_rate": 0.0},
        "compute": {"on_error": "fast_fail"},
    }

    validator.validate(config)


def test_yaml_schema_rejects_invalid_guardrails_mode() -> None:
    _require_jsonschema()
    validator = ConfigValidator()
    config = _base_config()
    config["guardrails"] = {"enabled": True, "mode": "panic"}

    with pytest.raises(ConfigValidationError):
        validator.validate(config)


def test_yaml_schema_rejects_guardrails_relations_fields_in_v1() -> None:
    _require_jsonschema()
    validator = ConfigValidator()
    config = _base_config()
    config["guardrails"] = {
        "enabled": True,
        "mode": "fast_fail",
        "relations": {"null_key_max_rate": 0.0, "fields": ["__ALL__"]},
    }

    with pytest.raises(ConfigValidationError):
        validator.validate(config)


def test_yaml_parser_resolves_guardrails_required_fields_alias() -> None:
    loader = YamlDemandLoader()
    yaml_text = """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest:mock_loader
  fields:
    order_id: &order_id
      extract: order_id
sources: {}
guardrails:
  enabled: true
  mode: fast_fail
  loader:
    required_fields:
      - *order_id
"""
    config = loader.load_string(yaml_text)
    assert config.guardrails is not None
    assert config.guardrails.loader is not None
    assert config.guardrails.loader.required_fields == ("order_id",)
