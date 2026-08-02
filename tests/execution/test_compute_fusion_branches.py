"""`c20` 行内融合的分支覆盖: 安全外壳跳过 / 稠密快路径回退 / 通用回退路径.

对应实现: `scalim.execution.executor.operators.compute.fusion`.
"""

from typing import Any, Dict, List, Optional, Sequence, Tuple

import pytest

import scalim.execution.executor.operators.compute.fusion as fusion_impl
from scalim.execution.context import BatchContext, DenseBatchContext
from scalim.execution.executor.operators.compute.fusion import (
    active_fusion_members,
    execute_fused_compute_group,
    fusion_disabled_reason,
)
from scalim.execution.guardrails import GuardrailsPolicy
from scalim.execution.runtime_bindings import RuntimeBindings
from scalim.planning.builder_helpers.fusion_groups import ComputeFusionGroup
from scalim.planning.plan import ExecutionPlan
from scalim.spec.ir import CallBySpecIr, CallByValueIr, DerivedFieldIr, FieldIr, RuntimeHandleIdIr

from tests.fixtures.executor_operator_fixtures import _CaptureHook, _make_main_source, _make_runtime
from scalim.hooks import HookManager


def _call_by(field_id: str, dep_fields: Sequence[str]) -> CallBySpecIr:
    return CallBySpecIr(
        reference=RuntimeHandleIdIr(handle_id="derived.{}".format(field_id)),
        args=tuple(CallByValueIr(kind="field", value=dep) for dep in dep_fields),
        field_names=tuple(dep_fields),
    )


def _derived(field_id: str, deps: Sequence[str]) -> DerivedFieldIr:
    return DerivedFieldIr(
        field_id=field_id,
        name=field_id,
        dependencies=tuple(deps),
        call_by=_call_by(field_id, deps),
    )


def _group(field_keys: Sequence[str], deps: Sequence[str]) -> ComputeFusionGroup:
    return ComputeFusionGroup(segment="pre_ref", field_keys=tuple(field_keys), deps=tuple(deps))


def _runtime(
    field_specs: Dict[str, Any],
    calculators: Dict[str, Any],
    *,
    value_transforms: Optional[Dict[str, Any]] = None,
    guardrails: Optional[GuardrailsPolicy] = None,
    hook_manager: Optional[HookManager] = None,
):  # type: ignore[no-untyped-def]
    plan = ExecutionPlan(field_specs=dict(field_specs))
    bindings = RuntimeBindings(
        derived_calculators=dict(calculators),
        value_transforms=dict(value_transforms or {}),
    )
    runtime = _make_runtime(
        plan,
        None,
        hook_manager=hook_manager,
        runtime_bindings=bindings,
        guardrails=guardrails,
    )
    runtime.batch_num = 3
    return runtime


def _two_field_runtime(
    deps: Sequence[str],
    calculator: Any,
    **kwargs: Any,
):  # type: ignore[no-untyped-def]
    specs = {key: _derived(key, deps) for key in ("d0", "d1")}
    return _runtime(specs, {"d0": calculator, "d1": calculator}, **kwargs)


def _plans(calculator: Any, value_transform: Any = None) -> List[Tuple[str, Any, Any]]:
    return [("d0", calculator, value_transform), ("d1", calculator, value_transform)]


def test_active_fusion_members_accepts_non_set_late_collection() -> None:
    group = _group(("d0", "d1"), ("a",))

    assert active_fusion_members(group, ["d0"]) == ("d1",)
    assert active_fusion_members(group, ()) == ("d0", "d1")


