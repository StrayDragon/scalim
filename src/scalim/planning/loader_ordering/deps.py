import logging
from collections import OrderedDict
from typing import TYPE_CHECKING, List, Tuple

from ...spec.ir.fields import FieldIr
from ...spec.ir.helpers import extract_from_fields, infer_lookup_steps
from ...spec.ir.sources import SourceIr

_logger = logging.getLogger(__name__)


def build_ref_field_ordering_deps(demand: "DemandIr", field_key: str, field: FieldIr) -> Tuple[str, ...]:
    """为引用字段的排序构建依赖信号.

    返回一个由字段键组成的元组,这些字段键来源于关联步骤的 `from_field`,
    可映射回其他引用加载器.该信号用于规划阶段的排序(不是运行时的 `lookup_keys`).
    """
    steps = field.lookup_steps
    if steps is None and field.relation and demand.main_source and isinstance(field.source, SourceIr):
        steps = infer_lookup_steps(field.relation, demand.main_source, field.source)

    if not steps:
        return ()

    main_source_id = demand.main_source.source_id if demand.main_source else ""
    raw_deps = extract_from_fields(steps)

    deps: List[str] = []
    for dep_key in raw_deps:
        if dep_key == field_key:
            continue
        dep_field = demand.fields.get(dep_key)
        if not isinstance(dep_field, FieldIr):
            continue
        if dep_field.source.source_id == main_source_id:
            continue
        if not isinstance(dep_field.source, SourceIr):
            continue
        if not (dep_field.lookup_steps or dep_field.relation):
            continue
        deps.append(dep_key)

    # 在保持顺序的同时去重(`Py3.6+` 的 `dict` 会保留插入顺序).
    return tuple(OrderedDict.fromkeys(deps))


if TYPE_CHECKING:
    from ...spec.ir.demand import DemandIr


__all__ = [
    "build_ref_field_ordering_deps",
]
