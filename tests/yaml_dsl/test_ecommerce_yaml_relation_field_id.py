from pathlib import Path

from scalim.dsl.yaml_dsl import DemandRunOptions, DemandRunSecurityOptions, DemandRunTemplateOptions, compile as compile_yaml
from scalim.spec.ir import FieldIr
from scalim_misc.notebook_support.pathing import demo_big_data_report_yaml_path


def test_ecommerce_yaml_relation_steps_support_field_id_alias(ecommerce_config_small, tmp_path: Path) -> None:
    _ = ecommerce_config_small
    _ = tmp_path
    yaml_path = demo_big_data_report_yaml_path(__file__)

    compilation = compile_yaml(
        str(yaml_path),
        options=DemandRunOptions(
            security=DemandRunSecurityOptions(allowed_modules=frozenset(["scalim_misc.demo_big_data_report.loaders"])),
            template=DemandRunTemplateOptions(init_vars={"order_ids": []}),
        ),
    )

    relation = compilation.config.relations.get("orders_to_categories")
    assert relation is not None
    assert relation.steps[1].from_ == "products.category_id"

    field_spec = compilation.demand_ir.fields["category_name"]
    assert isinstance(field_spec, FieldIr)
    assert field_spec.lookup_steps is not None
    assert field_spec.lookup_steps[-1].from_field == "category_id"
