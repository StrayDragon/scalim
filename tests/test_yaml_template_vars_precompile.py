import pytest

from scalim.dsl.by_yaml import compile, run_workflow
from scalim.dsl.by_yaml.workflow import WorkflowConfigError, load_workflow_config


def test_template_vars_precompile_supports_unquoted_placeholders_in_demand_yaml(tmp_path) -> None:
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
      path: {{ output_path }}
    fields:
      - order_id
""".lstrip(),
        encoding="utf-8",
    )

    compilation = compile(str(yaml_path), allowed_modules=frozenset(["tests"]), template_vars={"output_path": "./output/report.xlsx"})
    assert compilation.config.outputs[0].container.path == "./output/report.xlsx"


def test_template_vars_opt_in_does_not_render_when_not_provided(tmp_path) -> None:
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
      path: "{{ output_path }}"
    fields:
      - order_id
""".lstrip(),
        encoding="utf-8",
    )

    compilation = compile(str(yaml_path), allowed_modules=frozenset(["tests"]))
    assert compilation.config.outputs[0].container.path == "{{ output_path }}"


def test_template_vars_precompile_applies_to_import_fragments(tmp_path) -> None:
    frag = tmp_path / "common.yaml"
    frag.write_text(
        """
sources:
  customers:
    loader: tests.conftest.mock_loader
    key: customer_id
    lookup_chunk_size: {{ chunk_size }}
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
  loader: tests.conftest.mock_loader
  fields:
    order_id: {}
sources:
  $import: common.sources
""".lstrip(),
        encoding="utf-8",
    )

    compilation = compile(str(demand), allowed_modules=frozenset(["tests"]), template_vars={"chunk_size": 10})
    assert compilation.config.sources["customers"].lookup_chunk_size == 10


def test_template_vars_missing_var_in_demand_fails_fast_with_file_context(tmp_path) -> None:
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
      path: {{ missing }}
    fields:
      - order_id
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as exc_info:
        _ = compile(str(yaml_path), allowed_modules=frozenset(["tests"]), template_vars={})
    assert "missing" in str(exc_info.value)
    assert "demand.yaml" in str(exc_info.value)


def test_template_vars_missing_var_in_import_fragment_includes_import_trace(tmp_path) -> None:
    frag = tmp_path / "common.yaml"
    frag.write_text(
        """
sources:
  customers:
    loader: tests.conftest.mock_loader
    key: customer_id
    lookup_chunk_size: {{ missing }}
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
  loader: tests.conftest.mock_loader
  fields:
    order_id: {}
sources:
  $import: common.sources
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as exc_info:
        _ = compile(str(demand), allowed_modules=frozenset(["tests"]), template_vars={})
    assert "missing" in str(exc_info.value)
    assert "import trace" in str(exc_info.value)
    assert "common.yaml" in str(exc_info.value)


def test_template_vars_precompile_applies_to_workflow_yaml_max_concurrency(tmp_path) -> None:
    out_path = tmp_path / "out.csv"
    demand = tmp_path / "demand.yaml"
    demand_text = (
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
      path: "__OUT_PATH__"
    fields:
      - order_id
"""
    ).lstrip()
    demand.write_text(
        demand_text.replace("__OUT_PATH__", str(out_path)),
        encoding="utf-8",
    )

    wf = tmp_path / "workflow.yaml"
    wf.write_text(
        """
workflow:
  runs:
    - id: a
      demand: demand.yaml
  options:
    max_concurrency: {{ max_concurrency }}
    failure_policy: all_fail
""".lstrip(),
        encoding="utf-8",
    )

    cfg = load_workflow_config(str(wf), template_vars={"max_concurrency": 3})
    assert cfg.options.max_concurrency == 3

    result = run_workflow(str(wf), allowed_modules=frozenset(["tests"]), template_vars={"max_concurrency": 3})
    assert result.errors() == []


def test_template_vars_missing_var_in_workflow_yaml_is_wrapped_as_workflow_config_error(tmp_path) -> None:
    wf = tmp_path / "workflow.yaml"
    wf.write_text(
        """
workflow:
  runs:
    - id: a
      demand: demand.yaml
  options:
    max_concurrency: {{ missing }}
    failure_policy: all_fail
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(WorkflowConfigError) as exc_info:
        _ = load_workflow_config(str(wf), template_vars={})
    assert "missing" in str(exc_info.value)
