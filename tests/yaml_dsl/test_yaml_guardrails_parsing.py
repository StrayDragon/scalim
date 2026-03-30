from typing import Any

import pytest

from scalim.dsl.by_yaml.config_parsing.loader import YamlDemandLoader
from scalim.dsl.by_yaml.runtime import compiler as compiler_module
from scalim.dsl.by_yaml.schema_dsl.models import (
    GuardrailsComputeConfig,
    GuardrailsConfig,
    GuardrailsLoaderConfig,
    GuardrailsRelationsConfig,
)
from scalim.execution.guardrails import GuardrailsPolicy


class _NoValidate:
    def __bool__(self) -> bool:
        return False


def _load_without_validation(yaml_text: str):  # type: ignore[no-untyped-def]
    loader = YamlDemandLoader()
    loader._validator = _NoValidate()  # type: ignore[attr-defined]
    return loader.load_string(yaml_text)


def _base_yaml(extra: str = "") -> str:
    return (
        """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders:mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
"""
        + extra
    )


def test_yaml_parser_guardrails_loader_ignores_non_mapping_loader_block() -> None:
    config = _load_without_validation(
        _base_yaml(
            """
guardrails:
  enabled: true
  mode: fast_fail
  loader: 1
"""
        )
    )
    assert config.guardrails is not None
    assert config.guardrails.loader is None


def test_yaml_parser_guardrails_loader_required_fields_default_empty_tuple() -> None:
    config = _load_without_validation(
        _base_yaml(
            """
guardrails:
  enabled: true
  mode: fast_fail
  loader:
    validate_result: true
"""
        )
    )
    assert config.guardrails is not None
    assert config.guardrails.loader is not None
    assert config.guardrails.loader.required_fields == ()


def test_yaml_parser_guardrails_loader_required_fields_string_resolves() -> None:
    loader = YamlDemandLoader()
    config = loader.load_string(
        _base_yaml(
            """
guardrails:
  enabled: true
  mode: fast_fail
  loader:
    required_fields:
      - order_id
"""
        )
    )
    assert config.guardrails is not None
    assert config.guardrails.loader is not None
    assert config.guardrails.loader.required_fields == ("order_id",)


def test_yaml_parser_guardrails_loader_required_fields_rejects_non_list() -> None:
    with pytest.raises(TypeError, match="guardrails\\.loader\\.required_fields must be a list"):
        _ = _load_without_validation(
            _base_yaml(
                """
guardrails:
  enabled: true
  mode: fast_fail
  loader:
    required_fields: order_id
"""
            )
        )


def test_yaml_parser_guardrails_loader_required_fields_dict_must_be_yaml_alias() -> None:
    with pytest.raises(ValueError, match="guardrails\\.loader\\.required_fields\\[0\\] must be field_id string or YAML alias"):
        _ = _load_without_validation(
            _base_yaml(
                """
guardrails:
  enabled: true
  mode: fast_fail
  loader:
    required_fields:
      - {field: order_id}
"""
            )
        )


def test_yaml_parser_guardrails_loader_required_fields_rejects_bad_item_type() -> None:
    with pytest.raises(TypeError, match="guardrails\\.loader\\.required_fields\\[0\\] must be field_id string or YAML alias"):
        _ = _load_without_validation(
            _base_yaml(
                """
guardrails:
  enabled: true
  mode: fast_fail
  loader:
    required_fields:
      - 123
"""
            )
        )


def test_yaml_parser_guardrails_loader_required_fields_unknown_field_id_errors() -> None:
    loader = YamlDemandLoader()
    with pytest.raises(ValueError, match="references unknown field_id"):
        _ = loader.load_string(
            _base_yaml(
                """
guardrails:
  enabled: true
  mode: fast_fail
  loader:
    required_fields:
      - unknown
"""
            )
        )


def test_yaml_parser_guardrails_relations_parses_rates_float_and_none() -> None:
    loader = YamlDemandLoader()
    config = loader.load_string(
        _base_yaml(
            """
guardrails:
  enabled: true
  mode: quiet
  relations:
    null_key_max_rate: 0.1
"""
        )
    )
    assert config.guardrails is not None
    assert config.guardrails.relations is not None
    assert config.guardrails.relations.null_key_max_rate == 0.1
    assert config.guardrails.relations.type_error_max_rate is None


def test_yaml_parser_guardrails_relations_invalid_rate_returns_none() -> None:
    config = _load_without_validation(
        _base_yaml(
            """
guardrails:
  enabled: true
  mode: quiet
  relations:
    type_error_max_rate: bad
"""
        )
    )
    assert config.guardrails is not None
    assert config.guardrails.relations is not None
    assert config.guardrails.relations.type_error_max_rate is None


def test_yaml_parser_guardrails_compute_parses_on_error() -> None:
    loader = YamlDemandLoader()
    config = loader.load_string(
        _base_yaml(
            """
guardrails:
  enabled: true
  mode: fast_fail
  compute:
    on_error: quiet
"""
        )
    )
    assert config.guardrails is not None
    assert config.guardrails.compute is not None
    assert config.guardrails.compute.on_error == "quiet"


def test_yaml_parser_as_guardrail_mode_accepts_and_rejects() -> None:
    assert compiler_module._as_guardrail_mode("quiet") == "quiet"
    assert compiler_module._as_guardrail_mode("fast_fail") == "fast_fail"
    with pytest.raises(ValueError, match="Invalid guardrail mode"):
        _ = compiler_module._as_guardrail_mode("panic")


def test_yaml_parser_compile_guardrails_policy_from_config() -> None:
    cfg = GuardrailsConfig(
        enabled=True,
        mode="quiet",
        loader=GuardrailsLoaderConfig(
            validate_result=True,
            required_fields=("order_id",),
            on_transform_error="fast_fail",
        ),
        relations=GuardrailsRelationsConfig(null_key_max_rate=0.0, type_error_max_rate=None),
        compute=GuardrailsComputeConfig(on_error="quiet"),
    )
    policy = compiler_module._compile_guardrails_policy(cfg)
    assert isinstance(policy, GuardrailsPolicy)
    assert policy.enabled is True
    assert policy.mode == "quiet"
    assert policy.loader.validate_result is True
    assert policy.loader.required_fields == ("order_id",)
    assert policy.loader.on_transform_error == "fast_fail"
