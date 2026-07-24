import json
import re
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


_CALL_BY_KWARGS_VALUE_TOKEN_RE = re.compile("=\\s*([A-Za-z_][A-Za-z0-9_]*)")


def _call_by_kwargs_value_tokens(raw: str) -> List[str]:
    text = str(raw or "")
    if "(" not in text:
        return []
    args = text.split("(", 1)[1]
    if ")" in args:
        args = args.rsplit(")", 1)[0]
    return [str(m.group(1)) for m in _CALL_BY_KWARGS_VALUE_TOKEN_RE.finditer(args)]


def _is_call_by_kwargs_value_callsite(path: List[str]) -> bool:
    if not path or str(path[-1]) != "call_by":
        return False
    if len(path) >= 3 and str(path[0]) == "fields":
        return True
    return (
        len(path) >= 6 and str(path[0]) == "outputs" and str(path[1]).isdigit() and str(path[2]) == "aggregate" and str(path[3]) == "fields"
    )


def _collect_call_by_kwargs_value_field_refs(node: object, *, path: List[str]) -> List[tuple]:
    refs: List[tuple] = []

    if isinstance(node, dict):
        for key, value in node.items():
            key_str = str(key)
            next_path = [*path, key_str]
            if key_str == "call_by" and isinstance(value, str) and _is_call_by_kwargs_value_callsite(next_path):
                yaml_path = ".".join(next_path)
                for token in _call_by_kwargs_value_tokens(value):
                    if str(token).strip():
                        refs.append((yaml_path, str(token).strip()))
            refs.extend(_collect_call_by_kwargs_value_field_refs(value, path=next_path))
        return refs

    if isinstance(node, list):
        for idx, value in enumerate(node):
            refs.extend(_collect_call_by_kwargs_value_field_refs(value, path=[*path, str(idx)]))
        return refs

    return refs


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


def _collect_aggregate_field_refs(node: object, *, path: List[str]) -> List[tuple]:
    refs: List[tuple] = []

    if isinstance(node, dict):
        for key, value in node.items():
            key_str = str(key)
            next_path = [*path, key_str]

            # group_by
            if key_str == "group_by" and len(path) >= 3 and path[-1] == "aggregate" and path[-2].isdigit() and path[-3] == "outputs":
                if isinstance(value, str) and value.strip():
                    refs.append((".".join(next_path), value.strip()))
                elif isinstance(value, list):
                    for idx, item in enumerate(value):
                        if isinstance(item, str) and item.strip():
                            refs.append(("{}.{}".format(".".join(next_path), idx), item.strip()))
                        elif isinstance(item, list):
                            for j, inner in enumerate(item):
                                if isinstance(inner, str) and inner.strip():
                                    refs.append(("{}.{}.{}".format(".".join(next_path), idx, j), inner.strip()))

            # aggregate.fields.*.*.field / fields[*] / rank refs / score_by_rank
            if key_str == "fields" and len(path) >= 3 and path[-1] == "aggregate" and path[-2].isdigit() and path[-3] == "outputs":
                if isinstance(value, dict):
                    output_prefix = ".".join(next_path)  # outputs.<i>.aggregate.fields
                    for out_field_id, metrics in value.items():
                        if not isinstance(metrics, dict):
                            continue
                        out_id = str(out_field_id)
                        for metric_kind, metric_cfg in metrics.items():
                            kind = str(metric_kind)
                            if not isinstance(metric_cfg, dict):
                                continue

                            # rank/row_number/dense_rank
                            if kind in ("row_number", "rank", "dense_rank"):
                                by_value = metric_cfg.get("by")
                                if isinstance(by_value, str) and by_value.strip():
                                    refs.append(("{}.{}.{}.by".format(output_prefix, out_id, kind), by_value.strip()))
                                partition_by = metric_cfg.get("partition_by")
                                if isinstance(partition_by, list):
                                    for idx, v in enumerate(partition_by):
                                        if isinstance(v, str) and v.strip():
                                            refs.append(("{}.{}.{}.partition_by.{}".format(output_prefix, out_id, kind, idx), v.strip()))
                                order_by = metric_cfg.get("order_by")
                                if isinstance(order_by, list):
                                    for idx, v in enumerate(order_by):
                                        if isinstance(v, str) and v.strip():
                                            refs.append(("{}.{}.{}.order_by.{}".format(output_prefix, out_id, kind, idx), v.strip()))
                                continue

                            # score_by_rank has been removed; compute is the replacement.
                            # (This branch is kept for regression safety if any fixture still contains the key.)
                            if kind == "score_by_rank":
                                continue

                            field_value = metric_cfg.get("field")
                            if isinstance(field_value, str) and field_value.strip():
                                refs.append(("{}.{}.{}.field".format(output_prefix, out_id, kind), field_value.strip()))

                            fields_value = metric_cfg.get("fields")
                            if isinstance(fields_value, list):
                                for idx, v in enumerate(fields_value):
                                    if isinstance(v, str) and v.strip():
                                        refs.append(("{}.{}.{}.fields.{}".format(output_prefix, out_id, kind, idx), v.strip()))

            refs.extend(_collect_aggregate_field_refs(value, path=next_path))
        return refs

    if isinstance(node, list):
        for idx, value in enumerate(node):
            refs.extend(_collect_aggregate_field_refs(value, path=[*path, str(idx)]))
        return refs

    return refs


def _assert_non_empty_or_warned(items: list, warnings: tuple, *, label: str, yaml_path: Path) -> None:
    if items:
        return
    assert warnings, "empty result without warnings: {} {}".format(label, str(yaml_path))


