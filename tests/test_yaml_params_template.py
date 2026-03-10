import pytest

import scalim.dsl.by_yaml.params_template as params_tmpl
from scalim.dsl.by_yaml.config_parsing.errors import ConfigValidationError
from scalim.dsl.by_yaml.config_parsing.loader import YamlDemandLoader
from scalim.dsl.by_yaml.config_parsing.validator import ConfigValidator
from scalim.dsl.by_yaml.runtime.conversion import ConfigToIRConverter
from scalim.dsl.by_yaml.runtime.errors import ConversionError
from scalim.dsl.by_yaml.runtime.references import PythonReferenceResolver
from scalim.dsl.by_yaml.schema_dsl.models import (
    BindConfig,
    BindKeysConfig,
    DemandConfig,
    MainSourceConfig,
    RelationConfig,
    RelationStepConfig,
    SourceConfig,
)
from scalim.spec.ir.binding import LoaderCallContextIr


def test_parser_parse_bind_covers_use_rows_and_use_keys() -> None:
    loader = YamlDemandLoader()
    bind = loader._parse_bind(  # type: ignore[attr-defined]
        {
            "use_rows": {"param": "rows", "cache_mode": "batch"},
            "use_keys": {"param": "ids", "as": "list"},
        }
    )
    assert bind is not None
    assert bind.use_rows is not None
    assert bind.use_rows.param == "rows"
    assert bind.use_rows.cache_mode == "batch"
    assert bind.use_keys is not None
    assert bind.use_keys.param == "ids"
    assert bind.use_keys.as_ == "list"


def test_validator_rejects_params_non_mapping() -> None:
    config = {
        "name": "demo",
        "main_source": {"source_id": "orders", "loader": "tests.conftest.mock_loader", "fields": {"order_id": {"extract": "order_id"}}},
        "sources": {"s1": {"loader": "tests.conftest.mock_loader", "key": "id", "params": []}},
    }
    with pytest.raises(ConfigValidationError) as exc:
        ConfigValidator().validate(config)
    assert any("sources.s1.params" in msg and "must be a dictionary" in msg for msg in exc.value.errors)


def test_params_template_node_base_render_raises_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        params_tmpl._NodeBase().render(LoaderCallContextIr(), path="p")  # type: ignore[attr-defined]


def test_params_template_runtime_deepcopy_is_alias_safe_and_path_can_be_empty() -> None:
    payload = {"a": [1], "b": ({"c": {1}},)}
    template = params_tmpl.compile_params_template(
        {"payload": "$runtime.payload"},
        path="",
        runtime_vars={"payload": payload},
    )
    ctx = LoaderCallContextIr(is_ref_loader=False)

    out1 = template.render_kwargs(ctx, path="")
    out1["payload"]["a"].append(2)
    out1["payload"]["b"][0]["c"].add(2)

    out2 = template.render_kwargs(ctx, path="")
    assert out2["payload"]["a"] == [1]
    assert out2["payload"]["b"][0]["c"] == {1}


def test_params_template_missing_runtime_var_has_path_and_str() -> None:
    with pytest.raises(params_tmpl.ParamsTemplateCompileError) as exc:
        params_tmpl.compile_params_template({"x": "$runtime.missing"}, path="root", runtime_vars={})
    assert exc.value.path == "root.x"
    assert "Missing runtime var" in str(exc.value)
    assert "(path=root.x)" in str(exc.value)


def test_params_template_runtime_placeholder_does_not_do_substring_interpolation() -> None:
    template = params_tmpl.compile_params_template(
        {"sql": "and t > $runtime.end_dt"},
        path="p",
        runtime_vars={"end_dt": "SHOULD_NOT_APPLY"},
    )
    out = template.render_kwargs(LoaderCallContextIr(is_ref_loader=False), path="p")
    assert out["sql"] == "and t > $runtime.end_dt"


def test_params_template_invalid_runtime_placeholder_is_literal_string() -> None:
    template = params_tmpl.compile_params_template(
        {"sql": "$runtime.bad-name"},
        path="p",
        runtime_vars={},
    )
    out = template.render_kwargs(LoaderCallContextIr(is_ref_loader=False), path="p")
    assert out["sql"] == "$runtime.bad-name"


