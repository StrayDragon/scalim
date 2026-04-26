from collections import deque
from typing import Dict, FrozenSet, List, Optional, Set, Tuple, cast, overload

from ...exceptions import ScalimError
from ...vendor.compact.typing_extensionsx import override
from ...vendor.dataclassesx import dataclass
from ._source_contracts import LookupSourceRefIrBase, MainSourceRefIrBase, SourceRefIrBase
from .aliases import LookupKeySpec
from .binding import BindingIr
from .lookup_casts import LookupCastSpecIr


class ScalimRelationInferenceError(ScalimError, ValueError):
    """关联路径推断失败时抛出.

    同时继承 `ScalimError` 和 `ValueError`,使调用方既可按 `ScalimError`
    统一捕获框架异常,也可按 `ValueError` 做更细粒度的处理.
    """


@dataclass(frozen=True)
class FieldRefIr:
    """字段引用 - 用于构建关联条件.

    表达 `Source["field_name"]` 语法,支持方法调用构建关联表达式.

    示例 (推荐):
        - `orders_source["customer_id"].join(customers_source["customer_id"])`
        - 或: `orders_source["customer_id"].eq(customers_source["customer_id"])`
    """

    source: SourceRefIrBase
    """
    数据源(IR)实例
    """

    field_name: str
    """
    字段名
    """

    def join(self, other: object) -> "JoinConditionIr":
        """构建关联条件 - 推荐方式

        示例:
            - `relation = source_a["field_a"].join(source_b["field_b"])`
            - 多条件组合:
              `relation = source_a["f1"].join(source_b["f1"]).and_(source_a["f2"].join(source_b["f2"]))`
        """
        if not isinstance(other, FieldRefIr):
            msg = f"join() requires a FieldRefIr, got {type(other).__name__}"
            raise TypeError(msg)
        return JoinConditionIr(left=self, right=other)

    def eq(self, other: object) -> "JoinConditionIr":
        """构建关联条件 - `join()` 的别名,语义更清晰

        示例:
            - `relation = source_a["field_a"].eq(source_b["field_b"])`
        """
        return self.join(other)

    @override
    def __hash__(self) -> int:
        return hash((self.source.source_id, self.field_name))


@dataclass(frozen=True)
class JoinConditionIr:
    """
    联结条件(IR): 表达两个表达式之间的相等关系,支持通过方法组合多个条件.

    示例:
        - `orders["customer_id"].join(customers["customer_id"])`
    """

    left: FieldRefIr
    """
    左侧字段引用
    """

    right: FieldRefIr
    """
    右侧字段引用
    """

    @overload
    def and_(self, other: "JoinConditionIr") -> "RelationIr": ...

    @overload
    def and_(self, other: "RelationIr") -> "RelationIr": ...

    def and_(self, other: object) -> "RelationIr":
        """组合多个条件, 表达 "且" 的语义"""
        if isinstance(other, JoinConditionIr):
            return RelationIr(conditions=(self, other))
        if isinstance(other, RelationIr):
            return RelationIr(conditions=(self, *other.conditions))
        msg = "and_() requires JoinConditionIr or RelationIr, got {}".format(type(other).__name__)
        raise TypeError(msg)


