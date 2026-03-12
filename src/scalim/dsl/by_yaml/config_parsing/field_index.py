from typing import Any, Dict, List, Optional, Set, Tuple, cast

from ....vendor.compact.typing_extensionsx import override
from ..schema_dsl.constants import FIELD_KIND_SOURCE, OUTPUT_FIELD_DATA_KEY_KEY, OUTPUT_FIELD_ID_KEY, OUTPUT_FIELD_SOURCE_KEY
from ..schema_dsl.models import SOURCE_FIELD_KEYS
from .field_extract import derive_source_field_data_key
from .models import AliasIndex, FieldDef

ERR_OUTPUT_FIELDS_ENTRY = (
    "output.fields[{}] must be string sugar (field_id or source.field_id), explicit field object (field_id or field), or alias"
)


def build_source_data_key_index(field_defs: List[FieldDef]) -> Dict[str, Dict[str, List[FieldDef]]]:
    index: Dict[str, Dict[str, List[FieldDef]]] = {}
    for field_def in field_defs:
        if field_def.kind != FIELD_KIND_SOURCE:
            continue
        source_id = field_def.source_id or ""
        extract_raw = field_def.data.get(SOURCE_FIELD_KEYS["extract"])
        extract_expr = None if extract_raw is None else str(extract_raw)
        data_key = derive_source_field_data_key(field_id=field_def.field_id, extract=extract_expr)
        index.setdefault(source_id, {}).setdefault(data_key, []).append(field_def)
    return index


class OutputFieldErrors:
    def type_error(self, msg: str) -> None:
        raise TypeError(msg)

    def value_error(self, msg: str) -> None:
        raise ValueError(msg)

    def error(self, msg: str) -> None:
        raise ValueError(msg)


class CollectingOutputFieldErrors(OutputFieldErrors):
    _errors: List[str]

    def __init__(self, errors: List[str]) -> None:
        self._errors = errors

    @override
    def type_error(self, msg: str) -> None:
        self._errors.append(msg)

    @override
    def value_error(self, msg: str) -> None:
        self._errors.append(msg)

    @override
    def error(self, msg: str) -> None:
        self._errors.append(msg)


