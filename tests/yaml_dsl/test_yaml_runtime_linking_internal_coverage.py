import pytest

from scalim.dsl.yaml_dsl.runtime.errors import ScalimResolverError
from scalim.dsl.yaml_dsl.runtime.runtime_linking import (
    _build_ref_default_call_by_calculator,
    _bind_field_runtime_bindings,
    _bind_source_runtime_bindings,
    _compose_value_ops,
    _eval_call_by_value,
    _preflight_loader_params_signature,
    _resolve_callable_ref,
    _resolve_value_op_callable,
)
from scalim.dsl.yaml_dsl._internal.config_parsing.security import build_compute_engine
from scalim.execution.runtime_bindings import RuntimeBindings
from scalim.spec.ir import (
    BuiltinCallableIdIr,
    CallBySpecIr,
    CallByValueIr,
    ComputeCallContextIr,
    FieldIr,
    PythonReferenceIr,
    RuntimeHandleIdIr,
    ValueOpIr,
)
from scalim.spec.ir import DemandIr, DerivedFieldIr, KeyIr, MainSourceIr, SourceIr
from scalim.spec.ir._fields import FieldDefaultCaseIr
from scalim.spec.ir.binding import BindingIr, LoaderIr
from scalim.dsl.yaml_dsl.runtime.builtin_callables import default, default_of_value_cast


class _DummyResolver:
    def __init__(self) -> None:
        self.references = []

    def resolve(self, reference: str):  # noqa: ANN001
        self.references.append(str(reference))
        return lambda *_args, **_kwargs: None


def test_resolve_callable_ref_covers_runtime_handle_and_builtin_branches() -> None:
    resolver = _DummyResolver()

    fn = _resolve_callable_ref(BuiltinCallableIdIr(callable_id="custom/echo"), resolver=resolver)
    assert callable(fn)
    assert resolver.references[-1] == "^custom/echo"

    with pytest.raises(ScalimResolverError, match=r"Runtime handle references are not supported"):
        _resolve_callable_ref(RuntimeHandleIdIr(handle_id="h1"), resolver=resolver)


def test_eval_call_by_value_unknown_kind_raises() -> None:
    ctx = ComputeCallContextIr(
        row_id=1,
        batch_num=0,
        field_id="f",
        deps=(),
        values={},
    )
    with pytest.raises(ValueError, match=r"unknown call_by value kind"):
        _ = _eval_call_by_value(CallByValueIr(kind="unknown", value="x"), field_id="f", dep_values={}, ctx=ctx)


def test_preflight_loader_params_signature_missing_contract_is_noop() -> None:
    def loader(**_kwargs):  # noqa: ANN001
        return None

    # params_template missing `top_level_mapping_string_keys` -> early return.
    _preflight_loader_params_signature(location="sources.s1.params", reference="tests:loader", fn=loader, params_template=object())


def test_value_ops_internal_coverage_edges() -> None:
    resolver = _DummyResolver()

    class _OpMissingRef:
        kind = "transform"

    with pytest.raises(ValueError, match=r"requires callable_ref"):
        _ = _resolve_value_op_callable(field_id="f", kind="transform", op=_OpMissingRef(), resolver=resolver)

    class _OpBadRef:
        kind = "transform"
        callable_ref = object()

    with pytest.raises(TypeError, match=r"invalid callable_ref"):
        _ = _resolve_value_op_callable(field_id="f", kind="transform", op=_OpBadRef(), resolver=resolver)

    class _OpCastUnknown:
        kind = "cast"
        to = "unknown_cast"

    with pytest.raises(ValueError, match=r"Unknown value_cast"):
        _ = _compose_value_ops(field_id="f", ops=(_OpCastUnknown(),), resolver=resolver)

    # `format/transform` uses runtime linking + _ensure_field_value checks.
    def fmt(v):  # noqa: ANN001
        return "x{}".format(v)

    class _FmtResolver:
        def resolve(self, reference: str):  # noqa: ANN001
            assert reference
            return fmt

    class _OpFormat:
        kind = "format"
        callable_ref = PythonReferenceIr(reference="dummy:fmt", module_path="dummy", attr_path=("fmt",), style="dotted")

    transform = _compose_value_ops(field_id="f", ops=(_OpFormat(),), resolver=_FmtResolver())
    assert transform is not None
    assert transform(1) == "x1"

    class _OpUnknown:
        kind = "bad_kind"

    with pytest.raises(ValueError, match=r"Unknown ValueOpIr.kind"):
        _ = _compose_value_ops(field_id="f", ops=(_OpUnknown(),), resolver=resolver)


