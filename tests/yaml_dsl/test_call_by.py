import pytest

import scalim.dsl.yaml_dsl._internal.config_parsing.call_by as call_by_module
from scalim.dsl.yaml_dsl._internal.config_parsing.call_by import ScalimCallByParseError, parse_call_by
from scalim.dsl.yaml_dsl._internal.config_parsing.errors import ScalimConfigValidationError
from scalim.dsl.yaml_dsl._internal.config_parsing.validator import ConfigValidator
from decimal import Decimal
from types import MappingProxyType

from scalim.dsl.yaml_dsl.runtime.conversion import ConfigToIRConverter
from scalim.dsl.yaml_dsl.runtime.errors import ScalimConversionError, ScalimResolverError
from scalim.dsl.yaml_dsl.runtime._internal.callable_preflight import ScalimCallablePreflightError
from scalim.dsl.yaml_dsl.runtime._internal.call_by_signature import validate_call_by_signature
from scalim.dsl.yaml_dsl.runtime.references import SecurePythonReferenceResolver
from scalim.dsl.yaml_dsl.runtime.runtime_linking import resolve_runtime_bindings
from scalim.dsl.yaml_dsl.schema_dsl.models import DemandConfig, DerivedFieldConfig, MainSourceConfig, SourceFieldConfig
from scalim.execution.context import BatchContext
from scalim.execution.executor.operators.compute.executor import ComputeOperatorExecutor
from scalim.execution.executor.runtime.runtime import ExecutionRuntime
from scalim.execution.runtime_bindings import RuntimeBindings
from scalim.hooks import HookManager
from scalim.ob.manager import ObserverManager
from scalim.planning.operators import ComputeOperatorIr, OperatorType
from scalim.planning.plan import ExecutionPlan
from scalim.spec.ir import ComputeCallContextIr, DerivedFieldIr


def test_parse_call_by_extracts_reference_and_dependencies() -> None:
    parsed = parse_call_by("tests.fixtures.call_by_fns:add( a , b = b , c=1 )")
    assert parsed.reference == "tests.fixtures.call_by_fns:add"
    assert parsed.field_names == ("a", "b")

    dotted = parse_call_by("tests.fixtures.call_by_fns.echo(1)")
    assert dotted.reference == "tests.fixtures.call_by_fns.echo"


def test_validate_call_by_signature_covers_binding_error_shapes() -> None:
    # NOTE: This is a pure helper unit test. We pass local callables to
    # cover the signature-binding branches deterministically.

    def _fn_kwonly(*, a):  # type: ignore[no-untyped-def]
        return a

    def _fn_positional(a):  # type: ignore[no-untyped-def]
        return a

    def _fn_kwargs_only(**_kw):  # type: ignore[no-untyped-def]
        return None

    def _fn_kwonly_kwargs(*, a, **_kw):  # type: ignore[no-untyped-def]
        return a

    # 1) `inspect.signature` unavailable (non-callable) -> no-op
    validate_call_by_signature(
        location="case1",
        call_by="tests.fixtures.call_by_fns:echo()",
        parsed=parse_call_by("tests.fixtures.call_by_fns:echo()"),
        fn=object(),  # type: ignore[arg-type]
    )

    # 2) args empty -> hint is None (unexpected keyword)
    with pytest.raises(ScalimCallablePreflightError, match="函数签名不匹配"):
        validate_call_by_signature(
            location="case2",
            call_by="tests.fixtures.call_by_fns:echo(bad=1)",
            parsed=parse_call_by("tests.fixtures.call_by_fns:echo(bad=1)"),
            fn=_fn_kwonly,
        )

    # 3) signature accepts positional -> hint is None (too many positional args)
    with pytest.raises(ScalimCallablePreflightError, match="函数签名不匹配"):
        validate_call_by_signature(
            location="case3",
            call_by="tests.fixtures.call_by_fns:echo(a, b)",
            parsed=parse_call_by("tests.fixtures.call_by_fns:echo(a, b)"),
            fn=_fn_positional,
        )

    # 4) no positional, no kw-only (only **kwargs) -> hint is None
    with pytest.raises(ScalimCallablePreflightError, match="函数签名不匹配"):
        validate_call_by_signature(
            location="case4",
            call_by="tests.fixtures.call_by_fns:echo(a)",
            parsed=parse_call_by("tests.fixtures.call_by_fns:echo(a)"),
            fn=_fn_kwargs_only,
        )

    # 5) kw-only + kwargs present -> hint uses generic message
    with pytest.raises(ScalimCallablePreflightError, match="请使用关键字传参"):
        validate_call_by_signature(
            location="case5",
            call_by="tests.fixtures.call_by_fns:echo(a, extra=1)",
            parsed=parse_call_by("tests.fixtures.call_by_fns:echo(a, extra=1)"),
            fn=_fn_kwonly_kwargs,
        )

    # 6) kw-only but field name mismatched -> generic hint
    with pytest.raises(ScalimCallablePreflightError, match="请使用关键字传参"):
        validate_call_by_signature(
            location="case6",
            call_by="tests.fixtures.call_by_fns:echo(b)",
            parsed=parse_call_by("tests.fixtures.call_by_fns:echo(b)"),
            fn=_fn_kwonly,
        )

    # 7) kw-only and literal positional -> generic hint
    with pytest.raises(ScalimCallablePreflightError, match="请使用关键字传参"):
        validate_call_by_signature(
            location="case7",
            call_by="tests.fixtures.call_by_fns:echo(1)",
            parsed=parse_call_by("tests.fixtures.call_by_fns:echo(1)"),
            fn=_fn_kwonly,
        )

    # 8) kw-only and positional field matches -> rewrite hint
    with pytest.raises(ScalimCallablePreflightError, match="可改写为:"):
        validate_call_by_signature(
            location="case8",
            call_by="tests.fixtures.call_by_fns:echo(a)",
            parsed=parse_call_by("tests.fixtures.call_by_fns:echo(a)"),
            fn=_fn_kwonly,
        )


