from types import MappingProxyType
from typing import Callable, Hashable, Mapping, Optional, Set, Tuple, Union

from ...typedefs import FieldValue
from ...vendor.dataclassesx import dataclass
from .helpers import extract_from_fields
from .presentation import FieldPresentationIr
from .relations import JoinConditionIr, LookupStepIr, RelationIr
from .sources import SourceRefIr


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

    value_formatter: Optional[Callable[[FieldValue], FieldValue]] = None
    """
    输出格式化函数
    """

    transform: Optional[Callable[[FieldValue], FieldValue]] = None
    """
    值转换函数 (可选)
    """

    relation: "Optional[Union[JoinConditionIr, RelationIr]]" = None
    """
    关联关系 (支持运算符重载构建关联)
    """

    lookup_steps: Optional[Tuple[LookupStepIr, ...]] = None
    """
    显式关联步骤(有序),优先于 `relation` 推断.
    """

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

    def apply_transform(self, value: FieldValue) -> FieldValue:
        """应用转换函数(结果侧)

        参数:
            `value`: 原始值

        注意: 类型安全说明:
        - 如果有 `transform` 函数,返回类型由 `transform` 决定
        - 如果没有 `transform`,返回原始值 (类型保持为 `FieldValue`)
        """
        if self.transform is not None:
            value = self.transform(value)
        if self.value_formatter is not None:
            return self.value_formatter(value)
        return value


@dataclass(frozen=True)
class DerivedFieldIr:
    """派生字段(IR): 通过其他依赖字段计算(转换)得出的字段

    示例:
      ```python
      DerivedFieldIr(
          field_id="profit",
          name="利润",
          dependencies=("amount", "cost"),
          calculator=lambda amount, cost: amount - cost,
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

    calculator: Callable[..., FieldValue]
    """
    计算函数
    """

    presentation: Optional[FieldPresentationIr] = None
    """
    导出/展示元信息
    """

    value_formatter: Optional[Callable[[FieldValue], FieldValue]] = None
    """
    输出格式化函数
    """

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

    def compute(self, **field_values: FieldValue) -> FieldValue:
        """
        执行计算: 通过依赖字段的值计算得出新的值

        参数:
            `**field_values`: 依赖字段的值
        """
        result = self.calculator(**field_values)
        if self.value_formatter is not None:
            return self.value_formatter(result)
        return result


SupportedFieldIr = Union[FieldIr, DerivedFieldIr]
