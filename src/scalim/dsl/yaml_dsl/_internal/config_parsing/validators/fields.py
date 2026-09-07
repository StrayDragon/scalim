from typing import Any, cast

from ....schema_dsl.constants import FIELD_KIND_SOURCE
from ..call_by import extract_call_by_dependencies
from ..models import AliasIndex, FieldDef, RawDemand
from ._internal.validator_fields_derived import ValidatorFieldDerivedMixin
from ._internal.validator_fields_source import ValidatorFieldSourceMixin
from .constants import F
from .issues import ValidationIssue


class ValidatorFieldsMixin(ValidatorFieldSourceMixin, ValidatorFieldDerivedMixin):
    def _validate_fields(
        self,
        raw: RawDemand,
        errors: list[ValidationIssue],
        sources_info: dict[str, dict[str, bool]],
        main_source_id: str,
        relation_paths: dict[str, list[tuple[str, str, bool]]],
    ) -> None:
        sources_set: set[str] = set(sources_info.keys())
        if main_source_id:
            sources_set.add(main_source_id)

        field_defs: list[FieldDef] = []
        defs_by_id: dict[str, list[FieldDef]] = {}
        alias_index = AliasIndex()
        derived_fields_with_deps: list[tuple[str, list[str], str]] = []
        duplicate_fields_by_source: dict[str, set[str]] = {}
        seen_field_values_by_source: dict[str, dict[str, str]] = {}

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
        self._validate_source_field_default_call_by_dependencies_pre_ref(
            field_defs=field_defs,
            defs_by_id=defs_by_id,
            derived_fields_with_deps=derived_fields_with_deps,
            errors=errors,
            main_source_id=main_source_id,
        )

    def _validate_unique_field_ids(self, defs_by_id: dict[str, list[FieldDef]], errors: list[ValidationIssue]) -> None:
        for field_id, defs in defs_by_id.items():
            if len(defs) <= 1:
                continue
            self._add_error(
                errors,
                (
                    f"Field '{field_id}' is defined multiple times; field_id must be unique "
                    "(output.fields disambiguation has been removed; rename the field_id)"
                ),
                path="(fields)",
            )

    def _validate_source_field_default_call_by_dependencies_pre_ref(  # noqa: C901, PLR0912, PLR0915  # pragma: allow-c901 plan: c0
        self,
        *,
        field_defs: list[FieldDef],
        defs_by_id: dict[str, list[FieldDef]],
        derived_fields_with_deps: list[tuple[str, list[str], str]],
        errors: list[ValidationIssue],
        main_source_id: str,
    ) -> None:
        if not main_source_id:
            return

        # `pre-ref` 可用字段: `main_source` 的非 `ref` 源字段.
        pre_ref_available: set[str] = set()
        for field_def in field_defs:
            if field_def.kind != FIELD_KIND_SOURCE:
                continue
            if (field_def.source_id or "") != str(main_source_id):
                continue
            if field_def.data.get(F.RELATION) is not None:
                continue
            pre_ref_available.add(str(field_def.field_id))

        # `pre-ref` 派生字段: 仅依赖 `pre_ref_available` 或 `pre_ref_derived` 的派生字段.
        derived_deps_by_id: dict[str, tuple[str, ...]] = {str(fid): tuple(deps) for fid, deps, _path in derived_fields_with_deps}
        pre_ref_derived: set[str] = set()
        for fid, deps, _path in derived_fields_with_deps:
            if not deps:
                pre_ref_derived.add(str(fid))

        changed = True
        while changed:
            changed = False
            for fid, deps in derived_deps_by_id.items():
                if fid in pre_ref_derived:
                    continue
                if all((dep in pre_ref_available or dep in pre_ref_derived) for dep in deps):
                    pre_ref_derived.add(str(fid))
                    changed = True

        allowed_deps = set(pre_ref_available) | set(pre_ref_derived)

        for field_def in field_defs:
            if field_def.kind != FIELD_KIND_SOURCE:
                continue
            default_raw = field_def.data.get(F.DEFAULT)
            if default_raw is None or not isinstance(default_raw, list):
                continue
            default_cases = cast("list[object]", default_raw)  # pragma: allow-cast yaml scalar list boundary

            if (field_def.source_id or "") == str(main_source_id):
                base_path = f"main_source.fields.{field_def.field_id}"
            else:
                base_path = f"sources.{field_def.source_id}.fields.{field_def.field_id}"

            for idx, case_raw in enumerate(default_cases):
                if not isinstance(case_raw, dict):
                    continue
                case_dict = cast("dict[str, Any]", case_raw)  # pragma: allow-cast yaml mapping boundary
                call_by_raw = case_dict.get("call_by")
                if not isinstance(call_by_raw, str) or not call_by_raw.strip():
                    continue

                used_fields = extract_call_by_dependencies(call_by_raw)

                for dep in used_fields:
                    dep_key = str(dep)
                    if dep_key in allowed_deps:
                        continue

                    dep_defs = defs_by_id.get(dep_key, [])
                    dep_kind = dep_defs[0].kind if len(dep_defs) == 1 else ""
                    dep_source_id = dep_defs[0].source_id if len(dep_defs) == 1 else None
                    extra = ""
                    if dep_kind == FIELD_KIND_SOURCE:
                        extra = " (it is a source field; only main_source non-ref fields are allowed)"
                    elif dep_kind:
                        extra = f" (kind={dep_kind})"
                    if dep_source_id and dep_source_id != str(main_source_id):
                        extra = f"{extra} (source_id={dep_source_id!r})"

                    msg = (
                        f"Field '{field_def.field_id!s}' default.call_by depends on '{dep_key}' which is not pre-ref computable{extra}. "
                        "default.call_by is only allowed to depend on main_source non-ref fields "
                        "and derived fields that only depend on those."
                    )
                    self._add_error(
                        errors,
                        msg,
                        path=f"{base_path}.default.{int(idx)}.call_by",
                    )


__all__ = ()
