from typing import Callable, Dict, List

from ..utils import graph
from .plan import Stage


def build_stages(field_order: List[str], get_deps: Callable[[str], List[str]]) -> List[Stage]:
    levels = graph.compute_levels(field_order, get_deps, field_order)

    stage_map: Dict[int, List[str]] = {}
    for field_key in field_order:
        level = levels[field_key]
        if level not in stage_map:
            stage_map[level] = []
        stage_map[level].append(field_key)

    stages: List[Stage] = []
    for level in sorted(stage_map.keys()):
        stages.append(
            Stage(
                stage_id="stage_{}".format(level),
                field_keys=stage_map[level],
                level=level,
            )
        )

    return stages
