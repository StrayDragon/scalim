from collections import deque
from typing import TYPE_CHECKING, Any, Deque, Dict, List, Optional, Set, Tuple, Union

from .....spec.ir import LookupStepIr, MainSourceIr, SourceIr
from .....spec.ir.binding import BindingIr
from .....spec.ir.lookup_casts import LookupCastSpecIr
from ...schema_dsl.models import (
    DemandConfig,
    LookupCastConfig,
    RelationStepConfig,
    SourceFieldConfig,
)
from ..errors import ScalimConversionError

if TYPE_CHECKING:
    from .....spec.ir.aliases import NormalizedLookupKeySpec

StepInfo = Tuple[str, str, LookupStepIr]


class ConfigToIRConversionRelationMixin:
    _sources_ir: Optional[Dict[str, SourceIr]] = None
    _main_source_ir: Optional[MainSourceIr] = None
    _relation_steps: Optional[Dict[str, List[StepInfo]]] = None
    _relation_adjacency: Optional[Dict[str, List[StepInfo]]] = None
    _source_field_id_map: Optional[Dict[str, Dict[str, str]]] = None
    _source_data_key_map: Optional[Dict[str, Dict[str, List[str]]]] = None

    def _get_lookup_cast_spec(self, lookup_cast: LookupCastConfig) -> LookupCastSpecIr:
        _ = lookup_cast
        raise NotImplementedError

    def _create_binding(
        self,
        bind_config: Any,
        static_params: Any,
        key_field: "NormalizedLookupKeySpec",
    ) -> Optional[BindingIr]:
        _ = (bind_config, static_params, key_field)
        raise NotImplementedError

    def _require_sources_ir(self) -> Dict[str, SourceIr]:
        sources_ir = self._sources_ir
        if sources_ir is None:
            msg = "Source IR map is not initialized"
            raise ScalimConversionError(msg)
        return sources_ir

    def _require_relation_steps(self) -> Dict[str, List[StepInfo]]:
        relation_steps = self._relation_steps
        if relation_steps is None:
            msg = "Relation steps are not initialized"
            raise ScalimConversionError(msg)
        return relation_steps

    def _require_relation_adjacency(self) -> Dict[str, List[StepInfo]]:
        relation_adjacency = self._relation_adjacency
        if relation_adjacency is None:
            msg = "Relation adjacency is not initialized"
            raise ScalimConversionError(msg)
        return relation_adjacency

    def _require_source_field_id_map(self) -> Dict[str, Dict[str, str]]:
        source_field_id_map = self._source_field_id_map
        if source_field_id_map is None:
            msg = "Source field id map is not initialized"
            raise ScalimConversionError(msg)
        return source_field_id_map

    def _require_source_data_key_map(self) -> Dict[str, Dict[str, List[str]]]:
        source_data_key_map = self._source_data_key_map
        if source_data_key_map is None:
            msg = "Source data key map is not initialized"
            raise ScalimConversionError(msg)
        return source_data_key_map

    def _convert_relations(self, config: DemandConfig) -> Dict[str, List[StepInfo]]:
        relation_steps: Dict[str, List[StepInfo]] = {}
        for rel_id, rel_config in config.relations.items():
            relation_steps[rel_id] = self._convert_steps(rel_config.steps, config)
        return relation_steps

    def _build_relation_adjacency(self, relation_steps: Dict[str, List[StepInfo]]) -> Dict[str, List[StepInfo]]:
        adjacency: Dict[str, List[StepInfo]] = {}
        for steps in relation_steps.values():
            for step_info in steps:
                from_source_id, _to_source_id, _step_ir = step_info
                adjacency.setdefault(from_source_id, []).append(step_info)
        return adjacency

    def _convert_steps(self, steps: Tuple[RelationStepConfig, ...], config: DemandConfig) -> List[StepInfo]:
        step_infos: List[StepInfo] = []
        for step in steps:
            step_infos.append(self._convert_step(step, config))
        return step_infos

    def _convert_step(self, step: RelationStepConfig, config: DemandConfig) -> StepInfo:
        from_source_id, from_fields = self._parse_step_field(step.from_)
        to_source_id, to_fields = self._parse_step_field(step.to)

        to_source = self._require_source_ir(to_source_id)
        to_field = self._resolve_to_field(to_fields, to_source)
        lookup_cast_spec = self._resolve_step_lookup_cast(step)
        bind_ir = self._resolve_step_binding(step, config, to_source_id, to_source.key.key)

        step_ir = LookupStepIr(
            from_field=tuple(from_fields) if len(from_fields) > 1 else from_fields[0],
            to_source_id=to_source_id,
            to_field=to_field,
            lookup_cast=lookup_cast_spec,
            bind=bind_ir,
        )

        return from_source_id, to_source_id, step_ir

    def _require_source_ir(self, source_id: str) -> SourceIr:
        source = self._require_sources_ir().get(source_id)
        if source is None:
            msg = "Step references unknown source '{}'".format(source_id)
            raise ScalimConversionError(msg)
        return source

    def _resolve_to_field(self, to_fields: List[str], to_source: SourceIr) -> Optional["NormalizedLookupKeySpec"]:
        if len(to_fields) > 1:
            to_field: Optional["NormalizedLookupKeySpec"] = tuple(to_fields)
        else:
            to_field = to_fields[0]

        if to_field == to_source.key.key:
            return None
        return to_field

    def _resolve_step_lookup_cast(self, step: RelationStepConfig) -> Optional[LookupCastSpecIr]:
        if step.lookup_cast is None:
            return None
        return self._get_lookup_cast_spec(step.lookup_cast)

    def _resolve_step_binding(
        self,
        step: RelationStepConfig,
        config: DemandConfig,
        to_source_id: str,
        key_field: "NormalizedLookupKeySpec",
    ) -> Optional[BindingIr]:
        _ = (step, config, to_source_id, key_field)
        return None

    def _resolve_lookup_steps(
        self,
        field_config: SourceFieldConfig,
        config: DemandConfig,
        target_source: SourceIr,
    ) -> Optional[Tuple[LookupStepIr, ...]]:
        if self._main_source_ir is None:
            return None

        if field_config.relation is None:
            if target_source.source_id == self._main_source_ir.source_id:
                return None
            path = self._infer_unique_path(self._main_source_ir.source_id, target_source.source_id)
            return tuple(step for _from_id, _to_id, step in path) if path else None

        relation = field_config.relation
        if isinstance(relation, str):
            relation_config = config.relations.get(relation)
            if relation_config is None:
                msg = "Unsupported relation reference: '{}'".format(relation)
                raise ScalimConversionError(msg)
            relation_steps = relation_config.steps
        else:
            relation_steps = relation.steps

        steps = self._convert_steps(relation_steps, config)
        return tuple(step for _from_id, _to_id, step in steps)

    def _infer_unique_path(self, start_id: str, target_id: str) -> Optional[List[StepInfo]]:
        if start_id == target_id:
            return []

        adjacency = self._require_relation_adjacency()
        relation_steps = self._require_relation_steps()
        if not adjacency and relation_steps:
            adjacency = self._build_relation_adjacency(relation_steps)
            self._relation_adjacency = adjacency

        max_paths = 2
        found_paths: List[List[StepInfo]] = []
        queue: Deque[Tuple[str, List[StepInfo], Set[str]]] = deque([(start_id, [], {start_id})])

        while queue and len(found_paths) < max_paths:
            current, path, visited = queue.popleft()
            if current == target_id:
                found_paths.append(path)
                continue
            for step_info in adjacency.get(current, []):
                _from_source_id, to_source_id, _step_ir = step_info
                if to_source_id in visited:
                    continue
                next_visited = set(visited)
                next_visited.add(to_source_id)
                queue.append((to_source_id, [*path, step_info], next_visited))

        if len(found_paths) == 1:
            return found_paths[0]

        if not found_paths:
            msg = "No relation path found from '{}' to '{}'".format(start_id, target_id)
            raise ScalimConversionError(msg)

        msg = "Ambiguous relation paths from '{}' to '{}'".format(start_id, target_id)
        raise ScalimConversionError(msg)

    def _parse_source_field_expr(self, expr: str) -> Tuple[str, str]:
        if "." not in expr:
            msg = "Invalid field reference: '{}'".format(expr)
            raise ScalimConversionError(msg)
        source_id, field_name = expr.split(".", 1)
        if not source_id or not field_name:
            msg = "Invalid field reference: '{}'".format(expr)
            raise ScalimConversionError(msg)
        field_name = self._resolve_source_field_name(source_id, field_name)
        return source_id, field_name

    def _parse_step_field(self, value: Union[str, Tuple[str, ...]]) -> Tuple[str, List[str]]:
        if isinstance(value, tuple):
            source_id: Optional[str] = None
            fields: List[str] = []
            for item in value:
                src, field_name = self._parse_source_field_expr(item)
                if source_id is None:
                    source_id = src
                elif source_id != src:
                    msg = "Step fields must reference the same source, got '{}' and '{}'".format(source_id, src)
                    raise ScalimConversionError(msg)
                fields.append(field_name)
            if source_id is None:
                msg = "Empty step field list"
                raise ScalimConversionError(msg)
            return source_id, fields

        src, field_name = self._parse_source_field_expr(value)
        return src, [field_name]

    def _build_source_data_key_map(self, source_field_id_map: Dict[str, Dict[str, str]]) -> Dict[str, Dict[str, List[str]]]:
        data_key_map: Dict[str, Dict[str, List[str]]] = {}
        for source_id, field_map in source_field_id_map.items():
            source_data_keys = data_key_map.setdefault(source_id, {})
            for field_id, data_key in field_map.items():
                source_data_keys.setdefault(data_key, []).append(field_id)
        return data_key_map

    def _resolve_source_field_name(self, source_id: str, field_name: str) -> str:
        field_map = self._require_source_field_id_map().get(source_id)
        if not field_map:
            return field_name
        if field_name not in field_map:
            return field_name
        mapped = field_map[field_name]
        data_key_map = self._require_source_data_key_map().get(source_id, {})
        conflicts = data_key_map.get(field_name, [])
        if conflicts:
            unique = set(conflicts)
            if unique != {field_name}:
                msg = (
                    "Relation step field '{}.{}' is ambiguous: field_id '{}' maps to '{}', "
                    "but '{}' is also a data_key for field_id(s): {}. "
                    "Rename one of the fields to disambiguate."
                ).format(
                    source_id,
                    field_name,
                    field_name,
                    mapped,
                    field_name,
                    ", ".join(sorted(unique)),
                )
                raise ScalimConversionError(msg)
        return mapped


__all__ = ()
