import logging

from ....schema_dsl.constants import DEMAND_FIELDS_KEY
from ....schema_dsl.models import (
    DEMAND_KEYS,
    DERIVED_FIELD_KEYS,
    LOOKUP_CAST_KEYS,
    MAIN_SOURCE_KEYS,
    NORMALIZE_KEYS,
    RELATION_CONFIG_KEYS,
    RELATION_STEP_KEYS,
    SOURCE_FIELD_KEYS,
    SOURCE_KEYS,
)

MIN_PARTS_COUNT = 2

_VALIDATOR_LOGGER = logging.getLogger("scalim.dsl.yaml_dsl.validator")


class _FieldNames:
    NAME: str = DEMAND_KEYS["name"]
    # `batch_size` 从 `demand` `YAML` 主线迁出;这里保留常量仅用于错误信息路径与内部工具复用.
    BATCH_SIZE: str = "batch_size"
    MAIN_SOURCE: str = DEMAND_KEYS["main_source"]
    SOURCES: str = DEMAND_KEYS["sources"]
    FIELDS: str = DEMAND_FIELDS_KEY
    RELATIONS: str = DEMAND_KEYS["relations"]
    LOADER: str = SOURCE_KEYS["loader"]
    KEY: str = SOURCE_KEYS["key"]
    CACHE_MODE: str = SOURCE_KEYS["cache_mode"]
    BIND: str = "bind"
    LOOKUP_CAST: str = SOURCE_KEYS["lookup_cast"]
    LOOKUP_CHUNK_SIZE: str = SOURCE_KEYS["lookup_chunk_size"]
    NORMALIZE: str = SOURCE_KEYS["normalize"]
    PARAMS: str = SOURCE_KEYS["params"]
    NORMALIZE_KIND: str = NORMALIZE_KEYS["kind"]
    NORMALIZE_KEY_FIELD: str = NORMALIZE_KEYS["key_field"]
    NORMALIZE_ON_CONFLICT: str = NORMALIZE_KEYS["on_conflict"]
    NORMALIZE_ON_NONE: str = NORMALIZE_KEYS["on_none"]
    NORMALIZE_ON_EMPTY: str = NORMALIZE_KEYS["on_empty"]
    NORMALIZE_ON_MISSING: str = NORMALIZE_KEYS["on_missing"]
    NORMALIZE_FIELDS: str = NORMALIZE_KEYS["fields"]
    NORMALIZE_STEPS: str = NORMALIZE_KEYS["steps"]
    NORMALIZE_CALL_BY: str = NORMALIZE_KEYS["call_by"]
    NAME_KEY: str = LOOKUP_CAST_KEYS["name"]
    SEP: str = LOOKUP_CAST_KEYS["sep"]
    SOURCE: str = SOURCE_FIELD_KEYS["source"]
    EXTRACT: str = SOURCE_FIELD_KEYS["extract"]
    RELATION: str = SOURCE_FIELD_KEYS["relation"]
    FROM: str = RELATION_STEP_KEYS["from_"]
    STEPS: str = RELATION_CONFIG_KEYS["steps"]
    TO: str = RELATION_STEP_KEYS["to"]
    TO_BIND: str = "to_bind"
    VALUE_CAST: str = SOURCE_FIELD_KEYS["value_cast"]
    DEFAULT: str = SOURCE_FIELD_KEYS["default"]
    COMPUTE: str = DERIVED_FIELD_KEYS["compute"]
    CALL_BY: str = DERIVED_FIELD_KEYS["call_by"]
    DEPENDS_ON: str = "depends_on"
    SOURCE_ID: str = MAIN_SOURCE_KEYS["source_id"]
    ORDER_BY: str = MAIN_SOURCE_KEYS["order_by"]


F = _FieldNames


LEGACY_FIELDS = {
    "relations_sql_like",
    "relations_graph",
    "foreign_key",
    "target",
    "from",
    "via",
    "column",
    "pk",
    "pk_transform",
    "derived",
}

__all__ = ()