def test_bind_source_runtime_bindings_builds_extractor_wrapper() -> None:
    calls = []

    def _loader():  # type: ignore[no-untyped-def]
        calls.append("loader")
        return {}

    def _extract(lookup_key, result):  # type: ignore[no-untyped-def]
        calls.append("extract")
        return {"k": lookup_key, "r": result}

    class _Resolver:
        def resolve(self, reference: str):  # noqa: ANN001
            if reference == "tests:loader":
                return _loader
            if reference == "tests:extract":
                return _extract
            raise AssertionError("unexpected reference: {}".format(reference))

    source = SourceIr(
        source_id="s1",
        key=KeyIr(key="id"),
        loader_spec=LoaderIr(
            callable_ref=PythonReferenceIr(reference="tests:loader", module_path="tests", attr_path=("loader",), style="class"),
            extractor_ref=PythonReferenceIr(reference="tests:extract", module_path="tests", attr_path=("extract",), style="class"),
        ),
    )
    demand_ir = DemandIr.from_irs(
        sources=[source],
        fields=(),
        main_source=MainSourceIr(source_id="main", loader_ref=RuntimeHandleIdIr(handle_id="main.loader")),
    )

    bindings = RuntimeBindings()
    _bind_source_runtime_bindings(demand_ir, bindings=bindings, resolver=_Resolver())

    assert "s1" in bindings.loader_extractors
    wrapped = bindings.loader_extractors["s1"]
    assert wrapped("lk", {"lk": 1}) == {"k": "lk", "r": {"lk": 1}}
    assert "extract" in calls


def test_bind_source_runtime_bindings_skips_preflight_when_params_template_missing() -> None:
    def _loader(**_kwargs):  # noqa: ANN001
        return {}

    class _Resolver:
        def resolve(self, reference: str):  # noqa: ANN001
            assert reference == "tests:loader"
            return _loader

    source = SourceIr(
        source_id="s1",
        key=KeyIr(key="id"),
        loader_spec=LoaderIr(
            callable_ref=PythonReferenceIr(reference="tests:loader", module_path="tests", attr_path=("loader",), style="class"),
        ),
        bind=BindingIr(key_field="id"),
    )
    demand_ir = DemandIr.from_irs(
        sources=[source],
        fields=(),
        main_source=MainSourceIr(source_id="main", loader_ref=RuntimeHandleIdIr(handle_id="main.loader")),
    )

    bindings = RuntimeBindings()
    _bind_source_runtime_bindings(demand_ir, bindings=bindings, resolver=_Resolver())
    assert "s1" in bindings.source_loaders


def test_bind_field_runtime_bindings_rejects_invalid_derived_field_state() -> None:
    # DerivedFieldIr enforces invariants in __post_init__, but we still keep a runtime guard for
    # corrupted/untrusted instances (e.g., pickled state). Build an invalid instance without running __post_init__.
    bad = object.__new__(DerivedFieldIr)
    object.__setattr__(bad, "field_id", "bad")
    object.__setattr__(bad, "name", "Bad")
    object.__setattr__(bad, "dependencies", ("x",))
    object.__setattr__(bad, "compute_expr", "")
    object.__setattr__(bad, "call_by", None)
    object.__setattr__(bad, "presentation", None)
    object.__setattr__(bad, "value_ops", ())
    object.__setattr__(bad, "call_ctx_key", None)
    object.__setattr__(bad, "is_constant_compute", False)

    demand_ir = DemandIr.from_irs(
        sources=[],
        fields=(bad,),
        main_source=MainSourceIr(source_id="main", loader_ref=RuntimeHandleIdIr(handle_id="main.loader")),
    )

    with pytest.raises(ValueError, match=r"missing compute_expr/call_by"):
        _bind_field_runtime_bindings(
            demand_ir,
            bindings=RuntimeBindings(),
            resolver=_DummyResolver(),  # type: ignore[arg-type] internal tests: duck-typed resolver
            compute_engine=build_compute_engine(),
        )


