from scalim.dsl.by_yaml import compile as compile_yaml
from scalim_misc.notebook_support.pathing import demo_big_data_report_yaml_path


def test_output_fields_yaml_alias_list_is_flattened(ecommerce_config_small) -> None:
    _ = ecommerce_config_small
    yaml_path = demo_big_data_report_yaml_path(__file__)

    compilation = compile_yaml(
        str(yaml_path),
        allowed_modules=frozenset(["scalim_misc.demo_big_data_report.loaders"]),
        init_vars={"order_ids": []},
    )
    comp = compilation
    assert comp.request.output_composition is not None

    detail = None
    for target in comp.request.output_composition.targets:
        if target.target_id == "detail":
            detail = target
            break
    assert detail is not None

    field_ids = list(detail.layout.field_ids)
    assert field_ids and all(isinstance(x, str) for x in field_ids)
    assert not any(x.startswith("[") for x in field_ids)
    assert "order_id" in field_ids
    assert "final_price" in field_ids
