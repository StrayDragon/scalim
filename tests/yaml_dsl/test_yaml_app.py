from pathlib import Path

import pytest
from scalim.vendor.yamlx import yaml

from scalim.dsl.by_yaml import RunOverrides, run
from scalim.dsl.by_yaml.runtime.errors import ScalimAllowlistRequiredError
from scalim.dsl.by_yaml.runtime.introspection import load_output_config, resolve_required_field_ids
from scalim.dsl.by_yaml.config_parsing.errors import ScalimConfigValidationError
from scalim.sinks import InMemoryRowSink
from tests.support.pathing import fixtures_dir

_ALLOWED_MODULES = frozenset(["scalim_misc.example_report_ir"])


def _demo_yaml_path() -> Path:
    return fixtures_dir() / "order_report.yaml"


def _write_yaml_without_output(tmp_path: Path, source_path: Path) -> Path:
    config = yaml.safe_load(source_path.read_text(encoding="utf-8"))
    if isinstance(config, dict):
        config.pop("output", None)
    output_path = tmp_path / "order_report_no_output.yaml"
    output_path.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")
    return output_path


def _write_yaml_with_observability(tmp_path: Path, source_path: Path) -> Path:
    config = yaml.safe_load(source_path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise TypeError("expected mapping")
    config["observability"] = {
        "performance": {
            "enabled": True,
            "metrics": ["duration"],
            "sampling_interval": 1,
            "report": {"format": "none"},
        }
    }
    output_path = tmp_path / "order_report_observability.yaml"
    output_path.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")
    return output_path


@pytest.mark.parametrize(
    "filename,content",
    [
        ("empty.yaml", ""),
        ("list.yaml", "- 1\n- 2\n"),
    ],
    ids=["empty", "list"],
)
def test_load_output_config_defaults(tmp_path: Path, filename: str, content: str) -> None:
    yaml_path = tmp_path / filename
    yaml_path.write_text(content, encoding="utf-8")

    with pytest.raises(TypeError, match="mapping"):
        load_output_config(str(yaml_path))


def test_load_output_config_extracts_fields(tmp_path: Path) -> None:
    yaml_path = tmp_path / "export.yaml"
    yaml_path.write_text(
        """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  params:
    region: eu
  fields:
    order_id:
      extract: order_id
      name: Order ID
    amount:
      extract: amount
      name: Amount
sources: {}
outputs:
  - name: detail
    container: {type: csv, path: ./out.csv}
    fields: [order_id, amount]
""",
        encoding="utf-8",
    )

    result = load_output_config(str(yaml_path))
    assert result["params"] == {"region": "eu"}
    assert result["field_name_mapping"] == {"order_id": "Order ID", "amount": "Amount"}
    assert result["output_fields"] == ["order_id", "amount"]


def test_load_output_config_skips_invalid_field_entry(tmp_path: Path) -> None:
    yaml_path = tmp_path / "export_invalid.yaml"
    yaml_path.write_text(
        """
name: demo
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id:
      extract: order_id
    bad_field: 1
sources: {}
""",
        encoding="utf-8",
    )

    with pytest.raises(ScalimConfigValidationError) as exc:
        load_output_config(str(yaml_path))

    assert any("Field 'bad_field' must be a dictionary" in msg for msg in exc.value.errors)


def test_resolve_required_field_ids_includes_dependencies() -> None:
    yaml_path = _demo_yaml_path()

    fields = resolve_required_field_ids(
        str(yaml_path),
        allowed_modules=_ALLOWED_MODULES,
        output_fields=["profit"],
    )

    assert "profit" in fields
    assert "amount" in fields
    assert "cost" in fields
    assert fields.index("amount") < fields.index("profit")
    assert fields.index("cost") < fields.index("profit")


def test_resolve_required_field_ids_uses_output_fields_from_config() -> None:
    yaml_path = _demo_yaml_path()

    fields = resolve_required_field_ids(str(yaml_path), allowed_modules=_ALLOWED_MODULES)

    assert "order_id" in fields
    assert "profit" in fields


def test_resolve_required_field_ids_includes_main_source_order_by_fields(tmp_path: Path) -> None:
    yaml_path = tmp_path / "order_by.yaml"
    yaml_path.write_text(
        """
name: demo_order_by
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  order_by: [created_at]
  fields:
    order_id:
      extract: order_id
    created_at:
      extract: created_at
sources: {}
outputs:
  - name: detail
    container: {type: csv, path: ./out.csv}
    fields: [order_id]
""",
        encoding="utf-8",
    )

    fields = resolve_required_field_ids(
        str(yaml_path),
        allowed_modules=frozenset(["tests.fixtures.mock_loaders"]),
    )

    assert "order_id" in fields
    assert "created_at" in fields


def test_resolve_required_field_ids_requires_allowlist() -> None:
    yaml_path = _demo_yaml_path()

    with pytest.raises(ScalimAllowlistRequiredError):
        resolve_required_field_ids(str(yaml_path), allowed_modules=frozenset())


@pytest.mark.slow
def test_run_writes_output(tmp_path: Path) -> None:
    yaml_path = _demo_yaml_path()
    output_path = tmp_path / "export.csv"
    sink = InMemoryRowSink()

    result = run(
        str(yaml_path),
        allowed_modules=_ALLOWED_MODULES,
        overrides=RunOverrides(
            outputs=[
                {
                    "name": "detail",
                    "container": {"type": "csv", "path": str(output_path)},
                    "fields": ["order_id"],
                }
            ]
        ),
        sink=sink,
    )

    assert output_path.exists()
    assert result.total_rows > 0
    assert sink.get_data()


def test_resolve_required_field_ids_defaults_to_all_fields(tmp_path: Path) -> None:
    yaml_path = _write_yaml_without_output(tmp_path, _demo_yaml_path())

    fields = resolve_required_field_ids(str(yaml_path), allowed_modules=_ALLOWED_MODULES)

    assert "order_id" in fields
    assert "amount" in fields


@pytest.mark.slow
def test_run_with_performance_observability(tmp_path: Path) -> None:
    yaml_path = _write_yaml_with_observability(tmp_path, _demo_yaml_path())
    output_path = tmp_path / "perf.csv"

    result = run(
        str(yaml_path),
        allowed_modules=_ALLOWED_MODULES,
        overrides=RunOverrides(
            outputs=[
                {
                    "name": "detail",
                    "container": {"type": "csv", "path": str(output_path)},
                    "fields": ["order_id"],
                }
            ]
        ),
    )

    assert output_path.exists()
    assert result.total_rows > 0
