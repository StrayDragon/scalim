from collections.abc import Callable

from ...spec.ir.demand import DemandIr
from ...spec.ir.fields import FieldIr
from ...spec.ir.helpers import extract_from_fields, infer_lookup_steps
from ...spec.ir.relations import LookupStepIr
from ...spec.ir.sources import SourceIr, SourceRefIr

InferLookupStepsFn = Callable[[object, SourceRefIr, SourceIr], tuple[LookupStepIr, ...] | None]


class LookupStepsResolver:
    """在规划阶段解析并缓存 `lookup_steps`,用于依赖/算子构建.

    缓存仅是内部优化: 测试不得对缓存命中/未命中进行断言.
    """

    _cache: dict[str, tuple[LookupStepIr, ...] | None]
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
        field_key: str | None = None,
    ) -> tuple[LookupStepIr, ...] | None:
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
) -> list[str]:
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


__all__ = [
    "InferLookupStepsFn",
    "LookupStepsResolver",
    "extract_relation_dependency_keys",
]
