from typing import Any, Dict, List, Optional, Tuple, Union

from ...schema_dsl.models import (
    DEMAND_KEYS,
    RELATION_CONFIG_KEYS,
    RELATION_STEP_KEYS,
    InlineRelationConfig,
    RelationConfig,
    RelationStepConfig,
)
from ..models import RawDemand
from .sources import ParserSourcesMixin
from .utils import list_or_none, mapping_or_none


class ParserRelationsMixin(ParserSourcesMixin):
    def _parse_relation_ref(self, relation_raw: object) -> Optional[InlineRelationConfig]:
        if isinstance(relation_raw, str):
            msg = "relation must be an object with steps; relation_id string is not supported"
            raise TypeError(msg)

        relation_dict = mapping_or_none(relation_raw)
        if relation_dict is None:
            return None

        steps_raw = relation_dict.get(RELATION_CONFIG_KEYS["steps"])
        steps = self._parse_steps(steps_raw)
        return InlineRelationConfig(steps=steps)

    def _parse_relations(self, raw: RawDemand) -> Dict[str, RelationConfig]:
        relations: Dict[str, RelationConfig] = {}
        raw_relations = raw.get_mapping(DEMAND_KEYS["relations"])
        if raw_relations is None:
            return relations

        for rel_id_raw, rel_data_raw in raw_relations.items():
            rel_data = mapping_or_none(rel_data_raw)
            if rel_data is None:
                continue

            rel_id = str(rel_id_raw)
            relations[rel_id] = self._parse_relation(rel_id, rel_data)

        return relations

    def _parse_relation(self, rel_id: str, rel_data: Dict[str, Any]) -> RelationConfig:
        steps = self._parse_steps(rel_data.get(RELATION_CONFIG_KEYS["steps"]))
        return RelationConfig(
            relation_id=rel_id,
            steps=steps,
        )

    def _parse_steps(self, steps_raw: object) -> Tuple[RelationStepConfig, ...]:
        step_items = list_or_none(steps_raw)
        if step_items is None:
            return ()

        steps: List[RelationStepConfig] = []
        for step_raw in step_items:
            step_data = mapping_or_none(step_raw)
            if step_data is None:
                continue

            from_value = self._parse_step_field(step_data.get(RELATION_STEP_KEYS["from_"]))
            to_value = self._parse_step_field(step_data.get(RELATION_STEP_KEYS["to"]))
            lookup_cast = self._parse_lookup_cast(step_data.get(RELATION_STEP_KEYS["lookup_cast"]))

            steps.append(
                RelationStepConfig(
                    from_=from_value,
                    to=to_value,
                    lookup_cast=lookup_cast,
                )
            )

        return tuple(steps)

    def _parse_step_field(self, raw_field: object) -> Union[str, Tuple[str, ...]]:
        field_items = list_or_none(raw_field)
        if field_items is not None:
            return tuple(str(item) for item in field_items)
        return str(raw_field) if raw_field is not None else ""
