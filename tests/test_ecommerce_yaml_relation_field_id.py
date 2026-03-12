from pathlib import Path

from scalim.dsl.by_yaml import OutputOverrides, RunOverrides, run
from scalim.sinks.sink_memory import InMemoryRowSink
from scalim.spec.ir import FieldIr


def test_ecommerce_yaml_relation_steps_support_field_id_alias(ecommerce_config_small, tmp_path: Path) -> None:
    _ = ecommerce_config_small
    repo_root = Path(__file__).resolve().parents[1]
    yaml_path = repo_root / "notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml"
    output_path = tmp_path / "ecommerce_report.csv"
    sink = InMemoryRowSink()

    result = run(
        str(yaml_path),
        allowed_modules=frozenset(["notebooks.marimo.demo_big_data_report._loaders"]),
        overrides=RunOverrides(output=OutputOverrides(path=str(output_path))),
        sink=sink,
        runtime_vars={"order_ids": []},
    )

    relation = result.config.relations.get("orders_to_categories")
    assert relation is not None
    assert relation.steps[1].from_ == "products.product_category_id"

    field_spec = result.demand_ir.fields["category_name"]
    assert isinstance(field_spec, FieldIr)
    assert field_spec.lookup_steps is not None
    assert field_spec.lookup_steps[-1].from_field == "category_id"

    assert any(row.get("category_name") for row in sink.get_data())