def test_compute_call_ctx_keeps_mappingproxy_values() -> None:
    values = MappingProxyType({"a": 1})
    ctx = ComputeCallContextIr(row_id="r1", batch_num=1, field_id="f", deps=(), values=values)
    assert ctx.values is values


def test_signature_accepts_positional_handles_py36_without_positional_only(monkeypatch: pytest.MonkeyPatch) -> None:
    import inspect

    from scalim.dsl.yaml_dsl.runtime._internal.call_by_signature import _signature_accepts_positional

    def _fn(a: object) -> object:
        return a

    sig = inspect.signature(_fn)
    monkeypatch.delattr(inspect.Parameter, "POSITIONAL_ONLY", raising=False)
    assert _signature_accepts_positional(sig) is True


def test_parse_call_by_dedupes_dependencies() -> None:
    parsed = parse_call_by("tests.fixtures.call_by_fns:echo(a, a)")
    assert parsed.field_names == ("a",)


def test_parse_call_by_rejects_illegal_ctx_attr() -> None:
    with pytest.raises(ScalimCallByParseError, match="Invalid ctx attribute"):
        parse_call_by("tests.fixtures.call_by_fns:echo($ctx.unknown)")


def test_parse_call_by_rejects_non_string_and_empty() -> None:
    with pytest.raises(ScalimCallByParseError, match="must be a string"):
        parse_call_by(None)  # type: ignore[arg-type]
    with pytest.raises(ScalimCallByParseError, match="must not be empty"):
        parse_call_by("   ")


def test_parse_call_by_rejects_invalid_reference_and_split_errors() -> None:
    with pytest.raises(ScalimCallByParseError, match="expected '<reference>\\(\\.\\.\\.\\)'"):
        parse_call_by("tests.fixtures.call_by_fns:echo")
    with pytest.raises(ScalimCallByParseError, match="missing reference"):
        parse_call_by("(1)")
    with pytest.raises(ScalimCallByParseError, match="unexpected trailing"):
        parse_call_by("tests.fixtures.call_by_fns:echo(1) trailing")
    with pytest.raises(ScalimCallByParseError, match="`call_by` 引用 .* 非法"):
        parse_call_by("module:attr:extra(1)")


def test_parse_call_by_rejects_invalid_args_syntax() -> None:
    with pytest.raises(ScalimCallByParseError, match="arguments syntax"):
        parse_call_by("tests.fixtures.call_by_fns:echo(a=)")


