# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false, reportAttributeAccessIssue=false, reportUnknownMemberType=false, reportUninitializedInstanceVariable=false

from typing import Any, Dict, List, Set, Tuple

from ..models import AliasIndex, FieldDef, RawDemand
from ..security import SecureComputeEngine
from ._internal.validator_fields_derived import ValidatorFieldDerivedMixin
from ._internal.validator_fields_output import OutputFieldIssueCollector, ValidatorFieldOutputMixin
from ._internal.validator_fields_source import ValidatorFieldSourceMixin
from .issues import ValidationIssue

_RESERVED_FIELD_IDS = frozenset(
    set(SecureComputeEngine.SAFE_BUILTINS)
    | set(SecureComputeEngine.FORBIDDEN_NAMES)
    | {
        "True",
        "False",
        "None",
    }
)


class ValidatorFieldsMixin(ValidatorFieldSourceMixin, ValidatorFieldDerivedMixin, ValidatorFieldOutputMixin):
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


__all__ = ["OutputFieldIssueCollector", "ValidatorFieldsMixin"]
