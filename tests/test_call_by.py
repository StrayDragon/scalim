import pytest

import scalim.dsl.by_yaml.config_parsing.call_by as call_by_module
from scalim.dsl.by_yaml.config_parsing.call_by import CallByParseError, parse_call_by
from scalim.dsl.by_yaml.config_parsing.errors import ConfigValidationError
from scalim.dsl.by_yaml.config_parsing.validator import ConfigValidator
from scalim.dsl.by_yaml.runtime.conversion import ConfigToIRConverter
from scalim.dsl.by_yaml.runtime.errors import ConversionError
from scalim.dsl.by_yaml.runtime.references import SecurePythonReferenceResolver
from scalim.dsl.by_yaml.schema_dsl.models import DemandConfig, DerivedFieldConfig, MainSourceConfig, SourceFieldConfig
from scalim.execution.context import BatchContext
from scalim.execution.executor.operators.compute.executor import ComputeOperatorExecutor
from scalim.execution.executor.runtime.runtime import ExecutionRuntime
from scalim.hooks.base import HookManager
from scalim.ob.manager import ObserverManager
from scalim.planning.operators import ComputeOperatorIr, OperatorType
from scalim.planning.plan import ExecutionPlan
from scalim.spec.ir.fields import DerivedFieldIr


def test_parse_call_by_extracts_reference_and_dependencies() -> None:
    parsed = parse_call_by("tests.call_by_fns:add( a , b = b , c=1 )")
    assert parsed.reference == "tests.call_by_fns:add"
    assert parsed.field_names == ("a", "b")

    dotted = parse_call_by("tests.call_by_fns.echo(1)")
    assert dotted.reference == "tests.call_by_fns.echo"


def test_parse_call_by_dedupes_dependencies() -> None:
    parsed = parse_call_by("tests.call_by_fns:echo(a, a)")
    assert parsed.field_names == ("a",)


def test_parse_call_by_rejects_illegal_ctx_attr() -> None:
    with pytest.raises(CallByParseError, match="Invalid ctx attribute"):
        parse_call_by("tests.call_by_fns:echo($ctx.unknown)")


def test_parse_call_by_rejects_non_string_and_empty() -> None:
    with pytest.raises(CallByParseError, match="must be a string"):
        parse_call_by(None)  # type: ignore[arg-type]
    with pytest.raises(CallByParseError, match="must not be empty"):
        parse_call_by("   ")


def test_parse_call_by_rejects_invalid_reference_and_split_errors() -> None:
    with pytest.raises(CallByParseError, match="expected '<reference>\\(\\.\\.\\.\\)'"):
        parse_call_by("tests.call_by_fns:echo")
    with pytest.raises(CallByParseError, match="missing reference"):
        parse_call_by("(1)")
    with pytest.raises(CallByParseError, match="unexpected trailing"):
        parse_call_by("tests.call_by_fns:echo(1) trailing")
    with pytest.raises(CallByParseError, match="Invalid call_by reference"):
        parse_call_by("module:attr:extra(1)")


def test_parse_call_by_rejects_invalid_args_syntax() -> None:
    with pytest.raises(CallByParseError, match="arguments syntax"):
        parse_call_by("tests.call_by_fns:echo(a=)")


def test_parse_call_by_rejects_unpacking_and_duplicate_kwargs() -> None:
    with pytest.raises(CallByParseError, match="\\*' argument unpacking"):
        parse_call_by("tests.call_by_fns:echo(*a)")
    with pytest.raises(CallByParseError, match="\\*\\*' keyword unpacking"):
        parse_call_by("tests.call_by_fns:echo(**a)")
    with pytest.raises(CallByParseError, match="duplicate keyword argument"):
        parse_call_by("tests.call_by_fns:echo(a=1, a=2)")


def test_parse_call_by_handles_strings_and_does_not_rewrite_inside_string() -> None:
    parsed = parse_call_by('tests.call_by_fns:echo(") $ctx.row_id")')
    assert parsed.reference == "tests.call_by_fns:echo"
    assert parsed.args
    assert parsed.args[0].kind == "literal"
    assert "$ctx.row_id" in parsed.args[0].value

    parsed = parse_call_by(r'tests.call_by_fns:echo("a\\\"b")')
    assert parsed.args[0].value == 'a\\"b'

    parsed = parse_call_by('tests.call_by_fns:echo("__scalim_ctx__")')
    assert parsed.args[0].value == "__scalim_ctx__"

    parsed = parse_call_by("tests.call_by_fns:echo()")
    assert parsed.args == ()