def test_parse_call_by_rejects_unpacking_and_duplicate_kwargs() -> None:
    with pytest.raises(ScalimCallByParseError, match="\\*' argument unpacking"):
        parse_call_by("tests.fixtures.call_by_fns:echo(*a)")
    with pytest.raises(ScalimCallByParseError, match="\\*\\*' keyword unpacking"):
        parse_call_by("tests.fixtures.call_by_fns:echo(**a)")
    with pytest.raises(ScalimCallByParseError, match="duplicate keyword argument"):
        parse_call_by("tests.fixtures.call_by_fns:echo(a=1, a=2)")


def test_parse_call_by_handles_strings_and_does_not_rewrite_inside_string() -> None:
    parsed = parse_call_by('tests.fixtures.call_by_fns:echo(") $ctx.row_id")')
    assert parsed.reference == "tests.fixtures.call_by_fns:echo"
    assert parsed.args
    assert parsed.args[0].kind == "literal"
    assert "$ctx.row_id" in parsed.args[0].value

    parsed = parse_call_by(r'tests.fixtures.call_by_fns:echo("a\\\"b")')
    assert parsed.args[0].value == 'a\\"b'

    parsed = parse_call_by('tests.fixtures.call_by_fns:echo("__scalim_ctx__")')
    assert parsed.args[0].value == "__scalim_ctx__"

    parsed = parse_call_by("tests.fixtures.call_by_fns:echo()")
    assert parsed.args == ()


def test_parse_call_by_rejects_placeholder_token() -> None:
    with pytest.raises(ScalimCallByParseError, match="Illegal token"):
        parse_call_by("tests.fixtures.call_by_fns:echo(__scalim_ctx__)")


def test_parse_call_by_rejects_attribute_access_and_unsupported_exprs_and_literals() -> None:
    with pytest.raises(ScalimCallByParseError, match="attribute access"):
        parse_call_by("tests.fixtures.call_by_fns:echo(a.b)")
    with pytest.raises(ScalimCallByParseError, match="Unsupported call_by argument type"):
        parse_call_by("tests.fixtures.call_by_fns:echo(a + b)")
    with pytest.raises(ScalimCallByParseError, match="Unsupported literal type"):
        parse_call_by("tests.fixtures.call_by_fns:echo(b'hi')")
    parsed = parse_call_by("tests.fixtures.call_by_fns:echo(-1)")
    assert parsed.args[0].kind == "literal"
    assert parsed.args[0].value == -1
    parsed = parse_call_by("tests.fixtures.call_by_fns:echo(+1)")
    assert parsed.args[0].value == 1
    with pytest.raises(ScalimCallByParseError, match="Unary \\+/-"):
        parse_call_by("tests.fixtures.call_by_fns:echo(-True)")
    with pytest.raises(ScalimCallByParseError, match="Only simple Python literals"):
        parse_call_by("tests.fixtures.call_by_fns:echo([1])")


def test_is_valid_loader_ref_coverage() -> None:
    assert call_by_module._is_valid_loader_ref("") is False
    assert call_by_module._is_valid_loader_ref("module:attr") is True
    assert call_by_module._is_valid_loader_ref(".module:attr") is True
    assert call_by_module._is_valid_loader_ref("..module:attr") is True
    assert call_by_module._is_valid_loader_ref(".module.attr") is True
    assert call_by_module._is_valid_loader_ref("^workflow/book_sheet_rows") is True
    assert call_by_module._is_valid_loader_ref(".attr") is False
    assert call_by_module._is_valid_loader_ref("bad-mod.attr") is False
    assert call_by_module._is_valid_loader_ref("module:attr:extra") is False
    assert call_by_module._is_valid_loader_ref(":attr") is False
    assert call_by_module._is_valid_loader_ref(".:attr") is False
    assert call_by_module._is_valid_loader_ref("..:attr") is False
    assert call_by_module._is_valid_loader_ref("module.:attr") is False
    assert call_by_module._is_valid_loader_ref("module") is False


def _base_validator_config() -> dict:
    return {
        "name": "demo",
        "main_source": {
            "source_id": "orders",
            "loader": "tests.fixtures.call_by_fns:dummy_main_loader",
            "fields": {
                "a": {"extract": "a"},
                "b": {"extract": "b"},
                "status": {"extract": "status"},
            },
        },
        "sources": {},
        "fields": {},
    }


