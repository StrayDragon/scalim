"""`write-precompute` 物化原语的分支覆盖.

对应实现: `scalim.execution.write_precompute`(行布局 / 记忆化 / 探针 / 错误降级 / 列依赖读取器).
"""

from typing import Any, Dict, List, Optional, Sequence

import pytest

import scalim.execution.write_precompute as wp
from scalim.execution.context import BatchContext, DenseBatchContext
from scalim.execution.guardrails import GuardrailsPolicy
from scalim.execution.runtime_bindings import RuntimeBindings
from scalim.execution.write_precompute import LateColumnMaterializer, LateFieldMaterializer
from scalim.hooks import BaseHook, HookManager
from scalim.planning.plan import ExecutionPlan
from scalim.spec.ir import CallBySpecIr, CallByValueIr, DerivedFieldIr, FieldIr, RuntimeHandleIdIr

from tests.fixtures.executor_operator_fixtures import _CaptureHook, _make_main_source, _make_runtime


class _ErrorOnlyHook(BaseHook):
    """只订阅错误事件: 保持 `wants(FIELD_COMPUTE)` 为假,以命中逐行/整列直呼快路径."""

    def __init__(self) -> None:
        self.errors: List[Any] = []

    def on_error(self, event) -> None:  # type: ignore[override]
        self.errors.append(event)


def _call_by(field_id: str, dep_fields: Sequence[str]) -> CallBySpecIr:
    return CallBySpecIr(
        reference=RuntimeHandleIdIr(handle_id="derived.{}".format(field_id)),
        args=tuple(CallByValueIr(kind="field", value=dep) for dep in dep_fields),
        field_names=tuple(dep_fields),
    )


def _derived(field_id: str, deps: Sequence[str], *, use_call_by: bool = True) -> DerivedFieldIr:
    if use_call_by:
        return DerivedFieldIr(field_id=field_id, name=field_id, dependencies=tuple(deps), call_by=_call_by(field_id, deps))
    return DerivedFieldIr(field_id=field_id, name=field_id, dependencies=tuple(deps), compute_expr=" + ".join(deps))


def _materializer(
    field_specs: Dict[str, Any],
    calculators: Dict[str, Any],
    late_fields: Sequence[str],
    *,
    value_transforms: Optional[Dict[str, Any]] = None,
    guardrails: Optional[GuardrailsPolicy] = None,
    hook_manager: Optional[HookManager] = None,
) -> LateFieldMaterializer:
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
    runtime.batch_num = 2
    return LateFieldMaterializer(runtime=runtime, late_fields=list(late_fields))


def test_non_derived_late_field_has_no_plan() -> None:
    main = _make_main_source()
    materializer = _materializer(
        {"raw": FieldIr(field_id="raw", name="raw", source_id=main.source_id)},
        {},
        ["raw"],
    )

    assert materializer.plan_for("raw") is None


def test_materialize_column_falls_back_to_context_for_unplanned_field() -> None:
    main = _make_main_source()
    materializer = _materializer(
        {"raw": FieldIr(field_id="raw", name="raw", source_id=main.source_id)},
        {},
        ["raw"],
    )
    column = LateColumnMaterializer(materializer=materializer, field_dependencies={})
    context = BatchContext()
    context.set_field_value("raw", 0, 11)
    context.set_field_value("raw", 1, 22)

    assert column.materialize_column(context, "raw", [0, 1]) == [11, 22]


def test_row_layout_handles_duplicate_target_positions() -> None:
    materializer = _materializer(
        {"late": _derived("late", ("amount",))},
        {"late": (lambda amount: int(amount) * 2)},
        ["late"],
    )
    context = BatchContext()
    context.set_field_value("amount", 0, 3)

    layout = materializer.build_row_layout(["amount", "late", "amount", "late"])

    assert layout.duplicate_positions == ((1, 3),)
    assert layout.eager_positions == ((0, "amount"), (2, "amount"))
    assert materializer.fill_row_values(layout, context, 0) == [3, 6, 3, 6]


def test_row_layout_skips_late_fields_outside_target_fields() -> None:
    materializer = _materializer(
        {"late": _derived("late", ("amount",))},
        {"late": (lambda amount: int(amount) * 2)},
        ["late"],
    )

    layout = materializer.build_row_layout(["amount"])

    assert layout.slots == ()


def test_direct_row_call_degrades_unexpected_error_to_none() -> None:
    def _boom(_amount: Any) -> Any:
        msg = "boom"
        raise RuntimeError(msg)

    hook = _ErrorOnlyHook()
    hub = HookManager()
    hub.register(hook)
    materializer = _materializer(
        {"late": _derived("late", ("amount",))},
        {"late": _boom},
        ["late"],
        hook_manager=hub,
    )
    context = BatchContext()
    context.set_field_value("amount", 0, 3)

    layout = materializer.build_row_layout(["amount", "late"])
    assert layout.direct_calls is True

    assert materializer.fill_row_values(layout, context, 0) == [3, None]
    assert len(hook.errors) == 1
    assert hook.errors[0].payload.context["unexpected"] is True
    # `guardrails` 未启用: 错误负载按依赖名重建.
    assert hook.errors[0].payload.context["dependencies"] == {"amount": 3}


