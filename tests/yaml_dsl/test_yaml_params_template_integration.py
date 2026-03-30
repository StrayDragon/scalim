from datetime import datetime
from pathlib import Path

import pytest

from scalim.dsl.by_yaml import run
from scalim.sinks import InMemoryRowSink

import tests.fixtures.params_template_loaders as loaders


def _write_yaml(tmp_path: Path, content: str) -> Path:
    yaml_path = tmp_path / "config.yaml"
    yaml_path.write_text(content, encoding="utf-8")
    return yaml_path


def test_run_renders_keys_directive_in_nested_params_and_passes_kwargs(tmp_path: Path) -> None:
    loaders.reset_calls()
    yaml_path = _write_yaml(
        tmp_path,
        """
name: t
main_source:
  source_id: orders
  loader: tests.fixtures.params_template_loaders:load_orders_main
  fields:
    order_id:
      extract: order_id
    customer_id:
      extract: customer_id

sources:
  customers:
    loader: tests.fixtures.params_template_loaders:load_customers_by_keys
    key: customer_id
    params:
      query:
        customer_ids: {$keys: {as: list}}
    fields:
      customer_name:
        extract: name
        relation:
          steps:
            - from: orders.customer_id
              to: customers.customer_id
""",
    )

    sink = InMemoryRowSink()
    _ = run(str(yaml_path), allowed_modules=frozenset(["tests.fixtures.params_template_loaders"]), sink=sink)

    assert loaders.CALL_COUNTS.get("customers_by_keys") == 1
    call_kwargs = loaders.CALL_KWARGS["customers_by_keys"][0]
    assert call_kwargs == {"query": {"customer_ids": [101, 102]}}


def test_run_passes_static_params_without_directives(tmp_path: Path) -> None:
    loaders.reset_calls()
    yaml_path = _write_yaml(
        tmp_path,
        """
name: t
main_source:
  source_id: orders
  loader: tests.fixtures.params_template_loaders:load_orders_main
  fields:
    order_id:
      extract: order_id
    customer_id:
      extract: customer_id

sources:
  customers:
    loader: tests.fixtures.params_template_loaders:load_customers_static
    key: customer_id
    params:
      group_by: level
    fields:
      customer_level:
        extract: level
        relation:
          steps:
            - from: orders.customer_id
              to: customers.customer_id
""",
    )

    sink = InMemoryRowSink()
    _ = run(str(yaml_path), allowed_modules=frozenset(["tests.fixtures.params_template_loaders"]), sink=sink)

    assert loaders.CALL_COUNTS.get("customers_static") == 1
    call_kwargs = loaders.CALL_KWARGS["customers_static"][0]
    assert call_kwargs == {"group_by": "level"}


@pytest.mark.parametrize(
    "cache_mode,expected_calls",
    [
        ("batch", 1),
        ("none", 2),
    ],
)
def test_rows_cache_mode_controls_relation_reuse(tmp_path: Path, cache_mode: str, expected_calls: int) -> None:
    loaders.reset_calls()
    yaml_path = _write_yaml(
        tmp_path,
        """
name: t
main_source:
  source_id: orders
  loader: tests.fixtures.params_template_loaders:load_orders_main
  fields:
    order_id:
      extract: order_id
    customer_id:
      extract: customer_id

sources:
  customers_rows:
    loader: tests.fixtures.params_template_loaders:load_customers_by_rows
    key: customer_id
    params:
      rows: {{$rows: {{cache_mode: {cache_mode}}}}}
    fields:
      customer_name:
        extract: name
        relation:
          steps:
            - from: orders.customer_id
              to: customers_rows.customer_id
      customer_level:
        extract: level
        relation:
          steps:
            - from: orders.customer_id
              to: customers_rows.customer_id
""".format(cache_mode=cache_mode),
    )

    sink = InMemoryRowSink()
    _ = run(str(yaml_path), allowed_modules=frozenset(["tests.fixtures.params_template_loaders"]), sink=sink)

    assert loaders.CALL_COUNTS.get("customers_by_rows") == expected_calls
    for call_kwargs in loaders.CALL_KWARGS.get("customers_by_rows", []):
        assert "rows" in call_kwargs
        rows = call_kwargs["rows"]
        assert isinstance(rows, list)
        assert any(isinstance(item, dict) and item.get("customer_id") in (101, 102) for item in rows)


def test_preload_forever_passes_params_when_non_empty_and_does_not_repeat_calls(tmp_path: Path) -> None:
    loaders.reset_calls()
    yaml_path = _write_yaml(
        tmp_path,
        """
name: t
main_source:
  source_id: orders
  loader: tests.fixtures.params_template_loaders:load_orders_main
  fields:
    order_id:
      extract: order_id

sources:
  refdata:
    loader: tests.fixtures.params_template_loaders:load_preload_refdata
    key: config_id
    cache_mode: preload_forever
    params:
      flag: 1
    fields:
      ref_value:
        extract: value
        relation:
          steps:
            - from: orders.order_id
              to: refdata.config_id
""",
    )

    sink = InMemoryRowSink()
    _ = run(str(yaml_path), allowed_modules=frozenset(["tests.fixtures.params_template_loaders"]), sink=sink)

    assert loaders.CALL_COUNTS.get("preload_refdata") == 1
    call_kwargs = loaders.CALL_KWARGS["preload_refdata"][0]
    assert call_kwargs.get("flag") == 1


def test_run_init_vars_injects_python_objects_into_main_source_params(tmp_path: Path) -> None:
    loaders.reset_calls()
    yaml_path = _write_yaml(
        tmp_path,
        """
name: t
main_source:
  source_id: orders
  loader: tests.fixtures.params_template_loaders:load_orders_main
  params:
    end_dt: {$init_var: end_dt}
  fields:
    order_id:
      extract: order_id
""",
    )

    end_dt = datetime(2024, 1, 31)
    sink = InMemoryRowSink()
    _ = run(
        str(yaml_path),
        allowed_modules=frozenset(["tests.fixtures.params_template_loaders"]),
        sink=sink,
        init_vars={"end_dt": end_dt},
    )

    assert loaders.CALL_COUNTS.get("orders") == 1
    call_kwargs = loaders.CALL_KWARGS["orders"][0]
    assert call_kwargs.get("end_dt") == end_dt


def test_run_init_vars_injects_values_into_source_params(tmp_path: Path) -> None:
    loaders.reset_calls()
    yaml_path = _write_yaml(
        tmp_path,
        """
name: t
main_source:
  source_id: orders
  loader: tests.fixtures.params_template_loaders:load_orders_main
  fields:
    order_id:
      extract: order_id
    customer_id:
      extract: customer_id

sources:
  customers:
    loader: tests.fixtures.params_template_loaders:load_customers_static
    key: customer_id
    params:
      group_by: {$init_var: group_by}
    fields:
      customer_level:
        extract: level
        relation:
          steps:
            - from: orders.customer_id
              to: customers.customer_id
""",
    )

    sink = InMemoryRowSink()
    _ = run(
        str(yaml_path),
        allowed_modules=frozenset(["tests.fixtures.params_template_loaders"]),
        sink=sink,
        init_vars={"group_by": "level"},
    )

    assert loaders.CALL_COUNTS.get("customers_static") == 1
    call_kwargs = loaders.CALL_KWARGS["customers_static"][0]
    assert call_kwargs.get("group_by") == "level"