def test_parse_call_by_rejects_placeholder_token() -> None:
    with pytest.raises(CallByParseError, match="Illegal token"):
        parse_call_by("tests.call_by_fns:echo(__scalim_ctx__)")


def test_parse_call_by_rejects_attribute_access_and_unsupported_exprs_and_literals() -> None:
    with pytest.raises(CallByParseError, match="attribute access"):
        parse_call_by("tests.call_by_fns:echo(a.b)")
    with pytest.raises(CallByParseError, match="Unsupported call_by argument type"):
        parse_call_by("tests.call_by_fns:echo(a + b)")
    with pytest.raises(CallByParseError, match="Unsupported literal type"):
        parse_call_by("tests.call_by_fns:echo(b'hi')")
    parsed = parse_call_by("tests.call_by_fns:echo(-1)")
    assert parsed.args[0].kind == "literal"
    assert parsed.args[0].value == -1
    parsed = parse_call_by("tests.call_by_fns:echo(+1)")
    assert parsed.args[0].value == 1
    with pytest.raises(CallByParseError, match="Unary \\+/-"):
        parse_call_by("tests.call_by_fns:echo(-True)")
    with pytest.raises(CallByParseError, match="Only simple Python literals"):
        parse_call_by("tests.call_by_fns:echo([1])")


def test_is_valid_loader_ref_coverage() -> None:
    assert call_by_module._is_valid_loader_ref("") is False
    assert call_by_module._is_valid_loader_ref("module:attr") is True
    assert call_by_module._is_valid_loader_ref("module:attr:extra") is False
    assert call_by_module._is_valid_loader_ref(":attr") is False
    assert call_by_module._is_valid_loader_ref("module.:attr") is False
    assert call_by_module._is_valid_loader_ref("module") is False