def test_params_template_compile_validates_options_and_conflicts() -> None:
    with pytest.raises(params_tmpl.ParamsTemplateCompileError, match="mutually exclusive"):
        params_tmpl.compile_params_template({"a": {"$keys": None}, "b": {"$rows": None}}, path="p")

    with pytest.raises(params_tmpl.ParamsTemplateCompileError, match="mutually exclusive"):
        params_tmpl.compile_params_template({"a": {"$rows": None}, "b": {"$keys": None}}, path="p")

    with pytest.raises(params_tmpl.ParamsTemplateCompileError, match="Conflicting `\\$keys\\.as`"):
        params_tmpl.compile_params_template({"a": {"$keys": {"as": "set"}}, "b": {"$keys": {"as": "list"}}}, path="p")

    with pytest.raises(params_tmpl.ParamsTemplateCompileError, match="Conflicting `\\$rows\\.cache_mode`"):
        params_tmpl.compile_params_template(
            {"a": {"$rows": {"cache_mode": "batch"}}, "b": {"$rows": {"cache_mode": "none"}}},
            path="p",
        )

    with pytest.raises(params_tmpl.ParamsTemplateCompileError, match="`\\$keys` is not allowed"):
        params_tmpl.compile_params_template({"ids": {"$keys": None}}, path="p", allow_keys=False)

    with pytest.raises(params_tmpl.ParamsTemplateCompileError, match="`\\$rows` is not allowed"):
        params_tmpl.compile_params_template({"rows": {"$rows": None}}, path="p", allow_rows=False)

    with pytest.raises(params_tmpl.ParamsTemplateCompileError, match="Directive node must be a single-key mapping"):
        params_tmpl.compile_params_template({"ids": {"$keys": {"as": "set"}, "other": 1}}, path="p")

    with pytest.raises(params_tmpl.ParamsTemplateCompileError, match="`\\$keys` options must be a mapping"):
        params_tmpl.compile_params_template({"ids": {"$keys": 1}}, path="p")

    with pytest.raises(params_tmpl.ParamsTemplateCompileError, match="Unknown `\\$keys` option"):
        params_tmpl.compile_params_template({"ids": {"$keys": {"bad": 1}}}, path="p")

    with pytest.raises(params_tmpl.ParamsTemplateCompileError, match="`\\$keys\\.as` must be a string"):
        params_tmpl.compile_params_template({"ids": {"$keys": {"as": 1}}}, path="p")

    with pytest.raises(params_tmpl.ParamsTemplateCompileError, match="`\\$keys\\.as` must be one of"):
        params_tmpl.compile_params_template({"ids": {"$keys": {"as": "bad"}}}, path="p")

    with pytest.raises(params_tmpl.ParamsTemplateCompileError, match="`\\$rows` options must be a mapping"):
        params_tmpl.compile_params_template({"rows": {"$rows": 1}}, path="p")

    with pytest.raises(params_tmpl.ParamsTemplateCompileError, match="Unknown `\\$rows` option"):
        params_tmpl.compile_params_template({"rows": {"$rows": {"bad": 1}}}, path="p")

    with pytest.raises(params_tmpl.ParamsTemplateCompileError, match="`\\$rows\\.cache_mode` must be a string"):
        params_tmpl.compile_params_template({"rows": {"$rows": {"cache_mode": 1}}}, path="p")

    with pytest.raises(params_tmpl.ParamsTemplateCompileError, match="`\\$rows\\.cache_mode` must be one of"):
        params_tmpl.compile_params_template({"rows": {"$rows": {"cache_mode": "bad"}}}, path="p")


