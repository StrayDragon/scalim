# pragma: allow-c901-file plan: c60

import re
from typing import Any

from ....params_template import ScalimParamsTemplateCompileError, compile_params_template
from ....reference_syntax import REFERENCE_FORMAT_EXAMPLES, is_valid_callable_reference
from ....schema_dsl.constants import (
    DEFAULT_CACHE_MODE,
    LOOKUP_CAST_NAME_ENUM,
    NORMALIZE_KIND_ENUM,
    NORMALIZE_ON_CONFLICT_ENUM,
    NORMALIZE_ON_EMPTY_ENUM,
    NORMALIZE_ON_MISSING_ENUM,
    NORMALIZE_ON_NONE_ENUM,
    SOURCE_ID_STRING_SCHEMA,
)
from ..field_extract import ScalimFieldExtractCompileError, compile_field_extract, derive_source_field_data_key
from ..parsers.utils import list_or_none, mapping_or_none
from .base import ValidatorMixinBase
from .constants import LEGACY_FIELDS, F
from .issues import ValidationIssue

_F = F
_SOURCE_ID_PATTERN_TEXT = str(SOURCE_ID_STRING_SCHEMA.get("pattern") or r"^[a-zA-Z_][a-zA-Z0-9_]*$")
_SOURCE_ID_PATTERN = re.compile(_SOURCE_ID_PATTERN_TEXT)
_IMPORT_KEY = "$import"


