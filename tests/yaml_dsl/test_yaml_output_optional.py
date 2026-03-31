from scalim.dsl.by_yaml.config_parsing.loader import YamlDemandLoader
from scalim.dsl.by_yaml import RunOverrides, compile


def test_loader_allows_missing_output() -> None:
    loader = YamlDemandLoader()

    yaml_content = """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
"""

    config = loader.load_string(yaml_content)

    assert config.outputs == ()


def test_compile_applies_output_overrides_when_output_missing(tmp_path) -> None:
    yaml_path = tmp_path / "demand.yaml"
    yaml_path.write_text(
        """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
""",
        encoding="utf-8",
    )

    out_path = tmp_path / "out.csv"
    compilation = compile(
        str(yaml_path),
        allowed_modules=frozenset(["tests.fixtures"]),
        overrides=RunOverrides(
            outputs=[
                {
                    "name": "detail",
                    "to": {"file": "detail_csv"},
                    "fields": ["order_id"],
                }
            ],
            resources={"files": {"detail_csv": {"kind": "csv_file", "path": str(out_path)}}},
        ),
    )

    assert compilation.config.outputs == ()
    assert compilation.request.output_composition is not None
    assert compilation.request.output_composition.targets[0].output.path == str(out_path)
    assert compilation.request.output_composition.targets[0].output.format == "csv"
