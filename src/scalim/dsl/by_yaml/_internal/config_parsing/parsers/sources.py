from typing import Any, Dict, List, Optional, Tuple, Union

from ....schema_dsl.constants import (
    DEFAULT_CACHE_MODE,
)
from ....schema_dsl.models import (
    DEMAND_KEYS,
    LOADER_RETRY_KEYS,
    LOOKUP_CAST_KEYS,
    MAIN_SOURCE_KEYS,
    NORMALIZE_KEYS,
    SOURCE_KEYS,
    LoaderRetryConfig,
    LookupCastConfig,
    MainSourceConfig,
    NormalizeConfig,
    NormalizeProjectFieldRuleConfig,
    NormalizeStepConfig,
    SourceConfig,
    SourceFieldConfig,
)
from ..models import RawDemand
from .utils import list_or_none, mapping_or_none, str_or_none


class ParserSourcesMixin:
    @staticmethod
    def _normalize_opt_str(value: object) -> Optional[str]:
        if value is None:
            return None
        raw = str(value).strip()
        return raw or None

    def _parse_normalize_project_fields(self, raw_value: object) -> Dict[str, NormalizeProjectFieldRuleConfig]:
        fields_raw = mapping_or_none(raw_value)
        if fields_raw is None:
            return {}

        fields_by_name: Dict[str, NormalizeProjectFieldRuleConfig] = {}
        for field_name_raw, field_rule_raw in fields_raw.items():
            field_name = str(field_name_raw or "").strip()
            if not field_name:
                continue
            field_rule = mapping_or_none(field_rule_raw)
            if field_rule is None:
                continue
            from_key = field_rule.get("from_key")
            extract = self._normalize_opt_str(field_rule.get("extract"))
            fields_by_name[field_name] = NormalizeProjectFieldRuleConfig(
                from_key=bool(from_key) if from_key is not None else None,
                extract=extract,
            )
        return fields_by_name

    def _parse_normalize_steps(self, raw_value: object) -> Tuple[NormalizeStepConfig, ...]:
        steps_raw = list_or_none(raw_value)
        if steps_raw is None:
            return ()

        steps_converted: List[NormalizeStepConfig] = []
        for item in steps_raw:
            step_dict = mapping_or_none(item)
            if step_dict is None:
                continue

            step_kind = str(step_dict.get("kind", "")).strip()
            step_on_empty = self._normalize_opt_str(step_dict.get("on_empty"))
            step_on_missing = self._normalize_opt_str(step_dict.get("on_missing"))
            step_fields = self._parse_normalize_project_fields(step_dict.get("fields"))

            steps_converted.append(
                NormalizeStepConfig(
                    kind=step_kind,
                    on_empty=step_on_empty,
                    on_missing=step_on_missing,
                    fields=step_fields,
                )
            )
        return tuple(steps_converted)

    def _parse_loader_retry(self, raw_retry: object) -> Optional[LoaderRetryConfig]:
        retry_dict = mapping_or_none(raw_retry)
        if retry_dict is None:
            return None

        def _as_int(value: object) -> Optional[int]:
            if isinstance(value, bool) or not isinstance(value, (int, float, str)):
                return None
            try:
                return int(value)
            except (TypeError, ValueError):
                return None

        def _as_float(value: object) -> Optional[float]:
            if isinstance(value, bool) or not isinstance(value, (int, float, str)):
                return None
            try:
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

        source_id = str(raw_main_source.get(MAIN_SOURCE_KEYS["source_id"], ""))
        loader = str(raw_main_source.get(MAIN_SOURCE_KEYS["loader"], ""))
        params = self._parse_params(raw_main_source)
        order_by = self._parse_order_by(raw_main_source)
        retry = self._parse_loader_retry(raw_main_source.get(MAIN_SOURCE_KEYS["retry"]))

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
            source_data = mapping_or_none(source_data_raw)
            if source_data is None:
                continue

            source_id = str(source_id_raw)
            key = self._parse_key(source_data)
            lookup_cast = self._parse_lookup_cast(source_data.get(SOURCE_KEYS["lookup_cast"]))
            lookup_chunk_size = self._parse_lookup_chunk_size(source_data.get(SOURCE_KEYS["lookup_chunk_size"]))
            normalize = self._parse_normalize(source_data.get(SOURCE_KEYS["normalize"]))
            params = self._parse_params(source_data)
            retry = self._parse_loader_retry(source_data.get(SOURCE_KEYS["retry"]))

            sources[source_id] = SourceConfig(
                source_id=source_id,
                loader=str(source_data.get(SOURCE_KEYS["loader"], "")),
                key=key,
                lookup_cast=lookup_cast,
                lookup_chunk_size=lookup_chunk_size,
                normalize=normalize,
                cache_mode=str(source_data.get(SOURCE_KEYS["cache_mode"], DEFAULT_CACHE_MODE)),
                retry=retry,
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
                normalize=source_config.normalize,
                cache_mode=source_config.cache_mode,
                retry=source_config.retry,
                fields=fields_by_source.get(source_id, {}),
                params=source_config.params,
            )
        return updated

    def _parse_lookup_chunk_size(self, raw_value: object) -> Optional[int]:
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

    def _parse_lookup_cast(self, raw_lookup: object) -> Optional[LookupCastConfig]:
        lookup_dict = mapping_or_none(raw_lookup)
        if lookup_dict is None:
            return None
        return LookupCastConfig(
            name=str(lookup_dict.get(LOOKUP_CAST_KEYS["name"], "")),
            sep=str_or_none(lookup_dict.get(LOOKUP_CAST_KEYS["sep"])),
        )

    def _parse_normalize(self, raw_value: object) -> Optional[NormalizeConfig]:
        norm_dict = mapping_or_none(raw_value)
        if norm_dict is None:
            return None

        kind = str(norm_dict.get(NORMALIZE_KEYS["kind"], "")).strip()
        key_field = str(norm_dict.get(NORMALIZE_KEYS["key_field"], "")).strip()
        on_conflict = str(norm_dict.get(NORMALIZE_KEYS["on_conflict"], "error")).strip() or "error"

        on_empty = None
        if NORMALIZE_KEYS["on_empty"] in norm_dict:
            on_empty = self._normalize_opt_str(norm_dict.get(NORMALIZE_KEYS["on_empty"]))

        on_missing = None
        if NORMALIZE_KEYS["on_missing"] in norm_dict:
            on_missing = self._normalize_opt_str(norm_dict.get(NORMALIZE_KEYS["on_missing"]))

        call_by = None
        if NORMALIZE_KEYS["call_by"] in norm_dict:
            call_by = self._normalize_opt_str(norm_dict.get(NORMALIZE_KEYS["call_by"]))

        fields_by_name = self._parse_normalize_project_fields(norm_dict.get(NORMALIZE_KEYS["fields"]))
        steps_converted = self._parse_normalize_steps(norm_dict.get(NORMALIZE_KEYS["steps"]))

        return NormalizeConfig(
            kind=kind,
            key_field=key_field,
            on_conflict=on_conflict,
            on_empty=on_empty,
            on_missing=on_missing,
            fields=fields_by_name,
            steps=steps_converted,
            call_by=call_by,
        )

    def _parse_key(self, source_data: Dict[str, Any]) -> Union[str, Tuple[str, ...]]:
        key_raw = source_data.get(SOURCE_KEYS["key"], "")
        key_items = list_or_none(key_raw)
        if key_items is not None:
            return tuple(str(item) for item in key_items)
        return str(key_raw)

    def _parse_params(self, source_data: Dict[str, Any]) -> Dict[str, Any]:
        params_raw = mapping_or_none(source_data.get(SOURCE_KEYS["params"]))
        if params_raw is None:
            return {}
        return dict(params_raw)

    def _parse_order_by(self, source_data: Dict[str, Any]) -> Tuple[str, ...]:
        order_raw = source_data.get(MAIN_SOURCE_KEYS["order_by"])
        if order_raw is None:
            return ()
        order_items = list_or_none(order_raw)
        if order_items is None:
            msg = "main_source.order_by must be a list"
            raise TypeError(msg)

        order_by: List[str] = []
        for item in order_items:
            if not isinstance(item, str):
                msg = "main_source.order_by items must be strings"
                raise TypeError(msg)
            raw = item.strip()
            if not raw or raw == "-":
                msg = "main_source.order_by items must be non-empty strings"
                raise ValueError(msg)
            order_by.append(raw)
        return tuple(order_by)


__all__ = ()
