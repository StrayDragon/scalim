import pytest

import scalim.dsl.yaml_dsl.params_template as params_tmpl
from scalim.dsl.yaml_dsl._internal.config_parsing.errors import ScalimConfigValidationError
from scalim.dsl.yaml_dsl._internal.config_parsing.loader import YamlDemandLoader
from scalim.dsl.yaml_dsl._internal.config_parsing.validator import ConfigValidator
from scalim.dsl.yaml_dsl.runtime.conversion import ConfigToIRConverter
from scalim.dsl.yaml_dsl.runtime.errors import ScalimConversionError
from scalim.dsl.yaml_dsl.schema_dsl.models import DemandConfig, MainSourceConfig, SourceConfig
from scalim.spec.ir.binding import LoaderCallContextIr


def test_validator_rejects_params_non_mapping() -> None:
    config = {
        "name": "demo",
        "main_source": {
            "source_id": "orders",
            "loader": "tests.fixtures.mock_loaders.mock_loader",
            "fields": {"order_id": {"extract": "order_id"}},
        },
        "sources": {"s1": {"loader": "tests.fixtures.mock_loaders.mock_loader", "key": "id", "params": []}},
    }
    with pytest.raises(ScalimConfigValidationError) as exc:
        ConfigValidator().validate(config)
    assert any("sources.s1.params" in msg and "must be a dictionary" in msg for msg in exc.value.errors)


def test_params_template_node_base_render_raises_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        params_tmpl._NodeBase().render(LoaderCallContextIr(), path="p")  # type: ignore[attr-defined]


def test_compiled_params_template_top_level_keys_skip_non_strings_and_seen_state_allows_duplicates() -> None:
    template = params_tmpl.CompiledParamsTemplate(
        root=params_tmpl.MappingNode(
            items=(
                (1, params_tmpl.LiteralNode(value=1)),
                ("a", params_tmpl.LiteralNode(value=2)),
            )
        )
    )
    assert template.top_level_mapping_string_keys() == ("a",)

    state_keys = params_tmpl._CompileState()
    state_keys.seen_keys("set", path="p")
    state_keys.seen_keys("set", path="p2")
    assert state_keys.directive_mode == "keys"

    state_rows = params_tmpl._CompileState()
    state_rows.seen_rows("batch", path="p")
    state_rows.seen_rows("batch", path="p2")
    assert state_rows.directive_mode == "rows"


def test_params_template_runtime_deepcopy_is_alias_safe_and_path_can_be_empty() -> None:
    payload = {"a": [1], "b": ({"c": {1}},)}
    template = params_tmpl.compile_params_template(
        {"payload": {"$init_var": "payload"}},
        path="",
        init_vars={"payload": payload},
    )
    ctx = LoaderCallContextIr(is_ref_loader=False)

    out1 = template.render_kwargs(ctx, path="")
    out1["payload"]["a"].append(2)
    out1["payload"]["b"][0]["c"].add(2)

    out2 = template.render_kwargs(ctx, path="")
    assert out2["payload"]["a"] == [1]
    assert out2["payload"]["b"][0]["c"] == {1}


def test_params_template_missing_init_var_has_path_and_str() -> None:
    with pytest.raises(params_tmpl.ScalimParamsTemplateCompileError) as exc:
        params_tmpl.compile_params_template({"x": {"$init_var": "missing"}}, path="root", init_vars={})
    assert exc.value.path == "root.x"
    assert "Missing init var" in str(exc.value)
    assert "(path=root.x)" in str(exc.value)


def test_params_template_init_var_directive_does_not_do_substring_interpolation() -> None:
    template = params_tmpl.compile_params_template(
        {"sql": "and t > $init_var.end_dt"},
        path="p",
        init_vars={"end_dt": "SHOULD_NOT_APPLY"},
    )
    out = template.render_kwargs(LoaderCallContextIr(is_ref_loader=False), path="p")
    assert out["sql"] == "and t > $init_var.end_dt"


