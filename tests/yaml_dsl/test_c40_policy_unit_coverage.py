"""c40 策略单元覆盖:LookupChunking / SourceCache / RowsReuse / apply / contracts 边界."""

from __future__ import annotations

import pytest

from scalim.dsl.yaml_dsl.runtime._internal.apply_source_runtime_policies import (
    apply_source_runtime_policies,
    resolve_chunk_parallelism_from_runtime,
)
from scalim.dsl.yaml_dsl.runtime.contracts import DemandRunRuntimeOptions
from scalim.dsl.yaml_dsl.runtime.source_policies import RowsReuse, SourceCache
from scalim.execution.lookup_chunking import LookupChunking, normalize_optional_max_chunk_workers
from scalim.spec.ir import DemandIr, KeyIr, LoaderIr, MainSourceIr, SourceIr
from scalim.spec.ir.binding import BindingIr
from scalim.spec.ir.callable_refs import RuntimeHandleIdIr
from scalim.typedefs import RowsReuseMode, SourceSpecIrCacheMode


def test_lookup_chunking_off_and_validation_branches() -> None:
    off = LookupChunking.off()
    assert off.is_off() is True
    assert off.effective_chunk_size() is None
    assert off.wants_parallel() is False

    with pytest.raises(TypeError, match="must be an int"):
        _ = LookupChunking.sized(True)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match=">= 1"):
        _ = LookupChunking.sized(0)
    with pytest.raises(ValueError, match="'off' or 'sized'"):
        _ = LookupChunking(size=None, parallel=False, max_chunk_workers=None, _kind="nope")
    with pytest.raises(ValueError, match="must not set size"):
        _ = LookupChunking(size=1, parallel=False, max_chunk_workers=None, _kind="off")
    with pytest.raises(ValueError, match="size >= 1"):
        _ = LookupChunking(size=None, parallel=False, max_chunk_workers=None, _kind="sized")
    with pytest.raises(TypeError, match="boolean"):
        _ = LookupChunking(size=2, parallel="yes", max_chunk_workers=None, _kind="sized")  # type: ignore[arg-type]

    assert normalize_optional_max_chunk_workers(None, label="w") is None
    assert normalize_optional_max_chunk_workers(3, label="w") == 3


def test_source_cache_and_rows_reuse_reject_non_enum_mode() -> None:
    with pytest.raises(TypeError, match="SourceSpecIrCacheMode"):
        _ = SourceCache(_mode="none")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="RowsReuseMode"):
        _ = RowsReuse(_mode="batch")  # type: ignore[arg-type]
    assert SourceCache.none().to_ir_mode() is SourceSpecIrCacheMode.NONE
    assert RowsReuse.batch().to_binding_cache_mode() == RowsReuseMode.BATCH.value


def test_demand_run_runtime_options_policy_mapping_normalize() -> None:
    empty = DemandRunRuntimeOptions(lookup_chunking=None, source_cache=None, rows_reuse=None)
    assert empty.lookup_chunking == {}
    assert empty.source_cache == {}
    assert empty.rows_reuse == {}

    with pytest.raises(TypeError, match="must be a Mapping"):
        _ = DemandRunRuntimeOptions(lookup_chunking=["x"])  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="non-empty"):
        _ = DemandRunRuntimeOptions(lookup_chunking={"": LookupChunking.off()})
    with pytest.raises(TypeError, match="must be a LookupChunking"):
        _ = DemandRunRuntimeOptions(lookup_chunking={"s": object()})  # type: ignore[dict-item]


def test_resolve_chunk_parallelism_takes_min_workers() -> None:
    enabled, workers = resolve_chunk_parallelism_from_runtime(
        parallelize_lookup_chunks=False,
        max_chunk_workers=8,
        lookup_chunking={
            "a": LookupChunking.sized(10, parallel=True, max_chunk_workers=4),
            "b": LookupChunking.sized(10, parallel=True, max_chunk_workers=None),
        },
    )
    assert enabled is True
    assert workers == 4


def _demand_with_source(*, bind=None, bindings=None) -> DemandIr:  # type: ignore[no-untyped-def]
    orders = MainSourceIr(source_id="orders", loader_ref=RuntimeHandleIdIr(handle_id="orders.loader"))
    source = SourceIr(
        source_id="customers",
        key=KeyIr(key="customer_id"),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr(handle_id="customers.loader")),
        bind=bind,
        bindings=bindings or {},
    )
    return DemandIr.from_irs(sources=[source], fields=[], main_source=orders)


def test_apply_rows_reuse_patches_bindings_and_noop_when_already_matching() -> None:
    rows_bind = BindingIr(
        key_field="customer_id",
        params_builder_ref=RuntimeHandleIdIr(handle_id="customers.params"),
        param_name="rows",
        mode="rows",
        cache_mode="batch",
    )
    demand = _demand_with_source(bindings={"customer_id": rows_bind})
    patched = apply_source_runtime_policies(
        demand,
        lookup_chunking={},
        source_cache={},
        rows_reuse={"customers": RowsReuse.none()},
    )
    assert patched.sources["customers"].bindings["customer_id"].cache_mode == "none"

    same = apply_source_runtime_policies(
        patched,
        lookup_chunking={},
        source_cache={},
        rows_reuse={"customers": RowsReuse.none()},
    )
    assert same is patched