def test_call_by_memoization_reuses_cached_result(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCALIM_EXP_CALL_BY_MEMOIZE_MAX_ENTRIES", "64")
    calls = {"n": 0}

    def _calc(amount: Any) -> Any:
        calls["n"] += 1
        if isinstance(amount, list):
            return len(amount)
        return int(amount) * 2

    materializer = _materializer({"late": _derived("late", ("amount",))}, {"late": _calc}, ["late"])
    plan = materializer.plan_for("late")
    assert plan is not None
    assert plan.memo_cache is not None

    first = materializer.compute_value(plan, 0, (3,), wants_field_compute=False, compute_mode="full")
    second = materializer.compute_value(plan, 1, (3,), wants_field_compute=False, compute_mode="full")
    unhashable_first = materializer.compute_value(plan, 2, ([7, 8],), wants_field_compute=False, compute_mode="full")
    unhashable_second = materializer.compute_value(plan, 3, ([7, 8],), wants_field_compute=False, compute_mode="full")

    assert (first, second) == (6, 6)
    assert (unhashable_first, unhashable_second) == (2, 2)
    # 第二次命中缓存不再调用计算器;不可哈希依赖不入缓存,每次都要重算.
    assert calls["n"] == 3


def test_dep_cardinality_probe_records_late_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCALIM_PROBE_CALL_BY_DEP_CARDINALITY", "128")
    materializer = _materializer(
        {"late": _derived("late", ("amount",))},
        {"late": (lambda amount: int(amount) * 2)},
        ["late"],
        value_transforms={"late": (lambda value: int(value) + 1)},
    )
    plan = materializer.plan_for("late")
    assert plan is not None
    assert plan.dep_cardinality is not None

    assert materializer.compute_value(plan, 0, (3,), wants_field_compute=False, compute_mode="full") == 7
    assert plan.dep_cardinality.stats_by_field["late"].call_count == 1


def test_compute_value_degrades_expected_and_unexpected_errors() -> None:
    def _boom(amount: Any) -> Any:
        if int(amount) < 0:
            msg = "unexpected"
            raise RuntimeError(msg)
        msg = "expected"
        raise ValueError(msg)

    hook = _CaptureHook()
    hub = HookManager()
    hub.register(hook)
    materializer = _materializer(
        {"late": _derived("late", ("amount",))},
        {"late": _boom},
        ["late"],
        hook_manager=hub,
    )
    plan = materializer.plan_for("late")
    assert plan is not None

    assert materializer.compute_value(plan, 0, (3,), wants_field_compute=True, compute_mode="full") is None
    assert materializer.compute_value(plan, 1, (-1,), wants_field_compute=True, compute_mode="full") is None

    assert len(hook.errors) == 2
    assert hook.errors[0].payload.context["dependencies"] == {"amount": 3}
    assert hook.errors[1].payload.context["unexpected"] is True


def test_dense_dep_reader_rejects_out_of_range_and_non_int_rows() -> None:
    context = DenseBatchContext(base_row_id=0, row_count=2, required_fields={"amount"})
    context.set_field_value("amount", 0, 5)
    storage = context.dense_get_storage_for_read("amount")
    assert storage is not None

    read = wp._make_dense_reader(storage, 0, 2)

    assert read(0) == 5
    # 未写入的行 / 越界行 / 非 `int` 行都读为 `None`.
    assert read(1) is None
    assert read(9) is None
    assert read("x") is None


def test_generic_dep_reader_used_for_non_dense_context() -> None:
    materializer = _materializer(
        {"late": _derived("late", ("amount",))},
        {"late": (lambda amount: int(amount or 0) * 2)},
        ["late"],
    )
    column = LateColumnMaterializer(materializer=materializer, field_dependencies={"late": ("amount",)})
    context = BatchContext()
    context.set_field_value("amount", 0, 4)
    context.set_field_value("amount", 1, 5)

    assert column.materialize_column(context, "late", [0, 1]) == [8, 10]


def test_dense_context_falls_back_to_generic_reader_for_missing_dep_storage() -> None:
    materializer = _materializer(
        {"late": _derived("late", ("missing",))},
        {"late": (lambda missing: "v={}".format(missing))},
        ["late"],
    )
    column = LateColumnMaterializer(materializer=materializer, field_dependencies={"late": ("missing",)})
    # 稠密上下文里 `missing` 从未写入 -> 没有稠密存储,回落到通用取值闭包.
    context = DenseBatchContext(base_row_id=0, row_count=1, required_fields={"amount"})
    context.set_field_value("amount", 0, 1)

    assert column.materialize_column(context, "late", [0]) == ["v=None"]


def test_column_direct_call_degrades_unexpected_error_to_none() -> None:
    def _boom(_amount: Any) -> Any:
        msg = "boom"
        raise RuntimeError(msg)

    hook = _ErrorOnlyHook()
    hub = HookManager()
    hub.register(hook)
    materializer = _materializer(
        {"late": _derived("late", ("amount",))},
        {"late": _boom},
        ["late"],
        hook_manager=hub,
    )
    column = LateColumnMaterializer(materializer=materializer, field_dependencies={"late": ("amount",)})
    context = BatchContext()
    context.set_field_value("amount", 0, 4)

    assert column.materialize_column(context, "late", [0]) == [None]
    assert len(hook.errors) == 1
    assert hook.errors[0].payload.context["unexpected"] is True


def test_row_values_reuse_late_column_dependency_values() -> None:
    materializer = _materializer(
        {
            "base": _derived("base", ("amount",)),
            "chained": _derived("chained", ("base",)),
        },
        {"base": (lambda amount: int(amount) + 1), "chained": (lambda base: int(base) * 10)},
        ["base", "chained"],
    )
    column = LateColumnMaterializer(
        materializer=materializer,
        field_dependencies={"base": ("amount",), "chained": ("base",)},
    )
    context = DenseBatchContext(base_row_id=0, row_count=2, required_fields={"amount"})
    context.set_field_value("amount", 0, 1)
    context.set_field_value("amount", 1, 2)

    base_values: List[Any] = column.materialize_column(context, "base", [0, 1])
    chained_values: List[Any] = column.materialize_column(context, "chained", [0, 1])
    column.release_after_write("chained")

    assert base_values == [2, 3]
    assert chained_values == [20, 30]
