from collections.abc import Callable

from ..utils import graph
from .plan import Stage


def build_stages(field_order: list[str], get_deps: Callable[[str], list[str]]) -> list[Stage]:
    levels = graph.compute_levels(field_order, get_deps, field_order)

    stage_map: dict[int, list[str]] = {}
    for field_key in field_order:
        level = levels[field_key]
        if level not in stage_map:
            stage_map[level] = []
        stage_map[level].append(field_key)

    stages: list[Stage] = []
    for level in sorted(stage_map.keys()):
        stages.append(
            Stage(
                stage_id=f"stage_{level}",
                field_keys=stage_map[level],
                level=level,
            )
        )

    return stages