def test_bind_field_runtime_bindings_binds_ref_default_call_by_calculator() -> None:
    def _default() -> int:
        return 7

    class _Resolver:
        def resolve(self, reference: str):  # noqa: ANN001
            assert reference == "tests:default"
            return _default

    source = SourceIr(
        source_id="s1",
        key=KeyIr(key="id"),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr(handle_id="s1.loader")),
    )
    field = FieldIr(
        field_id="ref_value",
        name="Ref",
        source=source,
        default_cases=(
            FieldDefaultCaseIr(
                when="relation_miss",
                kind="call_by",
                call_by=CallBySpecIr(
                    reference=PythonReferenceIr(reference="tests:default", module_path="tests", attr_path=("default",), style="dotted")
                ),
            ),
        ),
    )
    demand_ir = DemandIr.from_irs(
        sources=[source],
        fields=(field,),
        main_source=MainSourceIr(source_id="main", loader_ref=RuntimeHandleIdIr(handle_id="main.loader")),
    )

    bindings = RuntimeBindings()
    _bind_field_runtime_bindings(
        demand_ir,
        bindings=bindings,
        resolver=_Resolver(),  # type: ignore[arg-type] internal tests: duck-typed resolver
        compute_engine=build_compute_engine(),
    )

    calc = bindings.get_ref_default_calculator("ref_value", 0)
    assert calc is not None
    ctx = ComputeCallContextIr(row_id=1, batch_num=0, field_id="ref_value", deps=(), values={})
    assert calc(ctx=ctx) == 7


def test_bind_field_runtime_bindings_inlines_defaults_default_for_str() -> None:
    source = SourceIr(
        source_id="s1",
        key=KeyIr(key="id"),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr(handle_id="s1.loader")),
    )
    field = FieldIr(
        field_id="text",
        name="Text",
        source=source,
        value_ops=(ValueOpIr(kind="cast", to="str"),),
        default_cases=(
            FieldDefaultCaseIr(
                when="relation_miss",
                kind="call_by",
                call_by=CallBySpecIr(reference=BuiltinCallableIdIr(callable_id="defaults/default")),
            ),
        ),
    )
    demand_ir = DemandIr.from_irs(
        sources=[source],
        fields=(field,),
        main_source=MainSourceIr(source_id="main", loader_ref=RuntimeHandleIdIr(handle_id="main.loader")),
    )

    bindings = RuntimeBindings()
    _bind_field_runtime_bindings(
        demand_ir,
        bindings=bindings,
        resolver=_DummyResolver(),  # type: ignore[arg-type] internal tests: duck-typed resolver
        compute_engine=build_compute_engine(),
    )

    calc = bindings.get_ref_default_calculator("text", 0)
    assert calc is not None
    ctx = ComputeCallContextIr(row_id=1, batch_num=0, field_id="text", deps=(), values={})
    assert calc(ctx=ctx) == ""


def test_bind_field_runtime_bindings_inlines_defaults_default_for_int() -> None:
    source = SourceIr(
        source_id="s1",
        key=KeyIr(key="id"),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr(handle_id="s1.loader")),
    )
    field = FieldIr(
        field_id="n",
        name="N",
        source=source,
        value_ops=(ValueOpIr(kind="cast", to="int"),),
        default_cases=(
            FieldDefaultCaseIr(
                when="relation_miss",
                kind="call_by",
                call_by=CallBySpecIr(reference=BuiltinCallableIdIr(callable_id="defaults/default")),
            ),
        ),
    )
    demand_ir = DemandIr.from_irs(
        sources=[source],
        fields=(field,),
        main_source=MainSourceIr(source_id="main", loader_ref=RuntimeHandleIdIr(handle_id="main.loader")),
    )

    bindings = RuntimeBindings()
    _bind_field_runtime_bindings(
        demand_ir,
        bindings=bindings,
        resolver=_DummyResolver(),  # type: ignore[arg-type] internal tests: duck-typed resolver
        compute_engine=build_compute_engine(),
    )

    calc = bindings.get_ref_default_calculator("n", 0)
    assert calc is not None
    ctx = ComputeCallContextIr(row_id=1, batch_num=0, field_id="n", deps=(), values={})
    assert calc(ctx=ctx) == 0


