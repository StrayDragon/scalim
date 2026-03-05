from scalim.dsl.by_yaml.config_parsing.loader import YamlDemandLoader
from scalim.dsl.by_yaml import OutputOverrides, RunOverrides, compile


def test_loader_allows_missing_output() -> None:
    loader = YamlDemandLoader()

    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id:
      field: order_id
sources: {}
"""

    config = loader.load_string(yaml_content)

    assert config.output is None


def test_compile_applies_output_overrides_when_output_missing(tmp_path) -> None:
    yaml_path = tmp_path / "demand.yaml"
    yaml_path.write_text(
        """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id:
      field: order_id
sources: {}
""",
        encoding="utf-8",
    )

    out_path = tmp_path / "out.csv"
    compilation = compile(
        str(yaml_path),
        allowed_modules=frozenset(["tests"]),
        overrides=RunOverrides(output=OutputOverrides(path=str(out_path))),
    )

    assert compilation.config.output is None
    assert compilation.request.output.path == str(out_path)
    assert compilation.request.output.format == "csv"
