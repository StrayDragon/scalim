from pathlib import Path

import pytest

from scalim.dsl.by_yaml.config_parsing.error_envelope import ScalimYamlValidationError
from scalim.dsl.by_yaml import compile
from scalim.dsl.by_yaml.runtime.errors import ScalimResolverError
from scalim.execution.loader_retry import LoaderRetryPoliciesSpec, LoaderRetryPolicySpec


def test_yaml_retry_templates_anchor_merge_compiles(tmp_path: Path) -> None:
    yaml_text = """
name: retry_yaml

_templates:
  retry:
    db_default: &db_default
      enabled: true
      should_retry: "tests.loader_retry_allowlist_mod:should_retry"
      max_attempts: 5

retry:
  <<: *db_default
  max_attempts: 3

main_source:
  source_id: orders
  loader: "tests.loader_retry_allowlist_mod:load_orders"
  fields:
    order_id:
      extract: order_id
""".lstrip()

    yaml_path = tmp_path / "demand.yaml"
    yaml_path.write_text(yaml_text, encoding="utf-8")

    compilation = compile(
        str(yaml_path),
        allowed_modules=frozenset(["tests.loader_retry_allowlist_mod"]),
    )
    config = compilation.config
    request = compilation.request

    _ = config
    assert request.loader_retry is not None
    assert request.loader_retry.default.enabled is True
    assert request.loader_retry.default.max_attempts == 3
    assert request.loader_retry.by_loader == {}


def test_yaml_retry_should_retry_reference_requires_allowlist(tmp_path: Path) -> None:
    yaml_text = """
name: retry_yaml
retry:
  enabled: true
  should_retry: "tests.loader_retry_allowlist_mod:should_retry"
main_source:
  source_id: orders
  loader: "tests.loader_retry_allowlist_mod:load_orders"
  fields:
    order_id:
      extract: order_id
""".lstrip()
    yaml_path = tmp_path / "demand.yaml"
    yaml_path.write_text(yaml_text, encoding="utf-8")

    with pytest.raises(ScalimResolverError, match="allowed_modules"):
        _ = compile(
            str(yaml_path),
            allowed_modules=frozenset(["tests.resolver_allowlist_mod"]),
        )


def test_yaml_retry_driver_injection_can_provide_should_retry(tmp_path: Path) -> None:
    from tests import loader_retry_allowlist_mod as mod

    yaml_text = """
name: retry_yaml
retry:
  enabled: true
  max_attempts: 3
main_source:
  source_id: orders
  loader: "tests.loader_retry_allowlist_mod:load_orders"
  fields:
    order_id:
      extract: order_id
""".lstrip()
    yaml_path = tmp_path / "demand.yaml"
    yaml_path.write_text(yaml_text, encoding="utf-8")

    compilation = compile(
        str(yaml_path),
        allowed_modules=frozenset(["tests.loader_retry_allowlist_mod"]),
        loader_retry=LoaderRetryPoliciesSpec(default=LoaderRetryPolicySpec(should_retry=mod.should_retry, max_attempts=5)),
    )
    request = compilation.request

    assert request.loader_retry is not None
    assert request.loader_retry.default.enabled is True
    assert request.loader_retry.default.should_retry is mod.should_retry
    assert request.loader_retry.default.max_attempts == 5


def test_yaml_retry_enabled_without_should_retry_is_rejected(tmp_path: Path) -> None:
    yaml_text = """
name: retry_yaml
retry:
  enabled: true
main_source:
  source_id: orders
  loader: "tests.loader_retry_allowlist_mod:load_orders"
  fields:
    order_id:
      extract: order_id
""".lstrip()
    yaml_path = tmp_path / "demand.yaml"
    yaml_path.write_text(yaml_text, encoding="utf-8")

    with pytest.raises(ValueError, match="requires should_retry"):
        _ = compile(str(yaml_path), allowed_modules=frozenset(["tests.loader_retry_allowlist_mod"]))


def test_yaml_retry_driver_by_loader_unknown_key_is_rejected(tmp_path: Path) -> None:
    yaml_text = """
name: retry_yaml
main_source:
  source_id: orders
  loader: "tests.loader_retry_allowlist_mod:load_orders"
  fields:
    order_id:
      extract: order_id
""".lstrip()
    yaml_path = tmp_path / "demand.yaml"
    yaml_path.write_text(yaml_text, encoding="utf-8")

    with pytest.raises(ValueError, match="Unknown loader_retry.by_loader keys"):
        _ = compile(
            str(yaml_path),
            allowed_modules=frozenset(["tests.loader_retry_allowlist_mod"]),
            loader_retry=LoaderRetryPoliciesSpec(by_loader={"unknown": LoaderRetryPolicySpec(enabled=False)}),
        )


def test_yaml_retry_compiles_main_and_source_overrides_into_by_loader(tmp_path: Path) -> None:
    yaml_text = """
name: retry_yaml

_templates:
  retry:
    enabled_retry: &enabled_retry
      enabled: true
      should_retry: "tests.loader_retry_allowlist_mod:should_retry"

main_source:
  source_id: orders
  loader: "tests.loader_retry_allowlist_mod:load_orders"
  retry: *enabled_retry
  fields:
    order_id:
      extract: order_id

sources:
  customers:
    loader: "tests.loader_retry_allowlist_mod:load_customers"
    key: customer_id
    retry: *enabled_retry
""".lstrip()
    yaml_path = tmp_path / "demand.yaml"
    yaml_path.write_text(yaml_text, encoding="utf-8")

    compilation = compile(
        str(yaml_path),
        allowed_modules=frozenset(["tests.loader_retry_allowlist_mod"]),
    )
    request = compilation.request

    assert request.loader_retry is not None
    assert request.loader_retry.default.enabled is False
    assert set(request.loader_retry.by_loader.keys()) == {"customers", "orders"}


def test_yaml_templates_retry_invalid_enum_is_rejected_by_schema(tmp_path: Path) -> None:
    yaml_text = """
name: retry_yaml

_templates:
  retry:
    db_default:
      enabled: true
      should_retry: "tests.loader_retry_allowlist_mod:should_retry"
      backoff: "random"

main_source:
  source_id: orders
  loader: "tests.loader_retry_allowlist_mod:load_orders"
  fields:
    order_id:
      extract: order_id
""".lstrip()
    yaml_path = tmp_path / "demand.yaml"
    yaml_path.write_text(yaml_text, encoding="utf-8")

    with pytest.raises(ScalimYamlValidationError) as excinfo:
        _ = compile(str(yaml_path), allowed_modules=frozenset(["tests.loader_retry_allowlist_mod"]))

    assert any("_templates.retry.db_default.backoff" in env.path for env in excinfo.value.errors)