def test_bind_field_runtime_bindings_rejects_defaults_default_without_value_cast() -> None:
    source = SourceIr(
        source_id="s1",
        key=KeyIr(key="id"),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr(handle_id="s1.loader")),
    )
    field = FieldIr(
        field_id="x",
        name="X",
        source=source,
        default_cases=(
            FieldDefaultCaseIr(
                when="relation_miss",
                kind="call_by",
                call_by=CallBySpecIr(reference=BuiltinCallableIdIr(callable_id="defaults/default")),
            ),
        ),
    )
    demand_ir = DemandIr.from_irs(
        sources=[source],
        fields=(field,),
        main_source=MainSourceIr(source_id="main", loader_ref=RuntimeHandleIdIr(handle_id="main.loader")),
    )

    with pytest.raises(ScalimResolverError, match=r"requires explicit value_cast"):
        _bind_field_runtime_bindings(
            demand_ir,
            bindings=RuntimeBindings(),
            resolver=_DummyResolver(),  # type: ignore[arg-type] internal tests: duck-typed resolver
            compute_engine=build_compute_engine(),
        )


def test_bind_field_runtime_bindings_rejects_defaults_default_without_cast_op() -> None:
    source = SourceIr(
        source_id="s1",
        key=KeyIr(key="id"),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr(handle_id="s1.loader")),
    )
    field = FieldIr(
        field_id="x",
        name="X",
        source=source,
        value_ops=(
            ValueOpIr(
                kind="format",
                callable_ref=PythonReferenceIr(reference="tests:fmt", module_path="tests", attr_path=("fmt",), style="dotted"),
            ),
        ),
        default_cases=(
            FieldDefaultCaseIr(
                when="relation_miss",
                kind="call_by",
                call_by=CallBySpecIr(reference=BuiltinCallableIdIr(callable_id="defaults/default")),
            ),
        ),
    )
    demand_ir = DemandIr.from_irs(
        sources=[source],
        fields=(field,),
        main_source=MainSourceIr(source_id="main", loader_ref=RuntimeHandleIdIr(handle_id="main.loader")),
    )

    with pytest.raises(ScalimResolverError, match=r"requires explicit value_cast"):
        _bind_field_runtime_bindings(
            demand_ir,
            bindings=RuntimeBindings(),
            resolver=_DummyResolver(),  # type: ignore[arg-type] internal tests: duck-typed resolver
            compute_engine=build_compute_engine(),
        )


def test_bind_field_runtime_bindings_rejects_defaults_default_unknown_value_cast() -> None:
    source = SourceIr(
        source_id="s1",
        key=KeyIr(key="id"),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr(handle_id="s1.loader")),
    )
    field = FieldIr(
        field_id="x",
        name="X",
        source=source,
        value_ops=(ValueOpIr(kind="cast", to="bad_cast"),),
        default_cases=(
            FieldDefaultCaseIr(
                when="relation_miss",
                kind="call_by",
                call_by=CallBySpecIr(reference=BuiltinCallableIdIr(callable_id="defaults/default")),
            ),
        ),
    )
    demand_ir = DemandIr.from_irs(
        sources=[source],
        fields=(field,),
        main_source=MainSourceIr(source_id="main", loader_ref=RuntimeHandleIdIr(handle_id="main.loader")),
    )

    with pytest.raises(ScalimResolverError, match=r"unsupported value_cast"):
        _bind_field_runtime_bindings(
            demand_ir,
            bindings=RuntimeBindings(),
            resolver=_DummyResolver(),  # type: ignore[arg-type] internal tests: duck-typed resolver
            compute_engine=build_compute_engine(),
        )


def test_bind_field_runtime_bindings_skips_ref_default_case_when_not_call_by() -> None:
    source = SourceIr(
        source_id="s1",
        key=KeyIr(key="id"),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr(handle_id="s1.loader")),
    )
    field = FieldIr(
        field_id="x",
        name="X",
        source=source,
        default_cases=(FieldDefaultCaseIr(when="relation_miss", kind="literal", literal=1),),
    )
    demand_ir = DemandIr.from_irs(
        sources=[source],
        fields=(field,),
        main_source=MainSourceIr(source_id="main", loader_ref=RuntimeHandleIdIr(handle_id="main.loader")),
    )

    bindings = RuntimeBindings()
    _bind_field_runtime_bindings(
        demand_ir,
        bindings=bindings,
        resolver=_DummyResolver(),  # type: ignore[arg-type] internal tests: duck-typed resolver
        compute_engine=build_compute_engine(),
    )
    assert bindings.get_ref_default_calculator("x", 0) is None


