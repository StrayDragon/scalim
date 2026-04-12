import pytest

from scalim.dsl.yaml_dsl.runtime.errors import ScalimResolverError
from scalim.dsl.yaml_dsl.runtime.runtime_linking import (
    _compose_value_ops,
    _eval_call_by_value,
    _preflight_loader_params_signature,
    _resolve_callable_ref,
    _resolve_value_op_callable,
)
from scalim.spec.ir import BuiltinCallableIdIr, CallByValueIr, ComputeCallContextIr, PythonReferenceIr, RuntimeHandleIdIr


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
