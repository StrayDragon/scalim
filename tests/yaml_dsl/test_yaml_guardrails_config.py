import pytest

from scalim.dsl.by_yaml._internal.config_parsing.errors import ScalimConfigValidationError
from scalim.dsl.by_yaml._internal.config_parsing.error_envelope import ScalimYamlValidationError
from scalim.dsl.by_yaml._internal.config_parsing.loader import YamlDemandLoader
from scalim.dsl.by_yaml._internal.config_parsing.validator import ConfigValidator


def _base_config() -> dict:
    return {
        "name": "demo",
        "main_source": {
            "source_id": "orders",
            "loader": "tests.fixtures.mock_loaders:mock_loader",
            "fields": {
                "order_id": {"extract": "order_id"},
                "customer_id": {"extract": "customer_id"},
            },
        },
        "sources": {},
    }


def test_yaml_guardrails_key_is_rejected_by_validator() -> None:
    validator = ConfigValidator()
    config = _base_config()
    config["guardrails"] = {
        "enabled": True,
        "mode": "fast_fail",
        "loader": {"validate_result": True, "required_fields": ["order_id"], "on_transform_error": "quiet"},
        "relations": {"null_key_max_rate": 0.1, "type_error_max_rate": 0.0},
        "compute": {"on_error": "fast_fail"},
    }

    with pytest.raises(ScalimConfigValidationError) as excinfo:
        validator.validate(config)

    assert any(issue.path == "guardrails" for issue in excinfo.value.issues)


def test_yaml_guardrails_key_is_rejected_by_loader_load_string() -> None:
    loader = YamlDemandLoader()
    yaml_text = """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders:mock_loader
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
    with pytest.raises(ScalimYamlValidationError) as excinfo:
        _ = loader.load_string(yaml_text)

    assert any(env.path == "guardrails" for env in excinfo.value.errors)
