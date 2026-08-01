"""`write-precompute`: 把“仅用于最终写出”的派生字段延迟到写出前物化.

设计要点:
- 判定在规划期完成(`ExecutionPlan.late_fields`),此处只负责“依赖 -> 算法 -> 结果值”的物化原语;
- 行路径: 逐行按 `late` 子图拓扑计算,复用 `row-local` 依赖缓存,默认不写回 `BatchContext`;
- 列路径: 在写出该列前物化整列,链式 `late` 依赖列暂留到消费方写完后释放;
- 求值次数与早算路径一致,失败走既有 `compute` `guardrails`(`quiet` 降级 / `fast_fail` 抛错).
"""

# region imports

import logging
from typing import Any, Callable, Dict, FrozenSet, Hashable, List, Optional, Sequence, Tuple

from ..events import EventType
from ..spec.ir import DerivedFieldIr
from ..typedefs import FieldValue
from .compute_phase import COMPUTE_PHASE_META_KEY, COMPUTE_PHASE_WRITE_PRECOMPUTE
from .context import BatchContext, DenseBatchContext
from .executor.operators.compute.errors import handle_compute_error
from .executor.operators.compute.payloads import build_field_compute_dependencies_payload
from .executor.runtime.runtime import ExecutionRuntime

# endregion

_EXPECTED_COMPUTE_ERRORS = (
    TypeError,
    ValueError,
    ZeroDivisionError,
    ArithmeticError,
)


class _DiscardValueSink:
    """`handle_compute_error` 的上下文替身: `late` 结果默认不写回 `BatchContext`."""

    def set_field_value(self, _field_key: str, _row_id: Hashable, _value: FieldValue) -> None:
        return


_DISCARD_CONTEXT = _DiscardValueSink()


class _LateFieldPlan:
    """单个 `late` 字段的预解析执行计划(每次 `run` 只解析一次)."""

    __slots__: Tuple[str, ...] = ("calculator", "dep_cardinality", "deps", "field_key", "memo_cache", "value_transform")

    field_key: str
    deps: Tuple[str, ...]
    calculator: Any
    value_transform: Any
    memo_cache: Any
    dep_cardinality: Any

    def __init__(
        self,
        *,
        field_key: str,
        deps: Tuple[str, ...],
        calculator: Any,
        value_transform: Any,
        memo_cache: Any,
        dep_cardinality: Any,
    ) -> None:
        self.field_key = field_key
        self.deps = deps
        self.calculator = calculator
        self.value_transform = value_transform
        self.memo_cache = memo_cache
        self.dep_cardinality = dep_cardinality


class _LateRowSlot:
    """`late` 字段在写出行数组中的落位与依赖读取方式(每批解析一次)."""

    __slots__: Tuple[str, ...] = ("dep_slots", "plan", "position")

    plan: _LateFieldPlan
    position: int
    dep_slots: Tuple[Tuple[int, str], ...]

    def __init__(self, *, plan: _LateFieldPlan, position: int, dep_slots: Tuple[Tuple[int, str], ...]) -> None:
        self.plan = plan
        self.position = position
        self.dep_slots = dep_slots


class LateRowWriteLayout:
    """行写出布局: 先按上下文填非 `late` 位,再按拓扑序就地算出 `late` 位."""

    __slots__: Tuple[str, ...] = (
        "compute_mode",
        "direct_calls",
        "duplicate_positions",
        "eager_positions",
        "slots",
        "wants_field_compute",
        "width",
    )

    width: int
    eager_positions: Tuple[Tuple[int, str], ...]
    slots: Tuple[_LateRowSlot, ...]
    duplicate_positions: Tuple[Tuple[int, int], ...]
    wants_field_compute: bool
    compute_mode: str
    direct_calls: bool

    def __init__(
        self,
        *,
        width: int,
        eager_positions: Tuple[Tuple[int, str], ...],
        slots: Tuple[_LateRowSlot, ...],
        duplicate_positions: Tuple[Tuple[int, int], ...],
        wants_field_compute: bool,
        compute_mode: str,
    ) -> None:
        self.width = width
        self.eager_positions = eager_positions
        self.slots = slots
        self.duplicate_positions = duplicate_positions
        self.wants_field_compute = wants_field_compute
        self.compute_mode = compute_mode
        # 无事件订阅 / 无记忆化 / 无值转换 / 无探针时,逐行可直呼计算器(与早算稠密快路径对齐).
        self.direct_calls = not wants_field_compute and all(
            slot.plan.memo_cache is None and slot.plan.value_transform is None and slot.plan.dep_cardinality is None for slot in slots
        )