class ValidatorSourcesMixin(ValidatorMixinBase):
    _step_field_ids_by_source_data_key: dict[str, dict[str, set[str]]]

    @staticmethod
    def _build_lookup_cast_legacy_migration_hint(lookup_path: str, lookup_dict: dict[str, Any]) -> str:
        legacy_name = str(lookup_dict.get("name") or "").strip()
        legacy_sep = lookup_dict.get("sep")

        suggested: str | None = None
        if legacy_name in {"auto", "int", "str"}:
            suggested = f"lookup_cast: {{{legacy_name}: {{}}}}"
        elif legacy_name == "sep_first":
            sep = legacy_sep if isinstance(legacy_sep, str) else None
            if sep:
                suggested = f"lookup_cast: {{sep_first: {{sep: {sep!r}}}}}"
            else:
                suggested = "lookup_cast: {sep_first: {}}"

        msg = (
            f"Legacy YAML syntax is not supported: '{lookup_path}'. "
            "Replace `lookup_cast: {name: ...}` with a one-of cast-branch object."
            "\nMigration examples:\n"
            "  lookup_cast: {auto: {}}\n"
            "  lookup_cast: {int: {}}\n"
            "  lookup_cast: {str: {}}\n"
            '  lookup_cast: {sep_first: {sep: ","}}'
        )
        if suggested:
            msg = f"{msg}\nSuggested:\n  {suggested}"
        return msg

    @staticmethod
    def _build_normalize_legacy_migration_hint(norm_path: str, norm_dict: dict[str, Any]) -> str:
        legacy_kind = str(norm_dict.get(_F.NORMALIZE_KIND) or "").strip()
        suggested_branch = legacy_kind if legacy_kind in set(NORMALIZE_KIND_ENUM) else "index_by_key"

        suggested = f"normalize: {{{suggested_branch}: {{...}}}}"
        if _F.NORMALIZE_CALL_BY in norm_dict:
            suggested = "normalize: {call_by: <ref>, " + f"{suggested_branch}: {{...}}" + "}"

        msg = (
            f"Legacy YAML syntax is not supported: '{norm_path}'. "
            "Replace `normalize: {kind: <...>, ...}` with a one-of normalize-branch object."
            "\nMigration:\n"
            "  normalize: {kind: index_by_key, ...} -> normalize: {index_by_key: {...}}\n"
            "  normalize: {kind: take_first, ...} -> normalize: {take_first: {...}}\n"
            "  normalize: {kind: project_fields, ...} -> normalize: {project_fields: {...}}\n"
            "  normalize: {kind: map_values, ...} -> normalize: {map_values: {...}}\n"
            "\nExamples:\n"
            "  normalize: {index_by_key: {on_conflict: error}}\n"
            "  normalize: {take_first: {on_empty: miss}}\n"
            "  normalize: {project_fields: {fields: {id: {from_key: true}}}}\n"
            "  normalize: {map_values: {steps: [{take_first: {}}]}}\n"
            '  normalize: {call_by: "myapp.normalizes:normalize_source_x", index_by_key: {}}'
        )
        return f"{msg}\nSuggested:\n  {suggested}"

    @staticmethod
    def _build_normalize_step_legacy_migration_hint(step_path: str, step_dict: dict[str, Any]) -> str:
        legacy_kind = str(step_dict.get(_F.NORMALIZE_KIND) or "").strip()
        suggested_branch = legacy_kind if legacy_kind in {"take_first", "project_fields"} else "take_first"

        msg = (
            f"Legacy YAML syntax is not supported: '{step_path}.kind'. "
            "Replace `steps: [{kind: <...>, ...}]` with one-of step-branch objects."
            "\nMigration:\n"
            "  steps: [{kind: take_first, ...}] -> steps: [{take_first: {...}}]\n"
            "  steps: [{kind: project_fields, ...}] -> steps: [{project_fields: {...}}]"
        )
        return f"{msg}\nSuggested:\n  steps: [{{{suggested_branch}: {{...}}}}]"

    def _collect_field_data_key_map(self, fields_raw: Any) -> dict[str, set[str]]:
        data_key_map: dict[str, set[str]] = {}
        fields_dict = mapping_or_none(fields_raw)
        if fields_dict is None:
            return data_key_map
        for field_id_raw, field_data_raw in fields_dict.items():
            field_id = str(field_id_raw or "").strip()
            if not field_id:
                continue
            field_dict = mapping_or_none(field_data_raw)
            extract_val = None
            if field_dict is not None:
                extract_val = field_dict.get(_F.EXTRACT)
            extract_expr = None if extract_val is None else str(extract_val)
            data_key = derive_source_field_data_key(field_id=field_id, extract=extract_expr)
            data_key_map.setdefault(data_key, set()).add(field_id)
        return data_key_map

    def _validate_params_template_semantics(
        self,
        params_raw: Any,
        errors: list[ValidationIssue],
        *,
        path: str,
        allow_directives: bool,
    ) -> None:
        params_dict = mapping_or_none(params_raw)
        if params_raw is not None and params_dict is None:
            self._add_error(errors, f"'{path}' must be a dictionary", path=path)
            return
        try:
            _ = compile_params_template(
                params_dict or {},
                path=path,
                resolve_runtime=False,  # `init_vars` 在 `run/compile` 时提供,`YAML` 校验阶段不解析.
                allow_keys=allow_directives,
                allow_rows=allow_directives,
            )
        except ScalimParamsTemplateCompileError as exc:
            self._add_error(errors, exc.message, path=exc.path)

    def _collect_declared_field_names(self, fields_raw: Any) -> set[str]:
        names: set[str] = set()
        fields_dict = mapping_or_none(fields_raw)
        if fields_dict is None:
            return names
        for field_id_raw in fields_dict:
            field_id = str(field_id_raw or "").strip()
            if field_id:
                names.add(field_id)
        return names

    def _collect_source_key_names(self, key_raw: Any) -> set[str]:
        names: set[str] = set()
        key_list = list_or_none(key_raw)
        if key_list is not None:
            for item in key_list:
                key_field = str(item or "").strip()
                if key_field:
                    names.add(key_field)
            return names
        if isinstance(key_raw, str):
            key_field = key_raw.strip()
            if key_field:
                names.add(key_field)
        return names

    def _collect_step_allowed_fields(self, config: dict[str, Any], main_source_id: str) -> dict[str, set[str]]:
        allowed: dict[str, set[str]] = {}
        suggestions: dict[str, dict[str, set[str]]] = {}

        if main_source_id:
            main_dict = mapping_or_none(config.get(_F.MAIN_SOURCE))
            if main_dict is not None:
                allowed[main_source_id] = self._collect_declared_field_names(main_dict.get(_F.FIELDS))
                suggestions[main_source_id] = self._collect_field_data_key_map(main_dict.get(_F.FIELDS))
            else:
                allowed[main_source_id] = set()
                suggestions[main_source_id] = {}

        sources_raw = mapping_or_none(config.get(_F.SOURCES, {}))
        if sources_raw is None:
            self._step_field_ids_by_source_data_key = suggestions
            return allowed

        for source_id_raw, source_data_raw in sources_raw.items():
            source_id = str(source_id_raw)
            source_dict = mapping_or_none(source_data_raw)
            if source_dict is None:
                allowed[source_id] = set()
                suggestions[source_id] = {}
                continue
            source_allowed = self._collect_declared_field_names(source_dict.get(_F.FIELDS))
            source_allowed.update(self._collect_source_key_names(source_dict.get(_F.KEY)))
            allowed[source_id] = source_allowed
            suggestions[source_id] = self._collect_field_data_key_map(source_dict.get(_F.FIELDS))

        self._step_field_ids_by_source_data_key = suggestions
        return allowed

    def _validate_required_fields(self, config: dict[str, Any], errors: list[ValidationIssue]) -> None:
        required_fields = [_F.NAME, _F.MAIN_SOURCE]
        for field_name in required_fields:
            if field_name not in config:
                self._add_error(errors, f"Missing required field: '{field_name}'", path=field_name)

    def _validate_legacy_fields(self, config: dict[str, Any], errors: list[ValidationIssue]) -> None:  # noqa: C901, PLR0912
        if "output" in config:
            self._add_error(
                errors,
                (
                    "Legacy YAML syntax is not supported: top-level 'output'. "
                    "Upgrade to 'outputs' (list) and move output settings into 'outputs.*.to' / 'outputs.*.write'.\n\n"
                    "Minimal migration:\n"
                    "  resources:\n"
                    "    books:\n"
                    "      report: {xlsx: {path: ./output}}\n"
                    "  outputs:\n"
                    "    - name: detail\n"
                    "      to: {book: report, sheet: Detail}\n"
                    "      fields: [field_id, ...]"
                ),
                path="output",
            )

        for key in config:
            if key in LEGACY_FIELDS:
                self._add_error(errors, f"Legacy field '{key}' is not allowed", path=str(key))

        sources_raw = mapping_or_none(config.get(_F.SOURCES, {}))
        if sources_raw is not None:
            for source_id_raw, source_data_raw in sources_raw.items():
                source_dict = mapping_or_none(source_data_raw)
                if source_dict is None:
                    continue
                source_id = str(source_id_raw)
                for key in source_dict:
                    if key in LEGACY_FIELDS:
                        path = f"sources.{source_id}.{key}"
                        self._add_error(errors, f"Legacy field '{path}' is not allowed", path=path)

        fields_raw = mapping_or_none(config.get(_F.FIELDS, {}))
        if fields_raw is not None:
            for field_id_raw, field_data_raw in fields_raw.items():
                field_dict = mapping_or_none(field_data_raw)
                if field_dict is None:
                    continue
                field_id = str(field_id_raw)
                for key in field_dict:
                    if key in LEGACY_FIELDS:
                        path = f"fields.{field_id}.{key}"
                        self._add_error(errors, f"Legacy field '{path}' is not allowed", path=path)

    def _validate_sources(  # noqa: C901, PLR0912, PLR0915
        self, config: dict[str, Any], errors: list[ValidationIssue]
    ) -> dict[str, dict[str, bool]]:
        sources_info: dict[str, dict[str, bool]] = {}
        sources_raw = mapping_or_none(config.get(_F.SOURCES))
        if sources_raw is None:
            return sources_info

        for source_id_raw, source_data_raw in sources_raw.items():
            source_id = str(source_id_raw)
            if source_id == _IMPORT_KEY:
                continue
            if not _SOURCE_ID_PATTERN.match(source_id):
                self._add_error(
                    errors,
                    f"sources key '{source_id}' must match identifier pattern: {_SOURCE_ID_PATTERN_TEXT}",
                    path=f"sources.{source_id}",
                )
                continue
            source_dict = mapping_or_none(source_data_raw)
            if source_dict is None:
                self._add_error(errors, f"Source '{source_id}' must be a dictionary", path=f"sources.{source_id}")
                continue

            if _F.LOADER not in source_dict:
                self._add_error(
                    errors,
                    f"Source '{source_id}' missing required field '{_F.LOADER}'",
                    path=f"sources.{source_id}.{_F.LOADER}",
                )

            if _F.KEY not in source_dict:
                self._add_error(
                    errors,
                    f"Source '{source_id}' missing required field '{_F.KEY}'",
                    path=f"sources.{source_id}.{_F.KEY}",
                )

            loader_raw = source_dict.get(_F.LOADER)
            loader_ref = str(loader_raw or "").strip()
            if _F.LOADER in source_dict and not loader_ref:
                self._add_error(
                    errors,
                    f"sources.{source_id}.{_F.LOADER} must not be empty",
                    path=f"sources.{source_id}.{_F.LOADER}",
                )
            elif loader_ref and not self._is_valid_loader_ref(loader_ref):
                msg = f"数据源 '{source_id}' 的 loader 引用 '{loader_raw}' 非法. 期望格式: {REFERENCE_FORMAT_EXAMPLES}"
                self._add_error(errors, msg, path=f"sources.{source_id}.{_F.LOADER}")

            key_raw = source_dict.get(_F.KEY)
            key_path = f"sources.{source_id}.{_F.KEY}"
            if _F.KEY in source_dict and key_raw is None:
                self._add_error(errors, f"{key_path} must be a non-empty field_id or field_id list", path=key_path)
            key_items = list_or_none(key_raw)
            if key_items is not None:
                if not key_items:
                    self._add_error(errors, f"{key_path} must not be empty", path=key_path)
                for idx, item in enumerate(key_items):
                    if not isinstance(item, str):
                        self._add_error(errors, f"{key_path}.{int(idx)} must be a string", path=f"{key_path}.{int(idx)}")
                        continue
                    key_field = item.strip()
                    if not key_field:
                        self._add_error(errors, f"{key_path}.{int(idx)} must not be empty", path=f"{key_path}.{int(idx)}")
                        continue
                    if not _SOURCE_ID_PATTERN.match(key_field):
                        self._add_error(
                            errors,
                            f"{key_path}.{int(idx)} must match field_id pattern: {_SOURCE_ID_PATTERN_TEXT}",
                            path=f"{key_path}.{int(idx)}",
                        )
            elif isinstance(key_raw, str):
                key_field = key_raw.strip()
                if not key_field:
                    self._add_error(errors, f"{key_path} must not be empty", path=key_path)
                elif not _SOURCE_ID_PATTERN.match(key_field):
                    self._add_error(
                        errors,
                        f"{key_path} must match field_id pattern: {_SOURCE_ID_PATTERN_TEXT}",
                        path=key_path,
                    )

            bind_raw = source_dict.get(_F.BIND)
            if bind_raw is not None:
                self._add_error(
                    errors,
                    (
                        f"Legacy YAML syntax is not supported: 'sources.{source_id}.bind'. "
                        f"Move binding into 'sources.{source_id}.params' using `$keys` / `$rows` directives."
                        "\nExample:\n"
                        "  params:\n"
                        "    ids:\n"
                        "      $keys: {as: set}"
                    ),
                    path=f"sources.{source_id}.{_F.BIND}",
                )

            lookup_raw = source_dict.get(_F.LOOKUP_CAST)
            if lookup_raw is not None:
                self._validate_lookup_cast(lookup_raw, errors, f"sources.{source_id}")

            cache_mode = str(source_dict.get(_F.CACHE_MODE, DEFAULT_CACHE_MODE))
            if cache_mode not in {"none", "preload_forever"}:
                self._add_error(
                    errors,
                    f"Source '{source_id}' has invalid cache_mode '{cache_mode}' (expected: none/preload_forever)",
                    path=f"sources.{source_id}.{_F.CACHE_MODE}",
                )

            normalize_raw = source_dict.get(_F.NORMALIZE)
            if normalize_raw is not None:
                self._validate_normalize(
                    normalize_raw,
                    errors,
                    path_prefix=f"sources.{source_id}",
                    source_id=source_id,
                    key_raw=source_dict.get(_F.KEY),
                )

            allow_directives = cache_mode != "preload_forever"
            self._validate_params_template_semantics(
                source_dict.get(_F.PARAMS),
                errors,
                path=f"sources.{source_id}.{_F.PARAMS}",
                allow_directives=allow_directives,
            )

            sources_info[source_id] = {
                "preload": cache_mode == "preload_forever",
            }

        return sources_info

    def _validate_main_source(self, config: dict[str, Any], errors: list[ValidationIssue]) -> str:
        main_source_data = mapping_or_none(config.get(_F.MAIN_SOURCE))
        if main_source_data is None:
            self._add_error(errors, f"'{_F.MAIN_SOURCE}' must be a dictionary", path=_F.MAIN_SOURCE)
            return ""

        if _F.NORMALIZE in main_source_data:
            self._add_error(
                errors,
                "`main_source.normalize` is not supported. Define `normalize` under `sources.<id>` instead.",
                path=f"{_F.MAIN_SOURCE}.{_F.NORMALIZE}",
            )

        source_id_raw = main_source_data.get(_F.SOURCE_ID, "")
        source_id = str(source_id_raw or "")
        loader_raw = main_source_data.get(_F.LOADER)
        loader_ref = str(loader_raw or "").strip()
        sources_raw = mapping_or_none(config.get(_F.SOURCES, {}))

        if not source_id:
            self._add_error(
                errors,
                f"Main source missing required field '{_F.SOURCE_ID}'",
                path=f"{_F.MAIN_SOURCE}.{_F.SOURCE_ID}",
            )
        if source_id and not _SOURCE_ID_PATTERN.match(source_id):
            msg = f"main_source.source_id '{source_id}' must match identifier pattern: {_SOURCE_ID_PATTERN_TEXT}"
            self._add_error(errors, msg, path=f"{_F.MAIN_SOURCE}.{_F.SOURCE_ID}")
            source_id = ""

        if loader_raw is None:
            self._add_error(
                errors,
                f"Main source missing required field '{_F.LOADER}'",
                path=f"{_F.MAIN_SOURCE}.{_F.LOADER}",
            )
        elif not loader_ref:
            self._add_error(errors, f"main_source.{_F.LOADER} must not be empty", path=f"{_F.MAIN_SOURCE}.{_F.LOADER}")
        elif not self._is_valid_loader_ref(loader_ref):
            msg = f"主数据源的 loader 引用 '{loader_raw}' 非法. 期望格式: {REFERENCE_FORMAT_EXAMPLES}"
            self._add_error(errors, msg, path=f"{_F.MAIN_SOURCE}.{_F.LOADER}")

        if source_id and sources_raw is not None and source_id in sources_raw:
            self._add_error(
                errors,
                f"Main source '{source_id}' must not appear in 'sources'",
                path=f"{_F.MAIN_SOURCE}.{_F.SOURCE_ID}",
            )

        self._validate_main_source_order_by(main_source_data, errors)
        self._validate_params_template_semantics(
            main_source_data.get(_F.PARAMS),
            errors,
            path=f"{_F.MAIN_SOURCE}.{_F.PARAMS}",
            allow_directives=False,
        )

        return source_id

    def _validate_main_source_order_by(
        self,
        main_source_data: dict[str, Any],
        errors: list[ValidationIssue],
    ) -> None:
        order_by_raw = main_source_data.get(_F.ORDER_BY)
        if order_by_raw is None:
            return
        order_by_list = list_or_none(order_by_raw)
        if order_by_list is None:
            self._add_error(
                errors,
                f"'{_F.MAIN_SOURCE}.{_F.ORDER_BY}' must be a list",
                path=f"{_F.MAIN_SOURCE}.{_F.ORDER_BY}",
            )
            return
        main_fields_raw = mapping_or_none(main_source_data.get(_F.FIELDS))
        main_field_ids: set[str] = set(main_fields_raw.keys()) if main_fields_raw is not None else set()
        for idx, item in enumerate(order_by_list):
            item_path = f"{_F.MAIN_SOURCE}.{_F.ORDER_BY}[{idx}]"
            if not isinstance(item, str):
                self._add_error(errors, f"{item_path} must be a string", path=item_path)
                continue
            raw = item.strip()
            if not raw or raw == "-":
                self._add_error(errors, f"{item_path} must be a non-empty string", path=item_path)
                continue
            field_id = raw.removeprefix("-")
            if field_id not in main_field_ids:
                msg = f"main_source.order_by field '{field_id}' not found in main_source.fields"
                self._add_error(errors, msg, path=item_path)

    def _validate_lookup_cast(
        self,
        lookup_raw: Any,
        errors: list[ValidationIssue],
        context: str,
        path_prefix: str | None = None,
    ) -> None:
        lookup_path = f"{path_prefix or context}.lookup_cast"
        lookup_dict = mapping_or_none(lookup_raw)
        if lookup_dict is None:
            self._add_error(errors, f"{context} lookup_cast must be a dictionary", path=lookup_path)
            return

        if "name" in lookup_dict:
            msg = self._build_lookup_cast_legacy_migration_hint(lookup_path, lookup_dict)
            self._add_error(errors, msg, path=lookup_path)
            return

        self._validate_lookup_cast_oneof_shape(lookup_dict, errors, context, lookup_path)

    def _validate_lookup_cast_oneof_shape(
        self,
        lookup_dict: dict[str, Any],
        errors: list[ValidationIssue],
        context: str,
        lookup_path: str,
    ) -> None:
        branch_keys = tuple(LOOKUP_CAST_NAME_ENUM)
        branch_key_set = set(branch_keys)
        branches = [key for key in branch_keys if key in lookup_dict]
        unknown_keys = sorted(str(key) for key in lookup_dict if str(key) not in branch_key_set)
        if unknown_keys:
            self._add_error(
                errors,
                "{} lookup_cast has unknown keys: {}".format(context, ", ".join(unknown_keys)),
                path=lookup_path,
            )

        if len(branches) != 1:
            msg = "{} lookup_cast must select exactly one branch: {}".format(context, "/".join(branch_keys))
            self._add_error(errors, msg, path=lookup_path)
            return

        branch = branches[0]
        params_path = f"{lookup_path}.{branch}"
        params_dict = mapping_or_none(lookup_dict.get(branch))
        if params_dict is None:
            self._add_error(errors, f"{context} lookup_cast.{branch} must be a dictionary", path=params_path)
            return

        if branch == "sep_first":
            self._validate_lookup_cast_sep_first_params(params_dict, errors, context, params_path)
            return

        self._validate_lookup_cast_empty_params(branch, params_dict, errors, context, params_path)

    def _validate_lookup_cast_sep_first_params(
        self,
        params_dict: dict[str, Any],
        errors: list[ValidationIssue],
        context: str,
        params_path: str,
    ) -> None:
        unexpected = sorted(str(key) for key in params_dict if str(key) != "sep")
        if unexpected:
            self._add_error(
                errors,
                "{} lookup_cast.sep_first has unknown keys: {}".format(context, ", ".join(unexpected)),
                path=params_path,
            )
        if "sep" in params_dict and not isinstance(params_dict.get("sep"), str):
            self._add_error(
                errors,
                f"{context} lookup_cast.sep_first.sep must be a string",
                path=f"{params_path}.sep",
            )

    def _validate_lookup_cast_empty_params(
        self,
        branch: str,
        params_dict: dict[str, Any],
        errors: list[ValidationIssue],
        context: str,
        params_path: str,
    ) -> None:
        if not params_dict:
            return
        if "sep" in params_dict:
            msg = f"{context} lookup_cast.{branch} does not support 'sep'; only 'sep_first' branch accepts it"
            self._add_error(errors, msg, path=f"{params_path}.sep")
            return

        msg = f"{context} lookup_cast.{branch} must be an empty object"
        self._add_error(errors, msg, path=params_path)

    def _validate_normalize(
        self,
        normalize_raw: Any,
        errors: list[ValidationIssue],
        *,
        path_prefix: str,
        source_id: str,
        key_raw: Any,
    ) -> None:
        norm_path = f"{path_prefix}.{_F.NORMALIZE}"
        norm_dict = mapping_or_none(normalize_raw)
        if norm_dict is None:
            self._add_error(errors, f"'{norm_path}' must be a dictionary", path=norm_path)
            return

        self._validate_normalize_call_by(norm_dict, errors, norm_path=norm_path, source_id=source_id)

        if _F.NORMALIZE_KIND in norm_dict:
            msg = self._build_normalize_legacy_migration_hint(norm_path, norm_dict)
            self._add_error(errors, msg, path=f"{norm_path}.{_F.NORMALIZE_KIND}")
            return

        branches = [key for key in NORMALIZE_KIND_ENUM if key in norm_dict]
        if len(branches) != 1:
            msg = "sources.{} normalize must select exactly one branch: {}".format(source_id, "/".join(NORMALIZE_KIND_ENUM))
            self._add_error(errors, msg, path=norm_path)
            return

        branch = branches[0]
        branch_path = f"{norm_path}.{branch}"
        branch_dict = mapping_or_none(norm_dict.get(branch))
        if branch_dict is None:
            self._add_error(errors, f"'{branch_path}' must be a dictionary", path=branch_path)
            return

        if branch == "index_by_key":
            self._validate_normalize_index_by_key(branch_dict, errors, norm_path=branch_path, source_id=source_id, key_raw=key_raw)
        elif branch == "take_first":
            self._validate_normalize_take_first(branch_dict, errors, norm_path=branch_path, source_id=source_id)
        elif branch == "project_fields":
            self._validate_normalize_project_fields(branch_dict, errors, norm_path=branch_path, source_id=source_id)
        else:
            self._validate_normalize_map_values(branch_dict, errors, norm_path=branch_path, source_id=source_id)

    def _validate_normalize_call_by(
        self,
        norm_dict: dict[str, Any],
        errors: list[ValidationIssue],
        *,
        norm_path: str,
        source_id: str,
    ) -> None:
        call_by_raw = norm_dict.get(_F.NORMALIZE_CALL_BY)
        if call_by_raw is None:
            return
        if not isinstance(call_by_raw, str):
            self._add_error(
                errors,
                f"sources.{source_id} normalize.call_by must be a string",
                path=f"{norm_path}.{_F.NORMALIZE_CALL_BY}",
            )
            return

        call_by_ref = call_by_raw.strip()
        if not call_by_ref:
            self._add_error(
                errors,
                f"sources.{source_id} normalize.call_by must not be empty",
                path=f"{norm_path}.{_F.NORMALIZE_CALL_BY}",
            )
            return
        if self._is_valid_loader_ref(call_by_ref):
            return

        msg = f"sources.{source_id} normalize.call_by 引用 '{call_by_raw}' 非法. 期望格式: {REFERENCE_FORMAT_EXAMPLES}"
        self._add_error(errors, msg, path=f"{norm_path}.{_F.NORMALIZE_CALL_BY}")

    def _validate_normalize_index_by_key(
        self,
        norm_dict: dict[str, Any],
        errors: list[ValidationIssue],
        *,
        norm_path: str,
        source_id: str,
        key_raw: Any,
    ) -> None:
        self._validate_normalize_index_by_key_reject_unsupported_fields(norm_dict, errors, norm_path=norm_path, source_id=source_id)
        key_field = self._normalize_index_by_key_key_field(norm_dict, errors, norm_path=norm_path, source_id=source_id)
        self._validate_normalize_index_by_key_reject_composite_key(key_raw, errors, source_id=source_id)
        self._validate_normalize_index_by_key_key_field_matches_key(
            key_field,
            key_raw,
            errors,
            norm_path=norm_path,
            source_id=source_id,
        )
        self._validate_normalize_index_by_key_on_conflict(norm_dict, errors, norm_path=norm_path, source_id=source_id)
        self._validate_normalize_index_by_key_on_none(norm_dict, errors, norm_path=norm_path, source_id=source_id)

    def _validate_normalize_index_by_key_reject_unsupported_fields(
        self,
        norm_dict: dict[str, Any],
        errors: list[ValidationIssue],
        *,
        norm_path: str,
        source_id: str,
    ) -> None:
        if _F.NORMALIZE_ON_EMPTY in norm_dict:
            self._add_error(
                errors,
                f"sources.{source_id} normalize.index_by_key does not support on_empty",
                path=f"{norm_path}.{_F.NORMALIZE_ON_EMPTY}",
            )
        if _F.NORMALIZE_ON_MISSING in norm_dict:
            self._add_error(
                errors,
                f"sources.{source_id} normalize.index_by_key does not support on_missing",
                path=f"{norm_path}.{_F.NORMALIZE_ON_MISSING}",
            )
        if _F.NORMALIZE_FIELDS in norm_dict:
            self._add_error(
                errors,
                f"sources.{source_id} normalize.index_by_key does not support fields",
                path=f"{norm_path}.{_F.NORMALIZE_FIELDS}",
            )
        if _F.NORMALIZE_STEPS in norm_dict:
            self._add_error(
                errors,
                f"sources.{source_id} normalize.index_by_key does not support steps",
                path=f"{norm_path}.{_F.NORMALIZE_STEPS}",
            )

    def _normalize_index_by_key_key_field(
        self,
        norm_dict: dict[str, Any],
        errors: list[ValidationIssue],
        *,
        norm_path: str,
        source_id: str,
    ) -> str:
        key_field_raw = norm_dict.get(_F.NORMALIZE_KEY_FIELD)
        if key_field_raw is None:
            return ""
        if isinstance(key_field_raw, str):
            return key_field_raw.strip()

        self._add_error(
            errors,
            f"sources.{source_id} normalize.index_by_key.key_field must be a string",
            path=f"{norm_path}.{_F.NORMALIZE_KEY_FIELD}",
        )
        return str(key_field_raw).strip()

    def _validate_normalize_index_by_key_reject_composite_key(
        self,
        key_raw: Any,
        errors: list[ValidationIssue],
        *,
        source_id: str,
    ) -> None:
        key_items = list_or_none(key_raw)
        if key_items is None:
            return

        self._add_error(
            errors,
            f"sources.{source_id} normalize.index_by_key does not support composite key yet",
            path=f"sources.{source_id}.{_F.KEY}",
        )

    def _validate_normalize_index_by_key_key_field_matches_key(
        self,
        key_field: str,
        key_raw: Any,
        errors: list[ValidationIssue],
        *,
        norm_path: str,
        source_id: str,
    ) -> None:
        if not isinstance(key_raw, str):
            return
        declared_key = key_raw.strip()
        if not declared_key or not key_field:
            return
        if declared_key == key_field:
            return

        self._add_error(
            errors,
            f"sources.{source_id} normalize.index_by_key.key_field must equal sources.{source_id}.key",
            path=f"{norm_path}.{_F.NORMALIZE_KEY_FIELD}",
        )

    def _validate_normalize_index_by_key_on_conflict(
        self,
        norm_dict: dict[str, Any],
        errors: list[ValidationIssue],
        *,
        norm_path: str,
        source_id: str,
    ) -> None:
        on_conflict_raw = norm_dict.get(_F.NORMALIZE_ON_CONFLICT)
        if on_conflict_raw is None:
            return
        on_conflict = str(on_conflict_raw).strip()
        if on_conflict in set(NORMALIZE_ON_CONFLICT_ENUM):
            return

        self._add_error(
            errors,
            f"sources.{source_id} normalize.index_by_key.on_conflict must be one of: error/first/last",
            path=f"{norm_path}.{_F.NORMALIZE_ON_CONFLICT}",
        )

    def _validate_normalize_index_by_key_on_none(
        self,
        norm_dict: dict[str, Any],
        errors: list[ValidationIssue],
        *,
        norm_path: str,
        source_id: str,
    ) -> None:
        on_none_raw = norm_dict.get(_F.NORMALIZE_ON_NONE)
        if on_none_raw is None:
            return
        on_none = str(on_none_raw).strip()
        if on_none in set(NORMALIZE_ON_NONE_ENUM):
            return

        self._add_error(
            errors,
            f"sources.{source_id} normalize.index_by_key.on_none must be one of: raise/skip",
            path=f"{norm_path}.{_F.NORMALIZE_ON_NONE}",
        )

    def _validate_normalize_take_first(
        self,
        norm_dict: dict[str, Any],
        errors: list[ValidationIssue],
        *,
        norm_path: str,
        source_id: str,
    ) -> None:
        if _F.NORMALIZE_KEY_FIELD in norm_dict:
            self._add_error(
                errors,
                f"sources.{source_id} normalize.take_first does not support key_field",
                path=f"{norm_path}.{_F.NORMALIZE_KEY_FIELD}",
            )
        if _F.NORMALIZE_ON_CONFLICT in norm_dict:
            self._add_error(
                errors,
                f"sources.{source_id} normalize.take_first does not support on_conflict",
                path=f"{norm_path}.{_F.NORMALIZE_ON_CONFLICT}",
            )
        if _F.NORMALIZE_ON_NONE in norm_dict:
            self._add_error(
                errors,
                f"sources.{source_id} normalize.on_none is only supported for normalize.index_by_key",
                path=f"{norm_path}.{_F.NORMALIZE_ON_NONE}",
            )
        if _F.NORMALIZE_ON_MISSING in norm_dict:
            self._add_error(
                errors,
                f"sources.{source_id} normalize.take_first does not support on_missing",
                path=f"{norm_path}.{_F.NORMALIZE_ON_MISSING}",
            )
        if _F.NORMALIZE_FIELDS in norm_dict:
            self._add_error(
                errors,
                f"sources.{source_id} normalize.take_first does not support fields",
                path=f"{norm_path}.{_F.NORMALIZE_FIELDS}",
            )
        if _F.NORMALIZE_STEPS in norm_dict:
            self._add_error(
                errors,
                f"sources.{source_id} normalize.take_first does not support steps",
                path=f"{norm_path}.{_F.NORMALIZE_STEPS}",
            )

        on_empty_raw = norm_dict.get(_F.NORMALIZE_ON_EMPTY)
        if on_empty_raw is None:
            return
        on_empty = str(on_empty_raw).strip()
        if on_empty not in set(NORMALIZE_ON_EMPTY_ENUM):
            self._add_error(
                errors,
                f"sources.{source_id} normalize.take_first.on_empty must be one of: miss/null/error",
                path=f"{norm_path}.{_F.NORMALIZE_ON_EMPTY}",
            )

    def _validate_normalize_project_fields(
        self,
        norm_dict: dict[str, Any],
        errors: list[ValidationIssue],
        *,
        norm_path: str,
        source_id: str,
    ) -> None:
        if _F.NORMALIZE_KEY_FIELD in norm_dict:
            self._add_error(
                errors,
                f"sources.{source_id} normalize.project_fields does not support key_field",
                path=f"{norm_path}.{_F.NORMALIZE_KEY_FIELD}",
            )
        if _F.NORMALIZE_ON_CONFLICT in norm_dict:
            self._add_error(
                errors,
                f"sources.{source_id} normalize.project_fields does not support on_conflict",
                path=f"{norm_path}.{_F.NORMALIZE_ON_CONFLICT}",
            )
        if _F.NORMALIZE_ON_NONE in norm_dict:
            self._add_error(
                errors,
                f"sources.{source_id} normalize.on_none is only supported for normalize.index_by_key",
                path=f"{norm_path}.{_F.NORMALIZE_ON_NONE}",
            )
        if _F.NORMALIZE_ON_EMPTY in norm_dict:
            self._add_error(
                errors,
                f"sources.{source_id} normalize.project_fields does not support on_empty",
                path=f"{norm_path}.{_F.NORMALIZE_ON_EMPTY}",
            )
        if _F.NORMALIZE_STEPS in norm_dict:
            self._add_error(
                errors,
                f"sources.{source_id} normalize.project_fields does not support steps",
                path=f"{norm_path}.{_F.NORMALIZE_STEPS}",
            )

        on_missing_raw = norm_dict.get(_F.NORMALIZE_ON_MISSING)
        if on_missing_raw is not None:
            on_missing = str(on_missing_raw).strip()
            if on_missing not in set(NORMALIZE_ON_MISSING_ENUM):
                self._add_error(
                    errors,
                    f"sources.{source_id} normalize.project_fields.on_missing must be one of: error/null",
                    path=f"{norm_path}.{_F.NORMALIZE_ON_MISSING}",
                )

        fields_path = f"{norm_path}.{_F.NORMALIZE_FIELDS}"
        if _F.NORMALIZE_FIELDS not in norm_dict:
            self._add_error(errors, f"sources.{source_id} normalize.project_fields.fields is required", path=fields_path)
            return

        self._validate_normalize_project_fields_rules(
            norm_dict.get(_F.NORMALIZE_FIELDS),
            errors,
            fields_path=fields_path,
        )

    def _validate_normalize_map_values(
        self,
        norm_dict: dict[str, Any],
        errors: list[ValidationIssue],
        *,
        norm_path: str,
        source_id: str,
    ) -> None:
        if _F.NORMALIZE_KEY_FIELD in norm_dict:
            self._add_error(
                errors,
                f"sources.{source_id} normalize.map_values does not support key_field",
                path=f"{norm_path}.{_F.NORMALIZE_KEY_FIELD}",
            )
        if _F.NORMALIZE_ON_CONFLICT in norm_dict:
            self._add_error(
                errors,
                f"sources.{source_id} normalize.map_values does not support on_conflict",
                path=f"{norm_path}.{_F.NORMALIZE_ON_CONFLICT}",
            )
        if _F.NORMALIZE_ON_NONE in norm_dict:
            self._add_error(
                errors,
                f"sources.{source_id} normalize.on_none is only supported for normalize.index_by_key",
                path=f"{norm_path}.{_F.NORMALIZE_ON_NONE}",
            )
        if _F.NORMALIZE_ON_EMPTY in norm_dict:
            self._add_error(
                errors,
                f"sources.{source_id} normalize.map_values does not support on_empty",
                path=f"{norm_path}.{_F.NORMALIZE_ON_EMPTY}",
            )
        if _F.NORMALIZE_ON_MISSING in norm_dict:
            self._add_error(
                errors,
                f"sources.{source_id} normalize.map_values does not support on_missing",
                path=f"{norm_path}.{_F.NORMALIZE_ON_MISSING}",
            )
        if _F.NORMALIZE_FIELDS in norm_dict:
            self._add_error(
                errors,
                f"sources.{source_id} normalize.map_values does not support fields",
                path=f"{norm_path}.{_F.NORMALIZE_FIELDS}",
            )

        steps_path = f"{norm_path}.{_F.NORMALIZE_STEPS}"
        steps_list = list_or_none(norm_dict.get(_F.NORMALIZE_STEPS))
        if steps_list is None:
            self._add_error(errors, f"'{steps_path}' must be a list", path=steps_path)
            return
        if not steps_list:
            self._add_error(errors, f"'{steps_path}' must not be empty", path=steps_path)
            return

        for idx, step_raw in enumerate(steps_list):
            self._validate_normalize_map_values_step(step_raw, errors, steps_path=steps_path, idx=idx)

    def _validate_normalize_map_values_step(
        self,
        step_raw: Any,
        errors: list[ValidationIssue],
        *,
        steps_path: str,
        idx: int,
    ) -> None:
        step_path = f"{steps_path}[{idx}]"
        step_dict = mapping_or_none(step_raw)
        if step_dict is None:
            self._add_error(errors, f"'{step_path}' must be a dictionary", path=step_path)
            return

        if _F.NORMALIZE_CALL_BY in step_dict:
            self._add_error(errors, f"'{step_path}' does not support 'call_by'", path=f"{step_path}.{_F.NORMALIZE_CALL_BY}")

        if _F.NORMALIZE_KIND in step_dict:
            msg = self._build_normalize_step_legacy_migration_hint(step_path, step_dict)
            self._add_error(errors, msg, path=f"{step_path}.{_F.NORMALIZE_KIND}")
            return

        branches = [key for key in ("take_first", "project_fields") if key in step_dict]
        if len(branches) != 1:
            msg = f"'{step_path}' must select exactly one step branch: take_first/project_fields"
            self._add_error(errors, msg, path=step_path)
            return

        branch = branches[0]
        branch_path = f"{step_path}.{branch}"
        branch_dict = mapping_or_none(step_dict.get(branch))
        if branch_dict is None:
            self._add_error(errors, f"'{branch_path}' must be a dictionary", path=branch_path)
            return

        if branch == "take_first":
            self._validate_normalize_step_take_first(branch_dict, errors, step_path=branch_path)
            return

        self._validate_normalize_step_project_fields(branch_dict, errors, step_path=branch_path)

    def _validate_normalize_step_take_first(
        self,
        step_dict: dict[str, Any],
        errors: list[ValidationIssue],
        *,
        step_path: str,
    ) -> None:
        if _F.NORMALIZE_FIELDS in step_dict:
            self._add_error(errors, f"'{step_path}' does not support fields", path=f"{step_path}.{_F.NORMALIZE_FIELDS}")
        if _F.NORMALIZE_ON_MISSING in step_dict:
            self._add_error(errors, f"'{step_path}' does not support on_missing", path=f"{step_path}.{_F.NORMALIZE_ON_MISSING}")
        if _F.NORMALIZE_KEY_FIELD in step_dict:
            self._add_error(errors, f"'{step_path}' does not support key_field", path=f"{step_path}.{_F.NORMALIZE_KEY_FIELD}")
        if _F.NORMALIZE_ON_CONFLICT in step_dict:
            self._add_error(errors, f"'{step_path}' does not support on_conflict", path=f"{step_path}.{_F.NORMALIZE_ON_CONFLICT}")

        on_empty_raw = step_dict.get(_F.NORMALIZE_ON_EMPTY)
        if on_empty_raw is None:
            return
        on_empty = str(on_empty_raw).strip()
        if on_empty not in set(NORMALIZE_ON_EMPTY_ENUM):
            self._add_error(
                errors,
                f"'{step_path}.on_empty' must be one of: miss/null/error",
                path=f"{step_path}.{_F.NORMALIZE_ON_EMPTY}",
            )

    def _validate_normalize_step_project_fields(
        self,
        step_dict: dict[str, Any],
        errors: list[ValidationIssue],
        *,
        step_path: str,
    ) -> None:
        if _F.NORMALIZE_ON_EMPTY in step_dict:
            self._add_error(errors, f"'{step_path}' does not support on_empty", path=f"{step_path}.{_F.NORMALIZE_ON_EMPTY}")
        if _F.NORMALIZE_KEY_FIELD in step_dict:
            self._add_error(errors, f"'{step_path}' does not support key_field", path=f"{step_path}.{_F.NORMALIZE_KEY_FIELD}")
        if _F.NORMALIZE_ON_CONFLICT in step_dict:
            self._add_error(errors, f"'{step_path}' does not support on_conflict", path=f"{step_path}.{_F.NORMALIZE_ON_CONFLICT}")

        on_missing_raw = step_dict.get(_F.NORMALIZE_ON_MISSING)
        if on_missing_raw is not None:
            on_missing = str(on_missing_raw).strip()
            if on_missing not in set(NORMALIZE_ON_MISSING_ENUM):
                self._add_error(
                    errors,
                    f"'{step_path}.on_missing' must be one of: error/null",
                    path=f"{step_path}.{_F.NORMALIZE_ON_MISSING}",
                )

        fields_path = f"{step_path}.{_F.NORMALIZE_FIELDS}"
        if _F.NORMALIZE_FIELDS not in step_dict:
            self._add_error(errors, f"'{fields_path}' is required", path=fields_path)
            return

        self._validate_normalize_project_fields_rules(step_dict.get(_F.NORMALIZE_FIELDS), errors, fields_path=fields_path)

    def _validate_normalize_project_fields_rules(
        self,
        rules_raw: Any,
        errors: list[ValidationIssue],
        *,
        fields_path: str,
    ) -> None:
        fields_dict = mapping_or_none(rules_raw)
        if fields_dict is None:
            self._add_error(errors, f"'{fields_path}' must be a dictionary", path=fields_path)
            return
        if not fields_dict:
            self._add_error(errors, f"'{fields_path}' must not be empty", path=fields_path)
            return

        for field_name_raw, rule_raw in fields_dict.items():
            field_name = str(field_name_raw or "").strip()
            rule_path = "{}.{}".format(fields_path, field_name or "<empty>")
            rule_dict = mapping_or_none(rule_raw)
            if rule_dict is None:
                self._add_error(errors, f"'{rule_path}' must be a dictionary", path=rule_path)
                continue
            self._validate_normalize_project_field_rule(rule_dict, errors, rule_path=rule_path)

    def _validate_normalize_project_field_rule(
        self,
        rule_dict: dict[str, Any],
        errors: list[ValidationIssue],
        *,
        rule_path: str,
    ) -> None:
        has_from_key = "from_key" in rule_dict
        has_extract = "extract" in rule_dict
        if has_from_key and has_extract:
            self._add_error(errors, f"'{rule_path}' must not declare both 'from_key' and 'extract'", path=rule_path)
            return
        if not has_from_key and not has_extract:
            self._add_error(errors, f"'{rule_path}' must declare 'from_key' or 'extract'", path=rule_path)
            return

        if has_from_key:
            from_key_raw = rule_dict.get("from_key")
            if not isinstance(from_key_raw, bool):
                self._add_error(errors, f"'{rule_path}.from_key' must be a boolean", path=f"{rule_path}.from_key")
            return

        extract_raw = rule_dict.get("extract")
        if not isinstance(extract_raw, str):
            self._add_error(errors, f"'{rule_path}.extract' must be a string", path=f"{rule_path}.extract")
            return

        extract_expr = extract_raw.strip()
        if not extract_expr:
            self._add_error(errors, f"'{rule_path}.extract' must not be empty", path=f"{rule_path}.extract")
            return

        try:
            _ = compile_field_extract(extract_expr)
        except ScalimFieldExtractCompileError as exc:
            self._add_error(errors, f"Invalid extract path: {exc!s}", path=f"{rule_path}.extract")

    def _is_valid_loader_ref(self, loader_ref: str) -> bool:
        return is_valid_callable_reference(loader_ref)


__all__ = ()
