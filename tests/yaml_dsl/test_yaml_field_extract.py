from pathlib import Path

import pytest

from scalim.dsl.by_yaml import run
from scalim.dsl.by_yaml._internal.config_parsing.error_envelope import ScalimYamlValidationError
from scalim.dsl.by_yaml._internal.config_parsing.field_extract import (
    ScalimFieldExtractCompileError,
    compile_field_extract,
    derive_source_field_data_key,
)
from scalim.dsl.by_yaml._internal.config_parsing.loader import YamlDemandLoader
from scalim.execution.executor.helpers.field_access import extract_field_segments
from scalim.sinks import InMemoryRowSink


def test_compile_field_extract_parses_dot_and_bracket_segments() -> None:
    assert compile_field_extract("CustomerMark.clearn_reason_level") == ("CustomerMark", "clearn_reason_level")
    assert compile_field_extract("[1].clearn_reason_level") == (1, "clearn_reason_level")
    assert compile_field_extract('["a.b"].x') == ("a.b", "x")
    assert compile_field_extract("a[1].b") == ("a", 1, "b")
    assert compile_field_extract('["a\\\\b"]') == ("a\\b",)
    assert compile_field_extract('["a\\"b"]') == ('a"b',)


def test_compile_field_extract_does_not_cast_between_str_and_int_keys() -> None:
    assert compile_field_extract("[1].x") == (1, "x")
    assert compile_field_extract('["1"].x') == ("1", "x")


@pytest.mark.parametrize(
    "expr",
    [
        "",
        ".a",
        "a.",
        "a..b",
        "[",
        "[1",
        "[-1].x",
        "[ 1 ].x",
        "[1]x",
        "1",
        '["a\\q"]',
        '["a"',
        '["a',
        '["a\\',
    ],
    ids=[
        "empty",
        "leading-dot",
        "trailing-dot",
        "double-dot",
        "unclosed-bracket",
        "unclosed-int",
        "negative-int",
        "whitespace-int",
        "missing-sep-after-bracket",
        "bad-ident-start",
        "bad-escape",
        "unclosed-quote",
        "unclosed-quote-2",
        "unclosed-escape",
    ],
)
def test_compile_field_extract_rejects_invalid_expressions(expr: str) -> None:
    with pytest.raises(ScalimFieldExtractCompileError):
        compile_field_extract(expr)


def test_derive_source_field_data_key_only_for_flat_single_string_segment() -> None:
    assert derive_source_field_data_key(field_id="a", extract=None) == "a"
    assert derive_source_field_data_key(field_id="a", extract="b") == "b"
    assert derive_source_field_data_key(field_id="a", extract="a..b") == "a"
    assert derive_source_field_data_key(field_id="a", extract="b.c") == "a"
    assert derive_source_field_data_key(field_id="a", extract='["a.b"]') == "a.b"
    assert derive_source_field_data_key(field_id="a", extract="[1]") == "a"


def test_internal_extract_parsers_guard_out_of_bounds_inputs() -> None:
    from scalim.dsl.by_yaml._internal.config_parsing import field_extract as field_extract_module

    with pytest.raises(ScalimFieldExtractCompileError):
        field_extract_module._parse_identifier("a", 1)

    with pytest.raises(ScalimFieldExtractCompileError):
        field_extract_module._parse_bracket_int("]", 0)


def test_yaml_validator_rejects_invalid_extract_expression() -> None:
    loader = YamlDemandLoader()

    yaml_text = """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    bad:
      extract: "a..b"
""".lstrip()

    with pytest.raises(ScalimYamlValidationError) as exc:
        loader.load_string(yaml_text)

    assert any("invalid extract" in env.message for env in exc.value.errors)


def test_extract_field_segments_traverses_mapping_attr_and_getitem_and_rejects_list_index() -> None:
    data = {1: {"x": 2}, "a.b": {"x": 1}, "review_status": 0, "1": {"x": 10}}
    assert extract_field_segments(data, (1, "x")) == 2
    assert extract_field_segments(data, ("a.b", "x")) == 1
    assert extract_field_segments(data, ("review_status",)) == 0
    assert extract_field_segments(data, ("1", "x")) == 10

    assert extract_field_segments([{"x": 0}, {"x": 1}], (1, "x")) is None

    class Obj:
        def __init__(self) -> None:
            self.CustomerMark = {"clearn_reason_level": 2}

        def __getitem__(self, key):  # type: ignore[no-untyped-def]
            return {"x": 1}[key]

    assert extract_field_segments(Obj(), ("CustomerMark", "clearn_reason_level")) == 2
    assert extract_field_segments(Obj(), ("x",)) == 1


def test_yaml_run_extract_end_to_end_main_and_ref_load(tmp_path: Path) -> None:
    yaml_text = """
name: field_extract_integration
main_source:
  source_id: orders
  loader: "tests.fixtures.field_extract_loaders:load_orders"
  fields:
    order_id:
      extract: order_id
    good_level:
      extract: payload.CustomerMark.clearn_reason_level
    bad_level:
      extract: CustomerMark.clearn_reason_level
    list_index_x:
      extract: "list_payload[1].x"
    dotted_x:
      extract: '["a.b"].x'
    int_key_x:
      extract: "[1].x"
    str_key_x:
      extract: '["1"].x'

sources:
  clearn_reasons:
    loader: "tests.fixtures.field_extract_loaders:load_clearn_reasons"
    key: order_id
    params:
      order_id_set: {$keys: {as: set}}
    fields:
      customer_level:
        extract: "[1].clearn_reason_level"
        relation: &orders_to_clearn_reasons
          steps:
            - from: orders.order_id
              to: clearn_reasons.order_id
      operation_level:
        extract: "[2].clearn_reason_level"
        relation: *orders_to_clearn_reasons
      review_status:
        extract: review_status
        relation: *orders_to_clearn_reasons
""".lstrip()

    yaml_path = tmp_path / "demand.yaml"
    yaml_path.write_text(yaml_text, encoding="utf-8")

    sink = InMemoryRowSink()
    _ = run(
        str(yaml_path),
        allowed_modules=frozenset(["tests.fixtures.field_extract_loaders"]),
        sink=sink,
    )
    rows = sink.get_data()
    by_order_id = {row["order_id"]: row for row in rows}

    assert by_order_id[1]["good_level"] == 2
    assert by_order_id[1]["bad_level"] is None
    assert by_order_id[1]["list_index_x"] is None
    assert by_order_id[1]["dotted_x"] == 123
    assert by_order_id[1]["int_key_x"] == 2
    assert by_order_id[1]["str_key_x"] == 1
    assert by_order_id[1]["customer_level"] == 2
    assert by_order_id[1]["operation_level"] == 11
    assert by_order_id[1]["review_status"] == 0

    assert by_order_id[2]["good_level"] == 3
    assert by_order_id[2]["bad_level"] is None
    assert by_order_id[2]["list_index_x"] is None
    assert by_order_id[2]["dotted_x"] == 456
    assert by_order_id[2]["int_key_x"] == 20
    assert by_order_id[2]["str_key_x"] == 10
    assert by_order_id[2]["customer_level"] == 3
    assert by_order_id[2]["operation_level"] == 12
    assert by_order_id[2]["review_status"] == 0
