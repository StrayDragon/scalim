from pathlib import Path

import pytest

from scalim.dsl.by_yaml import UNSET, OutputOverrides, RunOverrides, compile
from scalim.ob.presets.viz import VizObserverConfig


def _write_yaml(tmp_path: Path, text: str) -> Path:
    yaml_path = tmp_path / "overlay.yaml"
    yaml_path.write_text(text.strip() + "\n", encoding="utf-8")
    return yaml_path


def test_unset_repr() -> None:
    assert repr(UNSET) == "UNSET"


def test_compile_applies_output_overrides_and_export_layout(tmp_path: Path) -> None:
    yaml_path = _write_yaml(
        tmp_path,
        """
name: overlay_demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id:
      extract: order_id
      name: Order ID
    amount:
      extract: amount
      name: Amount
sources: {}
""",
    )

    out_path = str(tmp_path / "out.xlsx")
    overrides = RunOverrides(
        output=OutputOverrides(
            format="excel",
            path=out_path,
            encoding="utf-16",
            streaming=False,
            include_header=False,
            header_fields_output_by="name",
            fields=["amount", "order_id"],
        )
    )

    compilation = compile(str(yaml_path), allowed_modules=frozenset(["tests.conftest"]), overrides=overrides)
    request = compilation.request
    assert request.output.format == "excel"
    assert request.output.path == out_path
    assert request.output.encoding == "utf-16"
    assert request.output.streaming is False
    assert request.output.include_header is False
    assert request.export_layout.field_ids == ("amount", "order_id")
    assert request.export_layout.header_names == ("Amount", "Order ID")


def test_compile_output_overrides_fields_none_selects_all_fields(tmp_path: Path) -> None:
    yaml_path = _write_yaml(
        tmp_path,
        """
name: overlay_fields_none
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id:
      extract: order_id
    amount:
      extract: amount
sources: {}
""",
    )

    overrides = RunOverrides(output=OutputOverrides(fields=None))

    compilation = compile(str(yaml_path), allowed_modules=frozenset(["tests.conftest"]), overrides=overrides)
    assert set(compilation.request.export_layout.field_ids) == set(compilation.demand_ir.fields.keys())


def test_compile_output_overrides_fields_empty_rejected(tmp_path: Path) -> None:
    yaml_path = _write_yaml(
        tmp_path,
        """
name: overlay_fields_empty
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
""",
    )

    overrides = RunOverrides(output=OutputOverrides(fields=[]))

    with pytest.raises(ValueError, match="overrides\\.output\\.fields cannot be empty"):
        _ = compile(str(yaml_path), allowed_modules=frozenset(["tests.conftest"]), overrides=overrides)


def test_compile_viz_config_override_enables_viz_without_yaml_observability(tmp_path: Path) -> None:
    yaml_path = _write_yaml(
        tmp_path,
        """
name: overlay_viz_enable
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
""",
    )

    viz_config = VizObserverConfig(
        output_path=str(tmp_path / "events.jsonl"),
        snapshot_path=str(tmp_path / "snapshot.json"),
    )
    overrides = RunOverrides(viz_config=viz_config)

    compilation = compile(str(yaml_path), allowed_modules=frozenset(["tests.conftest"]), overrides=overrides)
    assert compilation.request.observability is not None
    assert compilation.request.observability.viz_config is viz_config


def test_compile_viz_config_override_none_disables_viz(tmp_path: Path) -> None:
    yaml_path = _write_yaml(
        tmp_path,
        """
name: overlay_viz_disable
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
observability:
  viz:
    enabled: true
    output_dir: ./tmp
""",
    )

    overrides = RunOverrides(viz_config=None)

    compilation = compile(str(yaml_path), allowed_modules=frozenset(["tests.conftest"]), overrides=overrides)
    assert compilation.request.observability is not None
    assert compilation.request.observability.viz_config is None


def test_compile_viz_config_override_overrides_yaml_observability(tmp_path: Path) -> None:
    yaml_path = _write_yaml(
        tmp_path,
        """
name: overlay_viz_override
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
observability:
  performance:
    enabled: true
    metrics: [duration]
    sampling_interval: 1
    report:
      format: none
""",
    )

    viz_config = VizObserverConfig(
        output_path=str(tmp_path / "events.jsonl"),
        snapshot_path=str(tmp_path / "snapshot.json"),
    )
    overrides = RunOverrides(viz_config=viz_config)

    compilation = compile(str(yaml_path), allowed_modules=frozenset(["tests.conftest"]), overrides=overrides)
    assert compilation.request.observability is not None
    assert compilation.request.observability.viz_config is viz_config


def test_compile_keeps_null_batch_size_from_yaml(tmp_path: Path) -> None:
    yaml_path = _write_yaml(
        tmp_path,
        """
name: overlay_batch_size_null
batch_size: null
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
""",
    )

    compilation = compile(str(yaml_path), allowed_modules=frozenset(["tests.conftest"]))
    config = compilation.config
    request = compilation.request

    assert config.batch_size is None
    assert request.batch_size is None


def test_compile_batch_size_option_overrides_yaml_null(tmp_path: Path) -> None:
    yaml_path = _write_yaml(
        tmp_path,
        """
name: overlay_batch_size_override
batch_size: null
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  fields:
    order_id:
      extract: order_id
sources: {}
""",
    )

    compilation = compile(
        str(yaml_path),
        allowed_modules=frozenset(["tests.conftest"]),
        batch_size=256,
    )
    request = compilation.request

    assert request.batch_size == 256
