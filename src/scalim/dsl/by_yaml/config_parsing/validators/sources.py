# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false, reportAttributeAccessIssue=false, reportUnknownMemberType=false, reportUninitializedInstanceVariable=false

from typing import Any, Dict, List, Optional, Set, cast

from ...schema_dsl.constants import (
    BIND_AS_ENUM,
    BIND_CACHE_MODE_ENUM,
    DEFAULT_BIND_AS,
    DEFAULT_BIND_CACHE_MODE,
    DEFAULT_CACHE_MODE,
    LOOKUP_CAST_NAME_ENUM,
)
from .constants import LEGACY_FIELDS, MIN_PARTS_COUNT, F
from .issues import ValidationIssue

_F = F
_MIN_PARTS_COUNT = MIN_PARTS_COUNT


class ValidatorSourcesMixin:
    _step_allowed_fields_by_source: Dict[str, Set[str]]

    def _collect_declared_field_names(self, fields_raw: Any) -> Set[str]:
        names: Set[str] = set()
        if not isinstance(fields_raw, dict):
            return names
        for field_id_raw in fields_raw:
            field_id = str(field_id_raw or "").strip()
            if not field_id:
                continue
            names.add(field_id)
        return names

    def _collect_source_key_names(self, key_raw: Any) -> Set[str]:
        names: Set[str] = set()
        if isinstance(key_raw, list):
            for item in key_raw:
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
            main_raw: Any = config.get(_F.MAIN_SOURCE)
            if isinstance(main_raw, dict):
                main_dict = cast("Dict[str, Any]", main_raw)
                allowed[main_source_id] = self._collect_declared_field_names(main_dict.get(_F.FIELDS))
            else:
                allowed[main_source_id] = set()

        sources_raw: Any = config.get(_F.SOURCES, {})
        if not isinstance(sources_raw, dict):
            return allowed

        for source_id_raw, source_data_raw in sources_raw.items():
            source_id = str(source_id_raw)
            if not isinstance(source_data_raw, dict):
                allowed[source_id] = set()
                continue
            source_dict = cast("Dict[str, Any]", source_data_raw)
            source_allowed = self._collect_declared_field_names(source_dict.get(_F.FIELDS))
            source_allowed.update(self._collect_source_key_names(source_dict.get(_F.KEY)))
            allowed[source_id] = source_allowed

        return allowed

    def _validate_required_fields(self, config: Dict[str, Any], errors: List[ValidationIssue]) -> None:
        required_fields = [_F.NAME, _F.MAIN_SOURCE]
        for field in required_fields:
            if field not in config:
                self._add_error(errors, "Missing required field: '{}'".format(field), path=field)

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

        sources_raw: Any = config.get(_F.SOURCES, {})
        if isinstance(sources_raw, dict):
            for source_id, source_data in sources_raw.items():
                if not isinstance(source_data, dict):
                    continue
                for key in source_data:
                    if key in LEGACY_FIELDS:
                        path = "sources.{}.{}".format(source_id, key)
                        self._add_error(errors, "Legacy field '{}' is not allowed".format(path), path=path)

        fields_raw: Any = config.get(_F.FIELDS, {})
        if isinstance(fields_raw, dict):
            for field_id, field_data in fields_raw.items():
                if not isinstance(field_data, dict):
                    continue
                for key in field_data:
                    if key in LEGACY_FIELDS:
                        path = "fields.{}.{}".format(field_id, key)
                        self._add_error(errors, "Legacy field '{}' is not allowed".format(path), path=path)

    def _validate_sources(self, config: Dict[str, Any], errors: List[ValidationIssue]) -> Dict[str, Dict[str, bool]]:  # noqa: C901
        sources_info: Dict[str, Dict[str, bool]] = {}
        sources_raw: Any = config.get(_F.SOURCES)
        if not isinstance(sources_raw, dict):
            return sources_info

        for source_id_raw, source_data_raw in sources_raw.items():
            source_id: str = str(source_id_raw)

            if not isinstance(source_data_raw, dict):
                self._add_error(errors, "Source '{}' must be a dictionary".format(source_id), path="sources.{}".format(source_id))
                continue

            source_dict = cast("Dict[str, Any]", source_data_raw)

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

            loader: Any = source_dict.get(_F.LOADER, "")
            if loader and not self._is_valid_loader_ref(str(loader)):
                msg = (
                    "Source '{}' has invalid loader reference '{}'. Expected format: 'module.path:ClassName' or 'module.path.function'"
                ).format(source_id, loader)
                self._add_error(errors, msg, path="sources.{}.{}".format(source_id, _F.LOADER))

            bind_raw = source_dict.get(_F.BIND)
            if bind_raw is not None:
                self._validate_bind(bind_raw, errors, "sources.{}".format(source_id))

            lookup_raw = source_dict.get(_F.LOOKUP_CAST)
            if lookup_raw is not None:
                self._validate_lookup_cast(lookup_raw, errors, "sources.{}".format(source_id))

            cache_mode = str(source_dict.get(_F.CACHE_MODE, DEFAULT_CACHE_MODE))
            if cache_mode not in ("none", "preload_forever"):
                self._add_error(
                    errors,
                    "Source '{}' has invalid cache_mode '{}' (expected: none/preload_forever)".format(source_id, cache_mode),
                    path="sources.{}.{}".format(source_id, _F.CACHE_MODE),
                )
            bind_present = False
            if isinstance(bind_raw, dict):
                bind_dict = cast("Dict[str, Any]", bind_raw)
                if _F.USE_ROWS in bind_dict and isinstance(bind_dict.get(_F.USE_ROWS), dict):
                    bind_present = bool(cast("Dict[str, Any]", bind_dict[_F.USE_ROWS]).get(_F.PARAM))
                if _F.USE_KEYS in bind_dict and isinstance(bind_dict.get(_F.USE_KEYS), dict):
                    bind_present = bool(cast("Dict[str, Any]", bind_dict[_F.USE_KEYS]).get(_F.PARAM)) or bind_present
            sources_info[source_id] = {
                "bind": bind_present,
                "preload": cache_mode == "preload_forever",
            }

        return sources_info

    def _validate_main_source(self, config: Dict[str, Any], errors: List[ValidationIssue]) -> str:
        main_source_raw: Any = config.get(_F.MAIN_SOURCE)
        if not isinstance(main_source_raw, dict):
            self._add_error(errors, "'{}' must be a dictionary".format(_F.MAIN_SOURCE), path=_F.MAIN_SOURCE)
            return ""

        main_source_data = cast("Dict[str, Any]", main_source_raw)
        source_id = str(main_source_data.get(_F.SOURCE_ID, ""))
        loader = main_source_data.get(_F.LOADER)
        sources_raw: Any = config.get(_F.SOURCES, {})

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

        if source_id and isinstance(sources_raw, dict) and str(source_id) in sources_raw:
            self._add_error(
                errors,
                "Main source '{}' must not appear in 'sources'".format(source_id),
                path="{}.{}".format(_F.MAIN_SOURCE, _F.SOURCE_ID),
            )

        self._validate_main_source_order_by(main_source_data, errors)

        return source_id

    def _validate_main_source_order_by(
        self,
        main_source_data: Dict[str, Any],
        errors: List[ValidationIssue],
    ) -> None:
        order_by_raw: Any = main_source_data.get(_F.ORDER_BY)
        if order_by_raw is None:
            return
        if not isinstance(order_by_raw, list):
            self._add_error(
                errors,
                "'{}.{}' must be a list".format(_F.MAIN_SOURCE, _F.ORDER_BY),
                path="{}.{}".format(_F.MAIN_SOURCE, _F.ORDER_BY),
            )
            return
        main_fields_raw = main_source_data.get(_F.FIELDS)
        main_field_ids = set(main_fields_raw.keys()) if isinstance(main_fields_raw, dict) else set()
        for idx, item in enumerate(order_by_raw):
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

    def _validate_bind(
        self,
        bind_raw: Any,
        errors: List[ValidationIssue],
        context: str,
        path_prefix: Optional[str] = None,
    ) -> None:
        bind_path = "{}.bind".format(path_prefix or context)
        if not isinstance(bind_raw, dict):
            self._add_error(errors, "{} bind must be a dictionary".format(context), path=bind_path)
            return

        bind_dict = cast("Dict[str, Any]", bind_raw)
        use_rows_present = _F.USE_ROWS in bind_dict
        use_keys_present = _F.USE_KEYS in bind_dict
        if use_rows_present and use_keys_present:
            self._add_error(errors, "{} bind must not set both 'use_rows' and 'use_keys'".format(context), path=bind_path)
            return
        if not use_rows_present and not use_keys_present:
            self._add_error(errors, "{} bind must set one of 'use_rows' or 'use_keys'".format(context), path=bind_path)
            return

        if use_rows_present:
            self._validate_bind_use_rows(bind_dict.get(_F.USE_ROWS), errors, context, bind_path)
            return

        self._validate_bind_use_keys(bind_dict.get(_F.USE_KEYS), errors, context, bind_path)

    def _validate_bind_use_rows(
        self,
        raw_rows: Any,
        errors: List[ValidationIssue],
        context: str,
        bind_path: str,
    ) -> None:
        if not isinstance(raw_rows, dict):
            self._add_error(errors, "{} bind.use_rows must be a dictionary".format(context), path="{}.use_rows".format(bind_path))
            return
        rows_dict = cast("Dict[str, Any]", raw_rows)
        param = rows_dict.get(_F.PARAM)
        if not param:
            self._add_error(
                errors,
                "{} bind.use_rows missing required 'param'".format(context),
                path="{}.use_rows.{}".format(bind_path, _F.PARAM),
            )
        cache_mode = rows_dict.get(_F.ROWS_CACHE_MODE, DEFAULT_BIND_CACHE_MODE)
        if cache_mode is not None:
            cache_mode_value = str(cache_mode)
            if cache_mode_value not in BIND_CACHE_MODE_ENUM:
                self._add_error(
                    errors,
                    "{} bind.use_rows has invalid cache_mode '{}'".format(context, cache_mode_value),
                    path="{}.use_rows.{}".format(bind_path, _F.ROWS_CACHE_MODE),
                )
        extra_keys = set(rows_dict.keys()) - {_F.PARAM, _F.ROWS_CACHE_MODE}
        if extra_keys:
            self._add_error(
                errors,
                "{} bind.use_rows has unknown keys {}".format(context, sorted(extra_keys)),
                path="{}.use_rows".format(bind_path),
            )

    def _validate_bind_use_keys(
        self,
        raw_keys: Any,
        errors: List[ValidationIssue],
        context: str,
        bind_path: str,
    ) -> None:
        if not isinstance(raw_keys, dict):
            self._add_error(errors, "{} bind.use_keys must be a dictionary".format(context), path="{}.use_keys".format(bind_path))
            return
        keys_dict = cast("Dict[str, Any]", raw_keys)
        param = keys_dict.get(_F.PARAM)
        if not param:
            self._add_error(
                errors,
                "{} bind.use_keys missing required 'param'".format(context),
                path="{}.use_keys.{}".format(bind_path, _F.PARAM),
            )
        as_value = keys_dict.get(_F.AS, DEFAULT_BIND_AS)
        if as_value is not None:
            as_value_str = str(as_value)
            if as_value_str not in BIND_AS_ENUM:
                self._add_error(
                    errors,
                    "{} bind.use_keys has invalid as '{}'".format(context, as_value_str),
                    path="{}.use_keys.{}".format(bind_path, _F.AS),
                )
        extra_keys = set(keys_dict.keys()) - {_F.PARAM, _F.AS}
        if extra_keys:
            self._add_error(
                errors,
                "{} bind.use_keys has unknown keys {}".format(context, sorted(extra_keys)),
                path="{}.use_keys".format(bind_path),
            )

    def _validate_lookup_cast(
        self,
        lookup_raw: Any,
        errors: List[ValidationIssue],
        context: str,
        path_prefix: Optional[str] = None,
    ) -> None:
        lookup_path = "{}.lookup_cast".format(path_prefix or context)
        if not isinstance(lookup_raw, dict):
            self._add_error(errors, "{} lookup_cast must be a dictionary".format(context), path=lookup_path)
            return

        lookup_dict = cast("Dict[str, Any]", lookup_raw)
        name = str(lookup_dict.get(_F.NAME_KEY, ""))
        if name not in LOOKUP_CAST_NAME_ENUM:
            self._add_error(
                errors,
                "{} lookup_cast has invalid name '{}'".format(context, name),
                path="{}.{}".format(lookup_path, _F.NAME_KEY),
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
            if not all(p.isidentifier() for p in module_path.split(".")):
                return False
            return all(p.isidentifier() for p in attr_path.split("."))

        parts = loader_ref.split(".")
        if len(parts) < _MIN_PARTS_COUNT:
            return False
        return all(p.isidentifier() for p in parts)