def test_validator_rejects_call_by_in_source_fields() -> None:
    validator = ConfigValidator()
    config = _base_validator_config()
    config["main_source"]["fields"]["bad"] = {"extract": "x", "call_by": "tests.fixtures.call_by_fns:echo(a)"}

    with pytest.raises(ScalimConfigValidationError) as exc:
        validator.validate(config)

    assert any("must not declare call_by" in msg for msg in exc.value.errors)


def test_validator_rejects_call_by_in_sources_fields() -> None:
    validator = ConfigValidator()
    config = _base_validator_config()
    config["sources"] = {
        "s1": {
            "loader": "tests.fixtures.call_by_fns:dummy_main_loader",
            "key": "id",
            "fields": {"bad": {"extract": "x", "call_by": "tests.fixtures.call_by_fns:echo(a)"}},
        }
    }

    with pytest.raises(ScalimConfigValidationError) as exc:
        validator.validate(config)

    assert any("must not declare call_by" in msg for msg in exc.value.errors)


def test_validator_rejects_call_by_syntax_error() -> None:
    validator = ConfigValidator()
    config = _base_validator_config()
    config["fields"]["text"] = {"call_by": "tests.fixtures.call_by_fns:echo("}

    with pytest.raises(ScalimConfigValidationError) as exc:
        validator.validate(config)

    assert any("invalid call_by" in msg for msg in exc.value.errors)


def test_validator_rejects_call_by_non_python_literal() -> None:
    validator = ConfigValidator()
    config = _base_validator_config()
    config["fields"]["text"] = {"call_by": "tests.fixtures.call_by_fns:echo(true)"}

    with pytest.raises(ScalimConfigValidationError) as exc:
        validator.validate(config)

    assert any("Invalid literal 'true'" in msg for msg in exc.value.errors)


def test_validator_rejects_call_by_depends_on_mismatch() -> None:
    validator = ConfigValidator()
    config = _base_validator_config()
    config["fields"]["sum"] = {"call_by": "tests.fixtures.call_by_fns:add(a, b=b)", "depends_on": ["a"]}

    with pytest.raises(ScalimConfigValidationError) as exc:
        validator.validate(config)

    assert any("does not allow 'depends_on'" in msg for msg in exc.value.errors)


def test_validator_rejects_constant_call_by_without_depends_on() -> None:
    validator = ConfigValidator()
    config = _base_validator_config()
    config["fields"]["const"] = {"call_by": "tests.fixtures.call_by_fns:echo(1, $ctx.row_id)"}

    with pytest.raises(ScalimConfigValidationError) as exc:
        validator.validate(config)

    assert any("call_by has no field dependencies" in msg for msg in exc.value.errors)


def test_validator_rejects_call_by_and_compute_both_present() -> None:
    validator = ConfigValidator()
    config = _base_validator_config()
    config["fields"]["bad"] = {"compute": "a", "call_by": "tests.fixtures.call_by_fns:echo(a)"}

    with pytest.raises(ScalimConfigValidationError) as exc:
        validator.validate(config)

    assert any("must not declare both" in msg for msg in exc.value.errors)


def test_validator_rejects_call_by_type_and_empty() -> None:
    validator = ConfigValidator()
    config = _base_validator_config()
    config["fields"]["bad_type"] = {"call_by": 1}
    config["fields"]["bad_empty"] = {"call_by": ""}

    with pytest.raises(ScalimConfigValidationError) as exc:
        validator.validate(config)

    assert any("call_by must be a string" in msg for msg in exc.value.errors)
    assert any("call_by must not be empty" in msg for msg in exc.value.errors)


def test_validator_rejects_call_by_depends_on_empty_list() -> None:
    validator = ConfigValidator()
    config = _base_validator_config()
    config["fields"]["bad"] = {"call_by": "tests.fixtures.call_by_fns:echo(a)", "depends_on": []}

    with pytest.raises(ScalimConfigValidationError) as exc:
        validator.validate(config)

    assert any("does not allow 'depends_on'" in msg for msg in exc.value.errors)