def _invoke_calculator(plan: "_LateFieldPlan", dep_args: Tuple[Any, ...]) -> FieldValue:
    """调用派生计算器(与早算路径共享 `call_by` 记忆化语义)."""
    memo_cache = plan.memo_cache
    if memo_cache is None:
        return plan.calculator(*dep_args)

    hit, cached, hashable = memo_cache.try_get(dep_args)
    if hit:
        return cached
    result = plan.calculator(*dep_args)
    if hashable:
        memo_cache.store_miss(key=dep_args, value=result)
    return result


class LateFieldMaterializer:
    """`late` 派生字段的写出前物化器(行路径与列路径共用求值原语)."""

    _runtime: ExecutionRuntime
    _late_fields: Tuple[str, ...]
    _plans: Optional[List[_LateFieldPlan]]
    _plan_by_field: Dict[str, _LateFieldPlan]

    def __init__(self, *, runtime: ExecutionRuntime, late_fields: Sequence[str]) -> None:
        self._runtime = runtime
        self._late_fields = tuple(late_fields)
        self._plans = None
        self._plan_by_field = {}

    @property
    def late_fields(self) -> Tuple[str, ...]:
        return self._late_fields

    def _ensure_plans(self) -> List[_LateFieldPlan]:
        plans = self._plans
        if plans is not None:
            return plans

        runtime = self._runtime
        bindings = runtime.runtime_bindings
        memoization = runtime.call_by_memoization
        built: List[_LateFieldPlan] = []
        for field_key in self._late_fields:
            field_spec = runtime.field_specs.get(field_key)
            if not isinstance(field_spec, DerivedFieldIr):
                continue
            memo_cache = None
            if memoization is not None and field_spec.call_by is not None and memoization.is_field_allowed(field_key):
                memo_cache = memoization.get_or_create_field_cache(field_key)
            plan = _LateFieldPlan(
                field_key=field_key,
                deps=tuple(field_spec.dependencies or ()),
                calculator=bindings.require_derived_calculator(field_key),
                value_transform=bindings.get_value_transform(field_key),
                memo_cache=memo_cache,
                dep_cardinality=runtime.call_by_dep_cardinality if field_spec.call_by is not None else None,
            )
            built.append(plan)
            self._plan_by_field[field_key] = plan

        self._plans = built
        return built

    def plan_for(self, field_key: str) -> Optional[_LateFieldPlan]:
        _ = self._ensure_plans()
        return self._plan_by_field.get(field_key)

    def build_row_layout(self, target_fields: Sequence[str]) -> LateRowWriteLayout:
        """预解析写出行布局: 把“字段名 -> 落位/依赖来源”的解析提到逐行循环之外."""
        plans = self._ensure_plans()
        late_set = set(self._plan_by_field)

        position_of: Dict[str, int] = {}
        eager_positions: List[Tuple[int, str]] = []
        duplicate_positions: List[Tuple[int, int]] = []
        for idx, field_key in enumerate(target_fields):
            is_late = field_key in late_set
            if field_key in position_of:
                if is_late:
                    duplicate_positions.append((position_of[field_key], idx))
                else:
                    eager_positions.append((idx, field_key))
                continue
            position_of[field_key] = idx
            if not is_late:
                eager_positions.append((idx, field_key))

        slots: List[_LateRowSlot] = []
        for plan in plans:
            position = position_of.get(plan.field_key)
            if position is None:
                continue
            # 依赖若是写出目标(已在 `values` 中就位),直接按下标取;否则回落到上下文取值.
            dep_slots = tuple((position_of.get(dep, -1), dep) for dep in plan.deps)
            slots.append(_LateRowSlot(plan=plan, position=position, dep_slots=dep_slots))

        return LateRowWriteLayout(
            width=len(target_fields),
            eager_positions=tuple(eager_positions),
            slots=tuple(slots),
            duplicate_positions=tuple(duplicate_positions),
            wants_field_compute=self.wants_field_compute(),
            compute_mode=self.compute_mode(),
        )

    def fill_row_values(self, layout: LateRowWriteLayout, context: BatchContext, row_id: Hashable) -> List[FieldValue]:
        """按布局产出整行写出值(`late` 位就地物化,不写回 `BatchContext`)."""
        get_field_value = context.get_field_value
        values: List[FieldValue] = [None] * layout.width
        for position, field_key in layout.eager_positions:
            values[position] = get_field_value(field_key, row_id)

        compute_mode = layout.compute_mode
        direct_calls = layout.direct_calls
        for slot in layout.slots:
            dep_args = tuple(values[pos] if pos >= 0 else get_field_value(dep_key, row_id) for pos, dep_key in slot.dep_slots)
            if direct_calls:
                try:
                    values[slot.position] = slot.plan.calculator(*dep_args)
                except _EXPECTED_COMPUTE_ERRORS as exc:  # type: ignore[misc]
                    values[slot.position] = self.handle_direct_call_error(slot.plan, row_id, dep_args, exc, compute_mode, unexpected=False)
                except Exception as exc:
                    logging.exception(  # noqa: LOG015
                        "字段计算发生未预期的异常(write-precompute): 字段=%s, 行标识=%s",
                        slot.plan.field_key,
                        row_id,
                    )
                    values[slot.position] = self.handle_direct_call_error(slot.plan, row_id, dep_args, exc, compute_mode, unexpected=True)
            else:
                values[slot.position] = self.compute_value(
                    slot.plan,
                    row_id,
                    dep_args,
                    wants_field_compute=layout.wants_field_compute,
                    compute_mode=compute_mode,
                )

        for source, target in layout.duplicate_positions:
            values[target] = values[source]
        return values

    def handle_direct_call_error(
        self,
        plan: _LateFieldPlan,
        row_id: Hashable,
        dep_args: Tuple[Any, ...],
        exc: Exception,
        compute_mode: str,
        *,
        unexpected: bool,
    ) -> FieldValue:
        """直呼快路径的错误处理(与 `compute_value` 的 `guardrails` 语义一致)."""
        self._handle_error(
            plan,
            row_id,
            dep_args,
            dep_values_payload={},
            exc=exc,
            compute_mode=compute_mode,
            unexpected=unexpected,
        )
        return None

    def wants_field_compute(self) -> bool:
        return self._runtime.instrumentation.wants(EventType.FIELD_COMPUTE)

    def compute_mode(self) -> str:
        return self._runtime.guardrails.effective_compute_mode()

    def compute_value(
        self,
        plan: _LateFieldPlan,
        row_id: Hashable,
        dep_args: Tuple[Any, ...],
        *,
        wants_field_compute: bool,
        compute_mode: str,
    ) -> FieldValue:
        """共享求值原语: 依赖值元组 -> 结果值(含 `guardrails` 与事件)."""
        runtime = self._runtime
        deps = plan.deps
        dep_cardinality = plan.dep_cardinality
        if dep_cardinality is not None:
            dep_cardinality.record(field_key=plan.field_key, dep_args=dep_args)

        dep_values_payload: Dict[str, Any] = {}
        if wants_field_compute:
            dep_values_payload = build_field_compute_dependencies_payload(deps, dep_args)

        try:
            result = _invoke_calculator(plan, dep_args)

            if plan.value_transform is not None:
                result = plan.value_transform(result)

            if wants_field_compute:
                runtime.instrumentation.emit_field_compute(
                    plan.field_key,
                    row_id,
                    dep_values_payload,
                    result,
                    meta={COMPUTE_PHASE_META_KEY: COMPUTE_PHASE_WRITE_PRECOMPUTE},
                )
        except _EXPECTED_COMPUTE_ERRORS as exc:  # type: ignore[misc]
            self._handle_error(
                plan,
                row_id,
                dep_args,
                dep_values_payload=dep_values_payload,
                exc=exc,
                compute_mode=compute_mode,
                unexpected=False,
            )
            return None
        except Exception as exc:
            logging.exception(  # noqa: LOG015
                "字段计算发生未预期的异常(write-precompute): 字段=%s, 行标识=%s",
                plan.field_key,
                row_id,
            )
            self._handle_error(
                plan,
                row_id,
                dep_args,
                dep_values_payload=dep_values_payload,
                exc=exc,
                compute_mode=compute_mode,
                unexpected=True,
            )
            return None
        else:
            return result

    def _handle_error(
        self,
        plan: _LateFieldPlan,
        row_id: Hashable,
        dep_args: Tuple[Any, ...],
        *,
        dep_values_payload: Dict[str, Any],
        exc: Exception,
        compute_mode: str,
        unexpected: bool,
    ) -> None:
        runtime = self._runtime
        deps_payload: Dict[str, Any] = {}
        if not runtime.guardrails.enabled:
            deps_payload = dep_values_payload or build_field_compute_dependencies_payload(plan.deps, dep_args)
        handle_compute_error(
            runtime,
            _DISCARD_CONTEXT,
            field_key=plan.field_key,
            row_id=row_id,
            dependencies=deps_payload,
            dependency_names=plan.deps,
            exc=exc,
            compute_mode=compute_mode,
            unexpected=unexpected,
        )