@dataclass(frozen=True)
class RelationIr:
    """
    关联关系(IR): 可复用的多表多字段关联定义

    示例:
        - 单表单字段: `orders["customer_id"].join(customers["customer_id"])`
        - 单表多字段:
          `orders["region_id"].join(mapping["region_id"]).and_(orders["institution_id"].join(mapping["institution_id"]))`
        - 多表级联:
          `orders["pay_id"].join(pays["pay_id"]).and_(pays["country_id"].join(countries["country_id"]))`
    """

    conditions: Tuple[JoinConditionIr, ...]
    """
    若干关联条件
    """

    @overload
    def and_(self, other: "JoinConditionIr") -> "RelationIr": ...

    @overload
    def and_(self, other: "RelationIr") -> "RelationIr": ...

    def and_(self, other: object) -> "RelationIr":
        """支持继续组合条件, 表达 "且" 的语义"""
        if isinstance(other, JoinConditionIr):
            return RelationIr(conditions=(*self.conditions, other))
        if isinstance(other, RelationIr):
            return RelationIr(conditions=(*self.conditions, *other.conditions))
        msg = "and_() requires JoinConditionIr or RelationIr, got {}".format(type(other).__name__)
        raise TypeError(msg)

    def get_involved_sources(self) -> FrozenSet[SourceRefIrBase]:
        sources: Set[SourceRefIrBase] = set()
        for condition in self.conditions:
            sources.add(condition.left.source)
            sources.add(condition.right.source)
        return frozenset(sources)

    def _build_adjacency(self) -> Dict[str, List[Tuple[str, SourceRefIrBase, str]]]:
        adjacency: Dict[str, List[Tuple[str, SourceRefIrBase, str]]] = {}

        for condition in self.conditions:
            left_src = condition.left.source
            right_src = condition.right.source
            left_field = condition.left.field_name
            right_field = condition.right.field_name

            adjacency.setdefault(left_src.source_id, []).append((left_field, right_src, right_field))
            adjacency.setdefault(right_src.source_id, []).append((right_field, left_src, left_field))

        return adjacency

    def _build_lookup_steps(self, path: List[Tuple[str, SourceRefIrBase, str]]) -> "Tuple[LookupStepIr, ...]":
        steps: List[LookupStepIr] = []
        for from_field, next_source, to_field in path:
            if isinstance(next_source, MainSourceRefIrBase):
                msg = "主数据源不支持作为关联查找目标"
                raise TypeError(msg)
            lookup_source = cast("LookupSourceRefIrBase", next_source)  # pragma: allow-cast lookup source typed narrowing
            if to_field == lookup_source.key.key:
                steps.append(LookupStepIr(from_field=from_field, to_source=lookup_source))
            else:
                steps.append(LookupStepIr(from_field=from_field, to_source=lookup_source, to_field=to_field))
        return tuple(steps)

    def infer_lookup_path(self, from_source: SourceRefIrBase, to_source: LookupSourceRefIrBase) -> "Tuple[LookupStepIr, ...]":
        """
        推断从 `from_source` 到 `to_source` 的查找路径, 返回 `LookupStepIr` 序列
        """
        # 构建邻接表: `source_id` -> [(`field`, `next_source`, `next_field`)]
        adjacency = self._build_adjacency()

        # 使用广度优先搜索查找路径
        if from_source.source_id not in adjacency:
            msg = f"起始数据源 {from_source.source_id!r} 不在关联关系中"
            raise ScalimRelationInferenceError(msg)

        queue: "deque[Tuple[SourceRefIrBase, List[Tuple[str, SourceRefIrBase, str]]]]" = deque([(from_source, [])])
        visited: Set[str] = {from_source.source_id}

        while queue:
            current_source, path = queue.popleft()

            if current_source.source_id == to_source.source_id:
                # 找到路径,构建 `LookupStepIr` 序列
                return self._build_lookup_steps(path)

            # 探索邻居
            for from_field, next_source, to_field in adjacency.get(current_source.source_id, []):
                if next_source.source_id not in visited:
                    visited.add(next_source.source_id)
                    new_path = [*path, (from_field, next_source, to_field)]
                    queue.append((next_source, new_path))

        msg = f"无法从 {from_source.source_id!r} 到达 {to_source.source_id!r}"
        raise ScalimRelationInferenceError(msg)

    def infer_multi_field_lookup_path(self, from_source: SourceRefIrBase, to_source: LookupSourceRefIrBase) -> "Tuple[LookupStepIr, ...]":
        """
        推断多字段关联路径: 处理复合主键场景,将多个单字段条件合并为一个多字段 `LookupStepIr`
        """
        # 收集 `from_source` -> `to_source` 的所有直接条件
        direct_conditions: List[Tuple[str, str]] = []
        for condition in self.conditions:
            if condition.left.source == from_source and condition.right.source == to_source:
                direct_conditions.append((condition.left.field_name, condition.right.field_name))
            elif condition.right.source == from_source and condition.left.source == to_source:
                direct_conditions.append((condition.right.field_name, condition.left.field_name))

        if len(direct_conditions) > 1:
            # 多字段关联
            from_fields = tuple(f for f, _ in direct_conditions)
            to_fields = tuple(t for _, t in direct_conditions)
            return (LookupStepIr(from_field=from_fields, to_source=to_source, to_field=to_fields),)

        if len(direct_conditions) == 1:
            # 单字段关联
            from_field, to_field = direct_conditions[0]
            if to_field == to_source.key.key:
                return (LookupStepIr(from_field=from_field, to_source=to_source),)
            return (LookupStepIr(from_field=from_field, to_source=to_source, to_field=to_field),)

        # 没有直接关联,使用普通路径推断
        return self.infer_lookup_path(from_source, to_source)