def test_params_template_runtime_directive_render_raises_error_when_not_resolved_at_compile_time() -> None:
    template = params_tmpl.compile_params_template(
        {"end_dt": {"$init_var": "end_dt"}},
        path="p",
        resolve_runtime=False,
    )

    with pytest.raises(params_tmpl.ScalimParamsTemplateRenderError, match="must be resolved at compile time"):
        template.render_kwargs(LoaderCallContextIr(is_ref_loader=False), path="p")


def test_params_template_invalid_runtime_placeholder_is_literal_string() -> None:
    with pytest.raises(params_tmpl.ScalimParamsTemplateCompileError, match="Legacy `\\$runtime\\.<name>` placeholder is not supported"):
        _ = params_tmpl.compile_params_template(
            {"sql": "$runtime.bad-name"},
            path="p",
            init_vars={},
        )


def test_params_template_legacy_runtime_placeholder_missing_name_is_rejected() -> None:
    with pytest.raises(params_tmpl.ScalimParamsTemplateCompileError, match="Legacy `\\$runtime\\.<name>` placeholder is not supported"):
        _ = params_tmpl.compile_params_template(
            {"sql": "$runtime."},
            path="p",
            init_vars={},
        )


def test_params_template_legacy_runtime_placeholder_valid_name_is_rejected() -> None:
    with pytest.raises(
        params_tmpl.ScalimParamsTemplateCompileError,
        match="Legacy `\\$runtime\\.end_dt` placeholder is not supported",
    ):
        _ = params_tmpl.compile_params_template(
            {"sql": "$runtime.end_dt"},
            path="p",
            init_vars={},
        )


def test_params_template_init_var_directive_value_must_be_non_empty_string() -> None:
    with pytest.raises(params_tmpl.ScalimParamsTemplateCompileError, match="`\\$init_var` value must be a non-empty string"):
        _ = params_tmpl.compile_params_template(
            {"end_dt": {"$init_var": None}},
            path="p",
            init_vars={},
        )


def test_params_template_init_var_directive_value_rejects_invalid_name() -> None:
    with pytest.raises(params_tmpl.ScalimParamsTemplateCompileError, match="`\\$init_var` value 'bad-name' is invalid"):
        _ = params_tmpl.compile_params_template(
            {"end_dt": {"$init_var": "bad-name"}},
            path="p",
            init_vars={},
        )


def test_params_template_reserved_keys_inside_init_vars_are_treated_as_literal_values() -> None:
    payload = {"$keys": {"as": "set"}, "$rows": {"cache_mode": "batch"}}
    template = params_tmpl.compile_params_template(
        {"payload": {"$init_var": "payload"}},
        path="p",
        init_vars={"payload": payload},
    )
    out = template.render_kwargs(LoaderCallContextIr(is_ref_loader=False), path="p")
    assert out["payload"] == payload


def test_params_template_missing_init_var_reports_nested_path() -> None:
    with pytest.raises(params_tmpl.ScalimParamsTemplateCompileError) as exc:
        params_tmpl.compile_params_template(
            {"params": {"end_dt": {"$init_var": "end_dt"}}},
            path="sources.foo.params",
            init_vars={},
        )
    assert exc.value.path == "sources.foo.params.params.end_dt"


def test_params_template_renders_directives_in_nested_dict_and_list_positions() -> None:
    template_nested = params_tmpl.compile_params_template(
        {"params": {"ids": {"$keys": {"as": "list"}}}},
        path="p",
    )
    out_nested = template_nested.render_kwargs(LoaderCallContextIr(is_ref_loader=True, lookup_keys={2, 1}), path="p")
    assert out_nested == {"params": {"ids": [1, 2]}}

    template_list = params_tmpl.compile_params_template(
        {"ids": [{"$keys": None}]},
        path="p",
    )
    out_list = template_list.render_kwargs(LoaderCallContextIr(is_ref_loader=True, lookup_keys={1, 2}), path="p")
    assert out_list == {"ids": [{1, 2}]}