def _make_call_by_config(call_by: str, *, depends_on: tuple) -> DemandConfig:
    return DemandConfig(
        name="demo",
        main_source=MainSourceConfig(source_id="orders", loader="tests.fixtures.call_by_fns:dummy_main_loader"),
        sources={},
        source_fields={"status": SourceFieldConfig(field_id="status", source="orders", extract="status")},
        derived_fields={
            "text": DerivedFieldConfig(
                field_id="text",
                name="text",
                call_by=call_by,
                depends_on=depends_on,
            )
        },
    )


def test_converter_requires_allowlist_for_call_by() -> None:
    config = _make_call_by_config("tests.fixtures.call_by_fns:echo(status)", depends_on=("status",))
    converter = ConfigToIRConverter()
    demand_ir = converter.convert(config)
    derived = demand_ir.fields["text"]
    assert isinstance(derived, DerivedFieldIr)
    assert derived.call_by is not None
    assert derived.call_ctx_key == "$ctx"

    bindings = resolve_runtime_bindings(
        demand_ir,
        resolver=SecurePythonReferenceResolver(allowed_modules=frozenset(["tests.fixtures.call_by_fns"])),
    )
    calculator = bindings.require_derived_calculator("text")
    ctx = ComputeCallContextIr(
        row_id=1,
        batch_num=2,
        field_id="text",
        deps=("status",),
        values={"status": "x"},
    )
    assert calculator("x", ctx=ctx) == "x"


def test_converter_rejects_unknown_call_by_reference() -> None:
    config = _make_call_by_config("tests.fixtures.call_by_fns:missing(status)", depends_on=("status",))
    converter = ConfigToIRConverter()
    demand_ir = converter.convert(config)

    with pytest.raises(ScalimResolverError, match="不存在属性"):
        _ = resolve_runtime_bindings(
            demand_ir,
            resolver=SecurePythonReferenceResolver(allowed_modules=frozenset(["tests.fixtures.call_by_fns"])),
        )


def test_converter_compiles_call_by_and_ctx() -> None:
    config = _make_call_by_config("tests.fixtures.call_by_fns:status_text(status=status, ctx=$ctx)", depends_on=("status",))
    converter = ConfigToIRConverter()
    demand_ir = converter.convert(config)
    derived = demand_ir.fields["text"]
    assert isinstance(derived, DerivedFieldIr)
    assert derived.call_ctx_key == "$ctx"

    bindings = resolve_runtime_bindings(
        demand_ir,
        resolver=SecurePythonReferenceResolver(allowed_modules=frozenset(["tests.fixtures.call_by_fns"])),
    )
    calculator = bindings.require_derived_calculator("text")
    ctx = ComputeCallContextIr(
        row_id=1,
        batch_num=2,
        field_id="text",
        deps=("status",),
        values={"status": True},
    )
    assert calculator(True, ctx=ctx) == "ok:1:2"


def test_converter_rejects_call_by_positional_arg_for_keyword_only_param() -> None:
    # `is_valid_group(*, group_name, **kw)` requires keyword-only `group_name`.
    # Positional call_by args should fast-fail at runtime linking (signature preflight), instead of being swallowed as a compute TypeError.
    converter = ConfigToIRConverter()
    config = DemandConfig(
        name="demo",
        main_source=MainSourceConfig(source_id="orders", loader="tests.fixtures.call_by_fns:dummy_main_loader"),
        sources={},
        source_fields={"group_name": SourceFieldConfig(field_id="group_name", source="orders", extract="group_name")},
        derived_fields={
            "ok": DerivedFieldConfig(
                field_id="ok",
                name="ok",
                call_by="tests.fixtures.call_by_fns:is_valid_group(group_name)",
                depends_on=("group_name",),
            )
        },
    )

    demand_ir = converter.convert(config)
    with pytest.raises(ScalimResolverError, match="函数签名不匹配"):
        _ = resolve_runtime_bindings(
            demand_ir,
            resolver=SecurePythonReferenceResolver(allowed_modules=frozenset(["tests.fixtures.call_by_fns"])),
        )


