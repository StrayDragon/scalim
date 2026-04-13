import pytest

from scalim.execution.loader_call_params import build_loader_call_params
from scalim.execution.runtime_bindings import RuntimeBindings
from scalim.spec.ir import RuntimeHandleIdIr
from scalim.spec.ir.binding import BindingIr, LoaderCallContextIr


def test_runtime_bindings_require_missing_variants_raise_key_error_and_debug_summary_runs() -> None:
    bindings = RuntimeBindings()

    with pytest.raises(KeyError, match=r"Missing runtime main source loader"):
        _ = bindings.require_main_source_loader("main")

    with pytest.raises(KeyError, match=r"Missing runtime source loader"):
        _ = bindings.require_source_loader("s1")

    with pytest.raises(KeyError, match=r"Missing runtime derived calculator"):
        _ = bindings.require_derived_calculator("f1")

    summary = bindings.debug_summary()
    assert isinstance(summary, dict)
    assert summary.get("main_source_loaders") == 0


def test_build_loader_call_params_rejects_missing_runtime_params_builder() -> None:
    runtime_bindings = RuntimeBindings()
    binding = BindingIr(
        key_field="k",
        params_builder_ref=RuntimeHandleIdIr(handle_id="params_builder:s1:k"),
    )
    ctx = LoaderCallContextIr(source_id="s1")

    with pytest.raises(KeyError, match=r"Missing runtime params builder"):
        _ = build_loader_call_params(binding=binding, context=ctx, runtime_bindings=runtime_bindings)