def test_params_template_keys_composite_key_injects_tuple_elements() -> None:
    template = params_tmpl.compile_params_template({"ids": {"$keys": {"as": "list"}}}, path="p")
    out = template.render_kwargs(
        LoaderCallContextIr(is_ref_loader=True, lookup_keys={("r1", 2), ("r1", 1)}),
        path="p",
    )
    assert out["ids"] == [("r1", 1), ("r1", 2)]


def test_params_template_compile_validates_options_and_conflicts() -> None:
    with pytest.raises(params_tmpl.ScalimParamsTemplateCompileError, match="mutually exclusive"):
        params_tmpl.compile_params_template({"a": {"$keys": None}, "b": {"$rows": None}}, path="p")

    with pytest.raises(params_tmpl.ScalimParamsTemplateCompileError, match="mutually exclusive"):
        params_tmpl.compile_params_template({"a": {"$rows": None}, "b": {"$keys": None}}, path="p")

    with pytest.raises(params_tmpl.ScalimParamsTemplateCompileError, match="Conflicting `\\$keys\\.as`"):
        params_tmpl.compile_params_template({"a": {"$keys": {"as": "set"}}, "b": {"$keys": {"as": "list"}}}, path="p")

    with pytest.raises(params_tmpl.ScalimParamsTemplateCompileError, match="Conflicting `\\$rows\\.cache_mode`"):
        params_tmpl.compile_params_template(
            {"a": {"$rows": {"cache_mode": "batch"}}, "b": {"$rows": {"cache_mode": "none"}}},
            path="p",
        )

    with pytest.raises(params_tmpl.ScalimParamsTemplateCompileError, match="`\\$keys` is not allowed"):
        params_tmpl.compile_params_template({"ids": {"$keys": None}}, path="p", allow_keys=False)

    with pytest.raises(params_tmpl.ScalimParamsTemplateCompileError, match="`\\$rows` is not allowed"):
        params_tmpl.compile_params_template({"rows": {"$rows": None}}, path="p", allow_rows=False)

    with pytest.raises(params_tmpl.ScalimParamsTemplateCompileError, match="Directive node must be a single-key mapping"):
        params_tmpl.compile_params_template({"ids": {"$keys": {"as": "set"}, "other": 1}}, path="p")

    with pytest.raises(params_tmpl.ScalimParamsTemplateCompileError, match="`\\$keys` options must be a mapping"):
        params_tmpl.compile_params_template({"ids": {"$keys": 1}}, path="p")

    with pytest.raises(params_tmpl.ScalimParamsTemplateCompileError, match="Unknown `\\$keys` option"):
        params_tmpl.compile_params_template({"ids": {"$keys": {"bad": 1}}}, path="p")

    with pytest.raises(params_tmpl.ScalimParamsTemplateCompileError, match="`\\$keys\\.as` must be a string"):
        params_tmpl.compile_params_template({"ids": {"$keys": {"as": 1}}}, path="p")

    with pytest.raises(params_tmpl.ScalimParamsTemplateCompileError, match="`\\$keys\\.as` must be one of"):
        params_tmpl.compile_params_template({"ids": {"$keys": {"as": "bad"}}}, path="p")

    with pytest.raises(params_tmpl.ScalimParamsTemplateCompileError, match="`\\$rows` options must be a mapping"):
        params_tmpl.compile_params_template({"rows": {"$rows": 1}}, path="p")

    with pytest.raises(params_tmpl.ScalimParamsTemplateCompileError, match="Unknown `\\$rows` option"):
        params_tmpl.compile_params_template({"rows": {"$rows": {"bad": 1}}}, path="p")

    with pytest.raises(params_tmpl.ScalimParamsTemplateCompileError, match="`\\$rows\\.cache_mode` must be a string"):
        params_tmpl.compile_params_template({"rows": {"$rows": {"cache_mode": 1}}}, path="p")

    with pytest.raises(params_tmpl.ScalimParamsTemplateCompileError, match="`\\$rows\\.cache_mode` must be one of"):
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

    with pytest.raises(params_tmpl.ScalimParamsTemplateRenderError) as exc:
        _ = keys_list_template.render_kwargs(LoaderCallContextIr(is_ref_loader=False), path="p")
    assert "`$keys`" in str(exc.value)

    with pytest.raises(params_tmpl.ScalimParamsTemplateRenderError) as exc:
        _ = rows_template.render_kwargs(LoaderCallContextIr(is_ref_loader=True), path="p")
    assert "`$rows`" in str(exc.value)


