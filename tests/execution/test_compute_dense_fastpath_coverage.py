from typing import Any, Iterable, Tuple

import pytest

import scalim.execution.executor.operators.compute.executor as compute_impl
from scalim.execution.context import DenseBatchContext
from scalim.execution.guardrails import GuardrailsComputePolicy, GuardrailsPolicy
from scalim.execution.runtime_bindings import RuntimeBindings
from scalim.planning.plan import ExecutionPlan
from scalim.spec.ir import DerivedFieldIr

from tests.fixtures.executor_operator_fixtures import _make_runtime


def _make_dense_runtime(*, field_spec: DerivedFieldIr, runtime_bindings: RuntimeBindings):
    plan = ExecutionPlan(field_specs={field_spec.field_id: field_spec})
    runtime = _make_runtime(plan, None, runtime_bindings=runtime_bindings)
    runtime.batch_num = 7
    return runtime


def test_execute_row_compute_dense_returns_false_when_output_pruned() -> None:
    field_spec = DerivedFieldIr(field_id="out", name="Out", dependencies=("a",), compute_expr="a")
    runtime = _make_dense_runtime(field_spec=field_spec, runtime_bindings=RuntimeBindings(derived_calculators={"out": (lambda a: a)}))

    ctx = DenseBatchContext(base_row_id=0, row_count=1, required_fields={"keep"})
    ok = compute_impl._execute_row_compute_dense(
        field_spec=field_spec,
        context=ctx,
        batch_row_nth=[0],
        runtime=runtime,
        compute_mode="full",
        wants_field_compute=False,
    )
    assert ok is False


def test_execute_row_compute_dense_skips_disabled_rows() -> None:
    field_spec = DerivedFieldIr(field_id="out", name="Out", dependencies=("a",), compute_expr="a")
    runtime = _make_dense_runtime(field_spec=field_spec, runtime_bindings=RuntimeBindings(derived_calculators={"out": (lambda a: a)}))

    ctx = DenseBatchContext(base_row_id=0, row_count=1, required_fields={"a", "out"})
    ctx.set_field_value("a", 0, 1)
    ctx.disable_row(0)

    ok = compute_impl._execute_row_compute_dense(
        field_spec=field_spec,
        context=ctx,
        batch_row_nth=[0],
        runtime=runtime,
        compute_mode="full",
        wants_field_compute=False,
    )
    assert ok is True
    assert ctx.get_field_value("out", 0) is None


def test_execute_row_compute_dense_returns_false_for_non_int_row_id() -> None:
    field_spec = DerivedFieldIr(field_id="out", name="Out", dependencies=("a",), compute_expr="a")
    runtime = _make_dense_runtime(field_spec=field_spec, runtime_bindings=RuntimeBindings(derived_calculators={"out": (lambda a: a)}))

    ctx = DenseBatchContext(base_row_id=0, row_count=1, required_fields={"out"})
    ok = compute_impl._execute_row_compute_dense(
        field_spec=field_spec,
        context=ctx,
        batch_row_nth=["x"],  # type: ignore[list-item]
        runtime=runtime,
        compute_mode="full",
        wants_field_compute=False,
    )
    assert ok is False


def test_execute_row_compute_dense_returns_false_for_out_of_range_row_id() -> None:
    field_spec = DerivedFieldIr(field_id="out", name="Out", dependencies=("a",), compute_expr="a")
    runtime = _make_dense_runtime(field_spec=field_spec, runtime_bindings=RuntimeBindings(derived_calculators={"out": (lambda a: a)}))

    ctx = DenseBatchContext(base_row_id=0, row_count=1, required_fields={"out"})
    ok = compute_impl._execute_row_compute_dense(
        field_spec=field_spec,
        context=ctx,
        batch_row_nth=[5],
        runtime=runtime,
        compute_mode="full",
        wants_field_compute=False,
    )
    assert ok is False


def test_execute_row_compute_dense_deps_len_one_without_ctx() -> None:
    field_spec = DerivedFieldIr(field_id="out", name="Out", dependencies=("a",), compute_expr="a")
    runtime = _make_dense_runtime(
        field_spec=field_spec, runtime_bindings=RuntimeBindings(derived_calculators={"out": (lambda a: int(a or 0) + 1)})
    )

    ctx = DenseBatchContext(base_row_id=0, row_count=1, required_fields={"a", "out"})
    ctx.set_field_value("a", 0, 1)
    assert (
        compute_impl._execute_row_compute_dense(
            field_spec=field_spec,
            context=ctx,
            batch_row_nth=[0],
            runtime=runtime,
            compute_mode="full",
            wants_field_compute=False,
        )
        is True
    )
    assert ctx.get_field_value("out", 0) == 2