@pytest.mark.parametrize("yaml_path", _NOTEBOOK_YAML_FIXTURES, ids=lambda yaml_path: str(yaml_path))
def test_notebooks_yaml_fixtures_aggregate_field_ops_do_not_crash(yaml_path: Path) -> None:
    yaml_text = yaml_path.read_text(encoding="utf-8")
    yaml_data, _locations, _lines = load_yaml_mapping_text(
        yaml_text,
        source_path=str(yaml_path),
        detect_duplicate_keys=True,
    )

    refs = _collect_aggregate_field_refs(yaml_data, path=[])
    if not refs:
        return

    yaml_kind = editor_semantics.classify_yaml_dsl_kind(yaml_path, yaml_text)
    view = editor_semantics.build_yaml_dsl_editor_effective_view(
        yaml_text,
        yaml_path=yaml_path,
        yaml_kind=yaml_kind,
        allowed_yaml_roots=[yaml_path.parent.resolve(strict=False)],
    )
    scope_index = editor_semantics.build_yaml_dsl_expression_scope_index(
        yaml_text,
        yaml_path=yaml_path,
        yaml_kind=yaml_kind,
    )

    # completion: run once per unique yaml_path (empty prefix / Ctrl+Space style)
    seen_paths = set()
    for ref_path, _token in refs:
        if ref_path in seen_paths:
            continue
        seen_paths.add(ref_path)
        extraction = editor_semantics.YamlCursorExtractionResult(
            yaml_path=str(ref_path),
            kind="aggregate_field_ref",
            reference="",
        )
        completion = editor_semantics.complete_yaml_dsl_aggregate_field_reference(extraction, view=view, scope_index=scope_index)
        json.dumps(completion.as_dict())
        _assert_non_empty_or_warned(list(completion.items), tuple(completion.warnings), label="completion", yaml_path=yaml_path)

    for ref_path, token in refs:
        extraction = editor_semantics.YamlCursorExtractionResult(
            yaml_path=str(ref_path),
            kind="aggregate_field_ref",
            reference=str(token),
        )

        definition = editor_semantics.resolve_yaml_dsl_aggregate_field_definition(extraction, view=view, scope_index=scope_index)
        json.dumps(definition.as_dict())
        _assert_non_empty_or_warned(list(definition.locations), tuple(definition.warnings), label="definition", yaml_path=yaml_path)

        hover = editor_semantics.hover_yaml_dsl_aggregate_field_reference(extraction, view=view, scope_index=scope_index)
        json.dumps(hover.as_dict())
        if not str(hover.text or "").strip():
            assert hover.warnings, "empty hover without warnings: {}".format(str(yaml_path))


@pytest.mark.parametrize("yaml_path", _NOTEBOOK_YAML_FIXTURES, ids=lambda yaml_path: str(yaml_path))
def test_notebooks_yaml_fixtures_call_by_kwargs_value_field_ops_do_not_crash(yaml_path: Path) -> None:
    yaml_text = yaml_path.read_text(encoding="utf-8")
    yaml_data, _locations, _lines = load_yaml_mapping_text(
        yaml_text,
        source_path=str(yaml_path),
        detect_duplicate_keys=True,
    )

    refs = _collect_call_by_kwargs_value_field_refs(yaml_data, path=[])
    if not refs:
        return

    yaml_kind = editor_semantics.classify_yaml_dsl_kind(yaml_path, yaml_text)
    view = editor_semantics.build_yaml_dsl_editor_effective_view(
        yaml_text,
        yaml_path=yaml_path,
        yaml_kind=yaml_kind,
        allowed_yaml_roots=[yaml_path.parent.resolve(strict=False)],
    )
    scope_index = editor_semantics.build_yaml_dsl_expression_scope_index(
        yaml_text,
        yaml_path=yaml_path,
        yaml_kind=yaml_kind,
    )

    # completion: run once per unique yaml_path (empty prefix / Ctrl+Space style)
    seen_paths = set()
    for ref_path, _token in refs:
        if ref_path in seen_paths:
            continue
        seen_paths.add(ref_path)
        extraction = editor_semantics.YamlCursorExtractionResult(
            yaml_path=str(ref_path),
            kind="call_by_kwargs_value_field_ref",
            reference="",
        )
        completion = editor_semantics.complete_yaml_dsl_call_by_kwargs_value_field_reference(
            extraction,
            view=view,
            scope_index=scope_index,
        )
        json.dumps(completion.as_dict())
        _assert_non_empty_or_warned(list(completion.items), tuple(completion.warnings), label="completion", yaml_path=yaml_path)

    for ref_path, token in refs:
        extraction = editor_semantics.YamlCursorExtractionResult(
            yaml_path=str(ref_path),
            kind="call_by_kwargs_value_field_ref",
            reference=str(token),
        )

        definition = editor_semantics.resolve_yaml_dsl_call_by_kwargs_value_field_definition(
            extraction,
            view=view,
            scope_index=scope_index,
        )
        json.dumps(definition.as_dict())
        _assert_non_empty_or_warned(list(definition.locations), tuple(definition.warnings), label="definition", yaml_path=yaml_path)

        hover = editor_semantics.hover_yaml_dsl_call_by_kwargs_value_field_reference(
            extraction,
            view=view,
            scope_index=scope_index,
        )
        json.dumps(hover.as_dict())
        if not str(hover.text or "").strip():
            assert hover.warnings, "empty hover without warnings: {}".format(str(yaml_path))
