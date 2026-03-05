# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false, reportAttributeAccessIssue=false, reportUnknownMemberType=false

from typing import Any, Dict, List, Optional, Tuple, Union, cast

from ...schema_dsl.constants import (
    DEFAULT_BIND_AS,
    DEFAULT_BIND_CACHE_MODE,
    DEFAULT_CACHE_MODE,
)
from ...schema_dsl.models import (
    BIND_KEY_CONFIG_KEYS,
    BIND_KEYS,
    BIND_ROWS_KEYS,
    DEMAND_KEYS,
    LOADER_RETRY_KEYS,
    LOOKUP_CAST_KEYS,
    MAIN_SOURCE_KEYS,
    SOURCE_KEYS,
    BindConfig,
    BindKeysConfig,
    BindRowsConfig,
    LoaderRetryConfig,
    LookupCastConfig,
    MainSourceConfig,
    SourceConfig,
    SourceFieldConfig,
)
from ..models import RawDemand
from .utils import str_or_none


class ParserSourcesMixin:
    def _parse_loader_retry(self, raw_retry: Any) -> Optional[LoaderRetryConfig]:
        if not isinstance(raw_retry, dict):
            return None
        retry_dict: Dict[str, Any] = cast("Dict[str, Any]", raw_retry)

        def _as_int(value: Any) -> Optional[int]:
            try:
                if isinstance(value, bool):
                    return None
                return int(value)
            except (TypeError, ValueError):
                return None

        def _as_float(value: Any) -> Optional[float]:
            try:
                if isinstance(value, bool):
                    return None
                return float(value)
            except (TypeError, ValueError):
                return None

        enabled = None
        if LOADER_RETRY_KEYS["enabled"] in retry_dict:
            enabled = bool(retry_dict.get(LOADER_RETRY_KEYS["enabled"]))

        should_retry = None
        if LOADER_RETRY_KEYS["should_retry"] in retry_dict:
            should_retry = str_or_none(retry_dict.get(LOADER_RETRY_KEYS["should_retry"]))

        return LoaderRetryConfig(
            enabled=enabled,
            should_retry=should_retry,
            max_attempts=_as_int(retry_dict.get(LOADER_RETRY_KEYS["max_attempts"]))
            if LOADER_RETRY_KEYS["max_attempts"] in retry_dict
            else None,
            max_elapsed_seconds=_as_float(retry_dict.get(LOADER_RETRY_KEYS["max_elapsed_seconds"]))
            if LOADER_RETRY_KEYS["max_elapsed_seconds"] in retry_dict
            else None,
            backoff=str(retry_dict.get(LOADER_RETRY_KEYS["backoff"])) if LOADER_RETRY_KEYS["backoff"] in retry_dict else None,
            base_delay_seconds=_as_float(retry_dict.get(LOADER_RETRY_KEYS["base_delay_seconds"]))
            if LOADER_RETRY_KEYS["base_delay_seconds"] in retry_dict
            else None,
            max_delay_seconds=_as_float(retry_dict.get(LOADER_RETRY_KEYS["max_delay_seconds"]))
            if LOADER_RETRY_KEYS["max_delay_seconds"] in retry_dict
            else None,
            jitter=bool(retry_dict.get(LOADER_RETRY_KEYS["jitter"])) if LOADER_RETRY_KEYS["jitter"] in retry_dict else None,
        )

    def _parse_main_source(self, raw: RawDemand) -> MainSourceConfig:
        raw_main_source = raw.get_mapping(DEMAND_KEYS["main_source"])
        if raw_main_source is None:
            return MainSourceConfig()

        main_source_data = raw_main_source
        source_id = str(main_source_data.get(MAIN_SOURCE_KEYS["source_id"], ""))
        loader = str(main_source_data.get(MAIN_SOURCE_KEYS["loader"], ""))
        params = self._parse_params(main_source_data)
        order_by = self._parse_order_by(main_source_data)
        retry = self._parse_loader_retry(main_source_data.get(MAIN_SOURCE_KEYS["retry"]))

        return MainSourceConfig(
            source_id=source_id,
            loader=loader,
            params=params,
            retry=retry,
            order_by=order_by,
        )

    def _parse_sources(self, raw: RawDemand) -> Dict[str, SourceConfig]:
        sources: Dict[str, SourceConfig] = {}
        raw_sources = raw.get_mapping(DEMAND_KEYS["sources"])
        if raw_sources is None:
            return sources

        for source_id_raw, source_data_raw in raw_sources.items():
            if not isinstance(source_data_raw, dict):
                continue

            source_id: str = str(source_id_raw)
            source_data: Dict[str, Any] = source_data_raw

            key = self._parse_key(source_data)
            lookup_cast = self._parse_lookup_cast(source_data.get(SOURCE_KEYS["lookup_cast"]))
            lookup_chunk_size = self._parse_lookup_chunk_size(source_data.get(SOURCE_KEYS["lookup_chunk_size"]))
            bind = self._parse_bind(source_data.get(SOURCE_KEYS["bind"]))
            params = self._parse_params(source_data)
            retry = self._parse_loader_retry(source_data.get(SOURCE_KEYS["retry"]))

            sources[source_id] = SourceConfig(
                source_id=source_id,
                loader=str(source_data.get(SOURCE_KEYS["loader"], "")),
                key=key,
                lookup_cast=lookup_cast,
                lookup_chunk_size=lookup_chunk_size,
                cache_mode=str(source_data.get(SOURCE_KEYS["cache_mode"], DEFAULT_CACHE_MODE)),
                retry=retry,
                bind=bind,
                params=params,
            )

        return sources

    def _with_main_source_fields(
        self,
        main_source: MainSourceConfig,
        fields: Dict[str, SourceFieldConfig],
    ) -> MainSourceConfig:
        return MainSourceConfig(
            source_id=main_source.source_id,
            loader=main_source.loader,
            fields=fields,
            params=main_source.params,
            retry=main_source.retry,
            order_by=main_source.order_by,
        )

    def _with_source_fields(
        self,
        sources: Dict[str, SourceConfig],
        fields_by_source: Dict[str, Dict[str, SourceFieldConfig]],
    ) -> Dict[str, SourceConfig]:
        updated: Dict[str, SourceConfig] = {}
        for source_id, source_config in sources.items():
            updated[source_id] = SourceConfig(
                source_id=source_config.source_id,
                loader=source_config.loader,
                key=source_config.key,
                lookup_cast=source_config.lookup_cast,
                lookup_chunk_size=source_config.lookup_chunk_size,
                cache_mode=source_config.cache_mode,
                retry=source_config.retry,
                bind=source_config.bind,
                fields=fields_by_source.get(source_id, {}),
                params=source_config.params,
            )
        return updated

    def _parse_bind(self, raw_bind: Any) -> Optional[BindConfig]:
        if not isinstance(raw_bind, dict):
            return None

        bind_dict: Dict[str, Any] = raw_bind
        use_rows = None
        use_keys = None
        if BIND_KEYS["use_rows"] in bind_dict:
            raw_rows = bind_dict.get(BIND_KEYS["use_rows"])
            if isinstance(raw_rows, dict):
                rows_dict = cast("Dict[str, Any]", raw_rows)
                use_rows = BindRowsConfig(
                    param=str(rows_dict.get(BIND_ROWS_KEYS["param"], "")),
                    cache_mode=str(rows_dict.get(BIND_ROWS_KEYS["cache_mode"], DEFAULT_BIND_CACHE_MODE)),
                )
        if BIND_KEYS["use_keys"] in bind_dict:
            raw_keys = bind_dict.get(BIND_KEYS["use_keys"])
            if isinstance(raw_keys, dict):
                keys_dict = cast("Dict[str, Any]", raw_keys)
                use_keys = BindKeysConfig(
                    param=str(keys_dict.get(BIND_KEY_CONFIG_KEYS["param"], "")),
                    as_=str(keys_dict.get(BIND_KEY_CONFIG_KEYS["as_"], DEFAULT_BIND_AS)),
                )
        return BindConfig(use_rows=use_rows, use_keys=use_keys)

    def _parse_lookup_chunk_size(self, raw_value: Any) -> Optional[int]:
        if raw_value is None:
            return None
        if isinstance(raw_value, bool):
            return None
        if not isinstance(raw_value, (int, float, str)):
            return None
        try:
            return int(raw_value)
        except (TypeError, ValueError):
            return None

    def _parse_lookup_cast(self, raw_lookup: Any) -> Optional[LookupCastConfig]:
        if not isinstance(raw_lookup, dict):
            return None
        lookup_dict: Dict[str, Any] = raw_lookup
        return LookupCastConfig(
            name=str(lookup_dict.get(LOOKUP_CAST_KEYS["name"], "")),
            sep=str_or_none(lookup_dict.get(LOOKUP_CAST_KEYS["sep"])),
        )

    def _parse_key(self, source_data: Dict[str, Any]) -> Union[str, Tuple[str, ...]]:
        key_raw: Any = source_data.get(SOURCE_KEYS["key"], "")
        if isinstance(key_raw, list):
            return tuple(str(k) for k in key_raw)
        return str(key_raw)

    def _parse_params(self, source_data: Dict[str, Any]) -> Dict[str, Any]:
        params_raw: Any = source_data.get(SOURCE_KEYS["params"])
        if isinstance(params_raw, dict):
            return dict(params_raw)
        return {}

    def _parse_order_by(self, source_data: Dict[str, Any]) -> Tuple[str, ...]:
        order_raw: Any = source_data.get(MAIN_SOURCE_KEYS["order_by"])
        if order_raw is None:
            return ()
        if not isinstance(order_raw, list):
            msg = "main_source.order_by must be a list"
            raise TypeError(msg)
        order_by: List[str] = []
        for item in order_raw:
            if not isinstance(item, str):
                msg = "main_source.order_by items must be strings"
                raise TypeError(msg)
            raw = item.strip()
            if not raw or raw == "-":
                msg = "main_source.order_by items must be non-empty strings"
                raise ValueError(msg)
            order_by.append(raw)
        return tuple(order_by)