def test_converter_accepts_call_by_keyword_arg_for_keyword_only_param() -> None:
    converter = ConfigToIRConverter()
    config = DemandConfig(
        name="demo",
        main_source=MainSourceConfig(source_id="orders", loader="tests.fixtures.call_by_fns:dummy_main_loader"),
        sources={},
        source_fields={"group_name": SourceFieldConfig(field_id="group_name", source="orders", extract="group_name")},
        derived_fields={
            "ok": DerivedFieldConfig(
                field_id="ok",
                name="ok",
                call_by="tests.fixtures.call_by_fns:is_valid_group(group_name=group_name)",
                depends_on=("group_name",),
            )
        },
    )

    demand_ir = converter.convert(config)
    derived = demand_ir.fields["ok"]
    assert isinstance(derived, DerivedFieldIr)
    bindings = resolve_runtime_bindings(
        demand_ir,
        resolver=SecurePythonReferenceResolver(allowed_modules=frozenset(["tests.fixtures.call_by_fns"])),
    )
    calculator = bindings.require_derived_calculator("ok")
    ctx = ComputeCallContextIr(
        row_id=1,
        batch_num=0,
        field_id="ok",
        deps=("group_name",),
        values={"group_name": "vip"},
    )
    assert calculator("vip", ctx=ctx) is True


def test_converter_call_by_accepts_decimal_result() -> None:
    config = _make_call_by_config("tests.fixtures.call_by_fns:decimal_from_value(status)", depends_on=("status",))
    converter = ConfigToIRConverter()
    demand_ir = converter.convert(config)
    derived = demand_ir.fields["text"]
    assert isinstance(derived, DerivedFieldIr)
    bindings = resolve_runtime_bindings(
        demand_ir,
        resolver=SecurePythonReferenceResolver(allowed_modules=frozenset(["tests.fixtures.call_by_fns"])),
    )
    calculator = bindings.require_derived_calculator("text")
    ctx = ComputeCallContextIr(
        row_id=1,
        batch_num=0,
        field_id="text",
        deps=("status",),
        values={"status": "0.3"},
    )
    assert calculator("0.3", ctx=ctx) == Decimal("0.3")


def test_converter_rejects_missing_compute_and_call_by() -> None:
    config = DemandConfig(
        name="demo",
        main_source=MainSourceConfig(source_id="orders", loader="tests.fixtures.call_by_fns:dummy_main_loader"),
        sources={},
        source_fields={"status": SourceFieldConfig(field_id="status", source="orders", extract="status")},
        derived_fields={
            "bad": DerivedFieldConfig(
                field_id="bad",
                name="bad",
                depends_on=("status",),
            )
        },
    )
    converter = ConfigToIRConverter()

    with pytest.raises(ScalimConversionError, match="must declare"):
        converter.convert(config)


def test_converter_call_by_parse_error_and_literal_and_ctx_attr_and_missing_ctx() -> None:
    converter = ConfigToIRConverter()
    base = DemandConfig(
        name="demo",
        main_source=MainSourceConfig(source_id="orders", loader="tests.fixtures.call_by_fns:dummy_main_loader"),
        sources={},
        source_fields={"status": SourceFieldConfig(field_id="status", source="orders", extract="status")},
        derived_fields={},
    )

    bad = DemandConfig(
        **{
            **base.__dict__,
            "derived_fields": {
                "text": DerivedFieldConfig(field_id="text", name="text", call_by="tests.fixtures.call_by_fns:echo(", depends_on=("status",))
            },
        }
    )
    with pytest.raises(ScalimConversionError, match="invalid call_by"):
        converter.convert(bad)

    literal_cfg = DemandConfig(
        name=base.name,
        main_source=base.main_source,
        sources=base.sources,
        source_fields=base.source_fields,
        derived_fields={
            "text": DerivedFieldConfig(field_id="text", name="text", call_by="tests.fixtures.call_by_fns:echo(1)", depends_on=("status",))
        },
    )
    demand_ir = converter.convert(literal_cfg)
    derived = demand_ir.fields["text"]
    assert isinstance(derived, DerivedFieldIr)
    bindings = resolve_runtime_bindings(
        demand_ir,
        resolver=SecurePythonReferenceResolver(allowed_modules=frozenset(["tests.fixtures.call_by_fns"])),
    )
    calculator = bindings.require_derived_calculator("text")
    ctx = ComputeCallContextIr(
        row_id=1,
        batch_num=0,
        field_id="text",
        deps=("status",),
        values={"status": True},
    )
    assert calculator(True, ctx=ctx) == 1

    ctx_attr_cfg = DemandConfig(
        name=base.name,
        main_source=base.main_source,
        sources=base.sources,
        source_fields=base.source_fields,
        derived_fields={
            "text": DerivedFieldConfig(
                field_id="text",
                name="text",
                call_by="tests.fixtures.call_by_fns:needs_ctx_attr($ctx.row_id)",
                depends_on=("status",),
            )
        },
    )
    demand_ir = converter.convert(ctx_attr_cfg)
    derived = demand_ir.fields["text"]
    assert isinstance(derived, DerivedFieldIr)
    bindings = resolve_runtime_bindings(
        demand_ir,
        resolver=SecurePythonReferenceResolver(allowed_modules=frozenset(["tests.fixtures.call_by_fns"])),
    )
    calculator = bindings.require_derived_calculator("text")
    ctx = ComputeCallContextIr(
        row_id=9,
        batch_num=0,
        field_id="text",
        deps=("status",),
        values={"status": True},
    )
    assert calculator(True, ctx=ctx) == 9
    with pytest.raises(TypeError, match="requires ctx=ComputeCallContextIr"):
        calculator(True)


