from typing import Any, Dict, List, Optional, Set

from ...params_template import ScalimParamsTemplateCompileError, compile_params_template
from ...reference_syntax import REFERENCE_FORMAT_EXAMPLES, is_valid_callable_reference
from ...schema_dsl.constants import (
    DEFAULT_CACHE_MODE,
    LOOKUP_CAST_NAME_ENUM,
    NORMALIZE_KIND_ENUM,
    NORMALIZE_ON_CONFLICT_ENUM,
    NORMALIZE_ON_EMPTY_ENUM,
    NORMALIZE_ON_MISSING_ENUM,
)
from ...schema_dsl.models import LOADER_RETRY_KEYS
from ..field_extract import ScalimFieldExtractCompileError, compile_field_extract, derive_source_field_data_key
from ..parsers.utils import list_or_none, mapping_or_none
from .base import ValidatorMixinBase
from .constants import LEGACY_FIELDS, F
from .issues import ValidationIssue

_F = F


class ValidatorSourcesMixin(ValidatorMixinBase):
    _step_field_ids_by_source_data_key: Dict[str, Dict[str, Set[str]]]

    def _collect_field_data_key_map(self, fields_raw: object) -> Dict[str, Set[str]]:
        data_key_map: Dict[str, Set[str]] = {}
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

    def _validate_loader_retry_should_retry(
        self,
        retry_raw: object,
        errors: List[ValidationIssue],
        *,
        path_prefix: str,
    ) -> None:
        retry_dict = mapping_or_none(retry_raw)
        if retry_raw is not None and retry_dict is None:
            self._add_error(errors, "'{}' must be a dictionary".format(path_prefix), path=path_prefix)
            return
        if retry_dict is None:
            return

        should_retry_key = LOADER_RETRY_KEYS["should_retry"]
        if should_retry_key not in retry_dict:
            return
        should_retry_raw = retry_dict.get(should_retry_key)
        if should_retry_raw is None:
            return
        if not isinstance(should_retry_raw, str):
            self._add_error(
                errors,
                "'{}.{}' must be a string".format(path_prefix, should_retry_key),
                path="{}.{}".format(path_prefix, should_retry_key),
            )
            return
        should_retry_ref = should_retry_raw.strip()
        if should_retry_ref and not self._is_valid_loader_ref(should_retry_ref):
            msg = "'{}.{}' 的引用 '{}' 非法. 期望格式: {}".format(
                path_prefix, should_retry_key, should_retry_raw, REFERENCE_FORMAT_EXAMPLES
            )
            self._add_error(errors, msg, path="{}.{}".format(path_prefix, should_retry_key))

    def _validate_params_template_semantics(
        self,
        params_raw: object,
        errors: List[ValidationIssue],
        *,
        path: str,
        allow_directives: bool,
    ) -> None:
        params_dict = mapping_or_none(params_raw)
        if params_raw is not None and params_dict is None:
            self._add_error(errors, "'{}' must be a dictionary".format(path), path=path)
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

    def _collect_declared_field_names(self, fields_raw: object) -> Set[str]:
        names: Set[str] = set()
        fields_dict = mapping_or_none(fields_raw)
        if fields_dict is None:
            return names
        for field_id_raw in fields_dict:
            field_id = str(field_id_raw or "").strip()
            if field_id:
                names.add(field_id)
        return names

    def _collect_source_key_names(self, key_raw: object) -> Set[str]:
        names: Set[str] = set()
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

    def _collect_step_allowed_fields(self, config: Dict[str, Any], main_source_id: str) -> Dict[str, Set[str]]:
        allowed: Dict[str, Set[str]] = {}
        suggestions: Dict[str, Dict[str, Set[str]]] = {}

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

    def _validate_required_fields(self, config: Dict[str, Any], errors: List[ValidationIssue]) -> None:
        required_fields = [_F.NAME, _F.MAIN_SOURCE]
        for field_name in required_fields:
            if field_name not in config:
                self._add_error(errors, "Missing required field: '{}'".format(field_name), path=field_name)

    def _validate_batch_size(self, config: Dict[str, Any], errors: List[ValidationIssue]) -> None:
        if _F.BATCH_SIZE not in config:
            return
        raw = config.get(_F.BATCH_SIZE)
        if raw is None:
            return
        if isinstance(raw, bool) or not isinstance(raw, int):
            self._add_error(errors, "'{}' must be null or an integer >= 1".format(_F.BATCH_SIZE), path=_F.BATCH_SIZE)
            return
        if raw < 1:
            self._add_error(errors, "'{}' must be >= 1 when provided".format(_F.BATCH_SIZE), path=_F.BATCH_SIZE)

    def _validate_legacy_fields(self, config: Dict[str, Any], errors: List[ValidationIssue]) -> None:  # noqa: C901, PLR0912
        if "output" in config:
            self._add_error(
                errors,
                (
                    "Legacy YAML syntax is not supported: top-level 'output'. "
                    "Upgrade to 'outputs' (list) and move output settings into 'outputs.*.container'.\n\n"
                    "Minimal migration:\n"
                    "  outputs:\n"
                    "    - name: detail\n"
                    "      container: {type: workbook, path: ./output/report.xlsx, sheet: Detail}\n"
                    "      fields: [field_id, ...]"
                ),
                path="output",
            )

        for key in config:
            if key in LEGACY_FIELDS:
                self._add_error(errors, "Legacy field '{}' is not allowed".format(key), path=str(key))

        sources_raw = mapping_or_none(config.get(_F.SOURCES, {}))
        if sources_raw is not None:
            for source_id_raw, source_data_raw in sources_raw.items():
                source_dict = mapping_or_none(source_data_raw)
                if source_dict is None:
                    continue
                source_id = str(source_id_raw)
                for key in source_dict:
                    if key in LEGACY_FIELDS:
                        path = "sources.{}.{}".format(source_id, key)
                        self._add_error(errors, "Legacy field '{}' is not allowed".format(path), path=path)

        fields_raw = mapping_or_none(config.get(_F.FIELDS, {}))
        if fields_raw is not None:
            for field_id_raw, field_data_raw in fields_raw.items():
                field_dict = mapping_or_none(field_data_raw)
                if field_dict is None:
                    continue
                field_id = str(field_id_raw)
                for key in field_dict:
                    if key in LEGACY_FIELDS:
                        path = "fields.{}.{}".format(field_id, key)
                        self._add_error(errors, "Legacy field '{}' is not allowed".format(path), path=path)

    def _validate_sources(self, config: Dict[str, Any], errors: List[ValidationIssue]) -> Dict[str, Dict[str, bool]]:  # noqa: C901
        sources_info: Dict[str, Dict[str, bool]] = {}
        sources_raw = mapping_or_none(config.get(_F.SOURCES))
        if sources_raw is None:
            return sources_info

        for source_id_raw, source_data_raw in sources_raw.items():
            source_id = str(source_id_raw)
            source_dict = mapping_or_none(source_data_raw)
            if source_dict is None:
                self._add_error(errors, "Source '{}' must be a dictionary".format(source_id), path="sources.{}".format(source_id))
                continue

            if _F.LOADER not in source_dict:
                self._add_error(
                    errors,
                    "Source '{}' missing required field '{}'".format(source_id, _F.LOADER),
                    path="sources.{}.{}".format(source_id, _F.LOADER),
                )

            if _F.KEY not in source_dict:
                self._add_error(
                    errors,
                    "Source '{}' missing required field '{}'".format(source_id, _F.KEY),
                    path="sources.{}.{}".format(source_id, _F.KEY),
                )

            loader = source_dict.get(_F.LOADER, "")
            if loader and not self._is_valid_loader_ref(str(loader)):
                msg = "数据源 '{}' 的 loader 引用 '{}' 非法. 期望格式: {}".format(source_id, loader, REFERENCE_FORMAT_EXAMPLES)
                self._add_error(errors, msg, path="sources.{}.{}".format(source_id, _F.LOADER))

            self._validate_loader_retry_should_retry(
                source_dict.get("retry"),
                errors,
                path_prefix="sources.{}.retry".format(source_id),
            )

            bind_raw = source_dict.get(_F.BIND)
            if bind_raw is not None:
                self._add_error(
                    errors,
                    (
                        "Legacy YAML syntax is not supported: 'sources.{}.bind'. "
                        "Move binding into 'sources.{}.params' using `$keys` / `$rows` directives."
                        "\nExample:\n"
                        "  params:\n"
                        "    ids:\n"
                        "      $keys: {{as: set}}"
                    ).format(source_id, source_id),
                    path="sources.{}.{}".format(source_id, _F.BIND),
                )

            lookup_raw = source_dict.get(_F.LOOKUP_CAST)
            if lookup_raw is not None:
                self._validate_lookup_cast(lookup_raw, errors, "sources.{}".format(source_id))

            cache_mode = str(source_dict.get(_F.CACHE_MODE, DEFAULT_CACHE_MODE))
            if cache_mode not in {"none", "preload_forever"}:
                self._add_error(
                    errors,
                    "Source '{}' has invalid cache_mode '{}' (expected: none/preload_forever)".format(source_id, cache_mode),
                    path="sources.{}.{}".format(source_id, _F.CACHE_MODE),
                )

            normalize_raw = source_dict.get(_F.NORMALIZE)
            if normalize_raw is not None:
                self._validate_normalize(
                    normalize_raw,
                    errors,
                    path_prefix="sources.{}".format(source_id),
                    source_id=source_id,
                    key_raw=source_dict.get(_F.KEY),
                )

            allow_directives = cache_mode != "preload_forever"
            self._validate_params_template_semantics(
                source_dict.get(_F.PARAMS),
                errors,
                path="sources.{}.{}".format(source_id, _F.PARAMS),
                allow_directives=allow_directives,
            )

            sources_info[source_id] = {
                "preload": cache_mode == "preload_forever",
            }

        return sources_info

    def _validate_main_source(self, config: Dict[str, Any], errors: List[ValidationIssue]) -> str:
        main_source_data = mapping_or_none(config.get(_F.MAIN_SOURCE))
        if main_source_data is None:
            self._add_error(errors, "'{}' must be a dictionary".format(_F.MAIN_SOURCE), path=_F.MAIN_SOURCE)
            return ""

        if _F.NORMALIZE in main_source_data:
            self._add_error(
                errors,
                "`main_source.normalize` is not supported. Define `normalize` under `sources.<id>` instead.",
                path="{}.{}".format(_F.MAIN_SOURCE, _F.NORMALIZE),
            )

        source_id = str(main_source_data.get(_F.SOURCE_ID, ""))
        loader = main_source_data.get(_F.LOADER)
        sources_raw = mapping_or_none(config.get(_F.SOURCES, {}))

        if not source_id:
            self._add_error(
                errors,
                "Main source missing required field '{}'".format(_F.SOURCE_ID),
                path="{}.{}".format(_F.MAIN_SOURCE, _F.SOURCE_ID),
            )
        if not loader:
            self._add_error(
                errors,
                "Main source missing required field '{}'".format(_F.LOADER),
                path="{}.{}".format(_F.MAIN_SOURCE, _F.LOADER),
            )
        if loader and not self._is_valid_loader_ref(str(loader)):
            msg = "主数据源的 loader 引用 '{}' 非法. 期望格式: {}".format(loader, REFERENCE_FORMAT_EXAMPLES)
            self._add_error(errors, msg, path="{}.{}".format(_F.MAIN_SOURCE, _F.LOADER))

        self._validate_loader_retry_should_retry(
            main_source_data.get("retry"),
            errors,
            path_prefix="{}.retry".format(_F.MAIN_SOURCE),
        )

        if source_id and sources_raw is not None and source_id in sources_raw:
            self._add_error(
                errors,
                "Main source '{}' must not appear in 'sources'".format(source_id),
                path="{}.{}".format(_F.MAIN_SOURCE, _F.SOURCE_ID),
            )

        self._validate_main_source_order_by(main_source_data, errors)
        self._validate_params_template_semantics(
            main_source_data.get(_F.PARAMS),
            errors,
            path="{}.{}".format(_F.MAIN_SOURCE, _F.PARAMS),
            allow_directives=False,
        )

        return source_id

    def _validate_main_source_order_by(
        self,
        main_source_data: Dict[str, Any],
        errors: List[ValidationIssue],
    ) -> None:
        order_by_raw = main_source_data.get(_F.ORDER_BY)
        if order_by_raw is None:
            return
        order_by_list = list_or_none(order_by_raw)
        if order_by_list is None:
            self._add_error(
                errors,
                "'{}.{}' must be a list".format(_F.MAIN_SOURCE, _F.ORDER_BY),
                path="{}.{}".format(_F.MAIN_SOURCE, _F.ORDER_BY),
            )
            return
        main_fields_raw = mapping_or_none(main_source_data.get(_F.FIELDS))
        main_field_ids: Set[str] = set(main_fields_raw.keys()) if main_fields_raw is not None else set()
        for idx, item in enumerate(order_by_list):
            item_path = "{}.{}[{}]".format(_F.MAIN_SOURCE, _F.ORDER_BY, idx)
            if not isinstance(item, str):
                self._add_error(errors, "{} must be a string".format(item_path), path=item_path)
                continue
            raw = item.strip()
            if not raw or raw == "-":
                self._add_error(errors, "{} must be a non-empty string".format(item_path), path=item_path)
                continue
            field_id = raw[1:] if raw.startswith("-") else raw
            if field_id not in main_field_ids:
                msg = "main_source.order_by field '{}' not found in main_source.fields".format(field_id)
                self._add_error(errors, msg, path=item_path)

    def _validate_lookup_cast(
        self,
        lookup_raw: Any,
        errors: List[ValidationIssue],
        context: str,
        path_prefix: Optional[str] = None,
    ) -> None:
        lookup_path = "{}.lookup_cast".format(path_prefix or context)
        lookup_dict = mapping_or_none(lookup_raw)
        if lookup_dict is None:
            self._add_error(errors, "{} lookup_cast must be a dictionary".format(context), path=lookup_path)
            return

        name = str(lookup_dict.get(_F.NAME_KEY, ""))
        if name not in LOOKUP_CAST_NAME_ENUM:
            self._add_error(
                errors,
                "{} lookup_cast has invalid name '{}'".format(context, name),
                path="{}.{}".format(lookup_path, _F.NAME_KEY),
            )

    def _validate_normalize(
        self,
        normalize_raw: Any,
        errors: List[ValidationIssue],
        *,
        path_prefix: str,
        source_id: str,
        key_raw: Any,
    ) -> None:
        norm_path = "{}.{}".format(path_prefix, _F.NORMALIZE)
        norm_dict = mapping_or_none(normalize_raw)
        if norm_dict is None:
            self._add_error(errors, "'{}' must be a dictionary".format(norm_path), path=norm_path)
            return

        kind = str(norm_dict.get(_F.NORMALIZE_KIND, "")).strip()
        if kind not in set(NORMALIZE_KIND_ENUM):
            self._add_error(
                errors,
                "sources.{} normalize.kind must be one of: {}".format(source_id, "/".join(NORMALIZE_KIND_ENUM)),
                path="{}.{}".format(norm_path, _F.NORMALIZE_KIND),
            )

        self._validate_normalize_call_by(norm_dict, errors, norm_path=norm_path, source_id=source_id)

        if kind == "index_by_key":
            self._validate_normalize_index_by_key(norm_dict, errors, norm_path=norm_path, source_id=source_id, key_raw=key_raw)
            return

        if kind == "take_first":
            self._validate_normalize_take_first(norm_dict, errors, norm_path=norm_path, source_id=source_id)
            return

        if kind == "project_fields":
            self._validate_normalize_project_fields(norm_dict, errors, norm_path=norm_path, source_id=source_id)
            return

        if kind == "map_values":
            self._validate_normalize_map_values(norm_dict, errors, norm_path=norm_path, source_id=source_id)
            return

    def _validate_normalize_call_by(
        self,
        norm_dict: Dict[str, Any],
        errors: List[ValidationIssue],
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
                "sources.{} normalize.call_by must be a string".format(source_id),
                path="{}.{}".format(norm_path, _F.NORMALIZE_CALL_BY),
            )
            return

        call_by_ref = call_by_raw.strip()
        if not call_by_ref:
            self._add_error(
                errors,
                "sources.{} normalize.call_by must not be empty".format(source_id),
                path="{}.{}".format(norm_path, _F.NORMALIZE_CALL_BY),
            )
            return
        if self._is_valid_loader_ref(call_by_ref):
            return

        msg = "sources.{} normalize.call_by 引用 '{}' 非法. 期望格式: {}".format(source_id, call_by_raw, REFERENCE_FORMAT_EXAMPLES)
        self._add_error(errors, msg, path="{}.{}".format(norm_path, _F.NORMALIZE_CALL_BY))

    def _validate_normalize_index_by_key(
        self,
        norm_dict: Dict[str, Any],
        errors: List[ValidationIssue],
        *,
        norm_path: str,
        source_id: str,
        key_raw: Any,
    ) -> None:
        key_field = str(norm_dict.get(_F.NORMALIZE_KEY_FIELD, "")).strip()
        if not key_field:
            self._add_error(
                errors,
                "sources.{} normalize.key_field is required".format(source_id),
                path="{}.{}".format(norm_path, _F.NORMALIZE_KEY_FIELD),
            )

        key_items = list_or_none(key_raw)
        if key_items is not None:
            self._add_error(
                errors,
                "sources.{} normalize.kind=index_by_key does not support composite key yet".format(source_id),
                path="sources.{}.{}".format(source_id, _F.KEY),
            )

        if isinstance(key_raw, str):
            declared_key = key_raw.strip()
            if declared_key and key_field and declared_key != key_field:
                self._add_error(
                    errors,
                    "sources.{} normalize.key_field must equal sources.{}.key".format(source_id, source_id),
                    path="{}.{}".format(norm_path, _F.NORMALIZE_KEY_FIELD),
                )

        on_conflict_raw = norm_dict.get(_F.NORMALIZE_ON_CONFLICT)
        if on_conflict_raw is None:
            return
        on_conflict = str(on_conflict_raw).strip()
        if on_conflict not in set(NORMALIZE_ON_CONFLICT_ENUM):
            self._add_error(
                errors,
                "sources.{} normalize.on_conflict must be one of: error/first/last".format(source_id),
                path="{}.{}".format(norm_path, _F.NORMALIZE_ON_CONFLICT),
            )

    def _validate_normalize_take_first(
        self,
        norm_dict: Dict[str, Any],
        errors: List[ValidationIssue],
        *,
        norm_path: str,
        source_id: str,
    ) -> None:
        if _F.NORMALIZE_KEY_FIELD in norm_dict:
            self._add_error(
                errors,
                "sources.{} normalize.kind=take_first does not support normalize.key_field".format(source_id),
                path="{}.{}".format(norm_path, _F.NORMALIZE_KEY_FIELD),
            )
        if _F.NORMALIZE_ON_CONFLICT in norm_dict:
            self._add_error(
                errors,
                "sources.{} normalize.kind=take_first does not support normalize.on_conflict".format(source_id),
                path="{}.{}".format(norm_path, _F.NORMALIZE_ON_CONFLICT),
            )
        if _F.NORMALIZE_ON_MISSING in norm_dict:
            self._add_error(
                errors,
                "sources.{} normalize.kind=take_first does not support normalize.on_missing".format(source_id),
                path="{}.{}".format(norm_path, _F.NORMALIZE_ON_MISSING),
            )
        if _F.NORMALIZE_FIELDS in norm_dict:
            self._add_error(
                errors,
                "sources.{} normalize.kind=take_first does not support normalize.fields".format(source_id),
                path="{}.{}".format(norm_path, _F.NORMALIZE_FIELDS),
            )
        if _F.NORMALIZE_STEPS in norm_dict:
            self._add_error(
                errors,
                "sources.{} normalize.kind=take_first does not support normalize.steps".format(source_id),
                path="{}.{}".format(norm_path, _F.NORMALIZE_STEPS),
            )

        on_empty_raw = norm_dict.get(_F.NORMALIZE_ON_EMPTY)
        if on_empty_raw is None:
            return
        on_empty = str(on_empty_raw).strip()
        if on_empty not in set(NORMALIZE_ON_EMPTY_ENUM):
            self._add_error(
                errors,
                "sources.{} normalize.on_empty must be one of: miss/null/error".format(source_id),
                path="{}.{}".format(norm_path, _F.NORMALIZE_ON_EMPTY),
            )

    def _validate_normalize_project_fields(
        self,
        norm_dict: Dict[str, Any],
        errors: List[ValidationIssue],
        *,
        norm_path: str,
        source_id: str,
    ) -> None:
        if _F.NORMALIZE_KEY_FIELD in norm_dict:
            self._add_error(
                errors,
                "sources.{} normalize.kind=project_fields does not support normalize.key_field".format(source_id),
                path="{}.{}".format(norm_path, _F.NORMALIZE_KEY_FIELD),
            )
        if _F.NORMALIZE_ON_CONFLICT in norm_dict:
            self._add_error(
                errors,
                "sources.{} normalize.kind=project_fields does not support normalize.on_conflict".format(source_id),
                path="{}.{}".format(norm_path, _F.NORMALIZE_ON_CONFLICT),
            )
        if _F.NORMALIZE_ON_EMPTY in norm_dict:
            self._add_error(
                errors,
                "sources.{} normalize.kind=project_fields does not support normalize.on_empty".format(source_id),
                path="{}.{}".format(norm_path, _F.NORMALIZE_ON_EMPTY),
            )
        if _F.NORMALIZE_STEPS in norm_dict:
            self._add_error(
                errors,
                "sources.{} normalize.kind=project_fields does not support normalize.steps".format(source_id),
                path="{}.{}".format(norm_path, _F.NORMALIZE_STEPS),
            )

        on_missing_raw = norm_dict.get(_F.NORMALIZE_ON_MISSING)
        if on_missing_raw is not None:
            on_missing = str(on_missing_raw).strip()
            if on_missing not in set(NORMALIZE_ON_MISSING_ENUM):
                self._add_error(
                    errors,
                    "sources.{} normalize.on_missing must be one of: error/null".format(source_id),
                    path="{}.{}".format(norm_path, _F.NORMALIZE_ON_MISSING),
                )

        fields_path = "{}.{}".format(norm_path, _F.NORMALIZE_FIELDS)
        if _F.NORMALIZE_FIELDS not in norm_dict:
            self._add_error(errors, "sources.{} normalize.fields is required".format(source_id), path=fields_path)
            return

        self._validate_normalize_project_fields_rules(
            norm_dict.get(_F.NORMALIZE_FIELDS),
            errors,
            fields_path=fields_path,
        )

    def _validate_normalize_map_values(
        self,
        norm_dict: Dict[str, Any],
        errors: List[ValidationIssue],
        *,
        norm_path: str,
        source_id: str,
    ) -> None:
        if _F.NORMALIZE_KEY_FIELD in norm_dict:
            self._add_error(
                errors,
                "sources.{} normalize.kind=map_values does not support normalize.key_field".format(source_id),
                path="{}.{}".format(norm_path, _F.NORMALIZE_KEY_FIELD),
            )
        if _F.NORMALIZE_ON_CONFLICT in norm_dict:
            self._add_error(
                errors,
                "sources.{} normalize.kind=map_values does not support normalize.on_conflict".format(source_id),
                path="{}.{}".format(norm_path, _F.NORMALIZE_ON_CONFLICT),
            )
        if _F.NORMALIZE_ON_EMPTY in norm_dict:
            self._add_error(
                errors,
                "sources.{} normalize.kind=map_values does not support normalize.on_empty".format(source_id),
                path="{}.{}".format(norm_path, _F.NORMALIZE_ON_EMPTY),
            )
        if _F.NORMALIZE_ON_MISSING in norm_dict:
            self._add_error(
                errors,
                "sources.{} normalize.kind=map_values does not support normalize.on_missing".format(source_id),
                path="{}.{}".format(norm_path, _F.NORMALIZE_ON_MISSING),
            )
        if _F.NORMALIZE_FIELDS in norm_dict:
            self._add_error(
                errors,
                "sources.{} normalize.kind=map_values does not support normalize.fields".format(source_id),
                path="{}.{}".format(norm_path, _F.NORMALIZE_FIELDS),
            )

        steps_path = "{}.{}".format(norm_path, _F.NORMALIZE_STEPS)
        steps_list = list_or_none(norm_dict.get(_F.NORMALIZE_STEPS))
        if steps_list is None:
            self._add_error(errors, "'{}' must be a list".format(steps_path), path=steps_path)
            return
        if not steps_list:
            self._add_error(errors, "'{}' must not be empty".format(steps_path), path=steps_path)
            return

        for idx, step_raw in enumerate(steps_list):
            self._validate_normalize_map_values_step(step_raw, errors, steps_path=steps_path, idx=idx)

    def _validate_normalize_map_values_step(
        self,
        step_raw: object,
        errors: List[ValidationIssue],
        *,
        steps_path: str,
        idx: int,
    ) -> None:
        step_path = "{}[{}]".format(steps_path, idx)
        step_dict = mapping_or_none(step_raw)
        if step_dict is None:
            self._add_error(errors, "'{}' must be a dictionary".format(step_path), path=step_path)
            return

        if _F.NORMALIZE_CALL_BY in step_dict:
            self._add_error(
                errors, "'{}' does not support 'call_by'".format(step_path), path="{}.{}".format(step_path, _F.NORMALIZE_CALL_BY)
            )

        step_kind_raw = step_dict.get(_F.NORMALIZE_KIND)
        if step_kind_raw is None:
            self._add_error(errors, "'{}.kind' is required".format(step_path), path="{}.{}".format(step_path, _F.NORMALIZE_KIND))
            return
        if not isinstance(step_kind_raw, str):
            self._add_error(errors, "'{}.kind' must be a string".format(step_path), path="{}.{}".format(step_path, _F.NORMALIZE_KIND))
            return
        step_kind = step_kind_raw.strip()
        if step_kind not in {"take_first", "project_fields"}:
            self._add_error(
                errors,
                "'{}.kind' must be one of: take_first/project_fields".format(step_path),
                path="{}.{}".format(step_path, _F.NORMALIZE_KIND),
            )
            return

        if step_kind == "take_first":
            self._validate_normalize_step_take_first(step_dict, errors, step_path=step_path)
            return

        self._validate_normalize_step_project_fields(step_dict, errors, step_path=step_path)

    def _validate_normalize_step_take_first(
        self,
        step_dict: Dict[str, Any],
        errors: List[ValidationIssue],
        *,
        step_path: str,
    ) -> None:
        if _F.NORMALIZE_FIELDS in step_dict:
            self._add_error(errors, "'{}' does not support fields".format(step_path), path="{}.{}".format(step_path, _F.NORMALIZE_FIELDS))
        if _F.NORMALIZE_ON_MISSING in step_dict:
            self._add_error(
                errors, "'{}' does not support on_missing".format(step_path), path="{}.{}".format(step_path, _F.NORMALIZE_ON_MISSING)
            )
        if _F.NORMALIZE_KEY_FIELD in step_dict:
            self._add_error(
                errors, "'{}' does not support key_field".format(step_path), path="{}.{}".format(step_path, _F.NORMALIZE_KEY_FIELD)
            )
        if _F.NORMALIZE_ON_CONFLICT in step_dict:
            self._add_error(
                errors, "'{}' does not support on_conflict".format(step_path), path="{}.{}".format(step_path, _F.NORMALIZE_ON_CONFLICT)
            )

        on_empty_raw = step_dict.get(_F.NORMALIZE_ON_EMPTY)
        if on_empty_raw is None:
            return
        on_empty = str(on_empty_raw).strip()
        if on_empty not in set(NORMALIZE_ON_EMPTY_ENUM):
            self._add_error(
                errors,
                "'{}.on_empty' must be one of: miss/null/error".format(step_path),
                path="{}.{}".format(step_path, _F.NORMALIZE_ON_EMPTY),
            )

    def _validate_normalize_step_project_fields(
        self,
        step_dict: Dict[str, Any],
        errors: List[ValidationIssue],
        *,
        step_path: str,
    ) -> None:
        if _F.NORMALIZE_ON_EMPTY in step_dict:
            self._add_error(
                errors, "'{}' does not support on_empty".format(step_path), path="{}.{}".format(step_path, _F.NORMALIZE_ON_EMPTY)
            )
        if _F.NORMALIZE_KEY_FIELD in step_dict:
            self._add_error(
                errors, "'{}' does not support key_field".format(step_path), path="{}.{}".format(step_path, _F.NORMALIZE_KEY_FIELD)
            )
        if _F.NORMALIZE_ON_CONFLICT in step_dict:
            self._add_error(
                errors, "'{}' does not support on_conflict".format(step_path), path="{}.{}".format(step_path, _F.NORMALIZE_ON_CONFLICT)
            )

        on_missing_raw = step_dict.get(_F.NORMALIZE_ON_MISSING)
        if on_missing_raw is not None:
            on_missing = str(on_missing_raw).strip()
            if on_missing not in set(NORMALIZE_ON_MISSING_ENUM):
                self._add_error(
                    errors,
                    "'{}.on_missing' must be one of: error/null".format(step_path),
                    path="{}.{}".format(step_path, _F.NORMALIZE_ON_MISSING),
                )

        fields_path = "{}.{}".format(step_path, _F.NORMALIZE_FIELDS)
        if _F.NORMALIZE_FIELDS not in step_dict:
            self._add_error(errors, "'{}' is required".format(fields_path), path=fields_path)
            return

        self._validate_normalize_project_fields_rules(step_dict.get(_F.NORMALIZE_FIELDS), errors, fields_path=fields_path)

    def _validate_normalize_project_fields_rules(
        self,
        rules_raw: object,
        errors: List[ValidationIssue],
        *,
        fields_path: str,
    ) -> None:
        fields_dict = mapping_or_none(rules_raw)
        if fields_dict is None:
            self._add_error(errors, "'{}' must be a dictionary".format(fields_path), path=fields_path)
            return
        if not fields_dict:
            self._add_error(errors, "'{}' must not be empty".format(fields_path), path=fields_path)
            return

        for field_name_raw, rule_raw in fields_dict.items():
            field_name = str(field_name_raw or "").strip()
            rule_path = "{}.{}".format(fields_path, field_name or "<empty>")
            rule_dict = mapping_or_none(rule_raw)
            if rule_dict is None:
                self._add_error(errors, "'{}' must be a dictionary".format(rule_path), path=rule_path)
                continue
            self._validate_normalize_project_field_rule(rule_dict, errors, rule_path=rule_path)

    def _validate_normalize_project_field_rule(
        self,
        rule_dict: Dict[str, Any],
        errors: List[ValidationIssue],
        *,
        rule_path: str,
    ) -> None:
        has_from_key = "from_key" in rule_dict
        has_extract = "extract" in rule_dict
        if has_from_key and has_extract:
            self._add_error(errors, "'{}' must not declare both 'from_key' and 'extract'".format(rule_path), path=rule_path)
            return
        if not has_from_key and not has_extract:
            self._add_error(errors, "'{}' must declare 'from_key' or 'extract'".format(rule_path), path=rule_path)
            return

        if has_from_key:
            from_key_raw = rule_dict.get("from_key")
            if not isinstance(from_key_raw, bool):
                self._add_error(errors, "'{}.from_key' must be a boolean".format(rule_path), path="{}.from_key".format(rule_path))
            return

        extract_raw = rule_dict.get("extract")
        if not isinstance(extract_raw, str):
            self._add_error(errors, "'{}.extract' must be a string".format(rule_path), path="{}.extract".format(rule_path))
            return

        extract_expr = extract_raw.strip()
        if not extract_expr:
            self._add_error(errors, "'{}.extract' must not be empty".format(rule_path), path="{}.extract".format(rule_path))
            return

        try:
            _ = compile_field_extract(extract_expr)
        except ScalimFieldExtractCompileError as exc:
            self._add_error(errors, "Invalid extract path: {}".format(str(exc)), path="{}.extract".format(rule_path))

    def _is_valid_loader_ref(self, loader_ref: str) -> bool:
        return is_valid_callable_reference(loader_ref)
