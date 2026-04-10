import pytest

import scalim.dsl.yaml_dsl.runtime._internal.conversion_sources as conversion_sources
from scalim.dsl.yaml_dsl.runtime.errors import ScalimConversionError
from scalim.spec.ir import BuiltinCallableIdIr


class _DummyCallByValue:
    def __init__(self, *, kind: str, value: object) -> None:
        self.kind = kind
        self.value = value


def test_parse_callable_ref_rejects_empty_reference() -> None:
    with pytest.raises(ScalimConversionError, match="must not be empty"):
        conversion_sources._parse_callable_ref("", context_label="case")  # type: ignore[attr-defined]


def test_parse_callable_ref_rejects_invalid_builtin_reference() -> None:
    with pytest.raises(ScalimConversionError, match="invalid builtin callable reference"):
        conversion_sources._parse_callable_ref("^bad-id", context_label="case")  # type: ignore[attr-defined]


def test_parse_callable_ref_accepts_builtin_reference() -> None:
    ref = conversion_sources._parse_callable_ref("^demo_id", context_label="case")  # type: ignore[attr-defined]
    assert ref == BuiltinCallableIdIr(callable_id="demo_id")


def test_parse_callable_ref_reports_reference_syntax_error() -> None:
    with pytest.raises(ScalimConversionError, match="点号形式引用"):
        conversion_sources._parse_callable_ref("bad", context_label="case")  # type: ignore[attr-defined]


def test_convert_call_by_value_ir_rejects_unknown_kind() -> None:
    bad = _DummyCallByValue(kind="weird", value="x")
    with pytest.raises(ScalimConversionError, match="unknown call_by value kind"):
        conversion_sources._convert_call_by_value_ir(bad, field_id="field")  # type: ignore[attr-defined]
