from types import MappingProxyType
from typing import Any, Dict, Hashable, Mapping, Optional, Set, Tuple, Union

from ...typedefs import FieldValue
from ...vendor.dataclassesx import dataclass
from ._helpers import extract_from_fields
from ._relations import JoinConditionIr, LookupStepIr, RelationIr
from ._sources import SourceRefIr
from .callable_refs import CallableRefIr
from .presentation import FieldPresentationIr


@dataclass(frozen=True)
class CallByValueIr:
    """`call_by` 参数值规范(纯数据).

    `kind` 取值:
    - `literal`: `value` 为 `Python` 字面量(`int`/`float`/`str`/`bool`/`None` 等)
    - `field`: `value` 为依赖字段的 `field_id`
    - `ctx`: 忽略 `value`,使用上下文对象
    - `ctx_attr`: `value` 为上下文对象的属性名
    """

    kind: str
    value: object


@dataclass(frozen=True)
class CallBySpecIr:
    """派生字段的 `call_by` 规范(纯数据,不执行 `import`/解析)."""

    reference: CallableRefIr
    args: Tuple[CallByValueIr, ...] = ()
    kwargs: Tuple[Tuple[str, CallByValueIr], ...] = ()
    field_names: Tuple[str, ...] = ()


def call_by_requires_ctx(call_by: "CallBySpecIr") -> bool:
    for item in tuple(call_by.args or ()):
        kind = str(getattr(item, "kind", "") or "").strip()  # pragma: allow-dynattr dsl: CallByValueIr contract
        if kind in ("ctx", "ctx_attr"):
            return True
    for _key, item in tuple(call_by.kwargs or ()):
        kind = str(getattr(item, "kind", "") or "").strip()  # pragma: allow-dynattr dsl: CallByValueIr contract
        if kind in ("ctx", "ctx_attr"):
            return True
    return False


@dataclass(frozen=True)
class ValueOpIr:
    """值处理操作规范(纯数据,不包含可调用对象).

    `kind` 取值:
    - `cast`: 内置类型转换(例如 `to='decimal'`)
    - `transform`: 运行时解析 `callable_ref` 并执行转换
    - `format`: 运行时解析 `callable_ref` 并执行格式化
    """

    kind: str
    to: str = ""
    callable_ref: Optional[CallableRefIr] = None

    def __post_init__(self) -> None:
        kind = str(self.kind or "").strip()
        object.__setattr__(self, "kind", kind)
        if kind == "cast":
            to = str(self.to or "").strip()
            if not to:
                msg = "ValueOpIr(kind='cast') requires non-empty to"
                raise ValueError(msg)
            if self.callable_ref is not None:
                msg = "ValueOpIr(kind='cast') must not set callable_ref"
                raise ValueError(msg)
            object.__setattr__(self, "to", to)
            return

        if kind in ("transform", "format"):
            if self.to:
                msg = "ValueOpIr(kind={!r}) must not set to".format(kind)
                raise ValueError(msg)
            if self.callable_ref is None:
                msg = "ValueOpIr(kind={!r}) requires callable_ref".format(kind)
                raise ValueError(msg)
            return

        msg = "Unknown ValueOpIr.kind={!r}".format(kind)
        raise ValueError(msg)


@dataclass(frozen=True)
class FieldDefaultCaseIr:
    """`ref` 字段缺省值 `case` (`IR`).

    说明:
    - `case` 选择在执行期按 `when` + `first-match` 决定.
    - `v1` 仅使用 `when='relation_miss'`,但该结构显式预留扩展空间(例如 `hit_null`/`hit_empty_string`/`field_missing`).
    """

    when: str
    kind: str
    literal: FieldValue = None
    call_by: Optional[CallBySpecIr] = None

    def __post_init__(self) -> None:
        when = str(self.when or "").strip()
        kind = str(self.kind or "").strip()
        object.__setattr__(self, "when", when)
        object.__setattr__(self, "kind", kind)

        if kind == "literal":
            if self.call_by is not None:
                msg = "FieldDefaultCaseIr(kind='literal') must not set call_by"
                raise ValueError(msg)
            return

        if kind == "call_by":
            if self.call_by is None:
                msg = "FieldDefaultCaseIr(kind='call_by') requires call_by"
                raise ValueError(msg)
            return

        msg = "Unknown FieldDefaultCaseIr.kind={!r}".format(kind)
        raise ValueError(msg)


