from pathlib import Path

import pytest

from scalim.dsl.yaml_dsl._internal.config_parsing.errors import ScalimConfigValidationError
from scalim.dsl.yaml_dsl.runtime.introspection import load_output_config


def _write_yaml(tmp_path: Path, filename: str, content: str) -> Path:
    yaml_path = tmp_path / filename
    yaml_path.write_text(content, encoding="utf-8")
    return yaml_path


def test_load_output_config_resolves_output_fields_and_names(tmp_path: Path) -> None:
    yaml_path = _write_yaml(
        tmp_path,
        "export.yaml",
        """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
      name: Order ID
    region:
      extract: region
      name: Region
    customer_id:
      extract: customer_id
      name: Customer ID
sources:
  customers:
    loader: tests.fixtures.mock_loaders.mock_loader
    key: customer_id
    params:
      ids: {$keys: {as: set}}
    fields:
      customer_name:
        extract: customer_name
        name: Customer Name
        relation:
          steps:
            - from: orders.customer_id
              to: customers.customer_id
fields:
  profit:
    name: Profit
    compute: "order_id"
resources:
  files:
    detail_csv: {kind: csv_file, path: ./out.csv}
outputs:
  - name: detail
    to: {file: detail_csv}
    fields: [order_id, customer_name, region, profit]
""",
    )

    result = load_output_config(str(yaml_path))

    assert result["params"] == {}
    assert result["output_fields"] == ["order_id", "customer_name", "region", "profit"]
    assert result["field_name_mapping"]["order_id"] == "Order ID"
    assert result["field_name_mapping"]["customer_name"] == "Customer Name"
    assert result["field_name_mapping"]["region"] == "Region"
    assert result["field_name_mapping"]["profit"] == "Profit"


def test_load_output_config_default_aggregate_output_fields_includes_compute_and_matches_runtime_default(tmp_path: Path) -> None:
    from scalim.dsl.yaml_dsl._internal.config_parsing.loader import YamlDemandLoader
    from scalim.dsl.yaml_dsl.runtime import output_composition_yaml as oc_yaml

    yaml_path = _write_yaml(
        tmp_path,
        "export_agg.yaml",
        """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    customer_id: {extract: customer_id}
    amount: {extract: amount}
sources: {}
resources:
  files:
    summary_csv: {kind: csv_file, path: ./out.csv}
outputs:
  - name: summary
    to: {file: summary_csv}
    aggregate:
      group_by: [customer_id]
      fields:
        order_cnt: {count: {}}
        sum_amount: {sum: {field: amount}}
        avg_amount: {compute: "sum_amount / order_cnt"}
""",
    )

    result = load_output_config(str(yaml_path))
    assert result["output_fields"] == ["customer_id", "order_cnt", "sum_amount", "avg_amount"]

    config = YamlDemandLoader().load(str(yaml_path))
    assert config.outputs is not None
    assert config.outputs[0].aggregate is not None
    assert result["output_fields"] == list(oc_yaml._derived_output_layout_fields(config.outputs[0].aggregate))  # noqa: SLF001


@pytest.mark.parametrize(
    "filename,content,error_match",
    [
        (
            "export_missing.yaml",
            """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
sources: {}
resources:
  files:
    detail_csv: {kind: csv_file, path: ./out.csv}
outputs:
  - name: detail
    to: {file: detail_csv}
    fields: [missing]
""",
            "outputs.detail.fields reference unknown fields: missing",
        ),
        (
            "export_sources.yaml",
            """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
sources:
  bad: 1
  good:
    loader: tests.fixtures.mock_loaders.mock_loader
    key: customer_id
    fields:
      customer_id:
        extract: customer_id
        name: Customer
resources:
  files:
    detail_csv: {kind: csv_file, path: ./out.csv}
outputs:
  - name: detail
    to: {file: detail_csv}
    fields: [customer_id]
""",
            "Source 'bad' must be a dictionary",
        ),
        (
            "export_bad_output.yaml",
            """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
sources: {}
output:
  fields: customer_id
""",
            "Legacy YAML syntax is not supported: top-level 'output'",
        ),
    ],
    ids=["missing-output", "bad-sources", "bad-output-list"],
)
def test_load_output_config_validation_errors(
    tmp_path: Path,
    filename: str,
    content: str,
    error_match: str,
) -> None:
    yaml_path = _write_yaml(tmp_path, filename, content)

    with pytest.raises(ScalimConfigValidationError) as exc:
        load_output_config(str(yaml_path))

    assert any(error_match in msg for msg in exc.value.errors)
