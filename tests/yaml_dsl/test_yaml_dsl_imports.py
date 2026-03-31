import io
import argparse
from pathlib import Path

import pytest

import scalim.cli.yaml_dsl as yaml_dsl_cli
from scalim.dsl.by_yaml.config_parsing import imports as imports_mod
from scalim.dsl.by_yaml.config_parsing.error_envelope import ScalimYamlValidationError
from scalim.dsl.by_yaml.config_parsing.imports import ScalimYamlImportExpansionError, load_and_expand_imports
from scalim.dsl.by_yaml.config_parsing.loader import YamlDemandLoader
from scalim.dsl.by_yaml.config_parsing.validator import validate_yaml_text


def _args(path: Path, *, json_output: bool) -> argparse.Namespace:
    return argparse.Namespace(
        yaml_file=path,
        schema=None,
        strict=True,
        json=json_output,
        verbose=False,
        yaml_dsl_command=None,
        yaml_dsl_schema_command=None,
    )


def test_imports_expand_and_merge_sources_mapping(tmp_path) -> None:
    common = tmp_path / "common.yaml"
    common.write_text(
        """
sources:
  customers:
    loader: tests.fixtures.mock_loaders.mock_loader
    key: customer_id
""".lstrip(),
        encoding="utf-8",
    )

    demand = tmp_path / "demand.yaml"
    demand.write_text(
        """
name: demo
imports:
  common: ./common.yaml
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id: {}
sources:
  $import: common.sources
  customers:
    lookup_chunk_size: 10
""".lstrip(),
        encoding="utf-8",
    )

    config = YamlDemandLoader().load(demand)
    assert "customers" in config.sources
    assert config.sources["customers"].lookup_chunk_size == 10


def test_imports_list_order_is_deterministic(tmp_path) -> None:
    a = tmp_path / "a.yaml"
    a.write_text(
        """
sources:
  customers:
    loader: tests.fixtures.mock_loaders.mock_loader
    key: customer_id
    lookup_chunk_size: 1
""".lstrip(),
        encoding="utf-8",
    )
    b = tmp_path / "b.yaml"
    b.write_text(
        """
sources:
  customers:
    loader: tests.fixtures.mock_loaders.mock_loader
    key: customer_id
    lookup_chunk_size: 2
""".lstrip(),
        encoding="utf-8",
    )
    demand = tmp_path / "demand.yaml"
    demand.write_text(
        """
name: demo
imports:
  a: ./a.yaml
  b: ./b.yaml
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id: {}
sources:
  $import: [a.sources, b.sources]
""".lstrip(),
        encoding="utf-8",
    )

    config = YamlDemandLoader().load(demand)
    assert config.sources["customers"].lookup_chunk_size == 2


def test_imports_list_replace(tmp_path) -> None:
    frag = tmp_path / "frag.yaml"
    frag.write_text(
        """
base:
  resources:
    files:
      detail_csv: {kind: csv_file, path: ./a.csv}
  outputs:
    - name: detail
      to: {file: detail_csv}
      fields: [a]
""".lstrip(),
        encoding="utf-8",
    )
    demand = tmp_path / "demand.yaml"
    demand.write_text(
        """
name: demo
imports:
  f: ./frag.yaml
$import: f.base
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
sources: {}
resources:
  files:
    detail_csv: {kind: csv_file, path: ./b.csv}
outputs:
  - name: detail
    to: {file: detail_csv}
    fields: [b]
""".lstrip(),
        encoding="utf-8",
    )

    expanded = load_and_expand_imports(demand)
    assert expanded["outputs"][0]["fields"] == ["b"]