def test_execute_row_compute_dense_overwrites_existing_value_skips_present_count_increment() -> None:
    field_spec = DerivedFieldIr(field_id="out", name="Out", dependencies=("a",), compute_expr="a")
    runtime = _make_dense_runtime(
        field_spec=field_spec, runtime_bindings=RuntimeBindings(derived_calculators={"out": (lambda a: int(a or 0) + 10)})
    )

    ctx = DenseBatchContext(base_row_id=0, row_count=1, required_fields={"a", "out"})
    ctx.set_field_value("a", 0, 1)
    ctx.set_field_value("out", 0, 123)
    st = ctx.dense_get_storage_for_read("out")
    assert st is not None
    assert st.present_count == 1

    assert (
        compute_impl._execute_row_compute_dense(
            field_spec=field_spec,
            context=ctx,
            batch_row_nth=[0],
            runtime=runtime,
            compute_mode="full",
            wants_field_compute=False,
        )
        is True
    )
    assert ctx.get_field_value("out", 0) == 11
    st2 = ctx.dense_get_storage_for_read("out")
    assert st2 is not None
    assert st2.present_count == 1


def test_execute_row_compute_dense_deps_len_one_with_ctx_variants() -> None:
    def _calc(a: Any, **kwargs: Any) -> Any:
        ctx_obj = kwargs["ctx"]
        return "{}:{}".format(a, ctx_obj.row_id)

    field_spec = DerivedFieldIr(field_id="out", name="Out", dependencies=("a",), compute_expr="a", call_ctx_key="$ctx")
    runtime = _make_dense_runtime(field_spec=field_spec, runtime_bindings=RuntimeBindings(derived_calculators={"out": _calc}))

    ctx_missing = DenseBatchContext(base_row_id=0, row_count=1, required_fields={"a", "out"})
    assert (
        compute_impl._execute_row_compute_dense(
            field_spec=field_spec,
            context=ctx_missing,
            batch_row_nth=[0],
            runtime=runtime,
            compute_mode="full",
            wants_field_compute=False,
        )
        is True
    )
    assert ctx_missing.get_field_value("out", 0) == "None:0"

    ctx_present = DenseBatchContext(base_row_id=0, row_count=1, required_fields={"a", "out"})
    ctx_present.set_field_value("a", 0, 3)
    assert (
        compute_impl._execute_row_compute_dense(
            field_spec=field_spec,
            context=ctx_present,
            batch_row_nth=[0],
            runtime=runtime,
            compute_mode="full",
            wants_field_compute=False,
        )
        is True
    )
    assert ctx_present.get_field_value("out", 0) == "3:0"


def test_execute_row_compute_dense_deps_len_two_with_ctx_and_transform() -> None:
    def _calc(a: Any, b: Any, **kwargs: Any) -> Any:
        _ = kwargs["ctx"]
        return int(a or 0) + int(b or 0)

    field_spec = DerivedFieldIr(field_id="out", name="Out", dependencies=("a", "b"), compute_expr="a + b", call_ctx_key="$ctx")
    runtime = _make_dense_runtime(
        field_spec=field_spec,
        runtime_bindings=RuntimeBindings(
            derived_calculators={"out": _calc},
            value_transforms={"out": (lambda value: int(value) * 10)},
        ),
    )

    ctx = DenseBatchContext(base_row_id=0, row_count=1, required_fields={"a", "b", "out"})
    ctx.set_field_value("a", 0, 1)
    ctx.set_field_value("b", 0, 2)
    assert (
        compute_impl._execute_row_compute_dense(
            field_spec=field_spec,
            context=ctx,
            batch_row_nth=[0],
            runtime=runtime,
            compute_mode="full",
            wants_field_compute=False,
        )
        is True
    )
    assert ctx.get_field_value("out", 0) == 30