def test_params_template_render_kwargs_requires_mapping_and_allows_none() -> None:
    template_none = params_tmpl.compile_params_template(None, path="p")
    assert template_none.render_kwargs(LoaderCallContextIr(is_ref_loader=False), path="p") == {}
    assert template_none.is_empty_mapping() is False

    template_scalar = params_tmpl.compile_params_template(1, path="p")
    assert template_scalar.is_empty_mapping() is False
    with pytest.raises(params_tmpl.ScalimParamsTemplateRenderError, match="must render to a mapping"):
        _ = template_scalar.render_kwargs(LoaderCallContextIr(is_ref_loader=False), path="p")


def test_params_template_render_kwargs_rejects_non_string_keys() -> None:
    template = params_tmpl.compile_params_template({1: "x"}, path="p")
    with pytest.raises(params_tmpl.ScalimParamsTemplateRenderError, match="mapping keys must be strings") as exc:
        _ = template.render_kwargs(LoaderCallContextIr(is_ref_loader=False), path="p")
    assert exc.value.path == "p.1"


def test_converter_rejects_disallowed_directives_and_reports_template_errors() -> None:
    config = DemandConfig(
        name="demo",
        main_source=MainSourceConfig(
            source_id="orders",
            loader="tests.fixtures.mock_loaders.mock_loader",
            params={"ids": {"$keys": None}},
        ),
        sources={
            "customers": SourceConfig(
                source_id="customers",
                loader="tests.fixtures.mock_loaders.mock_loader",
                key="customer_id",
            )
        },
    )
    with pytest.raises(ScalimConversionError, match="`\\$keys` is not allowed"):
        ConfigToIRConverter().convert(config)

    config3 = DemandConfig(
        name="demo",
        main_source=MainSourceConfig(source_id="orders", loader="tests.fixtures.mock_loaders.mock_loader"),
        sources={
            "customers": SourceConfig(
                source_id="customers",
                loader="tests.fixtures.mock_loaders.mock_loader",
                key="customer_id",
                params={"payload": {"$init_var": "missing"}},
            )
        },
    )
    with pytest.raises(ScalimConversionError, match="Missing init var"):
        ConfigToIRConverter().convert(config3)


def test_params_template_legacy_runtime_directive_is_rejected_with_migration_hint_and_path() -> None:
    with pytest.raises(params_tmpl.ScalimParamsTemplateCompileError) as exc:
        params_tmpl.compile_params_template(
            {"x": {"$runtime": "end_dt"}},
            path="root",
            init_vars={"end_dt": 1},
        )
    assert exc.value.path == "root.x"
    assert "Legacy `{$runtime: end_dt}` directive is not supported" in str(exc.value)
    assert "`{$init_var: end_dt}`" in str(exc.value)


def test_params_template_legacy_runtime_directive_invalid_value_is_rejected() -> None:
    with pytest.raises(params_tmpl.ScalimParamsTemplateCompileError) as exc:
        params_tmpl.compile_params_template(
            {"x": {"$runtime": None}},
            path="root",
            init_vars={},
        )
    assert exc.value.path == "root.x"
    assert "Legacy `{$runtime: <name>}` directive is not supported" in str(exc.value)
    assert "`{$init_var: <name>}`" in str(exc.value)
