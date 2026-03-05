# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false, reportAttributeAccessIssue=false, reportUnknownMemberType=false

from typing import Any, Dict, List, Optional, Tuple, Union, cast

from ...schema_dsl.models import (
    DEMAND_KEYS,
    RELATION_CONFIG_KEYS,
    RELATION_STEP_KEYS,
    InlineRelationConfig,
    RelationConfig,
    RelationStepConfig,
)
from ..models import RawDemand


class ParserRelationsMixin:
    def _parse_relation_ref(self, relation_raw: Any) -> Optional[InlineRelationConfig]:
        if isinstance(relation_raw, str):
            msg = "relation must be an object with steps; relation_id string is not supported"
            raise TypeError(msg)
        if isinstance(relation_raw, dict):
            relation_dict = cast("Dict[str, Any]", relation_raw)
            steps_raw = relation_dict.get(RELATION_CONFIG_KEYS["steps"])
            steps = self._parse_steps(steps_raw)
            return InlineRelationConfig(steps=steps)
        return None

    def _parse_relations(self, raw: RawDemand) -> Dict[str, RelationConfig]:
        relations: Dict[str, RelationConfig] = {}
        raw_relations = raw.get_mapping(DEMAND_KEYS["relations"])
        if raw_relations is None:
            return relations

        for rel_id_raw, rel_data_raw in raw_relations.items():
            if not isinstance(rel_data_raw, dict):
                continue

            rel_id: str = str(rel_id_raw)
            rel_data: Dict[str, Any] = rel_data_raw

            relations[rel_id] = self._parse_relation(rel_id, rel_data)

        return relations

    def _parse_relation(self, rel_id: str, rel_data: Dict[str, Any]) -> RelationConfig:
        steps = self._parse_steps(rel_data.get(RELATION_CONFIG_KEYS["steps"]))
        return RelationConfig(
            relation_id=rel_id,
            steps=steps,
        )

    def _parse_steps(self, steps_raw: Any) -> Tuple[RelationStepConfig, ...]:
        if not isinstance(steps_raw, list):
            return ()

        steps: List[RelationStepConfig] = []
        for step_raw in steps_raw:
            if not isinstance(step_raw, dict):
                continue
            step_data: Dict[str, Any] = step_raw
            from_value = self._parse_step_field(step_data.get(RELATION_STEP_KEYS["from_"]))
            to_value = self._parse_step_field(step_data.get(RELATION_STEP_KEYS["to"]))
            lookup_cast = self._parse_lookup_cast(step_data.get(RELATION_STEP_KEYS["lookup_cast"]))
            to_bind = self._parse_bind(step_data.get(RELATION_STEP_KEYS["to_bind"]))

            steps.append(
                RelationStepConfig(
                    from_=from_value,
                    to=to_value,
                    lookup_cast=lookup_cast,
                    to_bind=to_bind,
                )
            )

        return tuple(steps)

    def _parse_step_field(self, raw_field: Any) -> Union[str, Tuple[str, ...]]:
        if isinstance(raw_field, list):
            return tuple(str(item) for item in raw_field)
        return str(raw_field) if raw_field is not None else ""
