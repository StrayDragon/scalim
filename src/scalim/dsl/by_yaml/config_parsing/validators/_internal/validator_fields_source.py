# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownParameterType=false, reportUnknownLambdaType=false, reportMissingParameterType=false, reportAttributeAccessIssue=false, reportUnknownMemberType=false, reportUnannotatedClassAttribute=false, reportUninitializedInstanceVariable=false, reportPrivateUsage=false, reportCallIssue=false, reportArgumentType=false, reportUnusedFunction=false, reportImplicitOverride=false, reportUnusedImport=false, reportMissingTypeArgument=false, reportUnnecessaryComparison=false, reportUnnecessaryCast=false
from typing import Any, Dict, List, Optional, Set, Tuple, cast

from ....schema_dsl.constants import FIELD_KIND_SOURCE, VALUE_CAST_ENUM
from ...models import AliasIndex, FieldDef, RawDemand
from ..constants import F
from ..issues import ValidationIssue

_F = F


class ValidatorFieldSourceMixin:
    def _validate_source_field_id_data_key_conflicts(
        self,
        field_defs: List[FieldDef],
        errors: List[ValidationIssue],
        main_source_id: str,
    ) -> None:
        field_ids_by_source: Dict[str, Set[str]] = {}
        data_key_map_by_source: Dict[str, Dict[str, Set[str]]] = {}

        for field_def in field_defs:
            if field_def.kind != FIELD_KIND_SOURCE:
                continue
            source_id = field_def.source_id or ""
            if not source_id:
                continue
            field_id = field_def.field_id
            data_key_raw = field_def.data.get(_F.FIELD)
            data_key = field_id if data_key_raw is None else str(data_key_raw)

            field_ids_by_source.setdefault(source_id, set()).add(field_id)
            data_key_map_by_source.setdefault(source_id, {}).setdefault(data_key, set()).add(field_id)

        for source_id, field_ids in field_ids_by_source.items():
            data_key_map = data_key_map_by_source.get(source_id, {})
            shared_names = set(field_ids) & set(data_key_map.keys())
            for name in sorted(shared_names):
                owners = set(data_key_map.get(name, set()))
                if owners == {name}:
                    continue
                msg = (
                    "Source '{}' has field_id/data_key naming conflict for '{}': "
                    "data_key '{}' is used by field_id(s): {}. "
                    "Rename one of the fields to disambiguate."
                ).format(
                    source_id,
                    name,
                    name,
                    ", ".join(sorted(owners)),
                )
                if main_source_id and source_id == main_source_id:
                    base_path = "main_source.fields"
                else:
                    base_path = "sources.{}.fields".format(source_id)
                self._add_error(errors, msg, path=base_path)

    def _add_field_def_v3(
        self,
        field_id_raw: Any,
        kind: str,
        source_id: Optional[str],
        data_raw: Any,
        field_defs: List[FieldDef],
        defs_by_id: Dict[str, List[FieldDef]],
        alias_index: AliasIndex,
        errors: List[ValidationIssue],
    ) -> Optional[FieldDef]:
        if not isinstance(data_raw, dict):
            self._add_error(errors, "Field '{}' must be a dictionary".format(field_id_raw))
            return None
        field_id = str(field_id_raw)
        field_dict = cast("Dict[str, Any]", data_raw)
        field_def = FieldDef(field_id=field_id, kind=kind, source_id=source_id, data=field_dict)
        field_defs.append(field_def)
        defs_by_id.setdefault(field_id, []).append(field_def)
        alias_index.add(field_dict, field_def)
        return field_def

    def _collect_main_source_fields_v3(
        self,
        raw: RawDemand,
        errors: List[ValidationIssue],
        sources_set: Set[str],
        sources_info: Dict[str, Dict[str, bool]],
        main_source_id: str,
        relation_paths: Dict[str, List[Tuple[str, str, bool]]],
        field_defs: List[FieldDef],
        defs_by_id: Dict[str, List[FieldDef]],
        alias_index: AliasIndex,
        duplicate_fields_by_source: Dict[str, Set[str]],
        seen_field_values_by_source: Dict[str, Dict[str, str]],
    ) -> None:
        raw_main = raw.get_mapping(_F.MAIN_SOURCE)
        if raw_main is None:
            return
        main_fields = raw_main.get(_F.FIELDS)
        if main_fields is None:
            return
        if not isinstance(main_fields, dict):
            self._add_error(errors, "'{}' must be a dictionary".format("main_source.fields"), path="main_source.fields")
            return

        for field_id_raw, field_data_raw in main_fields.items():
            if isinstance(field_data_raw, dict) and _F.COMPUTE in field_data_raw:
                self._add_error(
                    errors,
                    "main_source.fields '{}' must not declare compute".format(field_id_raw),
                    path="main_source.fields.{}".format(field_id_raw),
                )
                continue
            if isinstance(field_data_raw, dict) and _F.CALL_BY in field_data_raw:
                self._add_error(
                    errors,
                    "main_source.fields '{}' must not declare call_by".format(field_id_raw),
                    path="main_source.fields.{}".format(field_id_raw),
                )
                continue
            self._validate_field_id_not_reserved(
                str(field_id_raw),
                errors,
                path="main_source.fields.{}".format(field_id_raw),
            )
            field_def = self._add_field_def_v3(
                field_id_raw,
                FIELD_KIND_SOURCE,
                main_source_id or None,
                field_data_raw,
                field_defs,
                defs_by_id,
                alias_index,
                errors,
            )
            if field_def is None:
                continue
            self._validate_source_field(
                str(field_id_raw),
                field_def.data,
                sources_set,
                sources_info,
                main_source_id,
                relation_paths,
                errors,
                source_id_override=main_source_id,
                base_path="main_source.fields.{}".format(field_id_raw),
            )
            self._track_duplicate_source_field(
                main_source_id,
                str(field_id_raw),
                field_def.data,
                duplicate_fields_by_source,
                seen_field_values_by_source,
            )

    def _collect_source_fields_v3(
        self,
        raw: RawDemand,
        errors: List[ValidationIssue],
        sources_set: Set[str],
        sources_info: Dict[str, Dict[str, bool]],
        main_source_id: str,
        relation_paths: Dict[str, List[Tuple[str, str, bool]]],
        field_defs: List[FieldDef],
        defs_by_id: Dict[str, List[FieldDef]],
        alias_index: AliasIndex,
        duplicate_fields_by_source: Dict[str, Set[str]],
        seen_field_values_by_source: Dict[str, Dict[str, str]],
    ) -> None:
        raw_sources = raw.get_mapping(_F.SOURCES)
        if raw_sources is None:
            return

        for source_id_raw, source_data_raw in raw_sources.items():
            source_id = str(source_id_raw)
            if not isinstance(source_data_raw, dict):
                continue
            source_dict = cast("Dict[str, Any]", source_data_raw)
            source_fields = source_dict.get(_F.FIELDS)
            if source_fields is None:
                continue
            if not isinstance(source_fields, dict):
                self._add_error(
                    errors,
                    "'{}' must be a dictionary".format("sources.{}.fields".format(source_id)),
                    path="sources.{}.fields".format(source_id),
                )
                continue
            for field_id_raw, field_data_raw in source_fields.items():
                if isinstance(field_data_raw, dict) and _F.COMPUTE in field_data_raw:
                    self._add_error(
                        errors,
                        "sources.{}.fields '{}' must not declare compute".format(source_id, field_id_raw),
                        path="sources.{}.fields.{}".format(source_id, field_id_raw),
                    )
                    continue
                if isinstance(field_data_raw, dict) and _F.CALL_BY in field_data_raw:
                    self._add_error(
                        errors,
                        "sources.{}.fields '{}' must not declare call_by".format(source_id, field_id_raw),
                        path="sources.{}.fields.{}".format(source_id, field_id_raw),
                    )
                    continue
                self._validate_field_id_not_reserved(
                    str(field_id_raw),
                    errors,
                    path="sources.{}.fields.{}".format(source_id, field_id_raw),
                )
                field_def = self._add_field_def_v3(
                    field_id_raw,
                    FIELD_KIND_SOURCE,
                    source_id,
                    field_data_raw,
                    field_defs,
                    defs_by_id,
                    alias_index,
                    errors,
                )
                if field_def is None:
                    continue
                self._validate_source_field(
                    str(field_id_raw),
                    field_def.data,
                    sources_set,
                    sources_info,
                    main_source_id,
                    relation_paths,
                    errors,
                    source_id_override=source_id,
                    base_path="sources.{}.fields.{}".format(source_id, field_id_raw),
                )
                self._track_duplicate_source_field(
                    source_id,
                    str(field_id_raw),
                    field_def.data,
                    duplicate_fields_by_source,
                    seen_field_values_by_source,
                )

    def _validate_source_field(
        self,
        field_id: str,
        field_data: Dict[str, Any],
        sources_set: Set[str],
        sources_info: Dict[str, Dict[str, bool]],
        main_source_id: str,
        relation_paths: Dict[str, List[Tuple[str, str, bool]]],
        errors: List[ValidationIssue],
        source_id_override: Optional[str] = None,
        base_path: Optional[str] = None,
    ) -> None:
        field_path = base_path or "fields.{}".format(field_id)
        source_id = self._resolve_source_id_for_field(field_id, field_data, source_id_override, errors, field_path)
        if source_id is None:
            return

        if not self._validate_source_field_name(field_id, field_data, errors, field_path):
            return

        if source_id not in sources_set:
            self._add_error(
                errors,
                "Field '{}' references unknown source '{}'".format(field_id, source_id),
                path="{}.{}".format(field_path, _F.SOURCE),
            )
            return

        self._validate_source_field_value_cast(field_id, field_data, errors, field_path)
        relation_val = field_data.get(_F.RELATION)
        if relation_val is not None:
            self._validate_field_relation(
                field_id,
                relation_val,
                source_id,
                main_source_id,
                sources_set,
                sources_info,
                errors,
                field_path,
            )
        elif source_id != main_source_id:
            self._validate_relation_paths_for_field(field_id, source_id, main_source_id, relation_paths, errors, field_path)

    def _resolve_source_id_for_field(
        self,
        field_id: str,
        field_data: Dict[str, Any],
        source_id_override: Optional[str],
        errors: List[ValidationIssue],
        field_path: str,
    ) -> Optional[str]:
        if source_id_override is None:
            if _F.SOURCE not in field_data:
                self._add_error(
                    errors,
                    "Field '{}' missing required '{}'".format(field_id, _F.SOURCE),
                    path="{}.{}".format(field_path, _F.SOURCE),
                )
                return None

            source_val = field_data.get(_F.SOURCE)
            if not isinstance(source_val, str) or not source_val:
                self._add_error(
                    errors,
                    "Field '{}' has invalid source '{}', expected source_id".format(field_id, source_val),
                    path="{}.{}".format(field_path, _F.SOURCE),
                )
                return None
            return source_val

        if _F.SOURCE in field_data:
            source_val = field_data.get(_F.SOURCE)
            if not isinstance(source_val, str) or not source_val:
                self._add_error(
                    errors,
                    "Field '{}' has invalid source '{}', expected source_id".format(field_id, source_val),
                    path="{}.{}".format(field_path, _F.SOURCE),
                )
                return None
            if source_val != source_id_override:
                self._add_error(
                    errors,
                    "Field '{}' source '{}' does not match container source '{}'".format(field_id, source_val, source_id_override),
                    path="{}.{}".format(field_path, _F.SOURCE),
                )
                return None

        return source_id_override

    def _validate_source_field_name(
        self,
        field_id: str,
        field_data: Dict[str, Any],
        errors: List[ValidationIssue],
        field_path: str,
    ) -> bool:
        field_val = field_data.get(_F.FIELD)
        if field_val is not None and (not isinstance(field_val, str) or not field_val):
            self._add_error(
                errors,
                "Field '{}' has invalid field '{}', expected field name".format(field_id, field_val),
                path="{}.{}".format(field_path, _F.FIELD),
            )
            return False
        return True

    def _validate_source_field_value_cast(
        self,
        field_id: str,
        field_data: Dict[str, Any],
        errors: List[ValidationIssue],
        field_path: str,
    ) -> None:
        if _F.VALUE_CAST not in field_data:
            return
        value_cast = str(field_data.get(_F.VALUE_CAST))
        if value_cast not in VALUE_CAST_ENUM:
            self._add_error(
                errors,
                "Field '{}' has invalid value_cast '{}'. Must be one of: {}".format(
                    field_id,
                    value_cast,
                    ", ".join(VALUE_CAST_ENUM),
                ),
                path="{}.{}".format(field_path, _F.VALUE_CAST),
            )

    def _validate_field_relation(
        self,
        field_id: str,
        relation_val: Any,
        source_id: str,
        main_source_id: str,
        sources_set: Set[str],
        sources_info: Dict[str, Dict[str, bool]],
        errors: List[ValidationIssue],
        field_path: str,
    ) -> None:
        if isinstance(relation_val, dict):
            relation_dict = cast("Dict[str, Any]", relation_val)
            steps_val = relation_dict.get(_F.STEPS)
            steps = self._validate_steps(steps_val, sources_set, errors, field_path)
            if steps:
                self._validate_relation_path(field_id, source_id, main_source_id, steps, errors, field_path)
                self._validate_steps_binding_requirements(steps, sources_info, errors, field_path)
            return
        if isinstance(relation_val, str):
            self._add_error(
                errors,
                "Field '{}' relation must be steps object or alias (relation_id is not supported)".format(field_id),
                path="{}.{}".format(field_path, _F.RELATION),
            )
            return

        self._add_error(
            errors,
            "Field '{}' relation must be {{steps: [...]}}".format(field_id),
            path="{}.{}".format(field_path, _F.RELATION),
        )

    def _track_duplicate_source_field(
        self,
        source_id: str,
        field_id: str,
        field_dict: Dict[str, Any],
        duplicates: Dict[str, Set[str]],
        seen_values: Dict[str, Dict[str, str]],
    ) -> None:
        field_value_raw = field_dict.get(_F.FIELD)
        field_value = str(field_value_raw) if field_value_raw is not None else field_id
        source_dups = duplicates.setdefault(source_id, set())
        source_seen = seen_values.setdefault(source_id, {})
        if field_value in source_seen and source_seen[field_value] != field_id:
            source_dups.add(field_value)
        else:
            source_seen[field_value] = field_id
