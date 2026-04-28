import pytest

from scalim.dsl.yaml_dsl import DemandRunOptions, DemandRunSecurityOptions, compile
from scalim.dsl.yaml_dsl._internal.config_parsing.error_envelope import ScalimYamlValidationError
from scalim.dsl.yaml_dsl.init_var_nodes import InitVarRef
from scalim.dsl.yaml_dsl.runtime.output_path_resolve import resolve_output_container_path


def test_compile_pathless_csv_output_fails_fast_with_workflow_managed_hint(tmp_path) -> None:
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
resources:
  files:
    detail_csv:
      csv_file: {}
outputs:
  - name: detail
    to: {file: detail_csv}
    fields:
      - order_id
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(ScalimYamlValidationError) as excinfo:
        _ = compile(
            str(yaml_path),
            options=DemandRunOptions(security=DemandRunSecurityOptions(allowed_modules=frozenset(["tests.fixtures"]))),
        )
    assert any(e.path == "resources.files.detail_csv.csv_file.path" for e in excinfo.value.errors)


def test_resolve_output_container_path_branches() -> None:
    with pytest.raises(ValueError, match=r"x is required"):
        _ = resolve_output_container_path(None, init_vars=None, path="x")
    with pytest.raises(ValueError, match=r"x is required"):
        _ = resolve_output_container_path("   ", init_vars=None, path="x")

    with pytest.raises(TypeError, match=r"x must be a string path or InitVarRef"):
        _ = resolve_output_container_path({"$init_var": "p"}, init_vars={"p": "./out.csv"}, path="x")  # type: ignore[arg-type]

    assert resolve_output_container_path(InitVarRef(name="p", path="x"), init_vars={"p": "./out.csv"}, path="x") == "./out.csv"

    with pytest.raises(ValueError, match=r"Missing init_var 'p'"):
        _ = resolve_output_container_path(InitVarRef(name="p", path="x"), init_vars=None, path="x")
