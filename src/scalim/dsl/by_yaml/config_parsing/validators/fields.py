from typing import Dict, List, Set, Tuple

from ..models import AliasIndex, FieldDef, RawDemand
from ._internal.validator_fields_derived import ValidatorFieldDerivedMixin
from ._internal.validator_fields_source import ValidatorFieldSourceMixin
from .issues import ValidationIssue


class ValidatorFieldsMixin(ValidatorFieldSourceMixin, ValidatorFieldDerivedMixin):
    def _validate_fields(
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

        self._collect_main_source_fields(
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
        self._collect_source_fields(
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
        self._collect_derived_fields(
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
        self._validate_unique_field_ids(defs_by_id, errors)

    def _validate_unique_field_ids(self, defs_by_id: Dict[str, List[FieldDef]], errors: List[ValidationIssue]) -> None:
        for field_id, defs in defs_by_id.items():
            if len(defs) <= 1:
                continue
            self._add_error(
                errors,
                (
                    "Field '{}' is defined multiple times; field_id must be unique "
                    "(output.fields disambiguation has been removed; rename the field_id)"
                ).format(field_id),
                path="(fields)",
            )


__all__ = ["ValidatorFieldsMixin"]