@dataclass(frozen=True)
class LookupStepIr:
    """
    关联步骤(IR): 描述从一个或多个字段到另一个数据源的关联关系, 这是多级关联链的基本单元, 表达完全无歧义地指定关联路径

    示例:
        - 单字段关联: `LookupStepIr(from_field="pay_id", to_source=pays_source)`
        - 多字段关联:
          `LookupStepIr(from_field=["region_id", "institution_id"], to_source=mapping_source, to_field=["region_id", "institution_id"])`
    """

    from_field: LookupKeySpec
    """
    源字段名或字段名列表,从当前数据中取值
    """

    to_source: LookupSourceRefIrBase
    """
    目标数据源对象,明确指定要关联到哪个源
    """

    to_field: Optional[LookupKeySpec] = None
    """
    目标字段名或字段名列表(可选,默认使用 `to_source` 的键)
    """

    lookup_cast: Optional[LookupCastSpecIr] = None
    """
    关联键归一化转换(仅当前步骤)
    """

    bind: Optional[BindingIr] = None
    """
    下游加载参数绑定(仅当前步骤)
    """

    def __post_init__(self) -> None:
        # 确保 `from_field` 和 `to_field` 的类型一致
        if self.to_field is not None:
            from_is_multi = isinstance(self.from_field, (list, tuple))
            to_is_multi = isinstance(self.to_field, (list, tuple))
            if from_is_multi != to_is_multi:
                msg = "from_field and to_field must both be single or both be multiple"
                raise ValueError(msg)
            if from_is_multi:
                from_fields = self._normalize_fields(self.from_field)
                to_fields = self._normalize_fields(self.to_field)
                if len(from_fields) != len(to_fields):
                    msg = "from_field and to_field must have the same length"
                    raise ValueError(msg)

    def is_multi_field(self) -> bool:
        """
        是否为多字段关联
        """
        return isinstance(self.from_field, (list, tuple))

    @staticmethod
    def _normalize_fields(fields: LookupKeySpec) -> Tuple[str, ...]:
        if isinstance(fields, (list, tuple)):
            return tuple(fields)
        return (fields,)

    def get_from_fields(self) -> Tuple[str, ...]:
        """
        获取源字段列表
        """
        return self._normalize_fields(self.from_field)

    def get_to_fields_or_source_key(self) -> Tuple[str, ...]:
        """
        获取目标字段列表: 如果未指定 `to_field`,则使用 `to_source` 的键
        """
        if self.to_field is not None:
            return self._normalize_fields(self.to_field)
        # 默认使用数据源键
        key = self.to_source.key.key
        if isinstance(key, (list, tuple)):
            return tuple(key)
        return (key,)

    def get_to_key_or_source_key(self) -> LookupKeySpec:
        """
        获取目标键: 如果未指定 `to_field`,则使用 `to_source` 的键
        """
        if self.to_field is not None:
            return self.to_field
        return self.to_source.key.key


__all__ = ()