def test_execute_row_compute_dense_deps_len_three_with_ctx_missing_values() -> None:
    def _calc(a: Any, b: Any, c: Any, **kwargs: Any) -> Any:
        _ = kwargs["ctx"]
        return (a, b, c)

    field_spec = DerivedFieldIr(field_id="out", name="Out", dependencies=("a", "b", "c"), compute_expr="a", call_ctx_key="$ctx")
    runtime = _make_dense_runtime(field_spec=field_spec, runtime_bindings=RuntimeBindings(derived_calculators={"out": _calc}))

    ctx = DenseBatchContext(base_row_id=0, row_count=1, required_fields={"a", "b", "c", "out"})
    assert (
        compute_impl._execute_row_compute_dense(
            field_spec=field_spec,
            context=ctx,
            batch_row_nth=[0],
            runtime=runtime,
            compute_mode="full",
            wants_field_compute=False,
        )
        is True
    )
    assert ctx.get_field_value("out", 0) == (None, None, None)


def test_execute_row_compute_dense_deps_len_gt3_with_and_without_ctx() -> None:
    def _calc(*args: Any, **kwargs: Any) -> Any:
        ctx_obj = kwargs.get("ctx")
        return (tuple(args), bool(ctx_obj))

    deps = ("a", "b", "c", "d")

    with_ctx = DerivedFieldIr(field_id="out", name="Out", dependencies=deps, compute_expr="a", call_ctx_key="$ctx")
    runtime = _make_dense_runtime(field_spec=with_ctx, runtime_bindings=RuntimeBindings(derived_calculators={"out": _calc}))
    ctx = DenseBatchContext(base_row_id=0, row_count=1, required_fields=set(deps) | {"out"})
    for key, val in zip(deps, (1, 2, 3, 4)):
        ctx.set_field_value(str(key), 0, val)
    assert (
        compute_impl._execute_row_compute_dense(
            field_spec=with_ctx,
            context=ctx,
            batch_row_nth=[0],
            runtime=runtime,
            compute_mode="full",
            wants_field_compute=False,
        )
        is True
    )
    assert ctx.get_field_value("out", 0) == ((1, 2, 3, 4), True)

    without_ctx = DerivedFieldIr(field_id="out2", name="Out2", dependencies=deps, compute_expr="a")
    runtime2 = _make_dense_runtime(field_spec=without_ctx, runtime_bindings=RuntimeBindings(derived_calculators={"out2": _calc}))
    ctx2 = DenseBatchContext(base_row_id=0, row_count=1, required_fields=set(deps) | {"out2"})
    for key, val in zip(deps, (1, 2, 3, 4)):
        ctx2.set_field_value(str(key), 0, val)
    assert (
        compute_impl._execute_row_compute_dense(
            field_spec=without_ctx,
            context=ctx2,
            batch_row_nth=[0],
            runtime=runtime2,
            compute_mode="full",
            wants_field_compute=True,
        )
        is True
    )
    assert ctx2.get_field_value("out2", 0) == ((1, 2, 3, 4), False)


def test_execute_row_compute_dense_expected_error_with_prebuilt_payload_skips_rebuild() -> None:
    def _boom(a: Any, b: Any) -> Any:
        _ = (a, b)
        raise ZeroDivisionError("boom")

    field_spec = DerivedFieldIr(field_id="out", name="Out", dependencies=("a", "b"), compute_expr="a")
    runtime = _make_dense_runtime(field_spec=field_spec, runtime_bindings=RuntimeBindings(derived_calculators={"out": _boom}))

    ctx = DenseBatchContext(base_row_id=0, row_count=1, required_fields={"a", "b", "out"})
    ctx.set_field_value("a", 0, 1)
    ctx.set_field_value("b", 0, 2)
    assert (
        compute_impl._execute_row_compute_dense(
            field_spec=field_spec,
            context=ctx,
            batch_row_nth=[0],
            runtime=runtime,
            compute_mode="full",
            wants_field_compute=True,
        )
        is True
    )
    assert ctx.get_field_value("out", 0) is None