class OutputFieldResolver:
    _defs_by_id: Dict[str, List[FieldDef]]
    _defs_by_data_key_by_source: Dict[str, Dict[str, List[FieldDef]]]
    _alias_index: AliasIndex
    _errors: OutputFieldErrors

    def __init__(
        self,
        defs_by_id: Dict[str, List[FieldDef]],
        alias_index: AliasIndex,
        errors: OutputFieldErrors,
        defs_by_data_key_by_source: Optional[Dict[str, Dict[str, List[FieldDef]]]] = None,
    ) -> None:
        self._defs_by_id = defs_by_id
        self._defs_by_data_key_by_source = (
            defs_by_data_key_by_source
            if defs_by_data_key_by_source is not None
            else self._build_source_data_key_index_from_defs_by_id(defs_by_id)
        )
        self._alias_index = alias_index
        self._errors = errors

    @staticmethod
    def _build_source_data_key_index_from_defs_by_id(defs_by_id: Dict[str, List[FieldDef]]) -> Dict[str, Dict[str, List[FieldDef]]]:
        field_defs: List[FieldDef] = []
        for defs in defs_by_id.values():
            field_defs.extend(defs)
        return build_source_data_key_index(field_defs)

    def resolve_entry(
        self,
        item: Any,
        idx: int,
    ) -> Tuple[Optional[FieldDef], Optional[Dict[str, Any]], str]:
        if isinstance(item, str):
            return self._resolve_entry_string(item, idx)

        if isinstance(item, dict):
            return self._resolve_entry_mapping(cast("Dict[str, Any]", item), idx)

        self._errors.error(ERR_OUTPUT_FIELDS_ENTRY.format(idx))
        return None, None, "invalid"

    def _resolve_entry_string(self, item: str, idx: int) -> Tuple[Optional[FieldDef], Optional[Dict[str, Any]], str]:
        raw = item.strip()
        if not raw:
            self._errors.value_error("output.fields[{}] must be a non-empty string".format(idx))
            return None, None, "invalid"

        if "." not in raw:
            field_def, _override = self._resolve_explicit({OUTPUT_FIELD_ID_KEY: raw}, idx)
            return field_def, None, "string"

        if raw.count(".") != 1:
            self._errors.value_error(
                "output.fields[{}] invalid string '{}': source.field_id sugar must be two-segment (single '.')".format(idx, raw)
            )
            return None, None, "invalid"

        source, field_id = raw.split(".", 1)
        source = source.strip()
        field_id = field_id.strip()
        if not source or not field_id:
            self._errors.value_error(
                "output.fields[{}] invalid string '{}': source.field_id sugar must be '<source>.<field_id>'".format(idx, raw)
            )
            return None, None, "invalid"

        field_def, _override = self._resolve_explicit(
            {
                OUTPUT_FIELD_ID_KEY: field_id,
                OUTPUT_FIELD_SOURCE_KEY: source,
            },
            idx,
        )
        return field_def, None, "signature"

    def _resolve_entry_mapping(self, item: Dict[str, Any], idx: int) -> Tuple[Optional[FieldDef], Optional[Dict[str, Any]], str]:
        if OUTPUT_FIELD_ID_KEY in item:
            field_def, override = self._resolve_explicit(item, idx)
            return field_def, override, "field_id"

        direct_def = self._resolve_alias(item)
        if direct_def is not None:
            return direct_def, None, "alias"

        if OUTPUT_FIELD_DATA_KEY_KEY in item:
            field_def, override = self._resolve_data_key(item, idx)
            return field_def, override, "data_key"

        self._errors.error(ERR_OUTPUT_FIELDS_ENTRY.format(idx))
        return None, None, "invalid"

    def _resolve_alias(self, item: Dict[str, Any]) -> Optional[FieldDef]:
        return self._alias_index.get(item)

    def _resolve_explicit(
        self,
        item: Dict[str, Any],
        idx: int,
    ) -> Tuple[Optional[FieldDef], Optional[Dict[str, Any]]]:
        field_id_raw = item.get(OUTPUT_FIELD_ID_KEY)
        if field_id_raw is None:
            self._errors.value_error("output.fields[{}] missing field_id; use explicit field_id object".format(idx))
            return None, None

        field_id = str(field_id_raw)
        matched = self._defs_by_id.get(field_id, [])
        if not matched:
            self._errors.value_error("Output field '{}' not found".format(field_id))
            return None, None

        source_raw = item.get(OUTPUT_FIELD_SOURCE_KEY)
        if source_raw is not None:
            source = str(source_raw)
            matched = [field_def for field_def in matched if (field_def.source_id or "") == source]
            if not matched:
                self._errors.value_error("Output field '{}' has no match for source '{}'".format(field_id, source))
                return None, None

        if len(matched) > 1:
            if source_raw is None:
                self._errors.value_error(
                    "Output field '{}' is ambiguous; use 'source.field_id' sugar or add source to explicit field_id object".format(field_id)
                )
            else:
                self._errors.value_error("Output field '{}' is ambiguous; use unique field_id".format(field_id))
            return None, None

        override = dict(item)
        override.pop(OUTPUT_FIELD_ID_KEY, None)
        override.pop(OUTPUT_FIELD_SOURCE_KEY, None)
        if not override:
            return matched[0], None
        return matched[0], override

    def _resolve_data_key(
        self,
        item: Dict[str, Any],
        idx: int,
    ) -> Tuple[Optional[FieldDef], Optional[Dict[str, Any]]]:
        field_raw = item.get(OUTPUT_FIELD_DATA_KEY_KEY)
        if field_raw is None:
            self._errors.value_error("output.fields[{}] missing field; use explicit field object".format(idx))
            return None, None

        data_key = str(field_raw)
        source_raw = item.get(OUTPUT_FIELD_SOURCE_KEY)

        field_def: Optional[FieldDef]
        if source_raw is not None:
            field_def = self._resolve_data_key_with_source(data_key, str(source_raw))
        else:
            field_def = self._resolve_data_key_without_source(data_key)

        if field_def is None:
            return None, None

        return field_def, self._build_data_key_override(item)

    def _resolve_data_key_with_source(self, data_key: str, source: str) -> Optional[FieldDef]:
        matched = list(self._defs_by_data_key_by_source.get(source, {}).get(data_key, []))
        if not matched:
            self._errors.value_error("Output field data_key '{}' has no match for source '{}'".format(data_key, source))
            return None
        if len(matched) > 1:
            self._errors.value_error("Output field data_key '{}' is ambiguous in source '{}'; use field_id".format(data_key, source))
            return None
        return matched[0]

    def _resolve_data_key_without_source(self, data_key: str) -> Optional[FieldDef]:
        matched_all: List[FieldDef] = []
        matched_sources: Set[str] = set()
        for source_id, data_key_map in self._defs_by_data_key_by_source.items():
            matched = data_key_map.get(data_key, [])
            if not matched:
                continue
            matched_all.extend(matched)
            matched_sources.add(source_id)

        if not matched_all:
            self._errors.value_error("Output field data_key '{}' not found".format(data_key))
            return None
        if len(matched_sources) > 1:
            self._errors.value_error("Output field data_key '{}' is ambiguous; add source or use field_id".format(data_key))
            return None
        if len(matched_all) > 1:
            source_name = next(iter(matched_sources))
            self._errors.value_error("Output field data_key '{}' is ambiguous in source '{}'; use field_id".format(data_key, source_name))
            return None
        return matched_all[0]

    @staticmethod
    def _build_data_key_override(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        override = dict(item)
        override.pop(OUTPUT_FIELD_DATA_KEY_KEY, None)
        override.pop(OUTPUT_FIELD_SOURCE_KEY, None)
        if not override:
            return None
        return override
