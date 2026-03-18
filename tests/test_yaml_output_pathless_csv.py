import pytest

from scalim.dsl.by_yaml import compile
from scalim.dsl.by_yaml.runtime import output_composition_yaml as output_composition_yaml_mod


def test_compile_pathless_csv_output_fails_fast_with_workflow_managed_hint(tmp_path) -> None:
    yaml_path = tmp_path / "demand.yaml"
    yaml_path.write_text(
        """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
outputs:
  - name: detail
    container:
      type: csv
    fields:
      - order_id
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"Pathless CSV output.*workflow manages temp outputs for writes"):
        _ = compile(str(yaml_path), allowed_modules=frozenset(["tests"]))


def test_is_pathless_container_path_branches() -> None:
    assert output_composition_yaml_mod._is_pathless_container_path(None) is True  # noqa: SLF001
    assert output_composition_yaml_mod._is_pathless_container_path({"$init_var": "x"}) is False  # noqa: SLF001
