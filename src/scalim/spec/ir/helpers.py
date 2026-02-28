from collections.abc import Hashable
from typing import Any

from .aliases import LoaderCallable
from .binding import BindingIr, LoaderCallContextIr
from .relations import JoinConditionIr, LookupStepIr, RelationIr
from .sources import SourceIr, SourceRefIr


def infer_lookup_steps(
    relation: Any,
    from_source: SourceRefIr,
    to_source: SourceIr,
) -> tuple[LookupStepIr, ...] | None:
    """
    从 `relation` 推断 `LookupStepIr` 序列。

    这是一个统一的辅助函数,处理 `JoinConditionIr` 和 `RelationIr` 到 `LookupStepIr` 的转换。

    参数：
        `relation`: 关联关系（`JoinConditionIr` 或 `RelationIr`）
        `from_source`: 起始数据源
        `to_source`: 目标数据源

    注意：
        关联依赖方向与主数据源选择有关.推荐通过 `PlanBuilder`/`ExecutionPlan` 使用该推断逻辑,
        避免在 IR 层手工拼装导致方向不一致。

    返回：
        `LookupStepIr` 序列；无法推断时返回 `None`。

    示例：
        ```python
        # 单字段关联
        relation = orders["customer_id"].join(customers["customer_id"])
        steps = infer_lookup_steps(relation, orders_source, customers_source)
        # -> (LookupStep(from_field="customer_id", to_source=customers_source),)

        # 多级关联
        relation = orders["pay_id"].join(pays["pay_id"]).and_(pays["country_id"].join(countries["country_id"]))
        steps = infer_lookup_steps(relation, orders_source, countries_source)
        # -> (LookupStep(...), LookupStep(...))
        ```
    """

    try:
        if isinstance(relation, JoinConditionIr):
            # 单个条件,转换为 `RelationIr`
            rel = RelationIr(conditions=(relation,))
            return rel.infer_multi_field_lookup_path(from_source, to_source)
        if isinstance(relation, RelationIr):
            return relation.infer_multi_field_lookup_path(from_source, to_source)
    except ValueError:
        return None

    return None


def extract_from_fields(
    steps: tuple[LookupStepIr, ...],
) -> tuple[str, ...]:
    """
    从 `LookupStepIr` 序列中收集所有步骤的 `from_fields`,用于依赖分析。

    参数：
        `steps`: `LookupStepIr` 序列

    返回：
        所有 `from_fields` 的扁平化元组

    示例：
        ```python
        # 单级单字段
        steps = (LookupStepIr(from_field="customer_id", to_source=...),)
        extract_from_fields(steps)  # -> ("customer_id",)

        # 多级
        steps = (
            LookupStepIr(from_field="pay_id", to_source=pays),
            LookupStepIr(from_field="country_id", to_source=countries),
        )
        extract_from_fields(steps)  # -> ("pay_id", "country_id")

        # 多字段
        steps = (LookupStepIr(from_field=("region_id", "institution_id"), to_source=...),)
        extract_from_fields(steps)  # -> ("region_id", "institution_id")
        ```
    """
    result: list[str] = []
    for step in steps:
        from_fields = step.get_from_fields()  # 返回 `tuple[str, ...]`
        result.extend(from_fields)
    return tuple(result)


def call_loader_with_binding(
    binding: BindingIr | None,
    context: LoaderCallContextIr,
    loader_fn: LoaderCallable,
) -> dict[Hashable, Any]:
    if binding is None:
        return loader_fn()

    args, kwargs = binding.build_params(context)
    return loader_fn(*args, **kwargs)
