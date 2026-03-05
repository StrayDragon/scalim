# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false, reportAttributeAccessIssue=false, reportUnknownMemberType=false, reportUninitializedInstanceVariable=false

from typing import Any, Dict, List, Optional, Set, Tuple, cast

from .....vendor.compact.typing_extensionsx import override
from ...schema_dsl.constants import FIELD_KIND_DERIVED, FIELD_KIND_SOURCE, VALUE_CAST_ENUM
from ...schema_dsl.models import DEMAND_KEYS, OUTPUT_KEYS
from ..call_by import CallByParseError, extract_call_by_dependencies, parse_call_by
from ..field_index import OutputFieldErrors, OutputFieldResolver, build_source_data_key_index
from ..models import AliasIndex, FieldDef, RawDemand
from ..security import (
    ComputeExpressionError,
    SecureComputeEngine,
    SecurityError,
    extract_compute_dependencies,
    is_constant_compute_expression,
)
from .constants import F
from .issues import ValidationIssue

_F = F

_RESERVED_FIELD_IDS = frozenset(
    set(SecureComputeEngine.SAFE_BUILTINS)
    | set(SecureComputeEngine.FORBIDDEN_NAMES)
    | {
        "True",
        "False",
        "None",
    }
)


class OutputFieldIssueCollector(OutputFieldErrors):
    _errors: List["ValidationIssue"]
    _base_path: str
    _current_path: str

    def __init__(self, errors: List[ValidationIssue], base_path: str) -> None:
        self._errors = errors
        self._base_path = base_path
        self._current_path = base_path

    def set_index(self, idx: int) -> None:
        self._current_path = "{}.{}".format(self._base_path, idx)

    @override
    def type_error(self, msg: str) -> None:
        self._errors.append(ValidationIssue(severity="error", message=msg, path=self._current_path))

    @override
    def value_error(self, msg: str) -> None:
        self._errors.append(ValidationIssue(severity="error", message=msg, path=self._current_path))

    @override
    def error(self, msg: str) -> None:
        self._errors.append(ValidationIssue(severity="error", message=msg, path=self._current_path))


