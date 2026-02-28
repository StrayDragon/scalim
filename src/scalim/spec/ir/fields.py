from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from .helpers import extract_from_fields
from .presentation import FieldPresentationIr
from .relations import JoinConditionIr, LookupStepIr, RelationIr
from .sources import SourceRefIr


@dataclass(frozen=True)
class ComputeCallContextIr:
    """派生字段 call_by 上下文(IR): 运行时构建,用于提供受控上下文给用户函数."""

    row_id: Any
    batch_num: int
    field_id: str
    deps: tuple[str, ...]
    values: Mapping[str, Any]

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

    - 当未显式提供 `data_key`(或提供空字符串)时, 默认等于 `field_id`。
    """

    is_primary: bool = False
    """
    是否为主键字段
    """

    presentation: FieldPresentationIr | None = None
    """
    导出/展示元信息
    """

    value_formatter: Callable[[Any], Any] | None = None
    """
    输出格式化函数
    """

    transform: Callable[[Any], Any] | None = None
    """
    值转换函数 (可选)
    """

    relation: "JoinConditionIr | RelationIr | None" = None
    """
    关联关系 (支持运算符重载构建关联)
    """

    lookup_steps: tuple[LookupStepIr, ...] | None = None
    """
    显式 `lookup_steps`（有序），优先于 `relation` 推断。
    """

    def __post_init__(self) -> None:
        if not self.data_key:
            object.__setattr__(self, "data_key", self.field_id)

    def is_ref_field(self) -> bool:
        """是否是关联字段: 关联字段通过 `relation` 定义."""
        return self.relation is not None or bool(self.lookup_steps)

    def get_dependencies(self) -> tuple[str, ...]:
        """获取字段依赖的简化版本（仅返回 `relation` 左侧字段）。

        警告：此方法只提取 `relation` 条件的左侧字段作为依赖；当 DSL 中主表在右侧时
        （如 `"customers.id = orders.customer_id"`）会返回错误的依赖。

        推荐使用 `PlanBuilder` 或 `ExecutionPlan.field_dependencies` 获取正确的依赖，
        它们会根据主数据源方向使用 `infer_lookup_steps()` 正确推断依赖。

        返回：
            `relation` 条件中左侧字段名的元组。
        """
        if self.lookup_steps:
            return extract_from_fields(self.lookup_steps)
        # 如果有 `relation`,提取依赖的字段
        if self.relation:
            deps: set[str] = set()
            if isinstance(self.relation, JoinConditionIr):
                # 单个条件,提取左侧字段
                deps.add(self.relation.left.field_name)
            else:
                # 多个条件,提取所有左侧字段
                for condition in self.relation.conditions:
                    deps.add(condition.left.field_name)
            return tuple(deps)
        return ()

    def apply_transform(self, value: Any) -> Any:
        """应用转换函数(结果侧)

        参数：
            `value`: 原始值

        注意：类型安全说明：
        - 如果提供了 `transform` 函数，返回类型由 `transform` 决定。
        - 如果未提供 `transform`，则返回原始值（类型为 `Any`，需要调用方处理）。
        """
        if self.transform is not None:
            value = self.transform(value)
        if self.value_formatter is not None:
            return self.value_formatter(value)
        return value  # type: ignore[return-value]   - 没有 transform 时返回原始值


@dataclass(frozen=True)
class DerivedFieldIr:
    """派生字段(IR): 通过其他依赖字段计算(转换)得出的字段

    示例：

    ```python
    # 利润 = 金额 - 成本
    DerivedFieldSpec(
        field_key="profit",
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

    dependencies: tuple[str, ...]
    """
    依赖字段的 field_key 元组
    """

    calculator: Callable[..., Any]
    """
    计算函数
    """

    presentation: FieldPresentationIr | None = None
    """
    导出/展示元信息
    """

    value_formatter: Callable[[Any], Any] | None = None
    """
    输出格式化函数
    """

    call_ctx_key: str | None = None
    """
    call_by 上下文注入键(内部使用). 为 None 时不注入.
    """

    is_constant_compute: bool = False
    """
    是否为常量计算：批次内只计算一次并复用结果。

    注意：
    - 常量计算必须没有任何依赖字段，且不得使用 `call_by` 上下文。
    """

    def __post_init__(self) -> None:
        if self.is_constant_compute:
            if self.dependencies:
                msg = f"常量 compute 字段 {self.field_id!r} 必须不声明 dependencies"
                raise ValueError(msg)
            if self.call_ctx_key is not None:
                msg = f"常量 compute 字段 {self.field_id!r} 不允许 call_by 上下文"
                raise ValueError(msg)
            return

        if not self.dependencies:
            msg = f"派生字段 {self.field_id!r} 必须至少有一个依赖"
            raise ValueError(msg)

    def get_dependencies(self) -> tuple[str, ...]:
        return self.dependencies

    def compute(self, **field_values: Any) -> Any | None:
        """
        执行计算: 通过依赖字段的值计算得出新的值

        参数：
            `field_values`: 依赖字段的值
        """
        result = self.calculator(**field_values)
        if self.value_formatter is not None:
            return self.value_formatter(result)
        return result


SupportedFieldIr = FieldIr | DerivedFieldIr
