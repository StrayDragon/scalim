from pathlib import Path

import pytest

from scalim.dsl.yaml_dsl._internal.config_parsing.error_envelope import ScalimYamlValidationError
from scalim.dsl.yaml_dsl._internal.config_parsing.yaml_load import (
    build_yaml_location_index,
    error_loc_for_yaml_path,
    load_yaml_mapping_file,
    load_yaml_mapping_text,
    safe_yaml_parse_error_message,
)


def test_safe_yaml_parse_error_message_fallbacks_to_exception_type_name() -> None:
    assert safe_yaml_parse_error_message(ValueError("boom")) == "ValueError"


def test_load_yaml_mapping_text_detects_duplicate_keys_and_reports_loc() -> None:
    yaml_text = "a: 1\na: 2\n"
    with pytest.raises(ScalimYamlValidationError) as excinfo:
        _data, _locations, _lines = load_yaml_mapping_text(yaml_text, source_path="demo.yaml", detect_duplicate_keys=True)

    assert len(excinfo.value.errors) == 1
    env = excinfo.value.errors[0]
    assert env.code == "yaml_duplicate_key"
    assert env.source_path == "demo.yaml"
    assert env.path == "(root)"
    assert env.loc is not None
    assert env.loc.line == 2
    assert env.loc.column == 1


def test_load_yaml_mapping_text_allows_duplicate_keys_when_disabled() -> None:
    yaml_text = "a: 1\na: 2\n"
    data, _locations, _lines = load_yaml_mapping_text(yaml_text, source_path="demo.yaml", detect_duplicate_keys=False)
    assert data["a"] == 2


def test_load_yaml_mapping_text_reports_yaml_parse_error_with_loc() -> None:
    with pytest.raises(ScalimYamlValidationError) as excinfo:
        _data, _locations, _lines = load_yaml_mapping_text("name: [\n", source_path="demo.yaml")

    env = excinfo.value.errors[0]
    assert env.code == "yaml_parse_error"
    assert env.loc is not None
    assert env.loc.line >= 1
    assert env.loc.column >= 1


def test_load_yaml_mapping_text_wraps_unknown_exceptions(monkeypatch) -> None:
    import scalim.dsl.yaml_dsl._internal.config_parsing.yaml_load as yaml_load_mod

    def _boom(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("boom")

    monkeypatch.setattr(yaml_load_mod.YAML, "load", _boom)

    with pytest.raises(ScalimYamlValidationError) as excinfo:
        _data, _locations, _lines = yaml_load_mod.load_yaml_mapping_text(
            "a: 1\n",
            source_path="demo.yaml",
            detect_duplicate_keys=False,
        )

    env = excinfo.value.errors[0]
    assert env.code == "yaml_parse_error"
    assert "RuntimeError" in env.message


def test_error_loc_for_yaml_path_normalizes_arrow_prefix_and_honors_default_none() -> None:
    yaml_text = "root:\n  items:\n    - a\n"
    locations = build_yaml_location_index(yaml_text)

    arrow = error_loc_for_yaml_path("↳ root.items", locations)
    assert arrow is not None
    assert arrow.line == 2
    assert arrow.column == 3

    bracket = error_loc_for_yaml_path("root.items[0].unknown", locations)
    assert bracket is not None
    assert bracket.line == 3
    assert bracket.column == 7

    assert error_loc_for_yaml_path("missing.path", {}, default=None) is None
    fallback = error_loc_for_yaml_path("missing.path", {}, default=(7, 8))
    assert fallback is not None
    assert fallback.line == 7
    assert fallback.column == 8


def test_load_yaml_mapping_file_reports_read_error(tmp_path: Path) -> None:
    missing = tmp_path / "missing.yaml"

    with pytest.raises(ScalimYamlValidationError) as excinfo:
        _data, _locations, _lines = load_yaml_mapping_file(missing)

    env = excinfo.value.errors[0]
    assert env.code == "yaml_file_read_error"
    assert env.source_path == str(missing)
    assert env.path == "(file)"


def test_load_yaml_mapping_file_loads_mapping(tmp_path: Path) -> None:
    yaml_path = tmp_path / "ok.yaml"
    yaml_path.write_text("a: 1\n", encoding="utf-8")

    data, locations, lines = load_yaml_mapping_file(yaml_path)
    assert data["a"] == 1
    assert locations[""] == (1, 1)
    assert lines == ["a: 1"]


def test_load_yaml_mapping_text_normalizes_sequence_key_to_tuple() -> None:
    yaml_text = "? [a, b]\n: 1\n"
    data, _locations, _lines = load_yaml_mapping_text(yaml_text, source_path="demo.yaml", detect_duplicate_keys=True)
    assert data[("a", "b")] == 1


def test_load_yaml_mapping_text_rejects_unhashable_mapping_key() -> None:
    yaml_text = "? {a: b}\n: 1\n"
    with pytest.raises(ScalimYamlValidationError) as excinfo:
        _data, _locations, _lines = load_yaml_mapping_text(yaml_text, source_path="demo.yaml", detect_duplicate_keys=True)

    env = excinfo.value.errors[0]
    assert env.code == "yaml_parse_error"
    assert "TypeError" in env.message


def test_construct_ruamel_mapping_rejects_non_mapping_node() -> None:
    import scalim.dsl.yaml_dsl._internal.config_parsing.yaml_load as yaml_load_mod

    class _DummyNode:
        id = "sequence"

    with pytest.raises(TypeError) as excinfo:
        _ = yaml_load_mod._construct_ruamel_mapping(  # noqa: SLF001
            object(),
            _DummyNode(),
            deep=True,
            detect_duplicate_keys=True,
            source_path="demo.yaml",
        )
    assert "expected a mapping node" in str(excinfo.value)
