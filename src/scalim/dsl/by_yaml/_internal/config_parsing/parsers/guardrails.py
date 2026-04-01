from typing import Any, Dict, List, Optional, Tuple

from ....schema_dsl.constants import DEFAULT_GUARDRAILS_MODE
from ....schema_dsl.models import (
    DEMAND_KEYS,
    GUARDRAILS_COMPUTE_KEYS,
    GUARDRAILS_KEYS,
    GUARDRAILS_LOADER_KEYS,
    GUARDRAILS_RELATIONS_KEYS,
    GuardrailsComputeConfig,
    GuardrailsConfig,
    GuardrailsLoaderConfig,
    GuardrailsRelationsConfig,
)
from ..models import FieldDefIndex
from .utils import list_or_none, mapping_or_none


class ParserGuardrailsMixin:
    def _parse_guardrails(
        self,
        raw: Dict[str, Any],
        field_def_index: FieldDefIndex,
    ) -> Optional[GuardrailsConfig]:
        guardrails_dict = mapping_or_none(raw.get(DEMAND_KEYS["guardrails"]))
        if guardrails_dict is None:
            return None

        enabled = bool(guardrails_dict.get(GUARDRAILS_KEYS["enabled"], False))
        mode = str(guardrails_dict.get(GUARDRAILS_KEYS["mode"], DEFAULT_GUARDRAILS_MODE))

        loader = self._parse_guardrails_loader(guardrails_dict.get(GUARDRAILS_KEYS["loader"]), field_def_index)
        relations = self._parse_guardrails_relations(guardrails_dict.get(GUARDRAILS_KEYS["relations"]))
        compute = self._parse_guardrails_compute(guardrails_dict.get(GUARDRAILS_KEYS["compute"]))

        return GuardrailsConfig(
            enabled=enabled,
            mode=mode,
            loader=loader,
            relations=relations,
            compute=compute,
        )

    def _parse_guardrails_loader(
        self,
        loader_raw: object,
        field_def_index: FieldDefIndex,
    ) -> Optional[GuardrailsLoaderConfig]:
        loader_dict = mapping_or_none(loader_raw)
        if loader_dict is None:
            return None

        validate_result = bool(loader_dict.get(GUARDRAILS_LOADER_KEYS["validate_result"], False))
        required_fields = self._parse_guardrails_required_fields(
            loader_dict.get(GUARDRAILS_LOADER_KEYS["required_fields"]), field_def_index
        )
        on_transform_error_raw = loader_dict.get(GUARDRAILS_LOADER_KEYS["on_transform_error"])
        on_transform_error = str(on_transform_error_raw) if on_transform_error_raw is not None else None

        return GuardrailsLoaderConfig(
            validate_result=validate_result,
            required_fields=required_fields,
            on_transform_error=on_transform_error,
        )

    def _parse_guardrails_required_fields(
        self,
        required_fields_raw: object,
        field_def_index: FieldDefIndex,
    ) -> Tuple[str, ...]:
        if required_fields_raw is None:
            return ()
        required_field_items = list_or_none(required_fields_raw)
        if required_field_items is None:
            msg = "guardrails.loader.required_fields must be a list"
            raise TypeError(msg)

        required: List[str] = []
        for idx, item in enumerate(required_field_items):
            required.append(self._resolve_guardrails_field_ref(item, idx, field_def_index))
        return tuple(required)

    def _resolve_guardrails_field_ref(
        self,
        item: object,
        idx: int,
        field_def_index: FieldDefIndex,
    ) -> str:
        if isinstance(item, str):
            field_id = item
        else:
            typed = mapping_or_none(item)
            if typed is None:
                msg = "guardrails.loader.required_fields[{}] must be field_id string or YAML alias".format(idx)
                raise TypeError(msg)
            direct = field_def_index.alias_index.get(typed)
            if direct is None:
                msg = "guardrails.loader.required_fields[{}] must be field_id string or YAML alias".format(idx)
                raise ValueError(msg)
            field_id = direct.field_id

        if field_id not in field_def_index.defs_by_id:
            msg = "guardrails.loader.required_fields[{}] references unknown field_id '{}'".format(idx, field_id)
            raise ValueError(msg)

        return field_id

    def _parse_guardrails_relations(self, relations_raw: object) -> Optional[GuardrailsRelationsConfig]:
        relations_dict = mapping_or_none(relations_raw)
        if relations_dict is None:
            return None

        null_key_max_rate = self._parse_guardrails_rate(relations_dict.get(GUARDRAILS_RELATIONS_KEYS["null_key_max_rate"]))
        type_error_max_rate = self._parse_guardrails_rate(relations_dict.get(GUARDRAILS_RELATIONS_KEYS["type_error_max_rate"]))

        return GuardrailsRelationsConfig(
            null_key_max_rate=null_key_max_rate,
            type_error_max_rate=type_error_max_rate,
        )

    def _parse_guardrails_compute(self, compute_raw: object) -> Optional[GuardrailsComputeConfig]:
        compute_dict = mapping_or_none(compute_raw)
        if compute_dict is None:
            return None

        on_error_raw = compute_dict.get(GUARDRAILS_COMPUTE_KEYS["on_error"])
        on_error = str(on_error_raw) if on_error_raw is not None else None

        return GuardrailsComputeConfig(on_error=on_error)

    def _parse_guardrails_rate(self, raw_value: object) -> Optional[float]:
        if raw_value is None or isinstance(raw_value, bool) or not isinstance(raw_value, (int, float, str)):
            return None
        try:
            return float(raw_value)
        except (TypeError, ValueError):
            return None


__all__ = ()
