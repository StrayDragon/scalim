# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false, reportAttributeAccessIssue=false, reportUnknownMemberType=false

from collections import deque
from typing import Any, Deque, Dict, List, Optional, Tuple

from ...schema_dsl.constants import FIELD_KIND_DERIVED, FIELD_KIND_SOURCE
from ...schema_dsl.models import (
    DEMAND_KEYS,
    DERIVED_FIELD_KEYS,
    MAIN_SOURCE_KEYS,
    SOURCE_FIELD_KEYS,
    DerivedFieldConfig,
    SourceFieldConfig,
)
from ..call_by import extract_call_by_dependencies
from ..field_index import OutputFieldErrors, OutputFieldResolver, build_source_data_key_index
from ..models import AliasIndex, FieldDef, FieldDefIndex, RawDemand, collect_field_defs, field_def_key
from ..security import extract_compute_dependencies
from .results import ParsedFieldsResult
from .utils import str_or_none


class ParserFieldsMixin:
    def _parse_fields_v3(
        self,
        raw: RawDemand,
        main_source_id: str,
        raw_output_fields: Any,
    ) -> ParsedFieldsResult:
        index = self._collect_field_defs_v3(raw, main_source_id)
        output_field_ids, selected_defs, overrides = self._resolve_output_fields_v3(
            raw_output_fields,
            index.field_defs,
            index.defs_by_id,
            index.alias_index,
        )
        source_field_id_map = self._build_source_field_id_map(index.field_defs, overrides)
        required_defs = self._collect_required_field_defs(selected_defs, index.defs_by_id)
        order_by_defs = self._collect_order_by_field_defs(raw, main_source_id, index.defs_by_id)
        if order_by_defs:
            required_defs = self._merge_required_defs(required_defs, order_by_defs)

        source_fields, derived_fields, main_source_fields, source_fields_by_source = self._build_field_configs_v3(
            required_defs,
            overrides,
            main_source_id,
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
        if not isinstance(order_by_raw, list):
            return []
        order_defs: List[FieldDef] = []
        for item in order_by_raw:
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

    def _collect_field_defs_v3(self, raw: RawDemand, main_source_id: str) -> FieldDefIndex:
        return collect_field_defs(raw, main_source_id)

    def _build_field_configs_v3(
        self,
        required_defs: List[FieldDef],
        overrides: Dict[Tuple[str, Optional[str], str, int], Dict[str, Any]],
        main_source_id: str,
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
            override = overrides.get(field_def_key(field_def))
            if override:
                field_data.update(override)

            if field_def.kind == FIELD_KIND_DERIVED:
                derived_fields[field_def.field_id] = self._parse_derived_field(field_def.field_id, field_data)
                continue

            source_id = field_def.source_id or ""
            parsed = self._parse_source_field(field_def.field_id, field_data, source_id=source_id)
            source_fields[field_def.field_id] = parsed
            if source_id and source_id == main_source_id:
                main_source_fields[field_def.field_id] = parsed
            else:
                source_fields_by_source.setdefault(source_id, {})[field_def.field_id] = parsed

        return source_fields, derived_fields, main_source_fields, source_fields_by_source

    def _build_source_field_id_map(
        self,
        field_defs: List[FieldDef],
        overrides: Dict[Tuple[str, Optional[str], str, int], Dict[str, Any]],
    ) -> Dict[str, Dict[str, str]]:
        source_field_id_map: Dict[str, Dict[str, str]] = {}
        for field_def in field_defs:
            if field_def.kind != FIELD_KIND_SOURCE:
                continue
            source_id = field_def.source_id or ""
            if not source_id:
                continue
            field_data = dict(field_def.data)
            override = overrides.get(field_def_key(field_def))
            if override:
                field_data.update(override)
            field_name_raw = field_data.get(SOURCE_FIELD_KEYS["field"])
            field_name = field_def.field_id if field_name_raw is None else str(field_name_raw)
            source_field_id_map.setdefault(source_id, {})[field_def.field_id] = field_name
        return source_field_id_map

    def _resolve_output_fields_v3(
        self,
        raw_output_fields: Any,
        field_defs: List[FieldDef],
        defs_by_id: Dict[str, List[FieldDef]],
        alias_index: AliasIndex,
    ) -> Tuple[Optional[List[str]], List[FieldDef], Dict[Tuple[str, Optional[str], str, int], Dict[str, Any]]]:
        overrides: Dict[Tuple[str, Optional[str], str, int], Dict[str, Any]] = {}

        if raw_output_fields is None:
            if not field_defs:
                return None, [], overrides
            self._ensure_unique_field_ids(field_defs)
            return None, list(field_defs), overrides

        if not isinstance(raw_output_fields, list):
            msg = "output.fields must be a list"
            raise TypeError(msg)

        defs_by_data_key_by_source = build_source_data_key_index(field_defs)
        resolver = OutputFieldResolver(
            defs_by_id=defs_by_id,
            defs_by_data_key_by_source=defs_by_data_key_by_source,
            alias_index=alias_index,
            errors=OutputFieldErrors(),
        )
        selected_defs: List[FieldDef] = []
        for idx, item in enumerate(raw_output_fields):
            field_def, override, _entry_kind = resolver.resolve_entry(item, idx)
            if field_def is None:  # pragma: no cover
                continue  # pragma: no cover
            selected_defs.append(field_def)
            if override:
                field_key = field_def_key(field_def)
                existing = overrides.get(field_key)
                if existing is not None and existing != override:
                    msg = "Output field '{}' has conflicting overrides".format(field_def.field_id)
                    raise ValueError(msg)
                overrides[field_key] = override

        self._ensure_unique_output_defs(selected_defs)
        output_field_ids = [field_def.field_id for field_def in selected_defs]
        return output_field_ids, selected_defs, overrides

    def _ensure_unique_field_ids(self, field_defs: List[FieldDef]) -> None:
        seen: Dict[str, FieldDef] = {}
        for field_def in field_defs:
            existing = seen.get(field_def.field_id)
            if existing is None:
                seen[field_def.field_id] = field_def
                continue
            if existing is not field_def:
                msg = "Field '{}' is defined multiple times; output.fields is required to disambiguate ({})".format(
                    field_def.field_id,
                    "note: top-level output is optional",
                )
                raise ValueError(msg)

    def _ensure_unique_output_defs(self, field_defs: List[FieldDef]) -> None:
        seen: Dict[str, FieldDef] = {}
        for field_def in field_defs:
            existing = seen.get(field_def.field_id)
            if existing is None:
                seen[field_def.field_id] = field_def
                continue
            if existing is not field_def:
                msg = "Output field '{}' maps to multiple definitions; use unique field_id".format(field_def.field_id)
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

        inferred: List[str] = self._infer_derived_dependencies(field_id, field_data)
        depends_on: Tuple[str, ...] = tuple(inferred)

        return DerivedFieldConfig(
            field_id=field_id,
            name=str(field_data.get(DERIVED_FIELD_KEYS["name"], field_id)),
            compute=compute_expr,
            call_by=call_by_expr,
            depends_on=depends_on,
        )

    def _parse_source_field(self, field_id: str, field_data: Dict[str, Any], source_id: Optional[str] = None) -> SourceFieldConfig:
        resolved_source_id = source_id or str(field_data.get(SOURCE_FIELD_KEYS["source"], ""))
        field_name_raw = field_data.get(SOURCE_FIELD_KEYS["field"])
        field_name = field_id if field_name_raw is None else str(field_name_raw)
        relation = self._parse_relation_ref(field_data.get(SOURCE_FIELD_KEYS["relation"]))

        return SourceFieldConfig(
            field_id=field_id,
            source=resolved_source_id,
            field=field_name,
            name=str(field_data.get(SOURCE_FIELD_KEYS["name"], field_id)),
            relation=relation,
            value_cast=str_or_none(field_data.get(SOURCE_FIELD_KEYS["value_cast"])),
        )
