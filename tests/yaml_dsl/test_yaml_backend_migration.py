import argparse
import re
from pathlib import Path
from typing import Iterable, List

import pytest

import scalim.cli.yaml_dsl as yaml_dsl
from scalim.dsl.yaml_dsl._internal.config_parsing.yaml_load import load_yaml_mapping_text
from scalim.vendor.yamlx import yaml as pyyaml


def _fixture_paths() -> List[Path]:
    repo_root = Path(__file__).resolve().parents[2]
    paths: List[Path] = []
    paths.extend(sorted((repo_root / "tests" / "fixtures").glob("*.yaml")))
    paths.extend(sorted((repo_root / "notebooks" / "marimo").glob("**/declared_yaml_dsl/*.yaml")))
    return paths


_INTELLIJ_SCHEMA_PATTERN = re.compile(r"^\\s*#\\s*\\$schema\\s*:\\s*(?P<ref>.*)\\s*$".replace("\\\\", "\\"))
_YAML_LANGUAGE_SERVER_SCHEMA_PATTERN = re.compile(
    r"^\\s*#\\s*yaml-language-server\\s*:\\s*\\$schema\\s*=\\s*(?P<ref>.*)\\s*$".replace("\\\\", "\\")
)


def _strip_schema_modelines(lines: Iterable[str], *, max_scan_lines: int = 10) -> List[str]:
    line_list = list(lines)
    scan_limit = min(len(line_list), int(max_scan_lines))
    indices = [
        idx
        for idx in range(scan_limit)
        if _INTELLIJ_SCHEMA_PATTERN.match(line_list[idx]) or _YAML_LANGUAGE_SERVER_SCHEMA_PATTERN.match(line_list[idx])
    ]
    if not indices:
        return line_list
    start = min(indices)
    end = max(indices)
    if end + 1 < len(line_list) and not line_list[end + 1].strip():
        end += 1
    return [*line_list[:start], *line_list[end + 1 :]]


def test_yaml_12_scalar_semantics_on_yes_no_off_are_strings() -> None:
    yaml_text = "a: on\nb: yes\nc: no\nd: off\n"
    data, _locations, _lines = load_yaml_mapping_text(yaml_text, source_path="(memory)")
    assert data["a"] == "on"
    assert data["b"] == "yes"
    assert data["c"] == "no"
    assert data["d"] == "off"


@pytest.mark.parametrize("path", _fixture_paths())
def test_yaml_corpus_ruamel_matches_vendored_pyyaml(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    data_ruamel, _locations, _lines = load_yaml_mapping_text(text, source_path=str(path))

    data_pyyaml = pyyaml.safe_load(text)
    assert isinstance(data_pyyaml, dict), "expected YAML root mapping: {}".format(str(path))

    assert data_ruamel == data_pyyaml


def test_upsert_lsp_comment_roundtrip_is_stable_on_canonical_fixture(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    fixture_path = repo_root / "tests" / "fixtures" / "yaml_roundtrip_canonical.yaml"
    original = fixture_path.read_text(encoding="utf-8")

    yaml_path = tmp_path / "canonical.yaml"
    yaml_path.write_text(original, encoding="utf-8")

    args = argparse.Namespace(
        schema_type="demand",
        schema_path="http://localhost:62831",
        comment_style="all",
        paths=[yaml_path],
    )
    code = yaml_dsl._run_upsert_lsp_comment(args)
    assert code == 0

    updated = yaml_path.read_text(encoding="utf-8")
    lines = updated.splitlines()
    assert lines[0] == "---"
    assert lines[1] == "# yaml-language-server: $schema=http://localhost:62831/demand.gen.json"
    assert lines[2] == "# $schema: http://localhost:62831/demand.gen.json"
    assert "&main_source" in updated
    assert "&tags_transform" in updated
    assert "*tags_transform" in updated

    assert _strip_schema_modelines(original.splitlines()) == _strip_schema_modelines(updated.splitlines())

    code = yaml_dsl._run_upsert_lsp_comment(args)
    assert code == 0
    assert yaml_path.read_text(encoding="utf-8") == updated