def test_params_template_render_keys_and_rows_and_errors() -> None:
    keys_list_template = params_tmpl.compile_params_template({"ids": {"$keys": {"as": "list"}}}, path="p")
    out = keys_list_template.render_kwargs(LoaderCallContextIr(is_ref_loader=True, lookup_keys={3, 1, 2}), path="p")
    assert out["ids"] == [1, 2, 3]

    out2 = keys_list_template.render_kwargs(
        LoaderCallContextIr(is_ref_loader=True, lookup_keys={1, 2, 3}, lookup_keys_list=[3, 2, 1]),
        path="p",
    )
    assert out2["ids"] == [3, 2, 1]

    keys_set_template = params_tmpl.compile_params_template({"ids": {"$keys": None}}, path="p")
    out3 = keys_set_template.render_kwargs(LoaderCallContextIr(is_ref_loader=True, lookup_keys={1, 2}), path="p")
    assert out3["ids"] == {1, 2}

    keys_set_template2 = params_tmpl.compile_params_template({"ids": {"$keys": {}}}, path="p")
    out3b = keys_set_template2.render_kwargs(LoaderCallContextIr(is_ref_loader=True, lookup_keys={1, 2}), path="p")
    assert out3b["ids"] == {1, 2}

    rows_template = params_tmpl.compile_params_template({"rows": {"$rows": {"cache_mode": "batch"}}}, path="p")
    out4 = rows_template.render_kwargs(LoaderCallContextIr(is_ref_loader=True, batch_rows=[{"x": 1}]), path="p")
    assert out4["rows"] == [{"x": 1}]

    rows_template2 = params_tmpl.compile_params_template({"rows": {"$rows": {}}}, path="p")
    out4b = rows_template2.render_kwargs(LoaderCallContextIr(is_ref_loader=True, batch_rows=[{"x": 1}]), path="p")
    assert out4b["rows"] == [{"x": 1}]

    with pytest.raises(params_tmpl.ParamsTemplateRenderError) as exc:
        _ = keys_list_template.render_kwargs(LoaderCallContextIr(is_ref_loader=False), path="p")
    assert "`$keys`" in str(exc.value)

    with pytest.raises(params_tmpl.ParamsTemplateRenderError) as exc:
        _ = rows_template.render_kwargs(LoaderCallContextIr(is_ref_loader=True), path="p")
    assert "`$rows`" in str(exc.value)


def test_params_template_render_kwargs_requires_mapping_and_allows_none() -> None:
    template_none = params_tmpl.compile_params_template(None, path="p")
    assert template_none.render_kwargs(LoaderCallContextIr(is_ref_loader=False), path="p") == {}
    assert template_none.is_empty_mapping() is False

    template_scalar = params_tmpl.compile_params_template(1, path="p")
    assert template_scalar.is_empty_mapping() is False
    with pytest.raises(params_tmpl.ParamsTemplateRenderError, match="must render to a mapping"):
        _ = template_scalar.render_kwargs(LoaderCallContextIr(is_ref_loader=False), path="p")


def test_converter_rejects_legacy_to_bind_and_bind_and_reports_template_errors() -> None:
    resolver = PythonReferenceResolver(allowed_modules=frozenset(["tests.conftest"]))

    config = DemandConfig(
        name="demo",
        main_source=MainSourceConfig(
            source_id="orders",
            loader="tests.conftest.mock_loader",
            params={"ids": {"$keys": None}},
        ),
        sources={
            "customers": SourceConfig(
                source_id="customers",
                loader="tests.conftest.mock_loader",
                key="customer_id",
            )
        },
    )
    with pytest.raises(ConversionError, match="`\\$keys` is not allowed"):
        ConfigToIRConverter(resolver=resolver).convert(config)

    config2 = DemandConfig(
        name="demo",
        main_source=MainSourceConfig(source_id="orders", loader="tests.conftest.mock_loader"),
        sources={
            "customers": SourceConfig(
                source_id="customers",
                loader="tests.conftest.mock_loader",
                key="customer_id",
                bind=BindConfig(use_keys=BindKeysConfig(param="ids", as_="set")),
            )
        },
    )
    with pytest.raises(ConversionError, match="sources\\.customers\\.bind"):
        ConfigToIRConverter(resolver=resolver).convert(config2)

    config3 = DemandConfig(
        name="demo",
        main_source=MainSourceConfig(source_id="orders", loader="tests.conftest.mock_loader"),
        sources={
            "customers": SourceConfig(
                source_id="customers",
                loader="tests.conftest.mock_loader",
                key="customer_id",
                params={"payload": "$runtime.missing"},
            )
        },
    )
    with pytest.raises(ConversionError, match="Missing runtime var"):
        ConfigToIRConverter(resolver=resolver).convert(config3)

    config4 = DemandConfig(
        name="demo",
        main_source=MainSourceConfig(source_id="orders", loader="tests.conftest.mock_loader"),
        sources={"customers": SourceConfig(source_id="customers", loader="tests.conftest.mock_loader", key="customer_id")},
        relations={
            "r1": RelationConfig(
                relation_id="r1",
                steps=(
                    RelationStepConfig(
                        from_="orders.customer_id",
                        to="customers.customer_id",
                        to_bind=BindConfig(use_keys=BindKeysConfig(param="ids", as_="set")),
                    ),
                ),
            )
        },
    )
    with pytest.raises(ConversionError, match="to_bind"):
        ConfigToIRConverter(resolver=resolver).convert(config4)
