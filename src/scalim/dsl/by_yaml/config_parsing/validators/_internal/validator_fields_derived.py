from typing import Any, Dict, List, Tuple

from ....schema_dsl.constants import FIELD_KIND_DERIVED, FIELD_KIND_SOURCE
from ...call_by import CallByParseError, extract_call_by_dependencies, parse_call_by
from ...models import AliasIndex, FieldDef, RawDemand
from ...parsers.utils import mapping_or_none
from ...security import ComputeExpressionError, SecurityError, extract_compute_dependencies, is_constant_compute_expression
from ..base import ValidatorFieldBaseMixin
from ..constants import F
from ..issues import ValidationIssue

_F = F


class ValidatorFieldDerivedMixin(ValidatorFieldBaseMixin):
    def _collect_derived_fields(
        self,
        raw: RawDemand,
        errors: List[ValidationIssue],
        field_defs: List[FieldDef],
        defs_by_id: Dict[str, List[FieldDef]],
        alias_index: AliasIndex,
        derived_fields_with_deps: List[Tuple[str, List[str], str]],
    ) -> None:
        raw_fields_value = raw.data.get(_F.FIELDS)
        if raw_fields_value is None:
            return
        raw_fields = mapping_or_none(raw_fields_value)
        if raw_fields is None:
            self._add_error(errors, "'{}' must be a dictionary".format(_F.FIELDS), path=_F.FIELDS)
            return

        for field_id_raw, field_data_raw in raw_fields.items():
            field_id = str(field_id_raw)
            field_dict = mapping_or_none(field_data_raw)
            if field_dict is None:
                self._add_error(errors, "Field '{}' must be a dictionary".format(field_id), path="fields.{}".format(field_id))
                continue
            has_compute = _F.COMPUTE in field_dict
            has_call_by = _F.CALL_BY in field_dict
            if not has_compute and not has_call_by:
                self._add_error(
                    errors,
                    "Derived field '{}' must declare compute/call_by".format(field_id),
                    path="fields.{}".format(field_id),
                )
                continue
            self._validate_field_id_not_reserved(field_id, errors, path="fields.{}".format(field_id))
            _ = self._add_field_def(
                field_id,
                FIELD_KIND_DERIVED,
                None,
                field_dict,
                field_defs,
                defs_by_id,
                alias_index,
                errors,
            )
            self._validate_derived_field(field_id=field_id, field_data=field_dict, errors=errors)
            deps, dep_path = self._resolve_derived_dependencies(field_id=field_id, field_dict=field_dict)
            derived_fields_with_deps.append((field_id, deps, dep_path))

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
            _ = self._require_compute_engine().compile(compute_expr, dependencies)
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
