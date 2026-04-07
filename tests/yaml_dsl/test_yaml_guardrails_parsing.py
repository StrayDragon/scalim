from pathlib import Path

import pytest

from scalim.dsl.yaml_dsl import RunOptions, compile
from scalim.dsl.yaml_dsl._internal.config_parsing.loader import YamlDemandLoader
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


def test_yaml_guardrails_is_not_parsed_even_without_validation() -> None:
    config = _load_without_validation(
        _base_yaml(
            """
guardrails:
  enabled: true
  mode: fast_fail
  loader:
    validate_result: true
    required_fields: [order_id]
"""
        )
    )
    assert config.guardrails is None


def test_runtime_guardrails_injection_sets_request_guardrails(tmp_path: Path) -> None:
    yaml_path = tmp_path / "demand.yaml"
    yaml_path.write_text(_base_yaml(), encoding="utf-8")

    guardrails = GuardrailsPolicy(enabled=True, mode="quiet")
    compilation = compile(
        str(yaml_path),
        options=RunOptions(
            allowed_modules=frozenset(["tests.fixtures.mock_loaders"]),
            guardrails=guardrails,
        ),
    )
    assert compilation.request.guardrails == guardrails
