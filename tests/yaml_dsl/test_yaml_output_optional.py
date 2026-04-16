from scalim.dsl.yaml_dsl._internal.config_parsing.loader import YamlDemandLoader
from scalim.dsl.yaml_dsl import DemandRunOptions, DemandRunOutputOptions, DemandRunSecurityOptions, RunOverrides, compile


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

    out_root = tmp_path / "out"
    compilation = compile(
        str(yaml_path),
        options=DemandRunOptions(
            security=DemandRunSecurityOptions(allowed_modules=frozenset(["tests.fixtures"])),
            outputs=DemandRunOutputOptions(
                overrides=RunOverrides.csv_file(output_root=out_root, fields=("order_id",), output_name="detail", file_id="detail_csv")
            ),
        ),
    )

    assert compilation.config.outputs == ()
    assert compilation.request.output_composition is not None
    assert compilation.request.output_composition.targets[0].output.format == "csv"

    from pathlib import Path

    from scalim.execution.versioned_outputs import parse_versioned_output_path  # noqa: PLC0415

    out_path = Path(str(compilation.request.output_composition.targets[0].output.path))
    parsed = parse_versioned_output_path(out_path)
    assert parsed.root == out_root.resolve(strict=False)
    assert parsed.kind == "files"
    assert parsed.artifact_id == "detail_csv"