def test_bind_field_runtime_bindings_skips_ref_default_case_when_call_by_is_not_spec() -> None:
    class _BadCase:
        kind = "call_by"
        call_by = object()

    source = SourceIr(
        source_id="s1",
        key=KeyIr(key="id"),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr(handle_id="s1.loader")),
    )
    field = FieldIr(
        field_id="x",
        name="X",
        source=source,
        default_cases=(_BadCase(),),  # type: ignore[arg-type] internal tests: corrupted case instance
    )
    demand_ir = DemandIr.from_irs(
        sources=[source],
        fields=(field,),
        main_source=MainSourceIr(source_id="main", loader_ref=RuntimeHandleIdIr(handle_id="main.loader")),
    )

    bindings = RuntimeBindings()
    _bind_field_runtime_bindings(
        demand_ir,
        bindings=bindings,
        resolver=_DummyResolver(),  # type: ignore[arg-type] internal tests: duck-typed resolver
        compute_engine=build_compute_engine(),
    )
    assert bindings.get_ref_default_calculator("x", 0) is None


def test_bind_field_runtime_bindings_wraps_ref_default_call_by_preflight_errors() -> None:
    def _default():  # noqa: ANN001
        return 1

    class _Resolver:
        def resolve(self, reference: str):  # noqa: ANN001
            assert reference == "tests:default"
            return _default

    source = SourceIr(
        source_id="s1",
        key=KeyIr(key="id"),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr(handle_id="s1.loader")),
    )
    field = FieldIr(
        field_id="ref_value",
        name="Ref",
        source=source,
        default_cases=(
            FieldDefaultCaseIr(
                when="relation_miss",
                kind="call_by",
                call_by=CallBySpecIr(
                    reference=PythonReferenceIr(reference="tests:default", module_path="tests", attr_path=("default",), style="dotted"),
                    args=(CallByValueIr(kind="literal", value=1),),
                ),
            ),
        ),
    )
    demand_ir = DemandIr.from_irs(
        sources=[source],
        fields=(field,),
        main_source=MainSourceIr(source_id="main", loader_ref=RuntimeHandleIdIr(handle_id="main.loader")),
    )

    with pytest.raises(ScalimResolverError, match=r"fields\.ref_value\.default\[0\]\.call_by"):
        _bind_field_runtime_bindings(
            demand_ir,
            bindings=RuntimeBindings(),
            resolver=_Resolver(),  # type: ignore[arg-type] internal tests: duck-typed resolver
            compute_engine=build_compute_engine(),
        )


def test_build_ref_default_call_by_calculator_requires_ctx_and_evaluates_args_kwargs() -> None:
    calls = []

    def _fn(a, **kwargs):  # noqa: ANN001
        calls.append((a, dict(kwargs)))
        return 0

    call_by = CallBySpecIr(
        reference=PythonReferenceIr(reference="tests:fn", module_path="tests", attr_path=("fn",), style="dotted"),
        args=(CallByValueIr(kind="field", value="cs_id"),),
        kwargs=(("x", CallByValueIr(kind="literal", value=1)),),
        field_names=("cs_id",),
    )
    calc = _build_ref_default_call_by_calculator(field_id="f", idx=0, dep_keys=("cs_id",), call_by=call_by, fn=_fn)

    with pytest.raises(TypeError, match=r"requires ctx=ComputeCallContextIr"):
        _ = calc(123)

    ctx = ComputeCallContextIr(row_id=1, batch_num=0, field_id="f", deps=("cs_id",), values={"cs_id": 123})
    assert calc(123, ctx=ctx) == 0
    assert calls == [(123, {"x": 1})]


def test_field_default_case_ir_invariants() -> None:
    with pytest.raises(ValueError, match=r"must not set call_by"):
        _ = FieldDefaultCaseIr(
            when="relation_miss",
            kind="literal",
            literal=0,
            call_by=CallBySpecIr(reference=BuiltinCallableIdIr(callable_id="defaults/default")),
        )

    with pytest.raises(ValueError, match=r"requires call_by"):
        _ = FieldDefaultCaseIr(
            when="relation_miss",
            kind="call_by",
        )

    with pytest.raises(ValueError, match=r"Unknown FieldDefaultCaseIr\.kind"):
        _ = FieldDefaultCaseIr(
            when="relation_miss",
            kind="bad",
        )


def test_default_of_value_cast_callables_are_available() -> None:
    assert default_of_value_cast() == 0
    assert default() == 0