@dataclass(frozen=True)
class ComputeCallContextIr:
    """派生字段 `call_by` 上下文(IR): 运行时构建,用于提供受控上下文给用户函数."""

    row_id: Hashable
    batch_num: int
    field_id: str
    deps: Tuple[str, ...]
    values: Mapping[str, FieldValue]

    def __post_init__(self) -> None:
        if not isinstance(self.values, MappingProxyType):
            object.__setattr__(self, "values", MappingProxyType(dict(self.values)))

    def __getstate__(self) -> Dict[str, Any]:
        state: Dict[str, Any] = dict(self.__dict__)
        values = state.get("values")
        if isinstance(values, MappingProxyType):
            state["values"] = dict(values)
        return state

    def __setstate__(self, state: Dict[str, Any]) -> None:
        for key, value in state.items():
            object.__setattr__(self, key, value)
        self.__post_init__()


@dataclass(frozen=True)
class FieldIr:
    """
    字段(IR): 定义一个从数据源加载的字段的完整信息
    """

    field_id: str
    """
    字段唯一标识 (用于内部引用)
    """

    name: str
    """
    字段显示名称 (用于输出表头)
    """

    source: SourceRefIr
    """
    数据源对象引用 (类型安全)
    """

    data_key: str = ""
    """
    从数据中提取值的键名.

    - 当未显式提供 `data_key`(或提供空字符串)时, 默认等于 `field_id`.
    """

    extract_expr: str = ""
    """
    字段提取表达式(诊断友好).

    - 对 YAML DSL: 通常等于用户声明的 `extract` 原始字符串(或其规范化文本)
    - 对纯 IR 使用: 默认回退为 `data_key`
    """

    extract_segments: Tuple[Union[str, int], ...] = ()
    """
    字段提取的 `canonical segments(typed)`.

    - 仅支持 `str`/`int` 段
    - 当未显式提供时, 默认回退为单段 `(data_key,)`(保持旧 `flat getter` 行为)
    """

    is_primary: bool = False
    """
    是否为主键字段
    """

    presentation: Optional[FieldPresentationIr] = None
    """
    导出/展示元信息
    """

    value_ops: Tuple[ValueOpIr, ...] = ()
    """值处理操作序列(纯描述,不包含可调用对象)."""

    relation: "Optional[Union[JoinConditionIr, RelationIr]]" = None
    """
    关联关系 (支持运算符重载构建关联)
    """

    lookup_steps: Optional[Tuple[LookupStepIr, ...]] = None
    """
    显式关联步骤(有序),优先于 `relation` 推断.
    """

    default_cases: Tuple[FieldDefaultCaseIr, ...] = ()
    """可选:`ref` 字段在 `relation miss` 时的缺省值 `cases`(有序)."""

    def __post_init__(self) -> None:
        if not self.data_key:
            object.__setattr__(self, "data_key", self.field_id)
        if not self.extract_expr:
            object.__setattr__(self, "extract_expr", self.data_key)
        if not self.extract_segments:
            object.__setattr__(self, "extract_segments", (self.data_key,))

    def is_ref_field(self) -> bool:
        """是否是关联字段: 关联字段通过 `relation` 定义."""
        return self.relation is not None or bool(self.lookup_steps)

    def get_dependencies(self) -> Tuple[str, ...]:
        """获取字段依赖的简化版本(仅返回 `relation` 左侧字段).

        警告: 此方法只提取 `relation` 条件的左侧字段作为依赖,当 `DSL` 中主表在右侧时
        (如 `customers.id = orders.customer_id`)会返回错误的依赖.

        推荐使用 `PlanBuilder` 或 `ExecutionPlan.field_dependencies` 获取正确的依赖,
        它们会根据主数据源方向使用 `infer_lookup_steps()` 正确推断依赖.

        返回:
            `relation` 条件中左侧字段名的元组
        """
        if self.lookup_steps:
            return extract_from_fields(self.lookup_steps)
        # 如果存在 `relation`,提取依赖字段
        if self.relation:
            deps: Set[str] = set()
            if isinstance(self.relation, JoinConditionIr):
                # 单个条件,提取左侧字段
                deps.add(self.relation.left.field_name)
            else:
                # 多个条件,提取所有左侧字段
                for condition in self.relation.conditions:
                    deps.add(condition.left.field_name)
            return tuple(deps)
        return ()


