from scalim.dsl.by_yaml.config_parsing.effective_yaml import dump_effective_demand_yaml, load_effective_demand_yaml
from scalim.dsl.by_yaml.config_parsing.imports import ScalimYamlImportExpansionError


def test_effective_yaml_renders_and_dumps_without_import_syntax(tmp_path) -> None:
    frag = tmp_path / "frag.yaml"
    frag.write_text(
        """
base:
  a: 1
""".lstrip(),
        encoding="utf-8",
    )

    demand = tmp_path / "demand.yaml"
    demand.write_text(
        """
imports:
  f: ./frag.yaml
demo:
  $import: f.base
  out_path: {$init_var: out_path}
""".lstrip(),
        encoding="utf-8",
    )

    mapping = load_effective_demand_yaml(demand)
    assert "imports" not in mapping
    assert "$import" not in mapping
    assert mapping["demo"]["a"] == 1
    assert mapping["demo"]["out_path"]["$init_var"] == "out_path"

    dumped = dump_effective_demand_yaml(mapping)
    assert "imports:" not in dumped
    assert "$import:" not in dumped
    assert "$init_var" in dumped


def test_effective_yaml_fails_fast_on_import_expansion_error_with_diagnostics(tmp_path) -> None:
    frag = tmp_path / "frag.yaml"
    frag.write_text(
        """
demo:
  x: 1
""".lstrip(),
        encoding="utf-8",
    )

    demand = tmp_path / "demand.yaml"
    demand.write_text(
        """
imports:
  f: ./frag.yaml
$import: f
demo: "oops"
""".lstrip(),
        encoding="utf-8",
    )

    try:
        _ = load_effective_demand_yaml(demand)
    except ScalimYamlImportExpansionError as exc:
        msg = str(exc)
        assert "import trace:" in msg
        assert "logical path:" in msg
        assert exc.logical_path == "demo"
    else:
        raise AssertionError("Expected ScalimYamlImportExpansionError")


def test_effective_yaml_dump_rejects_non_effective_mapping() -> None:
    try:
        _ = dump_effective_demand_yaml({"imports": {"x": "./x.yaml"}})
    except ValueError as exc:
        assert "effective YAML" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
