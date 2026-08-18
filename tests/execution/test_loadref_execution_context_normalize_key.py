import pytest

from scalim.execution.context import BatchContext
from scalim.execution.executor.operators.load_ref.context import LoadRefExecutionContext
from scalim.spec.ir import KeyIr, LookupStepIr, RuntimeHandleIdIr, SourceIr
from scalim.spec.ir.binding import LoaderIr
from scalim.utils.relation_signature import build_relation_signature


def test_normalize_key_accepts_implicit_from_fields() -> None:
    class _InstrumentationStub:
        def emit_relation_lookup(self, **_kwargs) -> None:  # type: ignore[no-untyped-def]
            return

        def emit_diagnostic_warning(self, **_kwargs) -> None:  # type: ignore[no-untyped-def]
            return

    class _RuntimeStub:
        def __init__(self) -> None:
            self.key_normalize_cache = {}
            self.instrumentation = _InstrumentationStub()

        def normalize_lookup_key_with_status(self, raw_key, _step):  # type: ignore[no-untyped-def]
            return raw_key, "ok", None

        def resolve_lookup_source(self, step):  # type: ignore[no-untyped-def]
            return target_source

    target_source = SourceIr(
        source_id="targets",
        key=KeyIr(key="target_id"),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr(handle_id="targets.loader")),
    )
    step = LookupStepIr(from_field="fk_id", to_source_id=target_source.source_id)
    relation_signature = build_relation_signature((step,), {target_source.source_id: target_source})

    exec_ctx = LoadRefExecutionContext(
        runtime=_RuntimeStub(),  # type: ignore[arg-type]
        context=BatchContext(),
        batch_row_nth=[],
        field_key="target_name",
        relation_signature=relation_signature,
    )

    # Coverage: `from_fields=None` should fall back to `step.get_from_fields()`.
    assert exec_ctx.normalize_key(row_id=0, raw_key=1, step=step) == 1


def test_build_relation_signature_requires_sources_for_nonempty_steps() -> None:
    step = LookupStepIr(from_field="fk_id", to_source_id="targets")
    with pytest.raises(TypeError, match="missing required argument: 'sources'"):
        build_relation_signature((step,))