def _base_validator_config() -> dict:
    return {
        "name": "demo",
        "main_source": {
            "source_id": "orders",
            "loader": "tests.call_by_fns:dummy_main_loader",
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
    config["main_source"]["fields"]["bad"] = {"extract": "x", "call_by": "tests.call_by_fns:echo(a)"}

    with pytest.raises(ConfigValidationError) as exc:
        validator.validate(config)

    assert any("must not declare call_by" in msg for msg in exc.value.errors)


def test_validator_rejects_call_by_in_sources_fields() -> None:
    validator = ConfigValidator()
    config = _base_validator_config()
    config["sources"] = {
        "s1": {
            "loader": "tests.call_by_fns:dummy_main_loader",
            "key": "id",
            "fields": {"bad": {"extract": "x", "call_by": "tests.call_by_fns:echo(a)"}},
        }
    }

    with pytest.raises(ConfigValidationError) as exc:
        validator.validate(config)

    assert any("must not declare call_by" in msg for msg in exc.value.errors)


def test_validator_rejects_call_by_syntax_error() -> None:
    validator = ConfigValidator()
    config = _base_validator_config()
    config["fields"]["text"] = {"call_by": "tests.call_by_fns:echo("}

    with pytest.raises(ConfigValidationError) as exc:
        validator.validate(config)

    assert any("invalid call_by" in msg for msg in exc.value.errors)


def test_validator_rejects_call_by_non_python_literal() -> None:
    validator = ConfigValidator()
    config = _base_validator_config()
    config["fields"]["text"] = {"call_by": "tests.call_by_fns:echo(true)"}

    with pytest.raises(ConfigValidationError) as exc:
        validator.validate(config)

    assert any("Invalid literal 'true'" in msg for msg in exc.value.errors)


def test_validator_rejects_call_by_depends_on_mismatch() -> None:
    validator = ConfigValidator()
    config = _base_validator_config()
    config["fields"]["sum"] = {"call_by": "tests.call_by_fns:add(a, b=b)", "depends_on": ["a"]}

    with pytest.raises(ConfigValidationError) as exc:
        validator.validate(config)

    assert any("does not allow 'depends_on'" in msg for msg in exc.value.errors)


def test_validator_rejects_constant_call_by_without_depends_on() -> None:
    validator = ConfigValidator()
    config = _base_validator_config()
    config["fields"]["const"] = {"call_by": "tests.call_by_fns:echo(1, $ctx.row_id)"}

    with pytest.raises(ConfigValidationError) as exc:
        validator.validate(config)

    assert any("call_by has no field dependencies" in msg for msg in exc.value.errors)


def test_validator_rejects_call_by_and_compute_both_present() -> None:
    validator = ConfigValidator()
    config = _base_validator_config()
    config["fields"]["bad"] = {"compute": "a", "call_by": "tests.call_by_fns:echo(a)"}

    with pytest.raises(ConfigValidationError) as exc:
        validator.validate(config)

    assert any("must not declare both" in msg for msg in exc.value.errors)


def test_validator_rejects_call_by_type_and_empty() -> None:
    validator = ConfigValidator()
    config = _base_validator_config()
    config["fields"]["bad_type"] = {"call_by": 1}
    config["fields"]["bad_empty"] = {"call_by": ""}

    with pytest.raises(ConfigValidationError) as exc:
        validator.validate(config)

    assert any("call_by must be a string" in msg for msg in exc.value.errors)
    assert any("call_by must not be empty" in msg for msg in exc.value.errors)


def test_validator_rejects_call_by_depends_on_empty_list() -> None:
    validator = ConfigValidator()
    config = _base_validator_config()
    config["fields"]["bad"] = {"call_by": "tests.call_by_fns:echo(a)", "depends_on": []}

    with pytest.raises(ConfigValidationError) as exc:
        validator.validate(config)

    assert any("does not allow 'depends_on'" in msg for msg in exc.value.errors)


def _make_call_by_config(call_by: str, *, depends_on: tuple) -> DemandConfig:
    return DemandConfig(
        name="demo",
        main_source=MainSourceConfig(source_id="orders", loader="tests.call_by_fns:dummy_main_loader"),
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
    config = _make_call_by_config("tests.call_by_fns:echo(status)", depends_on=("status",))
    converter = ConfigToIRConverter(allow_unsafe_resolver=True)
    demand_ir = converter.convert(config)

    derived = demand_ir.fields["text"]
    assert isinstance(derived, DerivedFieldIr)
    assert derived.compute(status="x", **{"$ctx": object()}) == "x"


def test_converter_rejects_unknown_call_by_reference() -> None:
    config = _make_call_by_config("tests.call_by_fns:missing(status)", depends_on=("status",))
    converter = ConfigToIRConverter(
        resolver=SecurePythonReferenceResolver(allowed_modules=frozenset(["tests.call_by_fns"])),
    )

    with pytest.raises(ConversionError, match="failed to resolve call_by reference"):
        converter.convert(config)


def test_converter_compiles_call_by_and_ctx() -> None:
    config = _make_call_by_config("tests.call_by_fns:status_text(status=status, ctx=$ctx)", depends_on=("status",))
    converter = ConfigToIRConverter(
        resolver=SecurePythonReferenceResolver(allowed_modules=frozenset(["tests.call_by_fns"])),
    )

    demand_ir = converter.convert(config)
    derived = demand_ir.fields["text"]
    assert isinstance(derived, DerivedFieldIr)
    assert derived.call_ctx_key == "$ctx"

    ctx = {"row_id": 1, "batch_num": 2, "field_id": "text", "deps": ("status",), "values": {"status": True}}
    # Use a minimal duck-typed ctx in this unit test.
    result = derived.compute(status=True, **{"$ctx": type("Ctx", (), ctx)()})
    assert result == "ok:1:2"


def test_converter_rejects_missing_compute_and_call_by() -> None:
    config = DemandConfig(
        name="demo",
        main_source=MainSourceConfig(source_id="orders", loader="tests.call_by_fns:dummy_main_loader"),
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
    converter = ConfigToIRConverter(
        resolver=SecurePythonReferenceResolver(allowed_modules=frozenset(["tests.call_by_fns"])),
    )

    with pytest.raises(ConversionError, match="must declare"):
        converter.convert(config)


def test_converter_call_by_parse_error_and_literal_and_ctx_attr_and_missing_ctx() -> None:
    converter = ConfigToIRConverter(
        resolver=SecurePythonReferenceResolver(allowed_modules=frozenset(["tests.call_by_fns"])),
    )
    base = DemandConfig(
        name="demo",
        main_source=MainSourceConfig(source_id="orders", loader="tests.call_by_fns:dummy_main_loader"),
        sources={},
        source_fields={"status": SourceFieldConfig(field_id="status", source="orders", extract="status")},
        derived_fields={},
    )

    bad = DemandConfig(
        **{
            **base.__dict__,
            "derived_fields": {
                "text": DerivedFieldConfig(field_id="text", name="text", call_by="tests.call_by_fns:echo(", depends_on=("status",))
            },
        }
    )
    with pytest.raises(ConversionError, match="invalid call_by"):
        converter.convert(bad)

    literal_cfg = DemandConfig(
        name=base.name,
        main_source=base.main_source,
        sources=base.sources,
        source_fields=base.source_fields,
        derived_fields={
            "text": DerivedFieldConfig(field_id="text", name="text", call_by="tests.call_by_fns:echo(1)", depends_on=("status",))
        },
    )
    demand_ir = converter.convert(literal_cfg)
    derived = demand_ir.fields["text"]
    assert isinstance(derived, DerivedFieldIr)
    assert derived.compute(status=True, **{"$ctx": object()}) == 1

    ctx_attr_cfg = DemandConfig(
        name=base.name,
        main_source=base.main_source,
        sources=base.sources,
        source_fields=base.source_fields,
        derived_fields={
            "text": DerivedFieldConfig(
                field_id="text",
                name="text",
                call_by="tests.call_by_fns:needs_ctx_attr($ctx.row_id)",
                depends_on=("status",),
            )
        },
    )
    demand_ir = converter.convert(ctx_attr_cfg)
    derived = demand_ir.fields["text"]
    assert isinstance(derived, DerivedFieldIr)
    ctx = type("Ctx", (), {"row_id": 9, "batch_num": 0})()
    assert derived.compute(status=True, **{"$ctx": ctx}) == 9
    with pytest.raises(ValueError, match="requires context"):
        derived.compute(status=True)


def test_compute_operator_injects_ctx_when_configured() -> None:
    def _calc(amount, **kwargs):  # type: ignore[no-untyped-def]
        ctx = kwargs["$ctx"]
        return "{}:{}".format(ctx.row_id, ctx.batch_num)

    field_spec = DerivedFieldIr(
        field_id="score",
        name="Score",
        dependencies=("amount",),
        calculator=_calc,
        call_ctx_key="$ctx",
    )
    operator = ComputeOperatorIr(
        operator_id="compute_score",
        operator_type=OperatorType.COMPUTE.value,
        field_spec=field_spec,
        input_fields=("amount",),
    )

    plan = ExecutionPlan(field_specs={"score": field_spec}, target_fields=["score"])
    runtime = ExecutionRuntime(plan, HookManager(), ObserverManager(), None)
    runtime.batch_num = 7

    context = BatchContext()
    context.set_field_value("amount", 1, 100)
    context.set_field_value("amount", 2, 200)

    ComputeOperatorExecutor().execute(operator, context, [1, 2], runtime)

    assert context.get_field_value("score", 1) == "1:7"
    assert context.get_field_value("score", 2) == "2:7"


def test_converter_call_by_ctx_attr_missing_attribute_raises() -> None:
    converter = ConfigToIRConverter(
        resolver=SecurePythonReferenceResolver(allowed_modules=frozenset(["tests.call_by_fns"])),
    )
    config = _make_call_by_config("tests.call_by_fns:needs_ctx_attr($ctx.row_id)", depends_on=("status",))
    demand_ir = converter.convert(config)
    derived = demand_ir.fields["text"]
    assert isinstance(derived, DerivedFieldIr)

    with pytest.raises(AttributeError, match="call_by context missing attribute 'row_id'"):
        derived.compute(status=True, **{"$ctx": type("Ctx", (), {"batch_num": 1})()})


def test_converter_call_by_rejects_non_field_value_result() -> None:
    converter = ConfigToIRConverter(
        resolver=SecurePythonReferenceResolver(allowed_modules=frozenset(["tests.call_by_fns"])),
    )
    config = _make_call_by_config("tests.call_by_fns:echo($ctx.values)", depends_on=("status",))
    demand_ir = converter.convert(config)
    derived = demand_ir.fields["text"]
    assert isinstance(derived, DerivedFieldIr)

    ctx = type("Ctx", (), {"values": {"status": True}})()
    with pytest.raises(TypeError, match="returned unsupported type 'dict'"):
        derived.compute(status=True, **{"$ctx": ctx})
