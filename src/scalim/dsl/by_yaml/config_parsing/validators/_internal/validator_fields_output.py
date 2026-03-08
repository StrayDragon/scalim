from typing import Any, Dict, List, Set, cast

from ......vendor.compact.typing_extensionsx import override
from ....schema_dsl.constants import FIELD_KIND_SOURCE
from ....schema_dsl.models import DEMAND_KEYS, OUTPUT_KEYS
from ...field_index import OutputFieldErrors, OutputFieldResolver, build_source_data_key_index
from ...models import AliasIndex, FieldDef, RawDemand
from ..base import ValidatorMixinBase
from ..issues import ValidationIssue


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


class ValidatorFieldOutputMixin(ValidatorMixinBase):
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
        fields_list = cast("List[Any]", fields_raw)

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
        for idx, item in enumerate(fields_list):
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
            return
        source_id = field_def.source_id or ""
        dup_fields = duplicate_fields_by_source.get(source_id, set())
        field_value_raw = field_def.data.get("field")
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
