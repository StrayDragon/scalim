import textwrap

import pytest

import scalim_yaml_dsl_lsp.core as editor_semantics


def _pos(text: str, needle: str, *, offset: int = 0) -> editor_semantics.EditorPosition:
    idx = text.index(needle) + int(offset)
    line = text.count("\n", 0, idx) + 1
    line_start = text.rfind("\n", 0, idx)
    if line_start == -1:
        line_start = 0
    else:
        line_start += 1
    column = idx - line_start + 1
    return editor_semantics.EditorPosition(line=int(line), column=int(column))


def _range_for(text: str, needle: str) -> editor_semantics.EditorRange:
    start = _pos(text, needle, offset=0)
    end = editor_semantics.EditorPosition(line=start.line, column=start.column + len(needle))
    return editor_semantics.EditorRange(start=start, end=end)


@pytest.mark.parametrize(
    ("yaml_value", "expected_reference"),
    [
        ("pkg.mod:fn", "pkg.mod:fn"),
        ("pkg.mod.fn", "pkg.mod.fn"),
        ('"pkg.mod:fn"', "pkg.mod:fn"),
    ],
)
def test_cursor_extraction_loader_supports_quoted_and_unquoted(yaml_value: str, expected_reference: str) -> None:
    yaml_text = textwrap.dedent(
        f"""\
        name: demo
        main_source:
          source_id: orders
          loader: {yaml_value}
        sources: {{}}
        """
    )
    pos = _pos(yaml_text, expected_reference, offset=2)
    result = editor_semantics.extract_yaml_dsl_python_reference_by_cursor(yaml_text, pos)
    assert result.yaml_path == "main_source.loader"
    assert result.reference == expected_reference
    assert result.range == _range_for(yaml_text, expected_reference)
    assert result.warnings == ()


def test_cursor_extraction_call_by_parses_head_and_range() -> None:
    yaml_text = textwrap.dedent(
        """\
        name: demo
        call_by: "pkg.mod:fn(a=1)"
        sources: {}
        """
    )
    pos = _pos(yaml_text, "pkg.mod:fn", offset=2)
    result = editor_semantics.extract_yaml_dsl_python_reference_by_cursor(yaml_text, pos)
    assert result.yaml_path == "call_by"
    assert result.reference == "pkg.mod:fn"
    assert result.range == _range_for(yaml_text, "pkg.mod:fn")

    args_pos = _pos(yaml_text, "a=1", offset=1)
    result2 = editor_semantics.extract_yaml_dsl_python_reference_by_cursor(yaml_text, args_pos)
    assert result2.reference == ""
    assert result2.range is None


def test_cursor_extraction_retry_should_retry_supports_nested_path() -> None:
    yaml_text = textwrap.dedent(
        """\
        retry:
          should_retry: pkg.mod:pred
        """
    )
    pos = _pos(yaml_text, "pkg.mod:pred", offset=2)
    result = editor_semantics.extract_yaml_dsl_python_reference_by_cursor(yaml_text, pos)
    assert result.yaml_path == "retry.should_retry"
    assert result.reference == "pkg.mod:pred"
    assert result.range == _range_for(yaml_text, "pkg.mod:pred")


def test_cursor_extraction_returns_empty_when_cursor_not_in_value() -> None:
    yaml_text = "loader: pkg.mod:fn\n"
    pos = _pos(yaml_text, "loader", offset=2)
    result = editor_semantics.extract_yaml_dsl_python_reference_by_cursor(yaml_text, pos)
    assert result.reference == ""
    assert result.range is None


def test_cursor_extraction_degrades_on_yaml_parse_error() -> None:
    yaml_text = "name: [\n"
    result = editor_semantics.extract_yaml_dsl_python_reference_by_cursor(
        yaml_text,
        editor_semantics.EditorPosition(line=1, column=1),
    )
    assert result.reference == ""
    assert result.range is None
    assert result.warnings
