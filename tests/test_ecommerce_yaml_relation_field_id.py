from pathlib import Path

from scalim.dsl.by_yaml import compile as compile_yaml
from scalim.spec.ir import FieldIr


def test_ecommerce_yaml_relation_steps_support_field_id_alias(ecommerce_config_small, tmp_path: Path) -> None:
    _ = ecommerce_config_small
    repo_root = Path(__file__).resolve().parents[1]
    yaml_path = repo_root / "notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml"

    compilation = compile_yaml(
        str(yaml_path),
        allowed_modules=frozenset(["scalim_misc.demo_big_data_report.loaders"]),
        runtime_vars={"order_ids": []},
    )

    relation = compilation.config.relations.get("orders_to_categories")
    assert relation is not None
    assert relation.steps[1].from_ == "products.category_id"

    field_spec = compilation.demand_ir.fields["category_name"]
    assert isinstance(field_spec, FieldIr)
    assert field_spec.lookup_steps is not None
    assert field_spec.lookup_steps[-1].from_field == "category_id"
