from scalim.dsl.by_yaml._internal.config_parsing.effective_yaml import dump_effective_demand_yaml, load_effective_demand_yaml
from scalim.dsl.by_yaml._internal.config_parsing.imports import ScalimYamlImportExpansionError


def test_effective_yaml_renders_and_dumps_without_import_syntax(tmp_path) -> None:
    frag = tmp_path / "frag.yaml"
    frag.write_text(
        """
base:
  main_source:
    params:
      a: 1
""".lstrip(),
        encoding="utf-8",
    )

    demand = tmp_path / "demand.yaml"
    demand.write_text(
        """
name: demo
imports:
  f: ./frag.yaml
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  params:
    $import: f.base.main_source.params
    out_path: {$init_var: out_path}
sources: {}
""".lstrip(),
        encoding="utf-8",
    )

    mapping = load_effective_demand_yaml(demand)
    assert "imports" not in mapping
    assert "$import" not in mapping
    assert mapping["main_source"]["params"]["a"] == 1
    assert mapping["main_source"]["params"]["out_path"]["$init_var"] == "out_path"

    dumped = dump_effective_demand_yaml(mapping)
    assert "imports:" not in dumped
    assert "$import:" not in dumped
    assert "$init_var" in dumped


def test_effective_yaml_fails_fast_on_import_expansion_error_with_diagnostics(tmp_path) -> None:
    frag = tmp_path / "frag.yaml"
    frag.write_text(
        """
main_source:
  params:
    x: 1
""".lstrip(),
        encoding="utf-8",
    )

    demand = tmp_path / "demand.yaml"
    demand.write_text(
        """
imports:
  f: ./frag.yaml
main_source:
  params:
    $import: f.main_source.params
    x: {a: 1}
""".lstrip(),
        encoding="utf-8",
    )

    try:
        _ = load_effective_demand_yaml(demand)
    except ScalimYamlImportExpansionError as exc:
        msg = str(exc)
        assert "import trace:" in msg
        assert "logical path:" in msg
        assert exc.logical_path == "main_source.params.x"
    else:
        raise AssertionError("Expected ScalimYamlImportExpansionError")


def test_effective_yaml_dump_rejects_non_effective_mapping() -> None:
    try:
        _ = dump_effective_demand_yaml({"imports": {"x": "./x.yaml"}})
    except ValueError as exc:
        assert "effective YAML" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
