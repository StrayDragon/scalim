from pathlib import Path

from scalim.dsl.by_yaml import compile as compile_yaml


def test_output_fields_yaml_alias_list_is_flattened(ecommerce_config_small) -> None:
    _ = ecommerce_config_small
    repo_root = Path(__file__).resolve().parents[1]
    yaml_path = repo_root / "notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml"

    compilation = compile_yaml(
        str(yaml_path),
        allowed_modules=frozenset(["scalim_misc.demo_big_data_report.loaders"]),
        runtime_vars={"order_ids": []},
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
