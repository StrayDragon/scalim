from typing import Any, Dict, List, Optional, Set

from ...params_template import ParamsTemplateCompileError, compile_params_template
from ...schema_dsl.constants import (
    DEFAULT_CACHE_MODE,
    LOOKUP_CAST_NAME_ENUM,
)
from ..parsers.utils import list_or_none, mapping_or_none
from .base import ValidatorMixinBase
from .constants import LEGACY_FIELDS, MIN_PARTS_COUNT, F
from .issues import ValidationIssue

_F = F
_MIN_PARTS_COUNT = MIN_PARTS_COUNT


class ValidatorSourcesMixin(ValidatorMixinBase):
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
                resolve_runtime=False,  # `runtime_vars` 在 `run/compile` 时提供,`YAML` 校验阶段不解析.
                allow_keys=allow_directives,
                allow_rows=allow_directives,
            )
        except ParamsTemplateCompileError as exc:
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

        if main_source_id:
            main_dict = mapping_or_none(config.get(_F.MAIN_SOURCE))
            if main_dict is not None:
                allowed[main_source_id] = self._collect_declared_field_names(main_dict.get(_F.FIELDS))
            else:
                allowed[main_source_id] = set()

        sources_raw = mapping_or_none(config.get(_F.SOURCES, {}))
        if sources_raw is None:
            return allowed

        for source_id_raw, source_data_raw in sources_raw.items():
            source_id = str(source_id_raw)
            source_dict = mapping_or_none(source_data_raw)
            if source_dict is None:
                allowed[source_id] = set()
                continue
            source_allowed = self._collect_declared_field_names(source_dict.get(_F.FIELDS))
            source_allowed.update(self._collect_source_key_names(source_dict.get(_F.KEY)))
            allowed[source_id] = source_allowed

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

    def _validate_legacy_fields(self, config: Dict[str, Any], errors: List[ValidationIssue]) -> None:  # noqa: C901
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
                msg = (
                    "Source '{}' has invalid loader reference '{}'. Expected format: 'module.path:ClassName' or 'module.path.function'"
                ).format(source_id, loader)
                self._add_error(errors, msg, path="sources.{}.{}".format(source_id, _F.LOADER))

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
            msg = (
                "Main source has invalid loader reference '{}'. Expected format: 'module.path:ClassName' or 'module.path.function'"
            ).format(loader)
            self._add_error(errors, msg, path="{}.{}".format(_F.MAIN_SOURCE, _F.LOADER))

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
        if kind != "index_by_key":
            self._add_error(
                errors,
                "sources.{} normalize.kind must be 'index_by_key'".format(source_id),
                path="{}.{}".format(norm_path, _F.NORMALIZE_KIND),
            )

        key_field = str(norm_dict.get(_F.NORMALIZE_KEY_FIELD, "")).strip()
        if not key_field:
            self._add_error(
                errors,
                "sources.{} normalize.key_field is required".format(source_id),
                path="{}.{}".format(norm_path, _F.NORMALIZE_KEY_FIELD),
            )

        if kind == "index_by_key":
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
        if on_conflict not in {"error", "first", "last"}:
            self._add_error(
                errors,
                "sources.{} normalize.on_conflict must be one of: error/first/last".format(source_id),
                path="{}.{}".format(norm_path, _F.NORMALIZE_ON_CONFLICT),
            )

    def _is_valid_loader_ref(self, loader_ref: str) -> bool:  # noqa: PLR0911
        if not loader_ref:
            return False

        if ":" in loader_ref:
            parts = loader_ref.split(":")
            if len(parts) != _MIN_PARTS_COUNT:
                return False
            module_path, attr_path = parts
            if not module_path or not attr_path:
                return False
            if not all(part.isidentifier() for part in module_path.split(".")):
                return False
            return all(part.isidentifier() for part in attr_path.split("."))

        parts = loader_ref.split(".")
        if len(parts) < _MIN_PARTS_COUNT:
            return False
        return all(part.isidentifier() for part in parts)
