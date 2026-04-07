from typing import Any, Dict, List, Optional, Tuple, cast

from ......vendor.dataclassesx import dataclass
from ....schema_dsl.constants import DEMAND_FIELDS_KEY, FIELD_KIND_DERIVED, FIELD_KIND_SOURCE
from ....schema_dsl.models import DEMAND_KEYS, DERIVED_FIELD_KEYS, MAIN_SOURCE_KEYS, SOURCE_KEYS


def ensure_mapping(raw: Any) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        msg = "YAML config must be a mapping"
        raise TypeError(msg)
    return cast("Dict[str, Any]", raw)  # pragma: allow-cast yaml mapping typed narrowing


@dataclass(frozen=True)
class RawDemand:
    data: Dict[str, Any]

    @classmethod
    def from_raw(cls, raw: Any) -> "RawDemand":
        return cls(ensure_mapping(raw))

    def get_mapping(self, key: str) -> Optional[Dict[str, Any]]:
        value = self.data.get(key)
        if isinstance(value, dict):
            return cast("Dict[str, Any]", value)  # pragma: allow-cast yaml mapping typed narrowing
        return None

    def get_list(self, key: str) -> Optional[List[Any]]:
        value = self.data.get(key)
        if isinstance(value, list):
            return cast("List[Any]", value)  # pragma: allow-cast yaml list typed narrowing
        return None


@dataclass(frozen=True)
class FieldDef:
    field_id: str
    kind: str
    data: Dict[str, Any]
    source_id: Optional[str] = None


def field_def_key(field_def: "FieldDef") -> Tuple[str, Optional[str], str, int]:
    return (field_def.field_id, field_def.source_id, field_def.kind, id(field_def.data))


class AliasIndex:
    def __init__(self) -> None:
        self._by_obj_id: Dict[int, FieldDef] = {}

    def add(self, data: Dict[str, Any], field_def: FieldDef) -> None:
        self._by_obj_id[id(data)] = field_def

    def get(self, item: Dict[str, Any]) -> Optional[FieldDef]:
        return self._by_obj_id.get(id(item))


@dataclass(frozen=True)
class FieldDefIndex:
    field_defs: List[FieldDef]
    defs_by_id: Dict[str, List[FieldDef]]
    alias_index: AliasIndex


def collect_field_defs(raw: RawDemand, main_source_id: str) -> FieldDefIndex:
    field_defs: List[FieldDef] = []
    defs_by_id: Dict[str, List[FieldDef]] = {}
    alias_index = AliasIndex()

    _collect_main_source_fields(raw, main_source_id, field_defs, defs_by_id, alias_index)
    _collect_source_fields(raw, field_defs, defs_by_id, alias_index)
    _collect_derived_fields(raw, field_defs, defs_by_id, alias_index)

    return FieldDefIndex(field_defs=field_defs, defs_by_id=defs_by_id, alias_index=alias_index)


def _add_field_def(
    field_defs: List[FieldDef],
    defs_by_id: Dict[str, List[FieldDef]],
    alias_index: AliasIndex,
    field_id_raw: Any,
    kind: str,
    data_raw: Any,
    source_id: Optional[str] = None,
) -> None:
    if not isinstance(data_raw, dict):
        return
    field_id = str(field_id_raw)
    data = cast("Dict[str, Any]", data_raw)  # pragma: allow-cast yaml mapping typed narrowing
    field_def = FieldDef(field_id=field_id, kind=kind, data=data, source_id=source_id)
    field_defs.append(field_def)
    defs_by_id.setdefault(field_id, []).append(field_def)
    alias_index.add(data, field_def)


def _collect_main_source_fields(
    raw: RawDemand,
    main_source_id: str,
    field_defs: List[FieldDef],
    defs_by_id: Dict[str, List[FieldDef]],
    alias_index: AliasIndex,
) -> None:
    raw_main_source = raw.get_mapping(DEMAND_KEYS["main_source"])
    if raw_main_source is None:
        return
    main_fields_raw = raw_main_source.get(MAIN_SOURCE_KEYS["fields"])
    if not isinstance(main_fields_raw, dict):
        return
    main_fields_raw = cast("Dict[str, Any]", main_fields_raw)  # pragma: allow-cast yaml mapping typed narrowing
    source_id = main_source_id or None
    for field_id_raw, field_data_raw in main_fields_raw.items():
        _add_field_def(field_defs, defs_by_id, alias_index, field_id_raw, FIELD_KIND_SOURCE, field_data_raw, source_id)


def _collect_source_fields(
    raw: RawDemand,
    field_defs: List[FieldDef],
    defs_by_id: Dict[str, List[FieldDef]],
    alias_index: AliasIndex,
) -> None:
    raw_sources = raw.get_mapping(DEMAND_KEYS["sources"])
    if raw_sources is None:
        return
    for source_id_raw, source_data_raw in raw_sources.items():
        if not isinstance(source_data_raw, dict):
            continue
        source_dict = cast("Dict[str, Any]", source_data_raw)  # pragma: allow-cast yaml mapping typed narrowing
        source_fields_raw = source_dict.get(SOURCE_KEYS["fields"])
        if not isinstance(source_fields_raw, dict):
            continue
        source_fields_raw = cast("Dict[str, Any]", source_fields_raw)  # pragma: allow-cast yaml mapping typed narrowing
        source_id = str(source_id_raw)
        for field_id_raw, field_data_raw in source_fields_raw.items():
            _add_field_def(field_defs, defs_by_id, alias_index, field_id_raw, FIELD_KIND_SOURCE, field_data_raw, source_id)


def _collect_derived_fields(
    raw: RawDemand,
    field_defs: List[FieldDef],
    defs_by_id: Dict[str, List[FieldDef]],
    alias_index: AliasIndex,
) -> None:
    raw_fields = raw.get_mapping(DEMAND_FIELDS_KEY)
    if raw_fields is None:
        return
    for field_id_raw, field_data_raw in raw_fields.items():
        if not isinstance(field_data_raw, dict):
            continue
        field_dict = cast("Dict[str, Any]", field_data_raw)  # pragma: allow-cast yaml mapping typed narrowing
        if DERIVED_FIELD_KEYS["compute"] in field_dict or DERIVED_FIELD_KEYS["call_by"] in field_dict:
            _add_field_def(field_defs, defs_by_id, alias_index, field_id_raw, FIELD_KIND_DERIVED, field_dict, None)


__all__ = ()
