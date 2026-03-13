from pathlib import Path

from scalim.dsl.by_yaml.runtime import introspection as runtime_introspection
from scalim.dsl.by_yaml.schema_dsl.models import DemandConfig, OutputAggregateConfig, OutputAggregateMetricConfig, OutputTargetConfig
from scalim.ob.presets.viz import VizObserver


def test_default_output_fields_empty_outputs_returns_empty_list() -> None:
    assert runtime_introspection._default_output_fields_from_primary_output(DemandConfig()) == []  # noqa: SLF001


def test_default_output_fields_primary_detail_no_fields_returns_empty_list() -> None:
    config = DemandConfig(outputs=(OutputTargetConfig(name="detail", fields=()),))
    assert runtime_introspection._default_output_fields_from_primary_output(config) == []  # noqa: SLF001


def test_default_output_fields_primary_aggregate_includes_metrics_and_rank_field() -> None:
    agg = OutputAggregateConfig(
        group_by=("a",),
        metrics={"m": OutputAggregateMetricConfig(op="count")},
        rank_by="m",
        rank_field_id="r",
    )
    config = DemandConfig(outputs=(OutputTargetConfig(name="agg", aggregate=agg),))
    assert runtime_introspection._default_output_fields_from_primary_output(config) == ["a", "m", "r"]  # noqa: SLF001


def _write_minimal_yaml(tmp_path: Path) -> Path:
    yaml_path = tmp_path / "demo.demand.yaml"
    yaml_path.write_text(
        """
name: demo
main_source:
  source_id: orders
  loader: tests.conftest.mock_loader
  order_by: [order_id]
  fields:
    order_id:
      extract: order_id
    amount:
      extract: amount
sources: {}
outputs:
  - name: detail
    container: {type: workbook, path: ./out.xlsx, sheet: S}
    fields: [amount]
""".lstrip(),
        encoding="utf-8",
    )
    return yaml_path


def test_resolve_required_field_ids_appends_order_by_when_missing(tmp_path: Path) -> None:
    yaml_path = _write_minimal_yaml(tmp_path)

    required = runtime_introspection.resolve_required_field_ids(
        str(yaml_path),
        allowed_modules=frozenset(["tests"]),
        output_fields=["amount"],
    )
    assert required == ["amount", "order_id"]


def test_build_viz_observer_targets_branching(tmp_path: Path) -> None:
    yaml_path = _write_minimal_yaml(tmp_path)

    observer = runtime_introspection.build_viz_observer(
        str(yaml_path),
        allowed_modules=frozenset(["tests"]),
        output_fields=["amount"],
    )
    assert isinstance(observer, VizObserver)

    observer = runtime_introspection.build_viz_observer(
        str(yaml_path),
        allowed_modules=frozenset(["tests"]),
    )
    assert isinstance(observer, VizObserver)