def test_execute_row_compute_dense_unexpected_error_guardrails_enabled_skips_payload_build() -> None:
    def _boom(a: Any) -> Any:
        _ = a
        raise RuntimeError("boom")

    field_spec = DerivedFieldIr(field_id="out", name="Out", dependencies=("a",), compute_expr="a")
    runtime = _make_runtime(
        ExecutionPlan(field_specs={"out": field_spec}),
        None,
        runtime_bindings=RuntimeBindings(derived_calculators={"out": _boom}),
        guardrails=GuardrailsPolicy(enabled=True, compute=GuardrailsComputePolicy(on_error="quiet")),
    )
    runtime.batch_num = 7

    ctx = DenseBatchContext(base_row_id=0, row_count=1, required_fields={"a", "out"})
    ctx.set_field_value("a", 0, 1)
    assert (
        compute_impl._execute_row_compute_dense(
            field_spec=field_spec,
            context=ctx,
            batch_row_nth=[0],
            runtime=runtime,
            compute_mode="quiet",
            wants_field_compute=False,
        )
        is True
    )
    assert ctx.get_field_value("out", 0) is None


def test_execute_row_compute_dense_unexpected_error_with_prebuilt_payload_skips_rebuild() -> None:
    def _boom(a: Any, b: Any) -> Any:
        _ = (a, b)
        raise RuntimeError("boom")

    field_spec = DerivedFieldIr(field_id="out", name="Out", dependencies=("a", "b"), compute_expr="a")
    runtime = _make_dense_runtime(field_spec=field_spec, runtime_bindings=RuntimeBindings(derived_calculators={"out": _boom}))

    ctx = DenseBatchContext(base_row_id=0, row_count=1, required_fields={"a", "b", "out"})
    ctx.set_field_value("a", 0, 1)
    ctx.set_field_value("b", 0, 2)
    assert (
        compute_impl._execute_row_compute_dense(
            field_spec=field_spec,
            context=ctx,
            batch_row_nth=[0],
            runtime=runtime,
            compute_mode="full",
            wants_field_compute=True,
        )
        is True
    )
    assert ctx.get_field_value("out", 0) is None


def _iter_dep_values(deps: Tuple[str, ...]) -> Iterable[Tuple[str, int]]:
    for idx, key in enumerate(deps):
        yield str(key), int(idx + 1)


@pytest.mark.parametrize(
    "deps",
    [
        ("a",),
        ("a", "b"),
        ("a", "b", "c"),
        ("a", "b", "c", "d"),
    ],
)
def test_execute_row_compute_dense_builds_payload_on_expected_error(deps: Tuple[str, ...]) -> None:
    def _boom(*_args: Any, **_kwargs: Any) -> Any:
        raise ZeroDivisionError("boom")

    field_spec = DerivedFieldIr(field_id="out", name="Out", dependencies=deps, compute_expr="a")
    runtime = _make_dense_runtime(field_spec=field_spec, runtime_bindings=RuntimeBindings(derived_calculators={"out": _boom}))
    ctx = DenseBatchContext(base_row_id=0, row_count=1, required_fields=set(deps) | {"out"})
    for key, val in _iter_dep_values(deps):
        ctx.set_field_value(key, 0, val)

    assert (
        compute_impl._execute_row_compute_dense(
            field_spec=field_spec,
            context=ctx,
            batch_row_nth=[0],
            runtime=runtime,
            compute_mode="full",
            wants_field_compute=False,
        )
        is True
    )
    assert ctx.get_field_value("out", 0) is None


@pytest.mark.parametrize(
    "deps",
    [
        ("a",),
        ("a", "b"),
        ("a", "b", "c"),
        ("a", "b", "c", "d"),
    ],
)
def test_execute_row_compute_dense_builds_payload_on_unexpected_error(deps: Tuple[str, ...]) -> None:
    def _boom(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("boom")

    field_spec = DerivedFieldIr(field_id="out", name="Out", dependencies=deps, compute_expr="a")
    runtime = _make_dense_runtime(field_spec=field_spec, runtime_bindings=RuntimeBindings(derived_calculators={"out": _boom}))
    ctx = DenseBatchContext(base_row_id=0, row_count=1, required_fields=set(deps) | {"out"})
    for key, val in _iter_dep_values(deps):
        ctx.set_field_value(key, 0, val)

    assert (
        compute_impl._execute_row_compute_dense(
            field_spec=field_spec,
            context=ctx,
            batch_row_nth=[0],
            runtime=runtime,
            compute_mode="full",
            wants_field_compute=False,
        )
        is True
    )
    assert ctx.get_field_value("out", 0) is None
