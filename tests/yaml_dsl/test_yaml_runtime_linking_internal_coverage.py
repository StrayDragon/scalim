import pytest

from scalim.dsl.yaml_dsl.runtime.errors import ScalimResolverError
from scalim.dsl.yaml_dsl.runtime.runtime_linking import (
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
from scalim.spec.ir import BuiltinCallableIdIr, CallByValueIr, ComputeCallContextIr, PythonReferenceIr, RuntimeHandleIdIr
from scalim.spec.ir import DemandIr, DerivedFieldIr, KeyIr, MainSourceIr, SourceIr
from scalim.spec.ir.binding import LoaderIr


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