def _make_dense_reader(storage: Any, base_row_id: int, row_count: int) -> Callable[[Hashable], FieldValue]:
    """把稠密存储的 `values`/`present` 提到逐行循环之外(避免逐行字段查找)."""
    values: List[FieldValue] = storage.values
    present: bytearray = storage.present

    def _read(row_id: Hashable) -> FieldValue:
        if not isinstance(row_id, int):
            return None
        idx = int(row_id) - base_row_id
        if idx < 0 or idx >= row_count or present[idx] == 0:
            return None
        return values[idx]

    return _read


def _make_generic_reader(context: BatchContext, dep_key: str) -> Callable[[Hashable], FieldValue]:
    get_field_value = context.get_field_value

    def _read(row_id: Hashable) -> FieldValue:
        return get_field_value(dep_key, row_id)

    return _read


class LateColumnMaterializer:
    """列路径 `late` 物化: 写出某列前现场算该列,链式中间列暂留到消费方写完."""

    _materializer: LateFieldMaterializer
    _late_set: FrozenSet[str]
    _late_deps: Dict[str, Tuple[str, ...]]
    _pending_consumers: Dict[str, int]
    _columns: Dict[str, Dict[Hashable, FieldValue]]
    _remaining_consumers: Dict[str, int]

    def __init__(
        self,
        *,
        materializer: LateFieldMaterializer,
        field_dependencies: Dict[str, Tuple[str, ...]],
    ) -> None:
        self._materializer = materializer
        self._late_set = frozenset(materializer.late_fields)
        self._late_deps = {}
        self._pending_consumers = {}
        for field_key in materializer.late_fields:
            late_deps = tuple(dep for dep in field_dependencies.get(field_key, ()) if dep in self._late_set)
            self._late_deps[field_key] = late_deps
            for dep in late_deps:
                self._pending_consumers[dep] = self._pending_consumers.get(dep, 0) + 1
        self._columns = {}
        self._remaining_consumers = dict(self._pending_consumers)

    def reset(self) -> None:
        """批次开始时重置驻留列与引用计数."""
        self._columns = {}
        self._remaining_consumers = dict(self._pending_consumers)

    def is_late(self, field_key: str) -> bool:
        return field_key in self._late_set

    def materialize_column(
        self,
        context: BatchContext,
        field_key: str,
        row_ids: Sequence[Hashable],
    ) -> List[FieldValue]:
        """物化 `late` 列;若该列还有 `late` 消费者则暂留,否则算完即弃."""
        plan = self._materializer.plan_for(field_key)
        if plan is None:
            return [context.get_field_value(field_key, row_id) for row_id in row_ids]

        wants_field_compute = self._materializer.wants_field_compute()
        compute_mode = self._materializer.compute_mode()
        dep_readers = self._build_dep_readers(context, plan.deps)

        direct = not wants_field_compute and plan.memo_cache is None and plan.value_transform is None and plan.dep_cardinality is None
        if direct:
            values = self._compute_column_direct(plan, row_ids, dep_readers, compute_mode)
        else:
            values = self._compute_column_general(
                plan,
                row_ids,
                dep_readers,
                wants_field_compute=wants_field_compute,
                compute_mode=compute_mode,
            )

        if self._remaining_consumers.get(field_key, 0) > 0:
            self._columns[field_key] = dict(zip(row_ids, values))
        return values

    def _compute_column_direct(
        self,
        plan: _LateFieldPlan,
        row_ids: Sequence[Hashable],
        dep_readers: List[Callable[[Hashable], FieldValue]],
        compute_mode: str,
    ) -> List[FieldValue]:
        """无事件 / 无记忆化 / 无探针时的整列直呼快路径."""
        materializer = self._materializer
        calculator = plan.calculator
        values: List[FieldValue] = []
        for row_id in row_ids:
            dep_args = tuple(read(row_id) for read in dep_readers)
            try:
                values.append(calculator(*dep_args))
            except _EXPECTED_COMPUTE_ERRORS as exc:  # type: ignore[misc]
                values.append(materializer.handle_direct_call_error(plan, row_id, dep_args, exc, compute_mode, unexpected=False))
            except Exception as exc:
                logging.exception(  # noqa: LOG015
                    "字段计算发生未预期的异常(write-precompute): 字段=%s, 行标识=%s",
                    plan.field_key,
                    row_id,
                )
                values.append(materializer.handle_direct_call_error(plan, row_id, dep_args, exc, compute_mode, unexpected=True))
        return values

    def _compute_column_general(
        self,
        plan: _LateFieldPlan,
        row_ids: Sequence[Hashable],
        dep_readers: List[Callable[[Hashable], FieldValue]],
        *,
        wants_field_compute: bool,
        compute_mode: str,
    ) -> List[FieldValue]:
        compute_value = self._materializer.compute_value
        values: List[FieldValue] = []
        for row_id in row_ids:
            dep_args = tuple(read(row_id) for read in dep_readers)
            values.append(
                compute_value(
                    plan,
                    row_id,
                    dep_args,
                    wants_field_compute=wants_field_compute,
                    compute_mode=compute_mode,
                )
            )
        return values

    def _build_dep_readers(self, context: BatchContext, deps: Tuple[str, ...]) -> List[Callable[[Hashable], FieldValue]]:
        """为每个依赖预解析取值闭包(把存储查找提到逐行循环之外)."""
        dense = context if isinstance(context, DenseBatchContext) else None
        base_row_id = dense.dense_base_row_id() if dense is not None else 0
        row_count = dense.dense_row_count() if dense is not None else 0

        readers: List[Callable[[Hashable], FieldValue]] = []
        for dep_key in deps:
            dep_column = self._columns.get(dep_key)
            if dep_column is not None:
                readers.append(dep_column.get)
                continue
            if dense is not None:
                storage = dense.dense_get_storage_for_read(dep_key)
                if storage is not None:
                    readers.append(_make_dense_reader(storage, base_row_id, row_count))
                    continue
            readers.append(_make_generic_reader(context, dep_key))
        return readers

    def release_after_write(self, field_key: str) -> None:
        """该 `late` 列写完后,释放其不再被需要的 `late` 依赖列."""
        for dep in self._late_deps.get(field_key, ()):
            remaining = self._remaining_consumers.get(dep, 0) - 1
            self._remaining_consumers[dep] = remaining
            if remaining <= 0:
                _ = self._columns.pop(dep, None)


__all__ = (
    "LateColumnMaterializer",
    "LateFieldMaterializer",
    "LateRowWriteLayout",
)
