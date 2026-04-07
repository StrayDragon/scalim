import json
from pathlib import Path
from typing import Iterator, List

import pytest

import scalim_yaml_dsl_lsp.core as editor_semantics
from scalim.dsl.yaml_dsl._internal.config_parsing.yaml_load import load_yaml_mapping_text

_NOTEBOOK_FIXTURES_ROOT = Path("notebooks/marimo/demo_big_data_report/chapters_of_yaml_dsl/declared_yaml_dsl")


def _iter_yaml_files(root: Path) -> Iterator[Path]:
    paths: List[Path] = []
    for pattern in ("*.yaml", "*.yml"):
        paths.extend(list(root.rglob(pattern)))

    for path in sorted(paths):
        rel = path.relative_to(root)
        if ".tmp" in rel.parts:
            continue
        if path.name == "scalim.yaml":
            continue
        if "_shared" in rel.parts:
            continue
        if path.name.endswith("_fragments.yaml") or path.name.endswith("_fragments.yml"):
            continue
        yield path


_NOTEBOOK_YAML_FIXTURES = list(_iter_yaml_files(_NOTEBOOK_FIXTURES_ROOT))


def _assert_range_is_valid(rng: editor_semantics.EditorRange) -> None:
    assert rng.start.line >= 1
    assert rng.start.column >= 1
    assert rng.end.line >= rng.start.line
    if rng.end.line == rng.start.line:
        assert rng.end.column >= rng.start.column


def _call_by_head(raw: str) -> str:
    prefix = str(raw or "")
    if "(" in prefix:
        prefix = prefix.split("(", 1)[0]
    return prefix.strip()


def _collect_python_references(node: object, *, path: List[str]) -> List[str]:
    refs: List[str] = []

    if isinstance(node, dict):
        for key, value in node.items():
            key_str = str(key)
            next_path = [*path, key_str]
            if isinstance(value, str):
                if key_str == "loader":
                    refs.append(value.strip())
                elif key_str == "call_by":
                    head = _call_by_head(value)
                    if head:
                        refs.append(head)
                elif key_str == "should_retry" and path and path[-1] == "retry":
                    refs.append(value.strip())
            refs.extend(_collect_python_references(value, path=next_path))
        return refs

    if isinstance(node, list):
        for idx, value in enumerate(node):
            refs.extend(_collect_python_references(value, path=[*path, str(idx)]))
        return refs

    return refs


def test_notebooks_yaml_fixtures_discovery_is_non_empty() -> None:
    assert _NOTEBOOK_FIXTURES_ROOT.is_dir()
    assert _NOTEBOOK_YAML_FIXTURES


@pytest.mark.parametrize("yaml_path", _NOTEBOOK_YAML_FIXTURES, ids=lambda yaml_path: str(yaml_path))
def test_notebooks_yaml_fixtures_have_stable_diagnostics(yaml_path: Path) -> None:
    yaml_text = yaml_path.read_text(encoding="utf-8")
    result = editor_semantics.collect_yaml_dsl_editor_diagnostics(yaml_path, yaml_text=yaml_text)

    assert not result.errors, "unexpected diagnostics errors: {}".format([d.as_dict() for d in result.errors])

    payload = result.as_dict()
    json.dumps(payload)

    for diag in list(result.errors) + list(result.warnings):
        json.dumps(diag.as_dict())
        if diag.range is not None:
            _assert_range_is_valid(diag.range)


@pytest.mark.parametrize("yaml_path", _NOTEBOOK_YAML_FIXTURES, ids=lambda yaml_path: str(yaml_path))
def test_notebooks_yaml_fixtures_python_reference_ops_do_not_crash(yaml_path: Path) -> None:
    yaml_text = yaml_path.read_text(encoding="utf-8")
    yaml_data, _locations, _lines = load_yaml_mapping_text(
        yaml_text,
        source_path=str(yaml_path),
        detect_duplicate_keys=True,
    )
    references = _collect_python_references(yaml_data, path=[])

    python_roots: List[Path] = [
        Path("src").resolve(strict=False),
        Path("packages/scalim-misc/src").resolve(strict=False),
    ]

    for reference in references:
        definition = editor_semantics.resolve_python_definition(reference, python_roots=python_roots)
        json.dumps(definition.as_dict())

        hover = editor_semantics.hover_python_reference(reference, python_roots=python_roots)
        json.dumps(hover.as_dict())

        completion = editor_semantics.complete_python_reference(reference, python_roots=python_roots)
        json.dumps(completion.as_dict())