def test_compute_operator_injects_ctx_when_configured() -> None:
    field_spec = DerivedFieldIr(
        field_id="score",
        name="Score",
        dependencies=("amount",),
        compute_expr="amount",
        call_ctx_key="$ctx",
    )
    operator = ComputeOperatorIr(
        operator_id="compute_score",
        operator_type=OperatorType.COMPUTE.value,
        field_key="score",
        input_fields=("amount",),
    )

    plan = ExecutionPlan(operators=(operator,), field_specs={"score": field_spec}, target_fields=["score"])
    runtime_bindings = RuntimeBindings(
        derived_calculators={
            "score": lambda amount, ctx: "{}:{}".format(ctx.row_id, ctx.batch_num),
        }
    )
    runtime = ExecutionRuntime(
        plan=plan,
        hook_manager=HookManager(),
        observer_manager=ObserverManager(),
        main_source=None,
        sources={},
        runtime_bindings=runtime_bindings,
    )
    runtime.batch_num = 7

    context = BatchContext()
    context.set_field_value("amount", 1, 100)
    context.set_field_value("amount", 2, 200)

    ComputeOperatorExecutor().execute(operator, context, [1, 2], runtime)

    assert context.get_field_value("score", 1) == "1:7"
    assert context.get_field_value("score", 2) == "2:7"


def test_converter_call_by_ctx_attr_missing_attribute_raises() -> None:
    converter = ConfigToIRConverter()
    config = _make_call_by_config("tests.fixtures.call_by_fns:needs_ctx_attr($ctx.row_id)", depends_on=("status",))
    demand_ir = converter.convert(config)
    derived = demand_ir.fields["text"]
    assert isinstance(derived, DerivedFieldIr)

    bindings = resolve_runtime_bindings(
        demand_ir,
        resolver=SecurePythonReferenceResolver(allowed_modules=frozenset(["tests.fixtures.call_by_fns"])),
    )
    calculator = bindings.require_derived_calculator("text")
    with pytest.raises(TypeError, match="requires ctx=ComputeCallContextIr"):
        calculator(True, ctx=object())  # type: ignore[arg-type]


def test_converter_call_by_rejects_non_field_value_result() -> None:
    converter = ConfigToIRConverter()
    config = _make_call_by_config("tests.fixtures.call_by_fns:echo($ctx.values)", depends_on=("status",))
    demand_ir = converter.convert(config)
    derived = demand_ir.fields["text"]
    assert isinstance(derived, DerivedFieldIr)

    bindings = resolve_runtime_bindings(
        demand_ir,
        resolver=SecurePythonReferenceResolver(allowed_modules=frozenset(["tests.fixtures.call_by_fns"])),
    )
    calculator = bindings.require_derived_calculator("text")
    ctx = ComputeCallContextIr(
        row_id=1,
        batch_num=0,
        field_id="text",
        deps=("status",),
        values={"status": True},
    )
    with pytest.raises(TypeError, match="unsupported value type"):
        calculator(True, ctx=ctx)