def test_fusion_disabled_reason_skips_members_without_memoizable_call_by(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCALIM_EXP_CALL_BY_MEMOIZE_MAX_ENTRIES", "64")
    monkeypatch.setenv("SCALIM_EXP_CALL_BY_MEMOIZE_DENY", "denied")
    main = _make_main_source()
    specs: Dict[str, Any] = {
        # 非派生字段: 记忆化判定直接跳过.
        "raw": FieldIr(field_id="raw", name="raw", source=main),
        # `compute_expr`(无 `call_by`)与含 `$ctx` 的 `call_by` 都不参与记忆化.
        "expr": DerivedFieldIr(field_id="expr", name="expr", dependencies=("raw",), compute_expr="raw + 1"),
        "ctx": DerivedFieldIr(
            field_id="ctx",
            name="ctx",
            dependencies=("raw",),
            call_by=_call_by("ctx", ["raw"]),
            call_ctx_key="$ctx",
        ),
        # 可记忆化形态,但被 `deny` 过滤命中 -> 不构成禁用原因.
        "denied": _derived("denied", ("raw",)),
    }
    runtime = _runtime(
        specs,
        {"expr": (lambda a: a), "ctx": (lambda a, **_kw: a), "denied": (lambda a: a)},
    )
    assert runtime.call_by_memoization is not None

    group = _group(("expr", "ctx", "denied"), ("raw",))
    assert fusion_disabled_reason(runtime, group, ("raw", "expr", "ctx", "denied")) is None


def test_execute_fused_dense_returns_false_when_output_is_pruned() -> None:
    runtime = _two_field_runtime(("a",), lambda a: int(a or 0) + 1)
    ctx = DenseBatchContext(base_row_id=0, row_count=1, required_fields={"a", "d0"})
    ctx.set_field_value("a", 0, 1)

    ok = fusion_impl._execute_fused_dense(
        group=_group(("d0", "d1"), ("a",)),
        field_plans=_plans(lambda a: int(a or 0) + 1),
        context=ctx,
        batch_row_nth=[0],
        runtime=runtime,
    )

    assert ok is False


def test_execute_fused_dense_skips_disabled_rows() -> None:
    calculator = lambda a: int(a or 0) + 1  # noqa: E731
    runtime = _two_field_runtime(("a",), calculator)
    ctx = DenseBatchContext(base_row_id=0, row_count=2, required_fields={"a", "d0", "d1"})
    ctx.set_field_value("a", 0, 1)
    ctx.set_field_value("a", 1, 5)
    ctx.disable_row(0)

    ok = fusion_impl._execute_fused_dense(
        group=_group(("d0", "d1"), ("a",)),
        field_plans=_plans(calculator),
        context=ctx,
        batch_row_nth=[0, 1],
        runtime=runtime,
    )

    assert ok is True
    assert ctx.get_field_value("d0", 0) is None
    assert ctx.get_field_value("d1", 1) == 6


def test_execute_fused_dense_returns_false_for_non_int_row_id() -> None:
    calculator = lambda a: a  # noqa: E731
    runtime = _two_field_runtime(("a",), calculator)
    ctx = DenseBatchContext(base_row_id=0, row_count=1, required_fields={"a", "d0", "d1"})

    ok = fusion_impl._execute_fused_dense(
        group=_group(("d0", "d1"), ("a",)),
        field_plans=_plans(calculator),
        context=ctx,
        batch_row_nth=["x"],
        runtime=runtime,
    )

    assert ok is False


def test_execute_fused_dense_returns_false_for_out_of_range_row_id() -> None:
    calculator = lambda a: a  # noqa: E731
    runtime = _two_field_runtime(("a",), calculator)
    ctx = DenseBatchContext(base_row_id=0, row_count=1, required_fields={"a", "d0", "d1"})

    ok = fusion_impl._execute_fused_dense(
        group=_group(("d0", "d1"), ("a",)),
        field_plans=_plans(calculator),
        context=ctx,
        batch_row_nth=[5],
        runtime=runtime,
    )

    assert ok is False


def test_execute_fused_dense_supports_three_deps_with_missing_storage() -> None:
    deps = ("a", "b", "c")
    calculator = lambda a, b, c: (a, b, c)  # noqa: E731
    runtime = _two_field_runtime(deps, calculator)
    # 只写入 `a`/`b`: `c` 没有稠密存储(读为 `None`),`b` 存在但该行缺值.
    ctx = DenseBatchContext(base_row_id=0, row_count=2, required_fields={"a", "b", "d0", "d1"})
    ctx.set_field_value("a", 0, 1)
    ctx.set_field_value("b", 1, 2)

    ok = fusion_impl._execute_fused_dense(
        group=_group(("d0", "d1"), deps),
        field_plans=_plans(calculator),
        context=ctx,
        batch_row_nth=[0],
        runtime=runtime,
    )

    assert ok is True
    assert ctx.get_field_value("d0", 0) == (1, None, None)


def test_execute_fused_dense_applies_value_transform() -> None:
    calculator = lambda a: int(a or 0) + 1  # noqa: E731
    runtime = _two_field_runtime(("a",), calculator)
    ctx = DenseBatchContext(base_row_id=0, row_count=1, required_fields={"a", "d0", "d1"})
    ctx.set_field_value("a", 0, 1)

    ok = fusion_impl._execute_fused_dense(
        group=_group(("d0", "d1"), ("a",)),
        field_plans=_plans(calculator, value_transform=lambda value: int(value) * 10),
        context=ctx,
        batch_row_nth=[0],
        runtime=runtime,
    )

    assert ok is True
    assert ctx.get_field_value("d0", 0) == 20
    assert ctx.get_field_value("d1", 0) == 20


def test_execute_fused_dense_overwrite_keeps_present_count_stable() -> None:
    calculator = lambda a: int(a or 0) + 1  # noqa: E731
    runtime = _two_field_runtime(("a",), calculator)
    ctx = DenseBatchContext(base_row_id=0, row_count=1, required_fields={"a", "d0", "d1"})
    ctx.set_field_value("a", 0, 1)
    ctx.set_field_value("d0", 0, 999)

    ok = fusion_impl._execute_fused_dense(
        group=_group(("d0", "d1"), ("a",)),
        field_plans=_plans(calculator),
        context=ctx,
        batch_row_nth=[0],
        runtime=runtime,
    )

    assert ok is True
    assert ctx.get_field_value("d0", 0) == 2
    storage = ctx.dense_get_storage_for_read("d0")
    assert storage is not None
    assert storage.present_count == 1


def test_execute_fused_dense_reports_expected_error_with_dependency_payload() -> None:
    def _boom(a: Any) -> Any:
        _ = a
        msg = "boom"
        raise ValueError(msg)

    hook = _CaptureHook()
    hub = HookManager()
    hub.register(hook)
    runtime = _two_field_runtime(("a",), _boom, hook_manager=hub)
    ctx = DenseBatchContext(base_row_id=0, row_count=1, required_fields={"a", "d0", "d1"})
    ctx.set_field_value("a", 0, 1)

    ok = fusion_impl._execute_fused_dense(
        group=_group(("d0", "d1"), ("a",)),
        field_plans=_plans(_boom),
        context=ctx,
        batch_row_nth=[0],
        runtime=runtime,
    )

    assert ok is True
    assert ctx.get_field_value("d0", 0) is None
    # 同一行内两个字段都失败: 依赖负载只构建一次并复用.
    assert len(hook.errors) == 2
    assert hook.errors[0].payload.context["dependencies"] == {"a": 1}


def test_execute_fused_dense_reports_unexpected_error() -> None:
    def _boom(a: Any) -> Any:
        _ = a
        msg = "boom"
        raise RuntimeError(msg)

    hook = _CaptureHook()
    hub = HookManager()
    hub.register(hook)
    runtime = _two_field_runtime(("a",), _boom, hook_manager=hub)
    ctx = DenseBatchContext(base_row_id=0, row_count=1, required_fields={"a", "d0", "d1"})
    ctx.set_field_value("a", 0, 1)

    ok = fusion_impl._execute_fused_dense(
        group=_group(("d0", "d1"), ("a",)),
        field_plans=_plans(_boom),
        context=ctx,
        batch_row_nth=[0],
        runtime=runtime,
    )

    assert ok is True
    assert ctx.get_field_value("d1", 0) is None
    assert len(hook.errors) == 2
    assert hook.errors[0].payload.context["unexpected"] is True


def test_execute_fused_compute_group_bails_out_on_non_derived_member() -> None:
    main = _make_main_source()
    specs: Dict[str, Any] = {
        "raw": FieldIr(field_id="raw", name="raw", source=main),
        "d0": _derived("d0", ("a",)),
    }
    runtime = _runtime(specs, {"d0": (lambda a: a)})
    ctx = BatchContext()

    execute_fused_compute_group(
        group=_group(("raw", "d0"), ("a",)),
        field_keys=("raw", "d0"),
        context=ctx,
        batch_row_nth=[0],
        runtime=runtime,
    )

    assert ctx.get_field_value("d0", 0) is None


def test_execute_fused_compute_group_generic_context_applies_transform() -> None:
    calculator = lambda a, b: int(a or 0) + int(b or 0)  # noqa: E731
    runtime = _two_field_runtime(
        ("a", "b"),
        calculator,
        value_transforms={"d0": (lambda value: int(value) * 10), "d1": (lambda value: int(value) * 100)},
    )
    ctx = BatchContext()
    ctx.set_field_value("a", "r0", 1)
    ctx.set_field_value("b", "r0", 2)

    execute_fused_compute_group(
        group=_group(("d0", "d1"), ("a", "b")),
        field_keys=("d0", "d1"),
        context=ctx,
        batch_row_nth=["r0"],
        runtime=runtime,
    )

    assert ctx.get_field_value("d0", "r0") == 30
    assert ctx.get_field_value("d1", "r0") == 300


def test_execute_fused_compute_group_generic_context_reports_expected_error() -> None:
    def _boom(a: Any) -> Any:
        _ = a
        msg = "boom"
        raise ZeroDivisionError(msg)

    hook = _CaptureHook()
    hub = HookManager()
    hub.register(hook)
    runtime = _two_field_runtime(("a",), _boom, hook_manager=hub)
    ctx = BatchContext()
    ctx.set_field_value("a", "r0", 7)

    execute_fused_compute_group(
        group=_group(("d0", "d1"), ("a",)),
        field_keys=("d0", "d1"),
        context=ctx,
        batch_row_nth=["r0"],
        runtime=runtime,
    )

    assert ctx.get_field_value("d0", "r0") is None
    assert len(hook.errors) == 2
    assert hook.errors[0].payload.context["dependencies"] == {"a": 7}


def test_execute_fused_compute_group_generic_context_reports_unexpected_error() -> None:
    def _boom(a: Any) -> Any:
        _ = a
        msg = "boom"
        raise RuntimeError(msg)

    hook = _CaptureHook()
    hub = HookManager()
    hub.register(hook)
    runtime = _two_field_runtime(("a",), _boom, hook_manager=hub)
    ctx = BatchContext()
    ctx.set_field_value("a", "r0", 7)

    execute_fused_compute_group(
        group=_group(("d0", "d1"), ("a",)),
        field_keys=("d0", "d1"),
        context=ctx,
        batch_row_nth=["r0"],
        runtime=runtime,
    )

    assert ctx.get_field_value("d1", "r0") is None
    assert len(hook.errors) == 2
    assert hook.errors[0].payload.context["unexpected"] is True