def test_imports_type_mismatch_fails_fast(tmp_path) -> None:
    frag = tmp_path / "frag.yaml"
    frag.write_text(
        """
base:
  resources:
    files:
      detail_csv: {kind: csv_file, path: ./a.csv}
  outputs:
    - name: detail
      to: {file: detail_csv}
      fields: [a]
""".lstrip(),
        encoding="utf-8",
    )
    demand = tmp_path / "demand.yaml"
    demand.write_text(
        """
name: demo
imports:
  f: ./frag.yaml
$import: f.base
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
sources: {}
outputs: "oops"
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(ScalimYamlImportExpansionError) as exc:
        _ = load_and_expand_imports(demand)
    assert "Type mismatch" in str(exc.value)
    assert exc.value.logical_path == "outputs"


@pytest.mark.parametrize(
    "bad_path",
    [
        "/abs/common.yaml",
        "\\\\secrets.yaml",
        "C:\\\\secrets.yaml",
        "file:///tmp/x.yaml",
        "fragments\\\\common.yaml",
        "@/common.yaml",
        "COMMON:/common.yaml",
    ],
)
def test_imports_path_constraints_reject_absolute_uri_and_reserved_alias_paths(tmp_path, bad_path: str) -> None:
    demand = tmp_path / "demand.yaml"
    demand.write_text(
        """
name: demo
imports:
  common: '{bad_path}'
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
sources: {{}}
""".format(bad_path=bad_path).lstrip(),
        encoding="utf-8",
    )
    with pytest.raises(ScalimYamlImportExpansionError) as excinfo:
        _ = load_and_expand_imports(demand)
    assert excinfo.value.logical_path == "imports"
    msg = str(excinfo.value)
    assert "imports.common invalid path" in msg
    assert "base_dir=" in msg
    assert "resolved=" in msg


def test_imports_scalim_preset_can_be_imported_and_expanded(tmp_path: Path) -> None:
    demand = tmp_path / "demand.yaml"
    demand.write_text(
        """
imports:
  std: "scalim://yaml-dsl/presets/common.yaml"
demo:
  $import: std.demo
  y: 2
""".lstrip(),
        encoding="utf-8",
    )
    expanded = load_and_expand_imports(demand)
    assert expanded["demo"]["x"] == 1
    assert expanded["demo"]["y"] == 2


def test_imports_scalim_yaml_alias_allows_reserved_prefix(tmp_path: Path) -> None:
    scalim_yaml = tmp_path / "scalim.yaml"
    scalim_yaml.write_text(
        """
yaml_dsl:
  import_aliases:
    "@": "./"
""".lstrip(),
        encoding="utf-8",
    )
    fragments = tmp_path / "fragments"
    fragments.mkdir(parents=True)
    common = fragments / "common.yaml"
    common.write_text(
        """
demo:
  x: 1
""".lstrip(),
        encoding="utf-8",
    )

    reports = tmp_path / "reports"
    reports.mkdir(parents=True)
    demand = reports / "demand.yaml"
    demand.write_text(
        """
imports:
  f: "@/fragments/common.yaml"
demo:
  $import: f.demo
  y: 2
""".lstrip(),
        encoding="utf-8",
    )
    expanded = load_and_expand_imports(demand)
    assert expanded["demo"]["x"] == 1
    assert expanded["demo"]["y"] == 2


def test_imports_scalim_yaml_import_allowed_roots_rejects_outside(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir(parents=True)
    common = outside / "common.yaml"
    common.write_text(
        """
demo:
  x: 1
""".lstrip(),
        encoding="utf-8",
    )

    scalim_yaml = tmp_path / "scalim.yaml"
    scalim_yaml.write_text(
        """
yaml_dsl:
  import_allowed_roots:
    - ./allowed
""".lstrip(),
        encoding="utf-8",
    )
    demand = tmp_path / "demand.yaml"
    demand.write_text(
        """
imports:
  f: ./outside/common.yaml
demo:
  $import: f.demo
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(ScalimYamlImportExpansionError) as excinfo:
        _ = load_and_expand_imports(demand)
    msg = str(excinfo.value)
    assert "YAML path escapes allowed roots" in msg
    assert "import_allowed_roots" in msg
    assert str(common.resolve(strict=False)) in msg


def test_imports_scalim_yaml_override_disables_upward_search(tmp_path: Path) -> None:
    outer_scalim_yaml = tmp_path / "scalim.yaml"
    outer_root = tmp_path / "outer"
    outer_root.mkdir(parents=True)
    outer_frag = outer_root / "fragments"
    outer_frag.mkdir(parents=True)
    (outer_frag / "common.yaml").write_text("demo:\n  x: 1\n", encoding="utf-8")
    outer_scalim_yaml.write_text(
        """
yaml_dsl:
  import_aliases:
    "@": "./outer"
""".lstrip(),
        encoding="utf-8",
    )

    project_root = tmp_path / "proj"
    project_root.mkdir(parents=True)
    inner_root = project_root / "inner"
    inner_root.mkdir(parents=True)
    inner_frag = inner_root / "fragments"
    inner_frag.mkdir(parents=True)
    (inner_frag / "common.yaml").write_text("demo:\n  x: 2\n", encoding="utf-8")
    (project_root / "scalim.yaml").write_text(
        """
yaml_dsl:
  import_aliases:
    "@": "./inner"
""".lstrip(),
        encoding="utf-8",
    )

    reports = project_root / "reports"
    reports.mkdir(parents=True)
    demand = reports / "demand.yaml"
    demand.write_text(
        """
imports:
  f: "@/fragments/common.yaml"
demo:
  $import: f.demo
""".lstrip(),
        encoding="utf-8",
    )

    expanded = load_and_expand_imports(demand)
    assert expanded["demo"]["x"] == 2

    expanded = load_and_expand_imports(demand, scalim_yaml_override=outer_scalim_yaml)
    assert expanded["demo"]["x"] == 1

    expanded = load_and_expand_imports(demand, project_root_override=tmp_path)
    assert expanded["demo"]["x"] == 1


def test_imports_mapping_resolve_hint_failures_are_handled(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    demand = tmp_path / "demand.yaml"
    demand.write_text(
        """
name: demo
imports:
  common: 'fragments\\\\common.yaml'
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
sources: {}
""".lstrip(),
        encoding="utf-8",
    )

    original_resolve = Path.resolve

    def _resolve(self: Path, *args, **kwargs):  # type: ignore[no-untyped-def]
        if "\\" in str(self):
            raise OSError("boom")
        return original_resolve(self, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", _resolve)

    with pytest.raises(ScalimYamlImportExpansionError) as excinfo:
        _ = load_and_expand_imports(demand)
    assert "resolved='(unknown)'" in str(excinfo.value)


def test_imports_path_constraints_support_child_dir(tmp_path) -> None:
    reports = tmp_path / "reports"
    reports.mkdir(parents=True)
    shared = reports / "_shared"
    shared.mkdir(parents=True)
    frag = shared / "common.yaml"
    frag.write_text(
        """
demo:
  x: 1
""".lstrip(),
        encoding="utf-8",
    )
    demand = reports / "demand.yaml"
    demand.write_text(
        """
imports:
  f: ./_shared/common.yaml
demo:
  $import: f.demo
  y: 2
""".lstrip(),
        encoding="utf-8",
    )
    expanded = load_and_expand_imports(demand)
    assert expanded["demo"]["x"] == 1
    assert expanded["demo"]["y"] == 2


def test_imports_path_constraints_support_parent_dir(tmp_path) -> None:
    shared = tmp_path / "_shared"
    shared.mkdir(parents=True)
    frag = shared / "common.yaml"
    frag.write_text(
        """
demo:
  x: 1
""".lstrip(),
        encoding="utf-8",
    )

    reports = tmp_path / "reports"
    reports.mkdir(parents=True)
    demand = reports / "demand.yaml"
    demand.write_text(
        """
imports:
  f: ../_shared/common.yaml
demo:
  $import: f.demo
""".lstrip(),
        encoding="utf-8",
    )
    with pytest.raises(ScalimYamlImportExpansionError) as excinfo:
        _ = load_and_expand_imports(demand)
    assert "YAML path escapes allowed roots" in str(excinfo.value)
    assert "allowed_yaml_roots" in str(excinfo.value)

    expanded = load_and_expand_imports(demand, allowed_yaml_roots=[tmp_path])
    assert expanded["demo"]["x"] == 1


def test_imports_symlink_escape_is_rejected_by_default(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    reports.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir(parents=True)
    secret = outside / "secret.yaml"
    secret.write_text(
        """
demo:
  x: 1
""".lstrip(),
        encoding="utf-8",
    )

    link = reports / "link.yaml"
    try:
        link.symlink_to(secret)
    except OSError:
        pytest.skip("symlink not supported in current environment")

    demand = reports / "demand.yaml"
    demand.write_text(
        """
imports:
  f: ./link.yaml
demo:
  $import: f.demo
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(ScalimYamlImportExpansionError) as excinfo:
        _ = load_and_expand_imports(demand)
    assert "YAML path escapes allowed roots" in str(excinfo.value)
    assert str(secret.resolve(strict=False)) in str(excinfo.value)


def test_imports_allowed_yaml_roots_must_exist_and_be_dir(tmp_path: Path) -> None:
    demand = tmp_path / "demand.yaml"
    demand.write_text("name: demo\nsources: {}\n", encoding="utf-8")
    missing_root = tmp_path / "missing_root"
    with pytest.raises(ValueError) as excinfo:
        _ = load_and_expand_imports(demand, allowed_yaml_roots=[missing_root])
    assert "allowed_yaml_roots must be existing directories" in str(excinfo.value)


def test_imports_cycle_detection(tmp_path) -> None:
    a = tmp_path / "a.yaml"
    b = tmp_path / "b.yaml"
    a.write_text(
        """
imports:
  b: ./b.yaml
$import: b
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
sources: {}
""".lstrip(),
        encoding="utf-8",
    )
    b.write_text(
        """
imports:
  a: ./a.yaml
$import: a
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(ScalimYamlImportExpansionError) as exc:
        _ = load_and_expand_imports(a)
    assert "cycle" in str(exc.value).lower()


def test_imports_max_depth(tmp_path) -> None:
    chain_len = 21
    for idx in range(chain_len):
        current = tmp_path / "f{}.yaml".format(idx)
        next_name = "f{}.yaml".format(idx + 1)
        if idx == chain_len - 1:
            current.write_text("x: {}\n", encoding="utf-8")
        else:
            current.write_text(
                """
imports:
  n: ./{next_name}
$import: n
""".format(next_name=next_name).lstrip(),
                encoding="utf-8",
            )

    with pytest.raises(ScalimYamlImportExpansionError) as exc:
        _ = load_and_expand_imports(tmp_path / "f0.yaml")
    assert "max depth" in str(exc.value).lower()


def test_validate_yaml_text_fail_fast_on_imports() -> None:
    result = validate_yaml_text(
        """
name: demo
imports:
  common: ./common.yaml
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
sources:
  $import: common.sources
""".lstrip()
    )
    assert result.ok is False
    assert "imports/$import" in result.errors[0].message


def test_yaml_demand_loader_load_string_fail_fast_on_imports() -> None:
    loader = YamlDemandLoader()
    with pytest.raises(ScalimYamlValidationError) as exc:
        _ = loader.load_string(
            """
name: demo
imports:
  common: ./common.yaml
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
sources: {}
""".lstrip()
        )
    assert any("imports/$import" in env.message for env in exc.value.errors)


def test_cli_validate_and_schema_validate_expand_imports(tmp_path) -> None:
    common = tmp_path / "common.yaml"
    common.write_text(
        """
sources:
  customers:
    loader: tests.fixtures.mock_loaders.mock_loader
    key: customer_id
""".lstrip(),
        encoding="utf-8",
    )

    demand = tmp_path / "demand.yaml"
    demand.write_text(
        """
name: demo
imports:
  common: ./common.yaml
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id: {}
sources:
  $import: common.sources
""".lstrip(),
        encoding="utf-8",
    )

    assert yaml_dsl_cli._run_validate(_args(demand, json_output=True)) == 0
    assert yaml_dsl_cli._run_schema_validate(_args(demand, json_output=True)) == 0


def test_imports_format_trace_empty_returns_empty_string() -> None:
    assert imports_mod._format_trace(()) == ""  # noqa: SLF001


def test_imports_normalize_import_path_rejects_empty() -> None:
    with pytest.raises(ValueError):
        _ = imports_mod._normalize_import_path("")  # noqa: SLF001


def test_imports_mapping_must_be_mapping(tmp_path) -> None:
    demand = tmp_path / "demand.yaml"
    demand.write_text(
        """
imports: []
""".lstrip(),
        encoding="utf-8",
    )
    with pytest.raises(ScalimYamlImportExpansionError) as excinfo:
        _ = load_and_expand_imports(demand)
    assert excinfo.value.logical_path == "imports"
    assert "imports must be a mapping" in str(excinfo.value)


def test_imports_mapping_alias_must_be_non_empty_string(tmp_path) -> None:
    demand = tmp_path / "demand.yaml"
    demand.write_text(
        """
imports:
  1: ./a.yaml
""".lstrip(),
        encoding="utf-8",
    )
    with pytest.raises(ScalimYamlImportExpansionError) as excinfo:
        _ = load_and_expand_imports(demand)
    assert excinfo.value.logical_path == "imports"
    assert "imports alias must be a non-empty string" in str(excinfo.value)


def test_imports_mapping_path_must_be_non_empty_string(tmp_path) -> None:
    demand = tmp_path / "demand.yaml"
    demand.write_text(
        """
imports:
  common: 1
""".lstrip(),
        encoding="utf-8",
    )
    with pytest.raises(ScalimYamlImportExpansionError) as excinfo:
        _ = load_and_expand_imports(demand)
    assert excinfo.value.logical_path == "imports"
    assert "imports.common path must be a non-empty string" in str(excinfo.value)


def test_imports_mapping_path_must_be_yaml_file(tmp_path) -> None:
    demand = tmp_path / "demand.yaml"
    demand.write_text(
        """
imports:
  common: ./common.json
""".lstrip(),
        encoding="utf-8",
    )
    with pytest.raises(ScalimYamlImportExpansionError) as excinfo:
        _ = load_and_expand_imports(demand)
    assert excinfo.value.logical_path == "imports"
    assert ".yaml/.yml" in str(excinfo.value)


def test_imports_contains_import_syntax_detects_nested_mapping() -> None:
    assert imports_mod.contains_import_syntax({"nested": {"imports": {"x": "./x.yaml"}}}) is True


def test_imports_contains_import_syntax_detects_nested_list() -> None:
    assert imports_mod.contains_import_syntax([{"ok": 1}, {"$import": "x"}]) is True


def test_imports_contains_import_syntax_returns_false_for_plain_data() -> None:
    assert imports_mod.contains_import_syntax({"ok": 1}) is False


@pytest.mark.parametrize(
    "bad_ref",
    [
        "",
        "1bad",
        "ok.bad-seg",
    ],
)
def test_imports_invalid_import_ref_is_wrapped(tmp_path, bad_ref: str) -> None:
    frag = tmp_path / "frag.yaml"
    frag.write_text("x: {}\n", encoding="utf-8")
    demand = tmp_path / "demand.yaml"
    demand.write_text(
        """
imports:
  f: ./frag.yaml
$import: "{bad_ref}"
""".format(bad_ref=bad_ref).lstrip(),
        encoding="utf-8",
    )
    with pytest.raises(ScalimYamlImportExpansionError) as excinfo:
        _ = load_and_expand_imports(demand)
    assert "Invalid $import ref" in str(excinfo.value)


def test_imports_unknown_alias_fails_fast(tmp_path) -> None:
    demand = tmp_path / "demand.yaml"
    demand.write_text(
        """
imports: {}
$import: missing
""".lstrip(),
        encoding="utf-8",
    )
    with pytest.raises(ScalimYamlImportExpansionError) as excinfo:
        _ = load_and_expand_imports(demand)
    assert "Unknown $import alias" in str(excinfo.value)


def test_imports_select_fragment_non_mapping_during_drill_fails(tmp_path) -> None:
    frag = tmp_path / "frag.yaml"
    frag.write_text("a: 1\n", encoding="utf-8")
    demand = tmp_path / "demand.yaml"
    demand.write_text(
        """
imports:
  f: ./frag.yaml
$import: f.a.b
""".lstrip(),
        encoding="utf-8",
    )
    with pytest.raises(ScalimYamlImportExpansionError) as excinfo:
        _ = load_and_expand_imports(demand)
    assert "non-mapping" in str(excinfo.value)


def test_imports_select_fragment_missing_key_fails(tmp_path) -> None:
    frag = tmp_path / "frag.yaml"
    frag.write_text("a: {}\n", encoding="utf-8")
    demand = tmp_path / "demand.yaml"
    demand.write_text(
        """
imports:
  f: ./frag.yaml
$import: f.a.b
""".lstrip(),
        encoding="utf-8",
    )
    with pytest.raises(ScalimYamlImportExpansionError) as excinfo:
        _ = load_and_expand_imports(demand)
    assert "missing key" in str(excinfo.value)


def test_imports_select_fragment_final_value_must_be_mapping(tmp_path) -> None:
    frag = tmp_path / "frag.yaml"
    frag.write_text("a: 1\n", encoding="utf-8")
    demand = tmp_path / "demand.yaml"
    demand.write_text(
        """
imports:
  f: ./frag.yaml
$import: f.a
""".lstrip(),
        encoding="utf-8",
    )
    with pytest.raises(ScalimYamlImportExpansionError) as excinfo:
        _ = load_and_expand_imports(demand)
    assert "non-mapping" in str(excinfo.value)


def test_imports_deep_merge_override_list_replaces_prior_list(tmp_path) -> None:
    a = tmp_path / "a.yaml"
    a.write_text(
        """
demo:
  items:
    - a
""".lstrip(),
        encoding="utf-8",
    )
    b = tmp_path / "b.yaml"
    b.write_text(
        """
demo:
  items:
    - b
""".lstrip(),
        encoding="utf-8",
    )
    demand = tmp_path / "demand.yaml"
    demand.write_text(
        """
imports:
  a: ./a.yaml
  b: ./b.yaml
demo:
  $import: [a.demo, b.demo]
""".lstrip(),
        encoding="utf-8",
    )
    expanded = load_and_expand_imports(demand)
    assert expanded["demo"]["items"] == ["b"]


def test_imports_deep_merge_override_type_mismatch_fails_fast(tmp_path) -> None:
    a = tmp_path / "a.yaml"
    a.write_text("x: {a: 1}\n", encoding="utf-8")
    b = tmp_path / "b.yaml"
    b.write_text("x: 1\n", encoding="utf-8")
    demand = tmp_path / "demand.yaml"
    demand.write_text(
        """
imports:
  a: ./a.yaml
  b: ./b.yaml
$import: [a, b]
""".lstrip(),
        encoding="utf-8",
    )
    with pytest.raises(ScalimYamlImportExpansionError) as excinfo:
        _ = load_and_expand_imports(demand)
    assert "Type mismatch during import merge" in str(excinfo.value)


def test_imports_deep_merge_fill_scalar_keeps_local_value(tmp_path) -> None:
    frag = tmp_path / "frag.yaml"
    frag.write_text("x: 1\n", encoding="utf-8")
    demand = tmp_path / "demand.yaml"
    demand.write_text(
        """
imports:
  f: ./frag.yaml
$import: f
x: 2
""".lstrip(),
        encoding="utf-8",
    )
    expanded = load_and_expand_imports(demand)
    assert expanded["x"] == 2


def test_imports_fragment_yaml_must_be_mapping(tmp_path) -> None:
    frag = tmp_path / "frag.yaml"
    frag.write_text("- 1\n- 2\n", encoding="utf-8")
    demand = tmp_path / "demand.yaml"
    demand.write_text(
        """
imports:
  f: ./frag.yaml
$import: f
""".lstrip(),
        encoding="utf-8",
    )
    with pytest.raises(ScalimYamlImportExpansionError) as excinfo:
        _ = load_and_expand_imports(demand)
    assert "YAML root must be a mapping" in str(excinfo.value)


def test_imports_cache_shortcuts_repeat_import_of_same_fragment(tmp_path) -> None:
    frag = tmp_path / "frag.yaml"
    frag.write_text("x: {}\n", encoding="utf-8")
    demand = tmp_path / "demand.yaml"
    demand.write_text(
        """
imports:
  f: ./frag.yaml
$import: [f, f]
""".lstrip(),
        encoding="utf-8",
    )
    expanded = load_and_expand_imports(demand)
    assert expanded["x"] == {}


def test_imports_import_must_be_str_or_list_of_str(tmp_path) -> None:
    frag = tmp_path / "frag.yaml"
    frag.write_text("x: {}\n", encoding="utf-8")
    demand = tmp_path / "demand.yaml"
    demand.write_text(
        """
imports:
  f: ./frag.yaml
demo:
  $import: 1
""".lstrip(),
        encoding="utf-8",
    )
    with pytest.raises(ScalimYamlImportExpansionError) as excinfo:
        _ = load_and_expand_imports(demand)
    assert "$import must be a string or list of strings" in str(excinfo.value)


def test_imports_import_list_entries_must_be_strings(tmp_path) -> None:
    frag = tmp_path / "frag.yaml"
    frag.write_text("x: {}\n", encoding="utf-8")
    demand = tmp_path / "demand.yaml"
    demand.write_text(
        """
imports:
  f: ./frag.yaml
demo:
  $import: [f, 1]
""".lstrip(),
        encoding="utf-8",
    )
    with pytest.raises(ScalimYamlImportExpansionError) as excinfo:
        _ = load_and_expand_imports(demand)
    assert "$import list entries must be strings" in str(excinfo.value)


def test_yaml_demand_loader_load_file_handle_rejects_import_syntax() -> None:
    loader = YamlDemandLoader()
    with pytest.raises(ScalimYamlValidationError) as excinfo:
        _ = loader.load(
            io.StringIO(
                (
                    """
name: demo
imports:
  common: ./common.yaml
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
sources: {}
"""
                ).lstrip()
            )
        )
    assert any("imports/$import" in env.message for env in excinfo.value.errors)


def test_yaml_demand_loader_load_wraps_import_expansion_error(tmp_path) -> None:
    frag = tmp_path / "frag.yaml"
    frag.write_text("x: {}\n", encoding="utf-8")
    demand = tmp_path / "demand.yaml"
    demand.write_text(
        """
name: demo
imports:
  f: ./frag.yaml
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
sources:
  $import: missing
""".lstrip(),
        encoding="utf-8",
    )

    loader = YamlDemandLoader()
    with pytest.raises(ScalimYamlValidationError) as excinfo:
        _ = loader.load(demand)
    assert any("Unknown $import alias" in env.message for env in excinfo.value.errors)