@dataclass(frozen=True)
class DerivedFieldIr:
    """派生字段(`IR`): 通过其他依赖字段计算(转换)得出的字段

    说明:
    - `DerivedFieldIr` 只保存纯数据(`compute_expr`/`call_by` 规范),不保存任何 `Python` 可调用对象.
    - 运行时会在“运行时链接”阶段把 `compute_expr` 编译为安全函数/把 `call_by.reference` 解析为可调用对象,
      并注入到 `RuntimeBindings.derived_calculators[field_id]`.

    示例(安全表达式 `compute`):
      ```python
      DerivedFieldIr(
          field_id="profit",
          name="利润",
          dependencies=("amount", "cost"),
          compute_expr="amount - cost",
      )
      ```

    示例(`call_by` 引用):
      ```python
      DerivedFieldIr(
          field_id="profit",
          name="利润",
          dependencies=("amount", "cost"),
          call_by=CallBySpecIr(
              reference=PythonReferenceIr(
                  reference="myapp.calculators:profit",
                  module_path="myapp.calculators",
                  attr_path=("profit",),
                  style="dotted",
              ),
          ),
      )
      ```
    """

    field_id: str
    """
    字段唯一标识
    """

    name: str
    """
    字段显示名称
    """

    dependencies: Tuple[str, ...]
    """
    依赖字段的 `field_key` 元组.
    """

    compute_expr: str = ""
    """可选: `compute` 表达式(纯文本,运行时再编译)."""

    call_by: Optional[CallBySpecIr] = None
    """可选: `call_by` 规范(纯数据,运行时再解析/绑定)."""

    presentation: Optional[FieldPresentationIr] = None
    """
    导出/展示元信息
    """

    value_ops: Tuple[ValueOpIr, ...] = ()
    """值处理操作序列(例如格式化;纯描述,不包含可调用对象)."""

    call_ctx_key: Optional[str] = None
    """
    用于 `call_by` 的上下文注入键(内部使用);为 `None` 时不注入.
    """

    is_constant_compute: bool = False
    """
    是否为常量计算:在单个批次内只计算一次并复用结果.

    注意:
    - 常量计算必须没有任何依赖字段,且不得使用 `call_by` 上下文.
    """

    def __post_init__(self) -> None:
        compute_expr = str(self.compute_expr or "").strip()
        object.__setattr__(self, "compute_expr", compute_expr)

        if compute_expr and self.call_by is not None:
            msg = "派生字段 {!r} 必须二选一: compute_expr 或 call_by".format(self.field_id)
            raise ValueError(msg)
        if not compute_expr and self.call_by is None:
            msg = "派生字段 {!r} 必须声明 compute_expr 或 call_by".format(self.field_id)
            raise ValueError(msg)

        if self.is_constant_compute:
            if self.dependencies:
                msg = "常量 compute 字段 {!r} 必须不声明 dependencies".format(self.field_id)
                raise ValueError(msg)
            if self.call_ctx_key is not None:
                msg = "常量 compute 字段 {!r} 不允许 call_by 上下文".format(self.field_id)
                raise ValueError(msg)
            return

        if not self.dependencies:
            msg = "派生字段 {!r} 必须至少有一个依赖".format(self.field_id)
            raise ValueError(msg)

    def get_dependencies(self) -> Tuple[str, ...]:
        return self.dependencies


SupportedFieldIr = Union[FieldIr, DerivedFieldIr]

__all__ = ()