class ValidatorFieldsMixin:
    _compute_engine: Any

    def _validate_field_id_not_reserved(self, field_id: str, errors: List[ValidationIssue], *, path: str) -> None:
        if field_id not in _RESERVED_FIELD_IDS:
            return
        msg = (
            "Field '{}' uses a reserved name that conflicts with compute builtins/constants. "
            "Rename the field_id to avoid ambiguous or broken compute dependency resolution (e.g. '{}_value')."
        ).format(field_id, field_id)
        self._add_error(errors, msg, path=path)

    def _validate_fields(
        self,
        raw: RawDemand,
        errors: List[ValidationIssue],
        sources_info: Dict[str, Dict[str, bool]],
        main_source_id: str,
        relation_paths: Dict[str, List[Tuple[str, str, bool]]],
    ) -> None:
        self._validate_fields_v3(raw, errors, sources_info, main_source_id, relation_paths)

    def _validate_fields_v3(
        self,
        raw: RawDemand,
        errors: List[ValidationIssue],
        sources_info: Dict[str, Dict[str, bool]],
        main_source_id: str,
        relation_paths: Dict[str, List[Tuple[str, str, bool]]],
    ) -> None:
        sources_set: Set[str] = set(sources_info.keys())
        if main_source_id:
            sources_set.add(main_source_id)

        field_defs: List[FieldDef] = []
        defs_by_id: Dict[str, List[FieldDef]] = {}
        alias_index = AliasIndex()
        derived_fields_with_deps: List[Tuple[str, List[str], str]] = []
        duplicate_fields_by_source: Dict[str, Set[str]] = {}
        seen_field_values_by_source: Dict[str, Dict[str, str]] = {}

        self._collect_main_source_fields_v3(
            raw,
            errors,
            sources_set,
            sources_info,
            main_source_id,
            relation_paths,
            field_defs,
            defs_by_id,
            alias_index,
            duplicate_fields_by_source,
            seen_field_values_by_source,
        )
        self._collect_source_fields_v3(
            raw,
            errors,
            sources_set,
            sources_info,
            main_source_id,
            relation_paths,
            field_defs,
            defs_by_id,
            alias_index,
            duplicate_fields_by_source,
            seen_field_values_by_source,
        )
        self._collect_derived_fields_v3(
            raw,
            errors,
            field_defs,
            defs_by_id,
            alias_index,
            derived_fields_with_deps,
        )

        self._validate_source_field_id_data_key_conflicts(field_defs, errors, main_source_id)
        self._validate_no_derived_source_overlap(defs_by_id, errors)
        self._validate_derived_dependencies(derived_fields_with_deps, defs_by_id, errors)
        self._validate_output_fields_v3(raw, errors, defs_by_id, alias_index, duplicate_fields_by_source)

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

    def _collect_derived_fields_v3(
        self,
        raw: RawDemand,
        errors: List[ValidationIssue],
        field_defs: List[FieldDef],
        defs_by_id: Dict[str, List[FieldDef]],
        alias_index: AliasIndex,
        derived_fields_with_deps: List[Tuple[str, List[str], str]],
    ) -> None:
        raw_fields_val = raw.data.get(_F.FIELDS)
        if raw_fields_val is None:
            return
        if not isinstance(raw_fields_val, dict):
            self._add_error(errors, "'{}' must be a dictionary".format(_F.FIELDS), path=_F.FIELDS)
            return
        raw_fields = raw_fields_val

        for field_id_raw, field_data_raw in raw_fields.items():
            if not isinstance(field_data_raw, dict):
                self._add_error(errors, "Field '{}' must be a dictionary".format(field_id_raw), path="fields.{}".format(field_id_raw))
                continue
            field_dict = cast("Dict[str, Any]", field_data_raw)
            has_compute = _F.COMPUTE in field_dict
            has_call_by = _F.CALL_BY in field_dict
            if not has_compute and not has_call_by:
                self._add_error(
                    errors,
                    "v3 fields '{}' only allow derived fields with compute/call_by".format(field_id_raw),
                    path="fields.{}".format(field_id_raw),
                )
                continue
            self._validate_field_id_not_reserved(
                str(field_id_raw),
                errors,
                path="fields.{}".format(field_id_raw),
            )
            _ = self._add_field_def_v3(
                field_id_raw,
                FIELD_KIND_DERIVED,
                None,
                field_data_raw,
                field_defs,
                defs_by_id,
                alias_index,
                errors,
            )
            self._validate_derived_field(field_id=str(field_id_raw), field_data=field_dict, errors=errors)
            deps, dep_path = self._resolve_derived_dependencies(field_id=str(field_id_raw), field_dict=field_dict)
            derived_fields_with_deps.append((str(field_id_raw), deps, dep_path))

    def _validate_no_derived_source_overlap(
        self,
        defs_by_id: Dict[str, List[FieldDef]],
        errors: List[ValidationIssue],
    ) -> None:
        for field_id, defs in defs_by_id.items():
            kinds = {field_def.kind for field_def in defs}
            if FIELD_KIND_DERIVED in kinds and FIELD_KIND_SOURCE in kinds:
                self._add_error(
                    errors,
                    "Field '{}' is defined as both source and derived; use unique field_id".format(field_id),
                    path="fields.{}".format(field_id),
                )

    def _validate_derived_field(self, field_id: str, field_data: Dict[str, Any], errors: List[ValidationIssue]) -> None:
        has_compute = _F.COMPUTE in field_data
        has_call_by = _F.CALL_BY in field_data
        if has_compute == has_call_by:
            if has_compute:
                msg = "Derived field '{}' must not declare both '{}' and '{}'".format(field_id, _F.COMPUTE, _F.CALL_BY)
            else:
                msg = "Derived field '{}' must declare '{}' or '{}'".format(field_id, _F.COMPUTE, _F.CALL_BY)
            self._add_error(errors, msg, path="fields.{}".format(field_id))
            return

        if _F.DEPENDS_ON in field_data:
            self._add_error(
                errors,
                "Derived field '{}' does not allow '{}'; dependencies are inferred from '{}'/'{}'".format(
                    field_id,
                    _F.DEPENDS_ON,
                    _F.COMPUTE,
                    _F.CALL_BY,
                ),
                path="fields.{}.{}".format(field_id, _F.DEPENDS_ON),
            )

        if has_compute:
            self._validate_derived_field_compute(field_id=field_id, field_data=field_data, errors=errors)
        else:
            self._validate_derived_field_call_by(field_id=field_id, field_data=field_data, errors=errors)

    def _validate_derived_field_compute(
        self,
        field_id: str,
        field_data: Dict[str, Any],
        errors: List[ValidationIssue],
    ) -> None:
        compute_val = field_data.get(_F.COMPUTE)
        if not isinstance(compute_val, str):
            self._add_error(
                errors,
                "Derived field '{}' compute must be a string".format(field_id),
                path="fields.{}.{}".format(field_id, _F.COMPUTE),
            )
            return
        self._validate_derived_expression(field_id, compute_val, errors)

    def _validate_derived_field_call_by(
        self,
        field_id: str,
        field_data: Dict[str, Any],
        errors: List[ValidationIssue],
    ) -> None:
        call_by_val = field_data.get(_F.CALL_BY)
        if not isinstance(call_by_val, str):
            self._add_error(
                errors,
                "Derived field '{}' call_by must be a string".format(field_id),
                path="fields.{}.{}".format(field_id, _F.CALL_BY),
            )
            return
        if not call_by_val:
            self._add_error(
                errors,
                "Derived field '{}' call_by must not be empty".format(field_id),
                path="fields.{}.{}".format(field_id, _F.CALL_BY),
            )
            return

        try:
            parsed = parse_call_by(call_by_val)
        except CallByParseError as exc:
            self._add_error(
                errors,
                "Derived field '{}' has invalid call_by: {}".format(field_id, exc),
                path="fields.{}.{}".format(field_id, _F.CALL_BY),
            )
            return

        used_fields = list(parsed.field_names)
        if not used_fields:
            self._add_error(
                errors,
                "Derived field '{}' call_by has no field dependencies".format(field_id),
                path="fields.{}.{}".format(field_id, _F.CALL_BY),
            )

    def _validate_derived_expression(
        self,
        field_id: str,
        compute_expr: str,
        errors: List[ValidationIssue],
    ) -> None:
        if not compute_expr:
            self._add_error(
                errors,
                "Derived field '{}' compute must not be empty".format(field_id),
                path="fields.{}.{}".format(field_id, _F.COMPUTE),
            )
            return
        dependencies = tuple(extract_compute_dependencies(compute_expr))
        try:
            _ = self._compute_engine.compile(compute_expr, dependencies)
        except (SecurityError, ComputeExpressionError) as exc:
            self._add_error(
                errors,
                "Derived field '{}' has invalid compute expression: {}".format(field_id, exc),
                path="fields.{}.{}".format(field_id, _F.COMPUTE),
            )
            return

        if not dependencies and not is_constant_compute_expression(compute_expr):
            self._add_error(
                errors,
                "Derived field '{}' compute has no field dependencies; only pure literal expressions are allowed".format(field_id),
                path="fields.{}.{}".format(field_id, _F.COMPUTE),
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

    def _validate_output_fields_v3(
        self,
        raw: RawDemand,
        errors: List[ValidationIssue],
        defs_by_id: Dict[str, List[FieldDef]],
        alias_index: AliasIndex,
        duplicate_fields_by_source: Dict[str, Set[str]],
    ) -> None:
        output_raw = raw.get_mapping(DEMAND_KEYS["output"])
        if output_raw is None:
            return
        fields_raw = output_raw.get(OUTPUT_KEYS["fields"])
        if fields_raw is None:
            self._validate_output_fields_required(defs_by_id, errors)
            return

        if not isinstance(fields_raw, list):
            self._add_error(errors, "output.fields must be a list", path="output.fields")
            return

        field_defs: List[FieldDef] = []
        for defs in defs_by_id.values():
            field_defs.extend(defs)
        defs_by_data_key_by_source = build_source_data_key_index(field_defs)

        collector = OutputFieldIssueCollector(errors, "output.fields")
        resolver = OutputFieldResolver(
            defs_by_id=defs_by_id,
            defs_by_data_key_by_source=defs_by_data_key_by_source,
            alias_index=alias_index,
            errors=collector,
        )
        seen: Dict[str, FieldDef] = {}
        for idx, item in enumerate(fields_raw):
            collector.set_index(idx)
            field_def, _override, entry_kind = resolver.resolve_entry(item, idx)
            if field_def is None:
                continue

            self._validate_output_field_source_ambiguity(field_def, entry_kind, duplicate_fields_by_source, errors)

            existing = seen.get(field_def.field_id)
            if existing is None:
                seen[field_def.field_id] = field_def
            elif existing is not field_def:
                self._add_error(
                    errors,
                    "Output field '{}' maps to multiple definitions; use unique field_id".format(field_def.field_id),
                    path="output.fields",
                )

    def _validate_output_fields_required(self, defs_by_id: Dict[str, List[FieldDef]], errors: List[ValidationIssue]) -> None:
        for field_id, defs in defs_by_id.items():
            if len(defs) > 1:
                self._add_error(
                    errors,
                    "output.fields is required to disambiguate field '{}' (note: top-level output is optional)".format(field_id),
                    path="output.fields",
                )

    def _validate_output_field_source_ambiguity(
        self,
        field_def: FieldDef,
        entry_kind: str,
        duplicate_fields_by_source: Dict[str, Set[str]],
        errors: List[ValidationIssue],
    ) -> None:
        if entry_kind not in {"string", "signature"}:
            return
        if field_def.kind != FIELD_KIND_SOURCE:
            return  # pragma: no cover
        source_id = field_def.source_id or ""
        dup_fields = duplicate_fields_by_source.get(source_id, set())
        field_value_raw = field_def.data.get(_F.FIELD)
        field_value = str(field_value_raw) if field_value_raw is not None else field_def.field_id
        if field_value in dup_fields:
            self._add_error(
                errors,
                "Output field '{}' is ambiguous in source '{}'; use single-key mapping or alias".format(
                    field_def.field_id,
                    source_id,
                ),
                path="output.fields",
            )

    def _validate_derived_dependencies(
        self,
        derived_fields_with_deps: List[Tuple[str, List[str], str]],
        defs_by_id: Dict[str, List[FieldDef]],
        errors: List[ValidationIssue],
    ) -> None:
        for field_id, depends_on, dep_path in derived_fields_with_deps:
            for dep in depends_on:
                dep_str = str(dep)
                matched = defs_by_id.get(dep_str, [])
                if not matched:
                    self._add_error(
                        errors,
                        "Derived field '{}' depends on unknown field '{}'".format(field_id, dep_str),
                        path=dep_path,
                    )
                elif len(matched) > 1:
                    self._add_error(
                        errors,
                        "Derived field '{}' depends on ambiguous field '{}'".format(field_id, dep_str),
                        path=dep_path,
                    )

    def _resolve_derived_dependencies(self, *, field_id: str, field_dict: Dict[str, Any]) -> Tuple[List[str], str]:
        compute_raw = field_dict.get(_F.COMPUTE)
        compute_expr = str(compute_raw or "")
        if compute_expr:
            return extract_compute_dependencies(compute_expr), "fields.{}.{}".format(field_id, _F.COMPUTE)

        call_by_raw = field_dict.get(_F.CALL_BY)
        call_by_expr = str(call_by_raw or "")
        if call_by_expr:
            return extract_call_by_dependencies(call_by_expr), "fields.{}.{}".format(field_id, _F.CALL_BY)

        return [], "fields.{}".format(field_id)

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
