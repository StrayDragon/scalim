import ast
import importlib
import importlib.machinery
import json
import textwrap
from pathlib import Path

import pytest

import scalim_yaml_dsl_lsp.core as editor_semantics
from scalim_yaml_dsl_lsp.core import (
    PythonDefinitionLocation,
    PythonDefinitionResult,
    YamlDslEditorProjectDiscovery,
)


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_discovery_zero_config_falls_back_to_entry_dir(tmp_path: Path) -> None:
    yaml_path = _write(tmp_path / "demand.yaml", "name: demo\nsources: {}\n")
    discovery = editor_semantics.discover_yaml_dsl_editor_project(yaml_path)
    assert isinstance(discovery, YamlDslEditorProjectDiscovery)
    assert discovery.scalim_yaml_path is None
    assert discovery.project_root == tmp_path
    assert discovery.python_roots == (tmp_path,)
    assert discovery.allowed_yaml_roots == (tmp_path,)


def test_discovery_workspace_root_override_infers_project_root_and_roots(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    demand_dir = repo / "anywhere" / "dsl"
    _ = _write(demand_dir / "demand.yaml", "name: demo\nmain_source: {source_id: x, loader: pkg.mod:fn}\n")
    (repo / "src").mkdir(parents=True)

    discovery = editor_semantics.discover_yaml_dsl_editor_project(demand_dir / "demand.yaml", workspace_root_override=repo)
    assert discovery.scalim_yaml_path is None
    assert discovery.project_root == repo
    assert discovery.python_roots[0] == repo / "src"
    assert repo in discovery.python_roots
    assert set(discovery.allowed_yaml_roots) == {repo, demand_dir}


def test_discovery_workspace_root_override_does_not_escape_boundary(tmp_path: Path) -> None:
    outer = tmp_path / "outer"
    inner = outer / "inner"
    _ = _write(outer / "scalim.yaml", "yaml_dsl:\n  import_roots: []\n")
    yaml_path = _write(inner / "demand.yaml", "name: demo\nsources: {}\n")

    discovery = editor_semantics.discover_yaml_dsl_editor_project(yaml_path, workspace_root_override=inner)
    assert discovery.scalim_yaml_path is None
    assert discovery.project_root == inner


def test_legacy_editor_semantics_import_path_is_removed() -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("scalim.dsl.yaml_dsl.editor_semantics")


def test_discovery_nearest_wins_scalim_yaml_and_editor_python_roots(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    sub = repo / "sub"
    entry_dir = sub / "wf"
    _ = _write(
        repo / "scalim.yaml",
        "yaml_dsl:\n  lsp:\n    python_roots: [./py]\n",
    )

    (sub / "py").mkdir(parents=True)
    (sub / "allowed").mkdir(parents=True)
    _ = _write(
        sub / "scalim.yaml",
        "yaml_dsl:\n  import_roots: [{path: ./allowed}]\n  lsp:\n    python_roots: [./py]\n",
    )

    yaml_path = _write(entry_dir / "demand.yaml", "name: demo\nsources: {}\n")
    discovery = editor_semantics.discover_yaml_dsl_editor_project(yaml_path)
    assert discovery.scalim_yaml_path == sub / "scalim.yaml"
    assert discovery.project_root == sub
    assert discovery.python_roots == (sub / "py",)
    assert set(discovery.allowed_yaml_roots) == {entry_dir, sub / "allowed"}


def test_discovery_scalim_yaml_without_editor_python_roots_still_infers_from_workspace_root(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    dsl_dir = repo / "dsl"
    pkg_src = repo / "packages" / "demo-pkg" / "src" / "demo_pkg"

    _ = _write(dsl_dir / "scalim.yaml", "yaml_dsl:\n  import_roots: [{path: .}]\n")
    yaml_path = _write(dsl_dir / "demand.yaml", "name: demo\nmain_source: {source_id: x, loader: demo_pkg.mod:fn}\n")

    _ = _write(pkg_src / "__init__.py", "")
    mod_path = _write(pkg_src / "mod.py", "def fn():\n    return 1\n")

    discovery = editor_semantics.discover_yaml_dsl_editor_project(yaml_path, workspace_root_override=repo)
    assert discovery.scalim_yaml_path == dsl_dir / "scalim.yaml"
    assert discovery.project_root == dsl_dir
    assert repo / "packages" / "demo-pkg" / "src" in discovery.python_roots
    assert dsl_dir in discovery.python_roots

    result = editor_semantics.resolve_python_definition(
        "demo_pkg.mod:fn",
        python_roots=list(discovery.python_roots),
        anchor_path=yaml_path,
    )
    assert result.locations and Path(result.locations[0].file_path) == mod_path


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("workflow: {}\n", editor_semantics.YAML_DSL_KIND_WORKFLOW),
        ("workflow: 1\n", editor_semantics.YAML_DSL_KIND_DEMAND),
        ("workflow: [\n", editor_semantics.YAML_DSL_KIND_DEMAND),
        ("name: demo\nmain_source: {}\n", editor_semantics.YAML_DSL_KIND_DEMAND),
        ("loader: pkg.mod:fn\n", editor_semantics.YAML_DSL_KIND_DEMAND),
    ],
)
def test_classify_yaml_kind_heuristic(text: str, expected: str, tmp_path: Path) -> None:
    yaml_path = tmp_path / "x.yaml"
    assert editor_semantics.classify_yaml_dsl_kind(yaml_path, text) == expected


def test_classify_yaml_kind_override_wins(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    wf_dir = repo / "wf"
    _ = _write(
        repo / "scalim.yaml",
        "yaml_dsl:\n  lsp:\n    kind_overrides:\n      - glob: wf/*.yaml\n        kind: workflow\n",
    )
    yaml_path = _write(wf_dir / "x.yaml", "name: demo\nsources: {}\n")
    assert (
        editor_semantics.classify_yaml_dsl_kind(
            yaml_path,
            yaml_path.read_text(encoding="utf-8"),
        )
        == editor_semantics.YAML_DSL_KIND_WORKFLOW
    )


def test_is_probably_yaml_dsl_document_heuristics(tmp_path: Path) -> None:
    any_yaml = tmp_path / "x.yaml"

    assert editor_semantics.is_probably_yaml_dsl_document(any_yaml, "foo: 1\n") is False
    assert editor_semantics.is_probably_yaml_dsl_document(any_yaml, "name: demo\nmain_source: {}\n") is True
    assert editor_semantics.is_probably_yaml_dsl_document(any_yaml, "workflow: {}\n") is True
    assert editor_semantics.is_probably_yaml_dsl_document(any_yaml, "x: {$init_var: order_ids}\n") is True
    assert editor_semantics.is_probably_yaml_dsl_document(any_yaml, "sources:\n  s:\n    loader: pkg.mod:fn\n") is True

    assert editor_semantics.is_probably_yaml_dsl_document(tmp_path / "scalim.yaml", "yaml_dsl: {}\n") is False


def test_schema_required_keys_are_loaded_from_gen_schema() -> None:
    editor_semantics._schema_required_keys.cache_clear()
    assert set(editor_semantics._schema_required_keys(editor_semantics.YAML_DSL_KIND_DEMAND)) == {"name", "main_source"}
    assert set(editor_semantics._schema_required_keys(editor_semantics.YAML_DSL_KIND_WORKFLOW)) == {"workflow"}


def test_schema_required_keys_degrade_for_unknown_kind() -> None:
    editor_semantics._schema_required_keys.cache_clear()
    assert editor_semantics._schema_required_keys("unknown-kind") == ()


def test_collect_demand_diagnostics_has_error_warning_and_range(tmp_path: Path) -> None:
    yaml_text = textwrap.dedent(
        """\
        name: demo
        observability: {}
        main_source:
          source_id: orders
          loader: tests.fixtures.mock_loaders.mock_loader
          unknown_field: 1
        sources: {}
        """
    )
    yaml_path = _write(tmp_path / "demand.yaml", yaml_text)
    result = editor_semantics.collect_yaml_dsl_editor_diagnostics(yaml_path, yaml_text=yaml_text)
    assert result.yaml_kind == editor_semantics.YAML_DSL_KIND_DEMAND
    assert result.errors

    unknown = [d for d in result.errors if d.path == "main_source.unknown_field"]
    assert unknown and unknown[0].range is not None
    assert unknown[0].range.start.line == 6
    assert unknown[0].range.start.column == 3

    error_paths = {e.path for e in result.errors}
    assert "observability" in error_paths
    assert "main_source.unknown_field" in error_paths
    # observability is fail-fast ERROR (not a warning)
    warn_paths = {w.path for w in result.warnings}
    assert "observability" not in warn_paths

def test_collect_demand_diagnostics_import_expansion_error_is_reported(tmp_path: Path) -> None:
    yaml_text = textwrap.dedent(
        """\
        name: demo
        main_source:
          source_id: orders
          loader: tests.fixtures.mock_loaders.mock_loader
        sources: {}
        $import: x.yaml
        """
    )
    yaml_path = _write(tmp_path / "demand.yaml", yaml_text)
    result = editor_semantics.collect_yaml_dsl_editor_diagnostics(yaml_path, yaml_text=yaml_text)
    assert any(d.code == "yaml_import_expansion_error" for d in result.errors)


def test_collect_demand_diagnostics_reports_yaml_root_not_mapping(tmp_path: Path) -> None:
    yaml_text = "[]\n"
    yaml_path = _write(tmp_path / "demand.yaml", yaml_text)
    result = editor_semantics.collect_yaml_dsl_editor_diagnostics(yaml_path, yaml_text=yaml_text)
    assert any(d.code == "yaml_root_not_mapping" for d in result.errors)


def test_workflow_diagnostics_reports_schema_issue_and_unknown_fields(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    wf_dir = repo / "wf"
    _ = _write(
        repo / "scalim.yaml",
        "yaml_dsl:\n  lsp:\n    kind_overrides:\n      - glob: wf/*.yaml\n        kind: workflow\n",
    )
    yaml_text = "workflow: []\nbad: 1\n"
    yaml_path = _write(wf_dir / "x.yaml", yaml_text)
    result = editor_semantics.collect_yaml_dsl_editor_diagnostics(yaml_path, yaml_text=yaml_text)
    assert result.yaml_kind == editor_semantics.YAML_DSL_KIND_WORKFLOW
    assert any("Schema validation error" in d.message for d in result.errors)
    assert any("Unknown field" in d.message for d in result.errors)


def test_workflow_diagnostics_warns_when_jsonschema_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    wf_dir = repo / "wf"
    _ = _write(
        repo / "scalim.yaml",
        "yaml_dsl:\n  lsp:\n    kind_overrides:\n      - glob: wf/*.yaml\n        kind: workflow\n",
    )
    yaml_text = "workflow: []\nbad: 1\n"
    yaml_path = _write(wf_dir / "x.yaml", yaml_text)
    monkeypatch.setattr(editor_semantics, "import_jsonschema_module", lambda: None)
    result = editor_semantics.collect_yaml_dsl_editor_diagnostics(yaml_path, yaml_text=yaml_text)
    assert any("jsonschema 不可用" in w.message for w in result.warnings)


def test_workflow_diagnostics_parse_error_is_captured(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    wf_dir = repo / "wf"
    _ = _write(
        repo / "scalim.yaml",
        "yaml_dsl:\n  lsp:\n    kind_overrides:\n      - glob: wf/*.yaml\n        kind: workflow\n",
    )
    yaml_text = "workflow: [\n"
    yaml_path = _write(wf_dir / "x.yaml", yaml_text)
    result = editor_semantics.collect_yaml_dsl_editor_diagnostics(yaml_path, yaml_text=yaml_text)
    assert any(d.code == "yaml_parse_error" for d in result.errors)


def test_workflow_diagnostics_handles_jsonschema_collector_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    wf_dir = repo / "wf"
    _ = _write(
        repo / "scalim.yaml",
        "yaml_dsl:\n  lsp:\n    kind_overrides:\n      - glob: wf/*.yaml\n        kind: workflow\n",
    )
    yaml_text = "workflow: {}\nbad: 1\n"
    yaml_path = _write(wf_dir / "x.yaml", yaml_text)

    def _raise_collector(*_args, **_kwargs):
        raise editor_semantics.ScalimJsonSchemaCollectorError("boom")

    monkeypatch.setattr(editor_semantics, "collect_jsonschema_validation_issues", _raise_collector)
    result = editor_semantics.collect_yaml_dsl_editor_diagnostics(yaml_path, yaml_text=yaml_text)
    assert any("boom" in w.message for w in result.warnings)

    def _raise_unexpected(*_args, **_kwargs):
        raise RuntimeError("nope")

    monkeypatch.setattr(editor_semantics, "collect_jsonschema_validation_issues", _raise_unexpected)
    result2 = editor_semantics.collect_yaml_dsl_editor_diagnostics(yaml_path, yaml_text=yaml_text)
    assert any("Schema validation failed unexpectedly" in w.message for w in result2.warnings)


def test_resolve_python_definition_and_hover_and_completion(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    _write(pkg / "__init__.py", "")
    _write(
        pkg / "mod.py",
        textwrap.dedent(
            """\
            X = 1
            Y: int = 2

            def foo():
                \"\"\"foo doc\"\"\"
                return 1

            class C:
                \"\"\"C doc\"\"\"
                Z = 1
                W: int = 2

                def m(self):
                    \"\"\"m doc\"\"\"
                    return 2
            """
        ),
    )

    definition = editor_semantics.resolve_python_definition("pkg.mod:foo", python_roots=[tmp_path])
    assert definition.locations and definition.locations[0].file_path.endswith("pkg/mod.py")
    assert definition.locations[0].range is not None

    nested = editor_semantics.resolve_python_definition("pkg.mod:C.m", python_roots=[tmp_path])
    assert nested.locations and nested.locations[0].symbol_path == "C.m"

    hover = editor_semantics.hover_python_reference("pkg.mod:foo", python_roots=[tmp_path])
    assert hover.text.strip() == "foo doc"

    comp = editor_semantics.complete_python_reference("pkg.mod:", python_roots=[tmp_path])
    assert "pkg.mod:foo" in comp.items
    assert "pkg.mod:C" in comp.items

    comp2 = editor_semantics.complete_python_reference("pkg.mod.f", python_roots=[tmp_path])
    assert "pkg.mod.foo" in comp2.items


def test_resolve_python_definition_object_method_infers_class_method_and_returns_fallback(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    _write(pkg / "__init__.py", "")
    _write(
        pkg / "mod.py",
        textwrap.dedent(
            """\
            class Klass:
                def a_method(self):
                    \"\"\"a_method doc\"\"\"
                    return []

            some_ref = Klass()
            """
        ),
    )

    result = editor_semantics.resolve_python_definition("pkg.mod:some_ref.a_method", python_roots=[tmp_path])
    assert len(result.locations) >= 2
    assert result.locations[0].symbol_path == "Klass.a_method"
    assert result.locations[1].symbol_path == "some_ref"

    hover = editor_semantics.hover_python_reference("pkg.mod:some_ref.a_method", python_roots=[tmp_path])
    assert hover.text.strip() == "a_method doc"


def test_resolve_python_definition_object_method_follows_imported_class(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    _write(pkg / "__init__.py", "")
    _write(
        pkg / "other.py",
        textwrap.dedent(
            """\
            class Klass:
                def a_method(self):
                    return 1
            """
        ),
    )
    _write(
        pkg / "mod.py",
        textwrap.dedent(
            """\
            from pkg.other import Klass

            some_ref = Klass()
            """
        ),
    )

    result = editor_semantics.resolve_python_definition("pkg.mod:some_ref.a_method", python_roots=[tmp_path])
    assert len(result.locations) >= 2
    assert result.locations[0].file_path.endswith("pkg/other.py")
    assert result.locations[0].symbol_path == "Klass.a_method"
    assert result.locations[1].file_path.endswith("pkg/mod.py")
    assert result.locations[1].symbol_path == "some_ref"


def test_resolve_python_definition_object_method_follows_imported_object_single_hop(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    _write(pkg / "__init__.py", "")
    _write(
        pkg / "other.py",
        textwrap.dedent(
            """\
            class Klass:
                def a_method(self):
                    return 1

            some_ref = Klass()
            """
        ),
    )
    _write(
        pkg / "mod.py",
        "from pkg.other import some_ref\n",
    )

    result = editor_semantics.resolve_python_definition("pkg.mod:some_ref.a_method", python_roots=[tmp_path])
    assert len(result.locations) >= 3
    assert result.locations[0].file_path.endswith("pkg/other.py")
    assert result.locations[0].symbol_path == "Klass.a_method"
    assert result.locations[1].file_path.endswith("pkg/mod.py")
    assert result.locations[1].symbol_path == "some_ref"
    assert result.locations[2].file_path.endswith("pkg/other.py")
    assert result.locations[2].symbol_path == "some_ref"


def test_finalize_location_candidates_sorts_and_dedupes() -> None:
    pos = editor_semantics.EditorPosition(line=1, column=1)
    rng = editor_semantics.EditorRange(start=pos, end=editor_semantics.EditorPosition(line=1, column=2))

    primary = PythonDefinitionLocation(file_path="c.py", range=rng, module_path="m", symbol_path="impl")
    secondary_b = PythonDefinitionLocation(file_path="b.py", range=rng, module_path="m", symbol_path="b")
    secondary_a = PythonDefinitionLocation(file_path="a.py", range=rng, module_path="m", symbol_path="a")

    cands = [
        editor_semantics._LocationCandidate(priority=editor_semantics._P1_BINDING, location=secondary_b),
        editor_semantics._LocationCandidate(priority=editor_semantics._P1_BINDING, location=secondary_a),
        editor_semantics._LocationCandidate(priority=editor_semantics._P0_IMPL, location=primary),
        editor_semantics._LocationCandidate(priority=editor_semantics._P1_BINDING, location=secondary_a),
    ]
    out = editor_semantics._finalize_location_candidates(cands)  # type: ignore[attr-defined]
    assert [loc.file_path for loc in out] == ["c.py", "a.py", "b.py"]


def test_resolve_python_definition_object_method_degrades_when_class_cannot_be_inferred(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    _write(pkg / "__init__.py", "")
    _write(
        pkg / "mod.py",
        textwrap.dedent(
            """\
            def factory():
                return object()

            some_ref = factory()
            """
        ),
    )

    result = editor_semantics.resolve_python_definition("pkg.mod:some_ref.a_method", python_roots=[tmp_path])
    assert result.locations and result.locations[0].symbol_path == "some_ref"
    assert any("无法静态推断" in w for w in result.warnings)


def test_resolve_python_definition_supports_relative_module_reference_with_anchor_path(tmp_path: Path) -> None:
    py_root = tmp_path / "py"
    report_dir = py_root / "myapp" / "reports"
    _write(report_dir / "__init__.py", "")
    _write(
        report_dir / "loaders.py",
        textwrap.dedent(
            """\
            def load_orders():
                \"\"\"load orders doc\"\"\"
                return 1
            """
        ),
    )
    anchor_yaml = _write(report_dir / "report.yaml", "name: demo\nsources: {}\n")

    definition = editor_semantics.resolve_python_definition(".loaders:load_orders", python_roots=[py_root], anchor_path=anchor_yaml)
    assert definition.locations and definition.locations[0].file_path.endswith("myapp/reports/loaders.py")

    hover = editor_semantics.hover_python_reference(".loaders:load_orders", python_roots=[py_root], anchor_path=anchor_yaml)
    assert hover.text.strip() == "load orders doc"

    comp = editor_semantics.complete_python_reference(".loaders:", python_roots=[py_root], anchor_path=anchor_yaml)
    assert ".loaders:load_orders" in comp.items


def test_resolve_python_definition_supports_parent_relative_module_reference(tmp_path: Path) -> None:
    py_root = tmp_path / "py"
    base_dir = py_root / "myapp" / "reports"
    nested_dir = base_dir / "subpkg"
    _write(base_dir / "__init__.py", "")
    _write(nested_dir / "__init__.py", "")
    _write(
        base_dir / "loaders.py",
        "def load_orders():\n    return 1\n",
    )
    anchor_yaml = _write(nested_dir / "report.yaml", "name: demo\nsources: {}\n")

    definition = editor_semantics.resolve_python_definition("..loaders:load_orders", python_roots=[py_root], anchor_path=anchor_yaml)
    assert definition.locations and definition.locations[0].file_path.endswith("myapp/reports/loaders.py")


def test_relative_module_reference_degrades_when_anchor_outside_python_roots(tmp_path: Path) -> None:
    py_root = tmp_path / "py"
    py_root.mkdir(parents=True, exist_ok=True)
    anchor_yaml = _write(tmp_path / "report.yaml", "name: demo\nsources: {}\n")
    result = editor_semantics.resolve_python_definition(".loaders:load_orders", python_roots=[py_root], anchor_path=anchor_yaml)
    assert result.locations == ()
    assert any("base_module_path" in w for w in result.warnings)


def test_relative_module_reference_prefers_deepest_python_root(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    src_root = repo / "src"
    report_dir = src_root / "myapp" / "reports"
    _write(report_dir / "__init__.py", "")
    _write(report_dir / "loaders.py", "def load_orders():\n    return 1\n")
    anchor_yaml = _write(report_dir / "report.yaml", "name: demo\nsources: {}\n")

    result = editor_semantics.resolve_python_definition(
        ".loaders:load_orders",
        python_roots=[repo, src_root],
        anchor_path=anchor_yaml,
    )
    assert result.locations
    assert result.locations[0].module_path == "myapp.reports.loaders"


@pytest.mark.parametrize(
    "reference",
    [
        "",
        "^builtin/id",
        "not-a-reference",
        ".rel.mod:foo",
    ],
)
def test_resolve_python_definition_failure_modes(reference: str, tmp_path: Path) -> None:
    result = editor_semantics.resolve_python_definition(reference, python_roots=[tmp_path])
    assert result.locations == ()
    assert result.warnings


def test_resolve_python_definition_module_origin_missing_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    missing_origin = str(tmp_path / "missing.py")
    module_name = "missing_mod_for_test"

    original = editor_semantics.PathFinder.find_spec

    def _patched_find_spec(fullname: str, path=None, target=None):  # noqa: ANN001
        if fullname != module_name:
            return original(fullname, path, target)
        spec = importlib.machinery.ModuleSpec(fullname, loader=None)
        spec.origin = missing_origin  # type: ignore[assignment]
        return spec

    monkeypatch.setattr(editor_semantics.PathFinder, "find_spec", _patched_find_spec)

    result = editor_semantics.resolve_python_definition("{}:foo".format(module_name), python_roots=[tmp_path])
    assert result.locations == ()
    assert any("模块文件不存在" in w for w in result.warnings)


def test_resolve_attr_path_node_read_and_syntax_error_branches(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    bad = _write(tmp_path / "bad.py", "def x(:\n")
    parsed = editor_semantics.parse_python_reference("bad:x")
    node, warn = editor_semantics._resolve_attr_path_node(bad, parsed)  # type: ignore[attr-defined]
    assert node is None
    assert "模块语法解析失败" in warn

    def _boom(*_a, **_k):
        raise OSError("boom")

    monkeypatch.setattr(Path, "read_text", _boom)
    node2, warn2 = editor_semantics._resolve_attr_path_node(bad, parsed)  # type: ignore[attr-defined]
    assert node2 is None
    assert "读取模块文件失败" in warn2


def test_node_range_branches(tmp_path: Path) -> None:
    assert editor_semantics._node_range(ast.AST()) is None  # type: ignore[attr-defined]

    class _BadPos:
        lineno = "x"
        col_offset = 0
        end_lineno = 1
        end_col_offset = 0

    assert editor_semantics._node_range(_BadPos()) is None  # type: ignore[arg-type]

    node = ast.parse("x = 1").body[0]
    rng = editor_semantics._node_range(node)  # type: ignore[attr-defined]
    assert rng is not None
    assert rng.end.column >= rng.start.column

    class _NoEndPos:
        lineno = 1
        col_offset = 0

    rng2 = editor_semantics._node_range(_NoEndPos())  # type: ignore[arg-type]
    assert rng2 is not None
    assert rng2.end.column >= rng2.start.column


def test_list_module_symbols_error_branch(tmp_path: Path) -> None:
    symbols, warn = editor_semantics._list_module_symbols(tmp_path / "missing.py")  # type: ignore[attr-defined]
    assert symbols == ()
    assert warn


def test_hover_handles_parse_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake = PythonDefinitionResult(
        locations=(PythonDefinitionLocation(file_path=str(tmp_path / "missing.py"), range=None, module_path="m", symbol_path="s"),),
        warnings=(),
    )
    monkeypatch.setattr(editor_semantics, "resolve_python_definition", lambda *_a, **_k: fake)
    result = editor_semantics.hover_python_reference("pkg.mod:foo", python_roots=[tmp_path])
    assert result.text == ""
    assert any("hover 解析失败" in w for w in result.warnings)


def test_complete_python_reference_reports_missing_module_path(tmp_path: Path) -> None:
    result = editor_semantics.complete_python_reference("nope", python_roots=[tmp_path])
    assert result.items == ()
    assert result.warnings


def test_editor_semantics_as_dict_payloads_are_json_serializable(tmp_path: Path) -> None:
    pos = editor_semantics.EditorPosition(line=1, column=2)
    rng = editor_semantics.EditorRange(start=pos, end=editor_semantics.EditorPosition(line=1, column=3))
    diag = editor_semantics.EditorDiagnostic(
        severity="error",
        message="m",
        path="a.b",
        source_path="x.yaml",
        code="E1",
        range=rng,
        suggestions=("s1", "s2"),
    )
    discovery = editor_semantics.YamlDslEditorProjectDiscovery(
        project_root=tmp_path,
        scalim_yaml_path=tmp_path / "scalim.yaml",
        python_roots=(tmp_path,),
        allowed_yaml_roots=(tmp_path,),
    )
    result = editor_semantics.YamlDslEditorDiagnosticsResult(
        yaml_kind=editor_semantics.YAML_DSL_KIND_DEMAND,
        discovery=discovery,
        errors=(diag,),
        warnings=(),
    )
    loc = PythonDefinitionLocation(file_path=str(tmp_path / "m.py"), range=rng, module_path="m", symbol_path="s")
    definition = PythonDefinitionResult(locations=(loc,), warnings=("warn",))
    hover = editor_semantics.PythonHoverResult(text="t", warnings=("warn",))
    completion = editor_semantics.PythonCompletionResult(items=("a",), warnings=("warn",))

    payloads = [
        pos.as_dict(),
        rng.as_dict(),
        diag.as_dict(),
        discovery.as_dict(),
        result.as_dict(),
        loc.as_dict(),
        definition.as_dict(),
        hover.as_dict(),
        completion.as_dict(),
    ]
    _ = json.dumps(payloads, ensure_ascii=False)


def test_collect_yaml_dsl_editor_diagnostics_reads_file_when_yaml_text_missing(tmp_path: Path) -> None:
    yaml_path = _write(tmp_path / "demand.yaml", "name: demo\nsources: {}\n")
    result = editor_semantics.collect_yaml_dsl_editor_diagnostics(yaml_path)
    assert result.discovery.project_root == tmp_path


def test_classify_yaml_kind_override_outside_project_root_falls_back_to_heuristic(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    scalim_yaml = _write(
        repo / "scalim.yaml",
        "yaml_dsl:\n  lsp:\n    kind_overrides:\n      - glob: wf/*.yaml\n        kind: demand\n",
    )
    outside = _write(tmp_path / "outside.yaml", "workflow: {}\n")
    kind = editor_semantics.classify_yaml_dsl_kind(outside, outside.read_text(encoding="utf-8"), scalim_yaml_override=scalim_yaml)
    assert kind == editor_semantics.YAML_DSL_KIND_WORKFLOW


def test_classify_yaml_kind_override_no_match_falls_back_to_heuristic(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    scalim_yaml = _write(
        repo / "scalim.yaml",
        "yaml_dsl:\n  lsp:\n    kind_overrides:\n      - glob: wf/*.yaml\n        kind: workflow\n",
    )
    yaml_path = _write(repo / "demand.yaml", "name: demo\nsources: {}\n")
    kind = editor_semantics.classify_yaml_dsl_kind(yaml_path, yaml_path.read_text(encoding="utf-8"), scalim_yaml_override=scalim_yaml)
    assert kind == editor_semantics.YAML_DSL_KIND_DEMAND


def test_resolve_python_definition_reports_builtin_module_origin(tmp_path: Path) -> None:
    result = editor_semantics.resolve_python_definition("sys:path", python_roots=[tmp_path])
    assert result.locations == ()
    assert any("无法定位模块文件" in w for w in result.warnings)


def test_resolve_python_definition_propagates_ast_parse_warning(tmp_path: Path) -> None:
    _ = _write(tmp_path / "bad_mod.py", "def x(:\n")
    result = editor_semantics.resolve_python_definition("bad_mod:foo", python_roots=[tmp_path])
    assert result.locations == ()
    assert any("模块语法解析失败" in w for w in result.warnings)
    assert any("无法解析符号定义" in w for w in result.warnings)


def test_hover_returns_warnings_when_definition_has_no_locations(tmp_path: Path) -> None:
    result = editor_semantics.hover_python_reference("", python_roots=[tmp_path])
    assert result.text == ""
    assert any("引用不能为空" in w for w in result.warnings)


def test_hover_reports_reference_syntax_error_after_forced_location(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    mod = _write(tmp_path / "m.py", "x = 1\n")
    fake = PythonDefinitionResult(
        locations=(PythonDefinitionLocation(file_path=str(mod), range=None, module_path="m", symbol_path="x"),),
        warnings=("from-resolve",),
    )
    monkeypatch.setattr(editor_semantics, "resolve_python_definition", lambda *_a, **_k: fake)
    result = editor_semantics.hover_python_reference("not-a-reference", python_roots=[tmp_path])
    assert result.text == ""
    assert result.warnings


def test_hover_returns_empty_text_when_symbol_missing_after_forced_location(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    mod = _write(tmp_path / "m.py", "def foo():\n    return 1\n")
    fake = PythonDefinitionResult(
        locations=(PythonDefinitionLocation(file_path=str(mod), range=None, module_path="m", symbol_path="foo"),),
        warnings=(),
    )
    monkeypatch.setattr(editor_semantics, "resolve_python_definition", lambda *_a, **_k: fake)
    result = editor_semantics.hover_python_reference("m:missing", python_roots=[tmp_path])
    assert result.text == ""


def test_complete_python_reference_reports_builtin_module_origin(tmp_path: Path) -> None:
    result = editor_semantics.complete_python_reference("sys:", python_roots=[tmp_path])
    assert result.items == ()
    assert any("无法定位模块文件" in w for w in result.warnings)


def test_complete_python_reference_reports_module_ast_parse_failure(tmp_path: Path) -> None:
    _ = _write(tmp_path / "bad_comp.py", "def x(:\n")
    result = editor_semantics.complete_python_reference("bad_comp:", python_roots=[tmp_path])
    assert result.items == ()
    assert any("completion 解析失败" in w for w in result.warnings)


def test_find_spec_returns_none_on_exception(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def _boom(*_a, **_k):
        raise RuntimeError("boom")

    monkeypatch.setattr(editor_semantics.PathFinder, "find_spec", _boom)
    spec = editor_semantics._find_spec("x", roots=(tmp_path,))  # type: ignore[attr-defined]
    assert spec is None


def test_normalize_python_roots_dedups_and_preserves_order(tmp_path: Path) -> None:
    roots = editor_semantics._normalize_python_roots(  # type: ignore[attr-defined]
        [tmp_path, tmp_path],
        default_root=tmp_path,
    )
    assert roots == (tmp_path,)


def test_find_spec_returns_none_for_empty_module_path(tmp_path: Path) -> None:
    spec = editor_semantics._find_spec("", roots=(tmp_path,))  # type: ignore[attr-defined]
    assert spec is None


def test_find_spec_breaks_when_top_level_spec_missing(tmp_path: Path) -> None:
    spec = editor_semantics._find_spec("missing_pkg.mod", roots=(tmp_path,))  # type: ignore[attr-defined]
    assert spec is None


def test_find_spec_returns_none_when_parent_is_not_package(tmp_path: Path) -> None:
    _write(tmp_path / "m.py", "x = 1\n")
    spec = editor_semantics._find_spec("m.sub", roots=(tmp_path,))  # type: ignore[attr-defined]
    assert spec is None


def test_find_symbol_in_module_branches() -> None:
    tree = ast.parse("def foo():\n    return 1\n\nclass C:\n    def m(self):\n        return 2\n")
    assert editor_semantics._find_symbol_in_module(tree, ()) is None  # type: ignore[attr-defined]
    assert editor_semantics._find_symbol_in_module(tree, ("nope",)) is None  # type: ignore[attr-defined]

    node = editor_semantics._find_symbol_in_module(tree, ("foo", "bar"))  # type: ignore[attr-defined]
    assert isinstance(node, ast.FunctionDef)

    assert editor_semantics._find_symbol_in_module(tree, ("C", "missing")) is None  # type: ignore[attr-defined]
