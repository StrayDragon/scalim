from typing import Callable, Dict, List, Optional, Tuple

from ...spec.ir import DemandIr, FieldIr, LookupStepIr, SourceIr, SourceRefIr
from ...spec.ir._helpers import extract_from_fields, infer_lookup_steps

InferLookupStepsFn = Callable[[object, SourceRefIr, SourceIr], Optional[Tuple[LookupStepIr, ...]]]


class LookupStepsResolver:
    """用于在规划阶段解析并缓存关联步骤,以构建依赖关系/算子.

    缓存仅为内部优化:测试中禁止依赖缓存命中/未命中的行为.
    """

    _cache: Dict[str, Optional[Tuple[LookupStepIr, ...]]]
    _infer_lookup_steps: InferLookupStepsFn

    def __init__(
        self,
        *,
        infer_lookup_steps_fn: InferLookupStepsFn = infer_lookup_steps,
    ) -> None:
        self._cache = {}
        self._infer_lookup_steps = infer_lookup_steps_fn

    def resolve(
        self,
        field_spec: FieldIr,
        main_source: SourceRefIr,
        *,
        field_key: Optional[str] = None,
    ) -> Optional[Tuple[LookupStepIr, ...]]:
        cache_key = field_key or field_spec.field_id
        if field_spec.lookup_steps:
            self._cache[cache_key] = field_spec.lookup_steps
            return field_spec.lookup_steps

        if field_spec.relation and isinstance(field_spec.source, SourceIr):
            if cache_key in self._cache:
                return self._cache[cache_key]
            steps = self._infer_lookup_steps(field_spec.relation, main_source, field_spec.source)
            self._cache[cache_key] = steps
            return steps

        return None


def extract_relation_dependency_keys(
    *,
    demand: DemandIr,
    field_spec: FieldIr,
    resolver: LookupStepsResolver,
    field_key: str,
) -> List[str]:
    """提取 `FieldIr` 的依赖字段键(来自 `lookup_steps` 或 `relation`)."""
    if field_spec.lookup_steps:
        steps = resolver.resolve(field_spec, field_spec.source, field_key=field_key)
        return list(extract_from_fields(steps)) if steps else []

    if not field_spec.relation:
        return []

    main_source = demand.main_source
    if not main_source:
        return []

    if not isinstance(field_spec.source, SourceIr):
        return []

    steps = resolver.resolve(field_spec, main_source, field_key=field_key)
    if not steps:
        return []

    return list(extract_from_fields(steps))


__all__ = (
    "InferLookupStepsFn",
    "LookupStepsResolver",
    "extract_relation_dependency_keys",
)
