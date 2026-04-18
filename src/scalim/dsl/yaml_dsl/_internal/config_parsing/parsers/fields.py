from collections import deque
from typing import Any, Deque, Dict, List, Optional, Tuple, cast

from ....schema_dsl.constants import FIELD_KIND_DERIVED, FIELD_KIND_SOURCE
from ....schema_dsl.models import (
    DEMAND_KEYS,
    DERIVED_FIELD_KEYS,
    MAIN_SOURCE_KEYS,
    SOURCE_FIELD_KEYS,
    DerivedFieldConfig,
    RelationConfig,
    SourceFieldConfig,
)
from ..call_by import extract_call_by_dependencies
from ..field_extract import derive_source_field_data_key
from ..models import FieldDef, FieldDefIndex, RawDemand, collect_field_defs, field_def_key
from ..security import extract_compute_dependencies
from .relations import ParserRelationsMixin
from .results import ParsedFieldsResult
from .utils import list_or_none, str_or_none


class ParserFieldsMixin(ParserRelationsMixin):
    def _parse_fields(
        self,
        raw: RawDemand,
        main_source_id: str,
        required_field_ids: Optional[List[str]],
        relations: Dict[str, RelationConfig],
        *,
        field_def_index: Optional[FieldDefIndex] = None,
    ) -> ParsedFieldsResult:
        index = field_def_index or self._collect_field_defs(raw, main_source_id)
        self._ensure_unique_field_ids(index.field_defs)

        selected_defs = self._select_field_defs(required_field_ids, index.defs_by_id, index.field_defs)
        output_field_ids = list(required_field_ids) if required_field_ids is not None else None

        source_field_id_map = self._build_source_field_id_map(index.field_defs)
        required_defs = self._collect_required_field_defs(selected_defs, index.defs_by_id)
        order_by_defs = self._collect_order_by_field_defs(raw, main_source_id, index.defs_by_id)
        if order_by_defs:
            required_defs = self._merge_required_defs(required_defs, order_by_defs)

        source_fields, derived_fields, main_source_fields, source_fields_by_source = self._build_field_configs(
            required_defs,
            main_source_id,
            relations,
        )

        return ParsedFieldsResult(
            source_fields=source_fields,
            derived_fields=derived_fields,
            output_fields=output_field_ids,
            main_source_fields=main_source_fields,
            source_fields_by_source=source_fields_by_source,
            source_field_id_map=source_field_id_map,
            field_def_index=index,
        )

    def _select_field_defs(
        self,
        required_field_ids: Optional[List[str]],
        defs_by_id: Dict[str, List[FieldDef]],
        all_field_defs: List[FieldDef],
    ) -> List[FieldDef]:
        if required_field_ids is None:
            return list(all_field_defs)

        selected: List[FieldDef] = []
        for fid in required_field_ids:
            matched = defs_by_id.get(fid, [])
            if not matched:
                msg = "Required field '{}' is not defined".format(fid)
                raise ValueError(msg)
            if len(matched) > 1:
                msg = (
                    "Field '{}' is defined multiple times; field_id must be unique (output.fields disambiguation has been removed)".format(
                        fid
                    )
                )
                raise ValueError(msg)
            selected.append(matched[0])
        return selected

    def _collect_order_by_field_defs(
        self,
        raw: RawDemand,
        main_source_id: str,
        defs_by_id: Dict[str, List[FieldDef]],
    ) -> List[FieldDef]:
        raw_main = raw.get_mapping(DEMAND_KEYS["main_source"])
        if raw_main is None:
            return []
        order_by_raw = raw_main.get(MAIN_SOURCE_KEYS["order_by"])
        order_items = list_or_none(order_by_raw)
        if order_items is None:
            return []

        order_defs: List[FieldDef] = []
        for item in order_items:
            if not isinstance(item, str):
                continue
            raw_item = item.strip()
            if not raw_item or raw_item == "-":
                continue
            field_id = raw_item[1:] if raw_item.startswith("-") else raw_item
            matched = [field_def for field_def in defs_by_id.get(field_id, []) if (field_def.source_id or "") == main_source_id]
            if matched:
                order_defs.append(matched[0])
        return order_defs

    def _merge_required_defs(
        self,
        required_defs: List[FieldDef],
        extra_defs: List[FieldDef],
    ) -> List[FieldDef]:
        merged: Dict[Tuple[str, Optional[str], str, int], FieldDef] = {}
        for field_def in required_defs:
            merged[field_def_key(field_def)] = field_def
        for field_def in extra_defs:
            field_key = field_def_key(field_def)
            if field_key not in merged:
                merged[field_key] = field_def
        return list(merged.values())

    def _collect_field_defs(self, raw: RawDemand, main_source_id: str) -> FieldDefIndex:
        return collect_field_defs(raw, main_source_id)

    def _build_field_configs(
        self,
        required_defs: List[FieldDef],
        main_source_id: str,
        relations: Dict[str, RelationConfig],
    ) -> Tuple[
        Dict[str, SourceFieldConfig],
        Dict[str, DerivedFieldConfig],
        Dict[str, SourceFieldConfig],
        Dict[str, Dict[str, SourceFieldConfig]],
    ]:
        source_fields: Dict[str, SourceFieldConfig] = {}
        derived_fields: Dict[str, DerivedFieldConfig] = {}
        main_source_fields: Dict[str, SourceFieldConfig] = {}
        source_fields_by_source: Dict[str, Dict[str, SourceFieldConfig]] = {}

        for field_def in required_defs:
            field_data = dict(field_def.data)

            if field_def.kind == FIELD_KIND_DERIVED:
                derived_fields[field_def.field_id] = self._parse_derived_field(field_def.field_id, field_data)
                continue

            source_id = field_def.source_id or ""
            parsed = self._parse_source_field(field_def.field_id, field_data, source_id=source_id, relations=relations)
            source_fields[field_def.field_id] = parsed
            if source_id and source_id == main_source_id:
                main_source_fields[field_def.field_id] = parsed
            else:
                source_fields_by_source.setdefault(source_id, {})[field_def.field_id] = parsed

        return source_fields, derived_fields, main_source_fields, source_fields_by_source

    def _build_source_field_id_map(
        self,
        field_defs: List[FieldDef],
    ) -> Dict[str, Dict[str, str]]:
        source_field_id_map: Dict[str, Dict[str, str]] = {}
        for field_def in field_defs:
            if field_def.kind != FIELD_KIND_SOURCE:
                continue
            source_id = field_def.source_id or ""
            if not source_id:
                continue
            field_data = dict(field_def.data)
            extract_raw = field_data.get(SOURCE_FIELD_KEYS["extract"])
            extract_expr = None if extract_raw is None else str(extract_raw)
            data_key = derive_source_field_data_key(field_id=field_def.field_id, extract=extract_expr)
            source_field_id_map.setdefault(source_id, {})[field_def.field_id] = data_key
        return source_field_id_map

    def _ensure_unique_field_ids(self, field_defs: List[FieldDef]) -> None:
        seen: Dict[str, FieldDef] = {}
        for field_def in field_defs:
            existing = seen.get(field_def.field_id)
            if existing is None:
                seen[field_def.field_id] = field_def
                continue
            if existing is not field_def:
                msg = (
                    "Field '{}' is defined multiple times; field_id must be unique "
                    "(output.fields disambiguation has been removed; rename the field_id)"
                ).format(field_def.field_id)
                raise ValueError(msg)

    def _collect_required_field_defs(
        self,
        selected_defs: List[FieldDef],
        defs_by_id: Dict[str, List[FieldDef]],
    ) -> List[FieldDef]:
        required: Dict[Tuple[str, Optional[str], str, int], FieldDef] = {}
        for field_def in selected_defs:
            required[field_def_key(field_def)] = field_def
        queue: "Deque[FieldDef]" = deque(field_def for field_def in selected_defs if field_def.kind == FIELD_KIND_DERIVED)

        while queue:
            field_def = queue.popleft()
            depends_on = self._infer_derived_dependencies(field_def.field_id, field_def.data)
            for dep in depends_on:
                matched = defs_by_id.get(dep, [])
                if not matched:
                    msg = "Derived field '{}' depends on unknown field '{}'".format(field_def.field_id, dep)
                    raise ValueError(msg)
                if len(matched) > 1:
                    msg = "Derived field '{}' depends on ambiguous field '{}'".format(field_def.field_id, dep)
                    raise ValueError(msg)
                dep_def = matched[0]
                dep_key = field_def_key(dep_def)
                if dep_key in required:
                    continue
                required[dep_key] = dep_def
                if dep_def.kind == FIELD_KIND_DERIVED:
                    queue.append(dep_def)

        return list(required.values())

    def _infer_derived_dependencies(self, field_id: str, field_data: Dict[str, Any]) -> List[str]:
        if "depends_on" in field_data:
            msg = "Derived field '{}' does not allow 'depends_on'; dependencies are inferred from '{}'/'{}'".format(
                field_id,
                DERIVED_FIELD_KEYS["compute"],
                DERIVED_FIELD_KEYS["call_by"],
            )
            raise ValueError(msg)

        compute_expr_raw = field_data.get(DERIVED_FIELD_KEYS["compute"])
        compute_expr = str(compute_expr_raw or "")
        if compute_expr:
            return extract_compute_dependencies(compute_expr)

        call_by_raw = field_data.get(DERIVED_FIELD_KEYS["call_by"])
        call_by_expr = str(call_by_raw or "")
        if call_by_expr:
            return extract_call_by_dependencies(call_by_expr)
        return []

    def _parse_derived_field(self, field_id: str, field_data: Dict[str, Any]) -> DerivedFieldConfig:
        compute_expr_raw = field_data.get(DERIVED_FIELD_KEYS["compute"])
        compute_expr = str(compute_expr_raw) if compute_expr_raw is not None else None
        call_by_raw = field_data.get(DERIVED_FIELD_KEYS["call_by"])
        call_by_expr = str(call_by_raw) if call_by_raw is not None else None

        inferred = self._infer_derived_dependencies(field_id, field_data)
        depends_on: Tuple[str, ...] = tuple(inferred)

        return DerivedFieldConfig(
            field_id=field_id,
            name=str(field_data.get(DERIVED_FIELD_KEYS["name"], field_id)),
            compute=compute_expr,
            call_by=call_by_expr,
            depends_on=depends_on,
        )

    def _parse_source_field(
        self,
        field_id: str,
        field_data: Dict[str, Any],
        *,
        source_id: Optional[str] = None,
        relations: Dict[str, RelationConfig],
    ) -> SourceFieldConfig:
        resolved_source_id = source_id or str(field_data.get(SOURCE_FIELD_KEYS["source"], ""))
        extract_raw = field_data.get(SOURCE_FIELD_KEYS["extract"])
        extract_expr = str(extract_raw) if extract_raw is not None else None
        relation = self._parse_relation_ref(field_data.get(SOURCE_FIELD_KEYS["relation"]), relations=relations)

        default_raw = field_data.get(SOURCE_FIELD_KEYS["default"])
        default_cases: Optional[Tuple[Dict[str, Any], ...]] = None
        if default_raw is not None:
            if not isinstance(default_raw, list):
                msg = "Source field '{}' default must be a list".format(field_id)
                raise TypeError(msg)
            default_items = cast("List[object]", default_raw)  # pragma: allow-cast yaml scalar list boundary
            items: List[Dict[str, Any]] = []
            for idx, item in enumerate(default_items):
                if not isinstance(item, dict):
                    msg = "Source field '{}' default[{}] must be an object".format(field_id, int(idx))
                    raise TypeError(msg)
                item_dict = cast("Dict[str, Any]", item)  # pragma: allow-cast yaml mapping boundary
                items.append(dict(item_dict))
            default_cases = tuple(items)

        return SourceFieldConfig(
            field_id=field_id,
            source=resolved_source_id,
            extract=extract_expr,
            name=str(field_data.get(SOURCE_FIELD_KEYS["name"], field_id)),
            relation=relation,
            value_cast=str_or_none(field_data.get(SOURCE_FIELD_KEYS["value_cast"])),
            default=default_cases,
        )


__all__ = ()
