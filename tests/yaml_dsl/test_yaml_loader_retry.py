from pathlib import Path

import pytest

from scalim.dsl.by_yaml._internal.config_parsing.error_envelope import ScalimYamlValidationError
from scalim.dsl.by_yaml import compile
from scalim.execution.loader_retry import LoaderRetryPoliciesSpec, LoaderRetryPolicySpec


def test_yaml_retry_is_rejected_with_migration_guidance(tmp_path: Path) -> None:
    yaml_text = """
name: retry_yaml

retry:
  enabled: true
main_source:
  source_id: orders
  loader: "tests.fixtures.loader_retry_allowlist_mod:load_orders"
  fields:
    order_id:
      extract: order_id
""".lstrip()

    yaml_path = tmp_path / "demand.yaml"
    yaml_path.write_text(yaml_text, encoding="utf-8")

    with pytest.raises(ScalimYamlValidationError) as excinfo:
        _ = compile(str(yaml_path), allowed_modules=frozenset(["tests.fixtures.loader_retry_allowlist_mod"]))

    assert any(env.path == "retry" for env in excinfo.value.errors)


def test_yaml_retry_driver_injection_can_provide_should_retry(tmp_path: Path) -> None:
    from tests.fixtures import loader_retry_allowlist_mod as mod

    yaml_text = """
name: retry_yaml
main_source:
  source_id: orders
  loader: "tests.fixtures.loader_retry_allowlist_mod:load_orders"
  fields:
    order_id:
      extract: order_id
""".lstrip()
    yaml_path = tmp_path / "demand.yaml"
    yaml_path.write_text(yaml_text, encoding="utf-8")

    compilation = compile(
        str(yaml_path),
        allowed_modules=frozenset(["tests.fixtures.loader_retry_allowlist_mod"]),
        loader_retry=LoaderRetryPoliciesSpec(default=LoaderRetryPolicySpec(enabled=True, should_retry=mod.should_retry, max_attempts=5)),
    )
    request = compilation.request

    assert request.loader_retry is not None
    assert request.loader_retry.default.enabled is True
    assert request.loader_retry.default.should_retry is mod.should_retry
    assert request.loader_retry.default.max_attempts == 5


def test_driver_retry_enabled_without_should_retry_is_rejected(tmp_path: Path) -> None:
    yaml_text = """
name: retry_yaml
main_source:
  source_id: orders
  loader: "tests.fixtures.loader_retry_allowlist_mod:load_orders"
  fields:
    order_id:
      extract: order_id
""".lstrip()
    yaml_path = tmp_path / "demand.yaml"
    yaml_path.write_text(yaml_text, encoding="utf-8")

    with pytest.raises(ValueError, match="requires should_retry"):
        _ = compile(
            str(yaml_path),
            allowed_modules=frozenset(["tests.fixtures.loader_retry_allowlist_mod"]),
            loader_retry=LoaderRetryPoliciesSpec(default=LoaderRetryPolicySpec(enabled=True)),
        )


def test_yaml_retry_driver_by_loader_unknown_key_is_rejected(tmp_path: Path) -> None:
    yaml_text = """
name: retry_yaml
main_source:
  source_id: orders
  loader: "tests.fixtures.loader_retry_allowlist_mod:load_orders"
  fields:
    order_id:
      extract: order_id
""".lstrip()
    yaml_path = tmp_path / "demand.yaml"
    yaml_path.write_text(yaml_text, encoding="utf-8")

    with pytest.raises(ValueError, match="Unknown loader_retry.by_loader keys"):
        _ = compile(
            str(yaml_path),
            allowed_modules=frozenset(["tests.fixtures.loader_retry_allowlist_mod"]),
            loader_retry=LoaderRetryPoliciesSpec(by_loader={"unknown": LoaderRetryPolicySpec(enabled=False)}),
        )


def test_yaml_retry_in_main_source_and_sources_is_rejected(tmp_path: Path) -> None:
    yaml_text = """
name: retry_yaml

main_source:
  source_id: orders
  loader: "tests.fixtures.loader_retry_allowlist_mod:load_orders"
  retry:
    enabled: true
  fields:
    order_id:
      extract: order_id

sources:
  customers:
    loader: "tests.fixtures.loader_retry_allowlist_mod:load_customers"
    key: customer_id
    retry:
      enabled: true
""".lstrip()
    yaml_path = tmp_path / "demand.yaml"
    yaml_path.write_text(yaml_text, encoding="utf-8")

    with pytest.raises(ScalimYamlValidationError) as excinfo:
        _ = compile(str(yaml_path), allowed_modules=frozenset(["tests.fixtures.loader_retry_allowlist_mod"]))

    assert any(env.path in {"main_source.retry", "sources.customers.retry"} for env in excinfo.value.errors)


def test_driver_retry_by_loader_overrides_are_applied(tmp_path: Path) -> None:
    from tests.fixtures import loader_retry_allowlist_mod as mod

    yaml_text = """
name: retry_yaml
main_source:
  source_id: orders
  loader: "tests.fixtures.loader_retry_allowlist_mod:load_orders"
  fields:
    order_id:
      extract: order_id
sources:
  customers:
    loader: "tests.fixtures.loader_retry_allowlist_mod:load_customers"
    key: customer_id
""".lstrip()
    yaml_path = tmp_path / "demand.yaml"
    yaml_path.write_text(yaml_text, encoding="utf-8")

    compilation = compile(
        str(yaml_path),
        allowed_modules=frozenset(["tests.fixtures.loader_retry_allowlist_mod"]),
        loader_retry=LoaderRetryPoliciesSpec(
            by_loader={
                "orders": LoaderRetryPolicySpec(enabled=True, should_retry=mod.should_retry, max_attempts=2),
                "customers": LoaderRetryPolicySpec(enabled=True, should_retry=mod.should_retry, max_attempts=3),
            }
        ),
    )
    request = compilation.request

    assert request.loader_retry is not None
    assert request.loader_retry.default.enabled is False
    assert set(request.loader_retry.by_loader.keys()) == {"customers", "orders"}


def test_driver_retry_disabled_override_is_noop_and_request_omits_policy(tmp_path: Path) -> None:
    yaml_text = """
name: retry_yaml
main_source:
  source_id: orders
  loader: "tests.fixtures.loader_retry_allowlist_mod:load_orders"
  fields:
    order_id:
      extract: order_id
""".lstrip()
    yaml_path = tmp_path / "demand.yaml"
    yaml_path.write_text(yaml_text, encoding="utf-8")

    compilation = compile(
        str(yaml_path),
        allowed_modules=frozenset(["tests.fixtures.loader_retry_allowlist_mod"]),
        loader_retry=LoaderRetryPoliciesSpec(default=LoaderRetryPolicySpec(enabled=False)),
    )
    assert compilation.request.loader_retry is None
