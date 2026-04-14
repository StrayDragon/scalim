# pragma: allow-cast-file tests use casts for schema traversal helpers; not production runtime
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Optional, Sequence, Tuple, cast

from scalim.vendor.yamlx import yaml as vendored_yaml
from tests.support.pathing import repo_root as _repo_root


def _schema_path(name: str) -> Path:
    repo_root = _repo_root()
    return repo_root / "src" / "scalim" / "dsl" / "yaml_dsl" / "schema" / name


def _load_schema(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return cast("Dict[str, Any]", json.load(handle))


def _is_dict(value: Any) -> bool:
    return isinstance(value, dict)


def _is_list(value: Any) -> bool:
    return isinstance(value, list)


def _schema_enum_values(node: Mapping[str, Any]) -> List[str]:
    raw = node.get("enum")
    if not isinstance(raw, list):
        return []
    return [x for x in raw if isinstance(x, str)]


def _iter_doc_property_nodes(schema: Mapping[str, Any]) -> Iterator[Mapping[str, Any]]:
    """Iterate property schema nodes that are reachable by authoring surface.

    This intentionally skips constraint-only subtrees (e.g. `allOf` / `anyOf`) to avoid treating validation-only
    branches as user-facing config nodes.
    """

    def walk(node: Any, *, in_constraint: bool) -> Iterator[Mapping[str, Any]]:
        if not _is_dict(node):
            return
        typed = cast("Mapping[str, Any]", node)

        if not in_constraint:
            props = typed.get("properties")
            if _is_dict(props):
                for child in cast("Dict[str, Any]", props).values():
                    if not _is_dict(child):
                        continue
                    yield cast("Mapping[str, Any]", child)
                    yield from walk(child, in_constraint=False)

        items = typed.get("items")
        if _is_dict(items):
            yield from walk(items, in_constraint=in_constraint)
        elif _is_list(items):
            for item in cast("List[Any]", items):
                yield from walk(item, in_constraint=in_constraint)

        ap = typed.get("additionalProperties")
        if _is_dict(ap):
            yield from walk(ap, in_constraint=in_constraint)

        for key, child_constraint in (("oneOf", in_constraint), ("anyOf", True), ("allOf", True)):
            raw = typed.get(key)
            if not _is_list(raw):
                continue
            for opt in cast("List[Any]", raw):
                yield from walk(opt, in_constraint=child_constraint)

    root_props = schema.get("properties")
    if _is_dict(root_props):
        for value in cast("Dict[str, Any]", root_props).values():
            yield from walk(value, in_constraint=False)

    defs = schema.get("definitions")
    if _is_dict(defs):
        for def_schema in cast("Dict[str, Any]", defs).values():
            yield from walk(def_schema, in_constraint=False)


def _assert_has_heading(md: str) -> None:
    lines = md.splitlines()
    assert lines, "markdownDescription must be non-empty"
    assert lines[0].startswith("#### "), "markdownDescription must start with a '#### <path>' heading"
    assert lines[0].strip() != "####", "heading must include a config path"


def test_schema_nodes_have_structured_markdown_description() -> None:
    schema_paths = [
        _schema_path("demand.gen.json"),
        _schema_path("workflow.gen.json"),
        _schema_path("scalim_yaml.gen.json"),
    ]

    for path in schema_paths:
        schema = _load_schema(path)
        for node in _iter_doc_property_nodes(schema):
            md = node.get("markdownDescription")
            assert isinstance(md, str), "missing markdownDescription in {}".format(str(path))
            _assert_has_heading(md)

            desc = node.get("description")
            assert isinstance(desc, str), "missing description in {}".format(str(path))

            if ("##### 字段约束" in md) or ("##### 例子" in md):
                assert "##### 字段约束" in md
                assert "##### 例子" in md
                assert md.index("##### 字段约束") < md.index("##### 例子")
                assert "```yaml" in md[md.index("##### 例子") :], "examples section must include a YAML code block"


def test_schema_paths_disambiguate_common_fields() -> None:
    schema = _load_schema(_schema_path("demand.gen.json"))
    main_loader = schema["definitions"]["main_source"]["properties"]["loader"]["markdownDescription"]
    source_loader = schema["definitions"]["source"]["properties"]["loader"]["markdownDescription"]

    assert main_loader.splitlines()[0].strip() == "#### main_source.loader"
    assert source_loader.splitlines()[0].strip() == "#### sources.*.loader"


def test_import_required_workaround_is_expressed_in_brief_docs() -> None:
    schema = _load_schema(_schema_path("demand.gen.json"))
    md = schema["properties"]["main_source"]["markdownDescription"]
    assert "$import" in md


def test_workflow_paths_include_array_items() -> None:
    schema = _load_schema(_schema_path("workflow.gen.json"))
    demand_md = schema["properties"]["workflow"]["properties"]["runs"]["items"]["properties"]["demand"]["markdownDescription"]
    assert demand_md.splitlines()[0].strip() == "#### workflow.runs[*].demand"


def test_project_config_paths_do_not_leak_definition_names() -> None:
    schema = _load_schema(_schema_path("scalim_yaml.gen.json"))
    import_roots_md = schema["definitions"]["scalim_yaml_yaml_dsl"]["properties"]["import_roots"]["markdownDescription"]
    assert import_roots_md.splitlines()[0].strip() == "#### yaml_dsl.import_roots"


def test_enum_nodes_are_full_and_have_per_choice_semantics() -> None:
    schema = _load_schema(_schema_path("workflow.gen.json"))
    checked = 0
    for node in _iter_doc_property_nodes(schema):
        enum_vals = _schema_enum_values(node)
        if not enum_vals:
            continue
        checked += 1
        md = cast(str, node.get("markdownDescription") or "")
        assert "##### 字段约束" in md
        assert "##### 例子" in md

        # semantics: one list item per enum value; avoid "all values in one line"
        lines = [ln.strip() for ln in md.splitlines() if ln.strip().startswith("- ")]
        for val in enum_vals:
            token = "`{}`".format(val)
            candidates = [ln for ln in lines if (token in ln) and ("```" not in ln)]
            assert candidates, "enum value missing in docs: {} (val={})".format(enum_vals, val)
            # at least one candidate line must not contain other enum tokens
            others = ["`{}`".format(v) for v in enum_vals if v != val]
            assert any(not any(o in ln for o in others) for ln in candidates), "enum value should have its own semantics line: {}".format(
                val
            )

    assert checked >= 1


def test_fixture_snippet_extractor_supports_nesting_and_is_yaml_parseable() -> None:
    repo_root = _repo_root()
    ecommerce = repo_root / "notebooks/marimo/demo_big_data_report/chapters_of_yaml_dsl/declared_yaml_dsl/ecommerce_rank_score_report.yaml"
    workflow = (
        repo_root / "notebooks/marimo/demo_big_data_report/chapters_of_yaml_dsl/declared_yaml_dsl/workflow_fixture_cache_pool_pin.yaml"
    )
    scalim_yaml = repo_root / "notebooks/marimo/demo_big_data_report/chapters_of_yaml_dsl/declared_yaml_dsl/scalim.yaml"

    from scalim_misc.yaml_schema_doc_standardizer import _extract_snippets_from_fixture

    all_snippets: Dict[str, str] = {}
    for fixture in (ecommerce, workflow, scalim_yaml):
        all_snippets.update(_extract_snippets_from_fixture(str(fixture)))

    # expected ids (coverage smoke)
    assert "outputs[*].aggregate" in all_snippets
    assert "outputs[*].aggregate.fields" in all_snippets
    assert "workflow.options.cache_pool" in all_snippets
    assert "yaml_dsl.import_roots" in all_snippets
    assert "yaml_dsl.import_roots[*]" in all_snippets
    assert "yaml_dsl.lsp.kind_overrides[*]" in all_snippets

    # nested markers removed
    outer = all_snippets["outputs[*].aggregate"]
    assert "BEGIN AUTOGEN" not in outer
    assert "END AUTOGEN" not in outer

    # parseable YAML fragments
    for snippet_id, text in all_snippets.items():
        assert text.strip(), "snippet must be non-empty: {}".format(snippet_id)
        _ = vendored_yaml.safe_load(text)


def test_runtime_import_graph_does_not_pull_doc_standardizer() -> None:
    """Verify core does not import dev-only `scalim-misc` (direction: scalim-misc -> scalim only)."""

    repo_root = _repo_root()
    script = (
        "import sys; "
        "sys.path.insert(0, {!r}); "
        "import scalim.dsl.yaml_dsl.runtime.compiler as _c; "
        "import scalim.dsl.yaml_dsl._internal.config_parsing.loader as _l; "
        "import sys as _sys; "
        "print(any(m.startswith('scalim_misc') for m in _sys.modules))"
    ).format(str(repo_root / "src"))

    out = subprocess.check_output([sys.executable, "-c", script], text=True).strip()
    assert out == "False"


def test_core_sources_do_not_reference_scalim_misc_imports() -> None:
    repo_root = _repo_root()
    src_root = repo_root / "src" / "scalim"
    patterns = (
        "import scalim_misc",
        "from scalim_misc",
        'import_module("scalim_misc',
        "import_module('scalim_misc",
    )
    offenders: List[str] = []
    for path in src_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if any(pat in text for pat in patterns):
            offenders.append(str(path))
    assert not offenders, "core MUST NOT reference scalim-misc imports; offenders: {}".format(offenders)
