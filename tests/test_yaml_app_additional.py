from pathlib import Path

import pytest

from scalim.dsl.by_yaml.config_parsing.errors import ConfigValidationError
from scalim.dsl.by_yaml.runtime.introspection import load_output_config


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
  loader: tests.conftest.mock_loader
  fields:
    order_id: &order_id
      extract: order_id
      name: Order ID
    region: &region
      extract: region
      name: Region
    customer_id:
      extract: customer_id
      name: Customer ID
sources:
  customers:
    loader: tests.conftest.mock_loader
    key: customer_id
    params:
      ids: {$keys: {as: set}}
    fields:
      customer_name: &customer_name
        extract: customer_name
        name: Customer Name
fields:
  profit: &profit
    name: Profit
    compute: "order_id"
relations:
  orders_to_customers: &orders_to_customers
    steps:
      - from: orders.customer_id
        to: customers.customer_id
output:
  fields:
    - *order_id
    - field_id: customer_name
      name: Customer Name Override
    - field_id: region
      name: Region Override
    - *profit
""",
    )

    result = load_output_config(str(yaml_path))

    assert result["params"] == {}
    assert result["output_fields"] == ["order_id", "customer_name", "region", "profit"]
    assert result["field_name_mapping"]["order_id"] == "Order ID"
    assert result["field_name_mapping"]["customer_name"] == "Customer Name Override"
    assert result["field_name_mapping"]["region"] == "Region Override"
    assert result["field_name_mapping"]["profit"] == "Profit"


@pytest.mark.parametrize(
    "filename,content,error_match",
    [
        (
            "export_missing.yaml",
            """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
sources: {}
output:
  fields:
    - field_id: missing
      name: Missing
    - 123
""",
            "Output field 'missing' not found",
        ),
        (
            "export_sources.yaml",
            """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
sources:
  bad: 1
  good:
    loader: tests.conftest.mock_loader
    key: customer_id
    fields:
      customer_id:
        extract: customer_id
        name: Customer
output:
  fields:
    - field_id: customer_id
""",
            "Source 'bad' must be a dictionary",
        ),
        (
            "export_bad_output.yaml",
            """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
sources: {}
output:
  fields: customer_id
""",
            "output.fields must be a list",
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

    with pytest.raises(ConfigValidationError) as exc:
        load_output_config(str(yaml_path))

    assert any(error_match in msg for msg in exc.value.errors)
